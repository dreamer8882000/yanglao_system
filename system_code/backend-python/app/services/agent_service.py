"""DeepSeek-powered AI assistant for the elderly-care system.

The previous ``/agent/chat`` route was a stub that echoed the message and, worse,
emitted an SSE shape the frontend never understood (no ``event:`` lines, and a
``content`` field where the parser read ``text``), so the chat UI hung in the
"thinking" state forever and showed nothing.

This module replaces it with a real assistant:

  * DeepSeek chat-completions (OpenAI-compatible) with function calling;
  * three tools that query the real database: alert summary, elder lookup,
    schedule lookup;
  * a two-phase flow: a non-streaming tool-selection call, then a streaming
    answer, emitting the exact SSE events the frontend ``agent.js`` parser
    expects (``text`` / ``tool_call`` / ``tool_result`` / ``tool_result_data`` /
    ``suggest`` / ``done`` / ``error``).
"""
from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta
from typing import Any, Iterator

import httpx

from app.core.config import get_settings
from app.core.database import db

SYSTEM_PROMPT = (
    "你是智慧养老监护系统的 AI 助手「护卫AI」。你只能用中文回答。"
    "你可以调用工具查询系统里的告警、老人档案和值班排班，并基于真实数据回答。"
    "回答要简洁、直接；涉及数字时用查询到的真实值，不要编造。"
    "当用户询问当前未处理告警、老人情况或值班人员时，先调用对应工具。"
)

TOOL_LABELS = {
    "alert_summary": "汇总告警统计",
    "elder_search": "查询老人档案",
    "schedule_lookup": "查询值班安排",
}

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "alert_summary",
            "description": "汇总告警统计：按风险等级计数、未处理告警数。可指定统计最近 N 小时（默认 24）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "hours": {"type": "integer", "description": "统计最近多少小时，默认 24，范围 1-168"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "elder_search",
            "description": "查询老人档案。可按姓名模糊匹配、按房间号精确匹配，返回年龄/房间/健康备注。",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "老人姓名，模糊匹配"},
                    "room": {"type": "string", "description": "房间号，精确匹配"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "schedule_lookup",
            "description": "查询值班排班。可指定日期（YYYY-MM-DD，默认今天）与班次（day/night/full）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "日期 YYYY-MM-DD，默认今天"},
                    "shift": {"type": "string", "description": "班次 day/night/full"},
                },
                "required": [],
            },
        },
    },
]


def sse(event: str, payload: dict[str, Any]) -> str:
    """Format one Server-Sent-Event block the frontend parser expects."""
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, timedelta):
        return str(value)
    if hasattr(value, "item"):
        return value.item()
    return value


# ── Tool executors (all query the real DB with parameterised SQL) ────────────
def _tool_alert_summary(args: dict[str, Any], tenant_id: int) -> dict[str, Any]:
    try:
        hours = int(args.get("hours") or 24)
    except (TypeError, ValueError):
        hours = 24
    hours = max(1, min(168, hours))
    # 不加 tenant_id 的话，AI 助手的"最近告警统计"会把**所有机构**的告警
    # 加在一起回答 —— 这是多租户下最不容易被发现的泄露：接口鉴权没问题，
    # 页面也没显示别人的数据，只是数字悄悄变大了。
    tid = tenant_id
    rows = db.query(
        "SELECT risk_level, COUNT(*) AS cnt FROM alerts "
        "WHERE tenant_id = %s AND alert_time >= DATE_SUB(NOW(), INTERVAL %s HOUR) "
        "GROUP BY risk_level",
        [tid, hours],
    )
    pending = int(db.query("SELECT COUNT(*) AS c FROM alerts WHERE tenant_id=%s AND status=0",
                           [tid])[0]["c"])
    return {
        "hours": hours,
        "byLevel": {r["risk_level"]: int(r["cnt"]) for r in rows},
        "pending": pending,
    }


def _tool_elder_search(args: dict[str, Any], tenant_id: int) -> dict[str, Any]:
    name = str(args.get("name") or "").strip()
    room = str(args.get("room") or "").strip()
    where: list[str] = ["tenant_id = %s"]
    params: list[Any] = [tenant_id]
    if name:
        where.append("name LIKE %s")
        params.append(f"%{name}%")
    if room:
        where.append("room_no=%s")
        params.append(room)
    sql = "SELECT id, name, gender, age, room_no, health_notes, status FROM elders"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY room_no LIMIT 20"
    rows = db.query(sql, params)
    return {"count": len(rows), "elders": [_jsonable(r) for r in rows]}


def _tool_schedule_lookup(args: dict[str, Any], tenant_id: int) -> dict[str, Any]:
    date_val = str(args.get("date") or "").strip()
    shift = str(args.get("shift") or "").strip()
    where: list[str] = ["s.tenant_id = %s"]
    params: list[Any] = [tenant_id]
    if date_val:
        where.append("s.shift_date=%s")
        params.append(date_val)
    else:
        where.append("s.shift_date=CURDATE()")
    if shift:
        where.append("s.shift_type=%s")
        params.append(shift)
    sql = (
        "SELECT s.shift_date, s.shift_type, s.start_time, s.end_time, u.name AS user_name "
        "FROM schedules s JOIN users u ON s.user_id=u.id AND u.tenant_id=s.tenant_id"
    )
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY s.shift_date, s.start_time LIMIT 50"
    rows = db.query(sql, params)
    return {"count": len(rows), "schedules": [_jsonable(r) for r in rows]}


