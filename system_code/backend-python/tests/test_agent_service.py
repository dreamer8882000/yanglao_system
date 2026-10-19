"""Tests for the DeepSeek AI-assistant service (SSE contract + flow).

The frontend ``agent.js`` parses ``event: <type>`` / ``data: <json>`` blocks and
maps them to callbacks; the previous stub never emitted ``event:`` lines and used
the wrong field name, so the UI hung. These tests pin the exact contract and the
two-phase flow (tool selection -> streaming answer).
"""
from datetime import datetime, timedelta

from app.services import agent_service
#: stream_chat 现在必须显式传租户 —— 工具生成的是查询语句，租户决定了
#: 它能查到谁的数据，属于安全相关取值，不再依赖 ContextVar 隐式传播。
TENANT = 1
from app.services.agent_service import DeepSeekAgent, sse


def _event_types(events):
    return [e.split("\n", 1)[0].replace("event: ", "") for e in events]


def _agent(**kw):
    return DeepSeekAgent(kw.pop("api_key", "sk-test"),
                         "https://api.deepseek.com", "deepseek-chat", **kw)


def test_sse_format_text():
    assert sse("text", {"text": "你好"}) == 'event: text\ndata: {"text": "你好"}\n\n'


def test_sse_format_preserves_chinese_and_structure():
    out = sse("tool_result_data", {"tool": "elder_search", "data": {"name": "张国强"}})
    assert out.startswith("event: tool_result_data\n")
    assert '"name": "张国强"' in out


def test_jsonable_converts_datetime_and_timedelta():
    value = _jsonable = agent_service._jsonable
    assert value({"t": datetime(2026, 1, 1, 10, 0, 0), "d": timedelta(seconds=1)}) == \
        {"t": "2026-01-01T10:00:00", "d": "0:00:01"}


def test_stream_chat_not_configured_emits_error():
    agent = DeepSeekAgent("", "https://api.deepseek.com", "deepseek-chat")
    events = list(agent.stream_chat("你好", [], tenant_id=1))
    assert len(events) == 1
    assert "event: error" in events[0]
    assert "DEEPSEEK_API_KEY" in events[0]


def test_stream_chat_no_tool_streams_text_then_done(monkeypatch):
    agent = _agent()
    monkeypatch.setattr(agent, "_completion", lambda messages, tools=None, stream=False:
                        {"choices": [{"message": {"content": "好的", "tool_calls": None}}]})
    monkeypatch.setattr(agent, "_completion_stream", lambda messages: iter(["你好", "世界"]))

    events = list(agent.stream_chat("hi", [], tenant_id=1))
    assert _event_types(events) == ["text", "text", "text", "done"]


def test_stream_chat_with_tool_emits_tool_trace(monkeypatch):
    agent = _agent()

    def fake_completion(messages, tools=None, stream=False):
        return {"choices": [{"message": {
            "content": None,
            "tool_calls": [{"id": "call_1", "function": {"name": "alert_summary", "arguments": "{}"}}],
        }}]}

    monkeypatch.setattr(agent, "_completion", fake_completion)
    monkeypatch.setattr(agent_service, "execute_tool",
                        lambda name, args, tenant_id=None: {"pending": 3, "byLevel": {"HIGH": 1}})
    monkeypatch.setattr(agent, "_completion_stream", lambda messages: iter(["共 3 条未处理"]))

    events = list(agent.stream_chat("有哪些告警", [], tenant_id=1))
    types = _event_types(events)
    assert types[0] == "tool_call"
    assert "tool_result" in types
    assert "tool_result_data" in types
    assert "text" in types
    assert "suggest" in types
    assert types[-1] == "done"

    # tool_call payload shape the frontend expects
    tc_line = [e for e in events if e.startswith("event: tool_call")][0]
    assert '"tool": "alert_summary"' in tc_line
    assert '"callIdx": 0' in tc_line


def test_stream_chat_handles_exception_as_error(monkeypatch):
    agent = _agent()

    def boom(messages, tools=None, stream=False):
        raise RuntimeError("network down")

    monkeypatch.setattr(agent, "_completion", boom)
    events = list(agent.stream_chat("hi", [], tenant_id=1))
    assert _event_types(events) == ["error"]
    assert "network down" in events[0]
