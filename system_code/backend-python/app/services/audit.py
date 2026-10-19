"""Audit-trail writer.

The ``audit_logs`` table existed and the ``/api/audit`` CRUD route exposed it,
but **no business operation ever wrote a row**, so the 「操作审计」 page was
effectively empty and "who confirmed this alert / edited this record" was
unanswerable.

Writing the audit entry must never break the business operation it describes,
so every failure here is swallowed (and logged).
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

from app.core.database import db
from app.core.tenant import context_tenant_id

logger = logging.getLogger(__name__)


def client_ip(request: Any) -> str | None:
    if request is None:
        return None
    try:
        # X-Forwarded-For is attacker-controlled unless a trusted reverse proxy
        # overwrites it. Only honour it when the deployment explicitly opts in
        # (TRUST_PROXY_HEADERS=true); otherwise use the socket peer address.
        trust_forwarded = os.getenv('TRUST_PROXY_HEADERS', '').strip().lower() in {'1', 'true', 'yes', 'on'}
        if trust_forwarded:
            forwarded = request.headers.get('x-forwarded-for')
            if forwarded:
                return forwarded.split(',')[0].strip()
        return request.client.host if request.client else None
    except Exception:
        return None


def _clip(value: Any, width: int) -> str | None:
    """按列的宽度截断，而不是让 MySQL 抛 1406。

    写审计的失败是被吞掉的（审计不能弄坏业务），所以「值超长」这种错误
    只会在日志里留一行 warning —— 表现是**这条操作根本没被记录**。
    实测：批量处置 200 条告警时 resource_id 传了逗号拼接的 id 列表，
    超过 varchar(50)，整行审计直接丢失。截断至少保住"谁、什么时候、做了什么"。
    需要完整 id 列表时应当放进 detail（TEXT，无长度限制）。
    """
    if value is None:
        return None
    text = str(value)
    return text if len(text) <= width else text[:width - 1] + '…'


def tenant_of_username(username: str | None) -> int | None:
    """由登录名反查机构，用于**登录失败**这类尚无登录用户的审计。

    登录失败时 context 里没有租户（用户还没通过鉴权），若不显式解析，
    这行审计的 tenant_id 会是 NULL —— 而审计列表是按 tenant_id 过滤的，
    于是"谁在什么时候反复试密码"这条最该被看到的记录，任何机构都看不到。
    """
    if not username:
        return None
    row = db.query_one('SELECT tenant_id FROM users WHERE username=%s LIMIT 1', [username])
    return int(row['tenant_id']) if row and row.get('tenant_id') is not None else None


#: 用于区分"调用方没传 tenant_id"和"调用方明确传了 None"。
#:
#: 这个区别是真问题，不是吹毛求疵：登录失败审计由 auth.py 显式传
#: ``tenant_id=tenant_of_username(用户名)`` —— 用户名不存在时它的返回值就是 None，
#: 意思是"这行审计不属于任何机构"。原实现把 None 当成"没传"，
#: 于是回落到 ContextVar 里的租户上下文，把它**归到了上一个请求的机构**。
#: 实测：同一个不存在的账号的 258 次失败里，有 150 次被记到了机构 1 名下。
#: 后果有两个，都不小：
#:   ① 爆破记录被误记进某家机构的审计，机构自己看会以为是内部问题；
#:   ② 攻击者可以借此往任意机构的审计里灌数据。
_UNSET: Any = object()


def record_audit(action: str, *, user: dict[str, Any] | None = None,
                 resource_type: str | None = None, resource_id: Any = None,
                 detail: Any = None, request: Any = None,
                 username: str | None = None,
                 tenant_id: Any = _UNSET) -> bool:
    """Insert one audit row. Returns True on success; never raises."""
    try:
        user_id = user.get('id') if isinstance(user, dict) else None
        name = username or (user.get('username') if isinstance(user, dict) else None)
        payload = None
        if detail is not None:
            payload = detail if isinstance(detail, str) else json.dumps(
                detail, ensure_ascii=False, default=str)
        # 两种键名都要认：路由层传进来的可能是 _normalize_user 转过 camelCase 的
        # dict（tenantId），也可能是**数据库原始行**（tenant_id）—— 登录路由传的正是
        # 后者。只读 camelCase 会让"登录成功"这条最重要的审计悄悄变成 NULL，
        # 而 NULL 的审计行按 tenant_id 过滤后任何机构都看不到。
        if tenant_id is _UNSET:
            if isinstance(user, dict):
                tenant_id = user.get('tenantId')
                if tenant_id is None:
                    tenant_id = user.get('tenant_id')
            if tenant_id is None:
                tenant_id = context_tenant_id(required=False)
        db.insert(
            'INSERT INTO audit_logs (tenant_id, user_id, username, action, resource_type, '
            'resource_id, detail, ip) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)',
            [tenant_id, user_id, _clip(name, 100), _clip(action, 100),
             _clip(resource_type, 50), _clip(resource_id, 50),
             payload, _clip(client_ip(request), 50)],
        )
        return True
    except Exception as exc:  # noqa: BLE001 - auditing must not break the request
        logger.warning('audit write failed: %s', exc)
        return False