_TOOL_EXECUTORS = {
    "alert_summary": _tool_alert_summary,
    "elder_search": _tool_elder_search,
    "schedule_lookup": _tool_schedule_lookup,
}


def execute_tool(name: str, args: dict[str, Any],
                 tenant_id: int | None = None) -> dict[str, Any]:
    """执行一个工具。

    **租户是必传的显式参数，不再从 ContextVar 读取。**
    原来的做法是让工具去读 ``context_tenant_id()``，但这条链路上这个上下文
    极不可靠：``bind_tenant`` 写在 ``get_current_user``（一个 sync 依赖，跑在
    anyio 线程池里）中，写入只存在于那一次线程调用的上下文副本里；
    而工具是在 **SSE 生成器** 的后续 chunk 里、又经一次 ``to_thread`` 执行的。
    结果是工具拿不到租户、抛 403，再被下面的 ``except`` 变成一条
    ``{"error": ...}`` 当作**正常的工具结果**回给模型 —— AI 助手的三个工具
    全部不可用，而且没有任何日志说明原因。

    对于一个"决定了能查到哪些数据"的值，不该依赖这么微妙的传播机制：
    显式传参是唯一可靠的写法。未传时不执行，并返回明确的错误。
    """
    fn = _TOOL_EXECUTORS.get(name)
    if fn is None:
        return {"error": f"未知工具: {name}"}
    if tenant_id is None:
        return {"error": "缺少机构上下文，无法执行该查询"}
    try:
        return fn(args or {}, tenant_id)
    except Exception as exc:  # noqa: BLE001 - surface as tool result, not crash
        return {"error": f"{type(exc).__name__}: {exc}"}


class DeepSeekAgent:
    def __init__(self, api_key: str, base_url: str, model: str, timeout: float = 60.0) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _completion(self, messages: list[dict[str, Any]], tools: list | None, stream: bool) -> Any:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.3,
            "stream": stream,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()

    def _completion_stream(self, messages: list[dict[str, Any]]) -> Iterator[str]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.3,
            "stream": True,
        }
        with httpx.Client(timeout=self.timeout) as client:
            with client.stream(
                "POST", f"{self.base_url}/chat/completions",
                json=payload, headers=self._headers(),
            ) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data_str = line[len("data:"):].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        obj = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    delta = (obj.get("choices") or [{}])[0].get("delta") or {}
                    content = delta.get("content")
                    if content:
                        yield content

    def _suggestions(self, messages: list[dict[str, Any]]) -> list[str]:
        has_tool = any(m.get("role") == "tool" for m in messages)
        if not has_tool:
            return []
        return ["当前有哪些未处理告警？", "查询今日值班人员", "统计最近 7 天告警趋势"]

    def stream_chat(self, message: str, history: list[dict[str, Any]],
                    tenant_id: int | None = None) -> Iterator[str]:
        """Yield SSE event strings for one chat turn.

        ``tenant_id`` 必须由调用方传入并原样转交给工具：工具生成的是**查询语句**，
        租户决定了它能查到谁的数据，属于安全相关的取值，不做隐式传播。
        """
        if not self.configured:
            yield sse("error", {"message": "未配置 DEEPSEEK_API_KEY，无法使用 AI 助手"})
            return
        if not message.strip():
            yield sse("error", {"message": "消息不能为空"})
            return

        messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
        for item in history or []:
            role = item.get("role")
            content = item.get("content")
            if role in ("user", "assistant") and isinstance(content, str) and content:
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": message})

        try:
            first = self._completion(messages, tools=TOOLS, stream=False)
            choice = (first.get("choices") or [{}])[0]
            assistant_msg = choice.get("message") or {}
            tool_calls = assistant_msg.get("tool_calls") or []

            if tool_calls:
                messages.append(assistant_msg)
                for idx, tc in enumerate(tool_calls):
                    fn = tc.get("function") or {}
                    name = fn.get("name", "")
                    try:
                        args = json.loads(fn.get("arguments") or "{}")
                    except (json.JSONDecodeError, TypeError):
                        args = {}
                    yield sse("tool_call", {
                        "tool": name, "label": TOOL_LABELS.get(name, name),
                        "args": args, "callIdx": idx,
                    })
                    result = execute_tool(name, args, tenant_id=tenant_id)
                    yield sse("tool_result", {"tool": name, "success": "error" not in result, "callIdx": idx})
                    yield sse("tool_result_data", {"tool": name, "data": result, "callIdx": idx})
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id", f"call_{idx}"),
                        "content": json.dumps(result, ensure_ascii=False),
                    })

                for chunk in self._completion_stream(messages):
                    yield sse("text", {"text": chunk})
                yield sse("suggest", {"list": self._suggestions(messages)})
            else:
                content = assistant_msg.get("content") or ""
                if content:
                    yield sse("text", {"text": content})
                for chunk in self._completion_stream(messages):
                    yield sse("text", {"text": chunk})

            yield sse("done", {"content": ""})
        except httpx.HTTPStatusError as exc:
            yield sse("error", {"message": f"DeepSeek 接口错误 HTTP {exc.response.status_code}"})
        except Exception as exc:  # noqa: BLE001
            yield sse("error", {"message": f"{type(exc).__name__}: {exc}"})


_agent: DeepSeekAgent | None = None


def get_agent() -> DeepSeekAgent:
    global _agent
    if _agent is None:
        settings = get_settings()
        _agent = DeepSeekAgent(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            model=settings.deepseek_model,
        )
    return _agent
