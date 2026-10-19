"""多租户隔离的公共助手。

用法（路由内）::

    from app.core.tenant import tenant_scope

    where, params = tenant_scope(user)
    rows = db.query(f'SELECT * FROM elders WHERE {where}', params)

    # 与其它条件组合
    where, params = tenant_scope(user, extra='status=%s', extra_params=[1])

设计要点：
  * **默认拒绝**：拿不到 tenantId 时直接 403，而不是"不过滤" —— 后者会在
    任何一处遗漏上导致跨租户数据泄露，而这类遗漏很难靠人眼审查发现。
  * 跨租户访问统一按 **404** 处理（在 require_same_tenant 里），不返回 403。
    403 会告诉攻击者"这条数据存在、只是你没权限"，等于泄露了存在性。
"""
from contextvars import ContextVar
from typing import Any

from fastapi import HTTPException, status

#: 当前请求的租户上下文。
#:
#: 为什么需要它：AI 助手的工具执行链路是
#: 路由 → DeepSeekAgent.stream_chat → LLM 返回 tool_calls → execute_tool(name, args)，
#: 而 `execute_tool` 的入参完全由**大模型生成的 JSON** 决定，无法从中安全地取租户。
#: 把租户放进 ContextVar 由路由入口绑定，工具函数在任意深度都能读到，
#: 既不用改动 LLM 工具调用协议，也不会给模型留下"自己声明租户"的可乘之机。
_current_tenant: ContextVar[int | None] = ContextVar('current_tenant_id', default=None)


def bind_tenant(tenant_id: int | None) -> None:
    """在请求入口绑定租户；同一次请求内后续调用均可读到。"""
    _current_tenant.set(tenant_id)


def context_tenant_id(required: bool = True) -> int | None:
    """读取当前请求的租户。

    ``required=True`` 时拿不到就 403（默认拒绝）—— 与 tenant_id_of 同一原则：
    宁可让漏绑定的接口响亮地失败，也不让它静默地全库查询。
    """
    tid = _current_tenant.get()
    if tid is None and required:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail='请求缺少机构上下文，无法访问业务数据')
    return tid


def tenant_id_of(user: dict[str, Any]) -> int:
    tid = (user or {}).get('tenantId')
    if tid is None:
        # 平台级账号（无租户归属）目前不支持跨租户读取，一律拒绝
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail='当前账号未归属任何机构，无法访问业务数据')
    return int(tid)


def tenant_scope(user: dict[str, Any], extra: str = '',
                 extra_params: list[Any] | None = None) -> tuple[str, list[Any]]:
    """返回 (WHERE 片段, 参数)。始终至少包含 tenant_id=?。"""
    tid = tenant_id_of(user)
    where = 'tenant_id=%s'
    params: list[Any] = [tid]
    if extra:
        where += f' AND {extra}'
        params.extend(extra_params or [])
    return where, params


def tenant_id_param(user: dict[str, Any]) -> list[Any]:
    """只要参数列表（用于拼接已有的 WHERE）。"""
    return [tenant_id_of(user)]


def require_same_tenant(row: dict[str, Any] | None, user: dict[str, Any]) -> dict[str, Any]:
    """校验单条记录属于当前租户；不属于或不存在时统一 404。"""
    tid = tenant_id_of(user)
    if not row or int(row.get('tenant_id') or row.get('tenantId') or 0) != tid:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='数据不存在')
    return row
