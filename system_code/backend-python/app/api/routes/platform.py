"""平台级只读视图（SaaS 运营方视角）。

**为什么单独一个模块，而不是让平台账号复用业务接口**：
业务接口全部建立在 `tenant_id_of(user)` 之上，而它对"没有机构归属"的账号
是默认拒绝的（见 core/tenant.py）。平台账号的 tenant_id 就是 NULL，
所以它访问 /api/elders、/api/alerts、/api/cameras 一律 403 ——
这是**刻意保留**的安全网：跨机构视图不应该顺带把业务数据也打开。

于是这里只提供运营方真正需要的三样东西：
  1. 机构清单与规模（谁在用、用了多少）
  2. 跨机构安全事件（登录失败/限流）—— **包括 tenant_id 为 NULL 的孤儿审计**
  3. 跨机构审计流水（可按机构/关键词过滤）

第 2 点是本模块存在的直接动因：登录失败时如果用户名根本不存在，
就无从判断属于哪个机构，这行审计的 tenant_id 是 NULL；而租户侧的审计列表
按 tenant_id 过滤，于是"有人在反复猜密码"这条最该被看到的记录
**所有机构都看不到**（实测库里有 147 行这样的孤儿审计）。

隐私边界（写清楚，避免被当成"没做完"）：
  平台视图**不返回任何老人个人信息**（姓名/房间/健康数据）。运营方需要的是
  "这家机构有多少在住老人、告警量多少"，而不是"谁住在哪"。要看具体业务数据
  需要机构自己授权，本项目不做。
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query

from app.core.database import db
from app.core.security import require_platform
from app.core.timeutil import local_now

router = APIRouter(prefix='/platform', tags=['platform'])


def _scalar(sql: str, params: list[Any] | None = None) -> int:
    rows = db.query(sql, params or [])
    if not rows:
        return 0
    return int(list(rows[0].values())[0] or 0)


@router.get('/overview')
def overview(user: dict[str, Any] = Depends(require_platform)):
    """平台总览：机构数、各表总量、以及那批"谁也看不到"的孤儿审计数量。"""
    return {'success': True, 'data': {
        'tenantCount': _scalar('SELECT COUNT(*) FROM tenants'),
        'activeTenantCount': _scalar('SELECT COUNT(*) FROM tenants WHERE status=1'),
        'userCount': _scalar('SELECT COUNT(*) FROM users WHERE is_platform=0'),
        'elderCount': _scalar('SELECT COUNT(*) FROM elders WHERE status=1'),
        'cameraCount': _scalar('SELECT COUNT(*) FROM cameras'),
        'alertCount': _scalar('SELECT COUNT(*) FROM alerts'),
        # 孤儿审计：所属机构无法判断（多为登录失败用的不存在账号）。
        # 单列出来是因为它是"平台层必须看、租户层看不到"的那一类，
        # 数量非 0 就说明确实有人在试探账号。
        'orphanAuditCount': _scalar('SELECT COUNT(*) FROM audit_logs WHERE tenant_id IS NULL'),
        'failedLogin24h': _scalar(
            "SELECT COUNT(*) FROM audit_logs WHERE action='登录失败' "
            'AND created_at >= DATE_SUB(NOW(), INTERVAL 24 HOUR)'),
    }}


@router.get('/tenants')
def tenants(user: dict[str, Any] = Depends(require_platform)):
    """机构清单 + 各自的规模。

    每项规模都用一个子查询而不是多表 JOIN + GROUP BY：
    四张表之间没有可用的共同维度，JOIN 会产生笛卡尔积，
    数字会成倍虚高（这类"看起来只是慢"的统计错误最难被发现）。
    """
    rows = db.query(
        """
        SELECT t.id, t.code, t.name, t.contact, t.phone, t.status, t.created_at,
               (SELECT COUNT(*) FROM users u
                 WHERE u.tenant_id=t.id AND u.is_platform=0)     AS user_count,
               (SELECT COUNT(*) FROM elders e
                 WHERE e.tenant_id=t.id AND e.status=1)           AS elder_count,
               (SELECT COUNT(*) FROM cameras c WHERE c.tenant_id=t.id) AS camera_count,
               (SELECT COUNT(*) FROM alerts a WHERE a.tenant_id=t.id)  AS alert_count,
               (SELECT COUNT(*) FROM alerts a
                 WHERE a.tenant_id=t.id AND a.status=0)           AS pending_count,
               (SELECT MAX(a.alert_time) FROM alerts a
                 WHERE a.tenant_id=t.id)                          AS last_alert_at
        FROM tenants t
        ORDER BY t.id
        """
    )
    from app.repositories.base import keys_to_camel
    return {'success': True, 'data': keys_to_camel(rows)}


@router.get('/security')
def security(hours: int = Query(24, ge=1, le=720),
             user: dict[str, Any] = Depends(require_platform)):
    """安全事件：按 (账号, IP) 聚合登录失败与限流。

    为什么要聚合成"谁 从哪个 IP 试了多少次"而不是列流水：
    逐条列出 258 行登录失败没有任何可操作性；一眼看出
    "某个不存在的账号被从同一个 IP 试了 40 次"才是能立刻处理的信号。
    """
    since = local_now() - timedelta(hours=hours)
    rows = db.query(
        """
        SELECT username, ip,
               SUM(action='登录失败')   AS failed,
               SUM(action='登录被限流') AS locked,
               MIN(created_at)          AS first_at,
               MAX(created_at)          AS last_at,
               -- 命中已存在账号的失败次数：>0 说明对方猜对了用户名，
               -- 只差密码，风险高于纯粹的乱猜
               SUM(action='登录失败' AND tenant_id IS NOT NULL) AS known_account
        FROM audit_logs
        WHERE resource_type='auth' AND created_at >= %s
          AND action IN ('登录失败', '登录被限流')
        GROUP BY username, ip
        ORDER BY failed DESC, last_at DESC
        LIMIT 200
        """,
        [since.strftime('%Y-%m-%d %H:%M:%S')],
    )
    out = []
    for r in rows:
        out.append({
            'username': r.get('username') or '(空)',
            'ip': r.get('ip') or '—',
            'failed': int(r.get('failed') or 0),
            'locked': int(r.get('locked') or 0),
            'knownAccount': int(r.get('known_account') or 0),
            'firstAt': str(r.get('first_at') or ''),
            'lastAt': str(r.get('last_at') or ''),
            # 判定口径写在返回里，前端不必自己猜阈值；也避免以后有人改了一边
            'risk': ('high' if int(r.get('known_account') or 0) > 0
                     and int(r.get('failed') or 0) >= 5
                     else 'medium' if int(r.get('failed') or 0) >= 10
                     else 'low'),
        })
    return {'success': True, 'data': out, 'hours': hours}


@router.get('/audit')
def audit(page: int = 1, pageSize: int = 30, tenantId: int | None = None,
          keyword: str | None = None, onlyOrphans: bool = False,
          user: dict[str, Any] = Depends(require_platform)):
    """跨机构审计流水。

    ``onlyOrphans=true`` 只看 tenant_id 为 NULL 的那些 —— 也就是租户侧
    永远看不到的记录。
    """
    page = max(1, int(page or 1))
    page_size = min(200, max(1, int(pageSize or 30)))
    conds: list[str] = []
    params: list[Any] = []
    if onlyOrphans:
        conds.append('a.tenant_id IS NULL')
    elif tenantId is not None:
        conds.append('a.tenant_id=%s')
        params.append(int(tenantId))
    kw = (keyword or '').strip()
    if kw:
        conds.append('(a.action LIKE %s OR a.username LIKE %s OR a.resource_type LIKE %s)')
        params.extend([f'%{kw}%'] * 3)
    where = ('WHERE ' + ' AND '.join(conds)) if conds else ''

    total = _scalar(f'SELECT COUNT(*) FROM audit_logs a {where}', params)
    rows = db.query(
        f"""SELECT a.id, a.tenant_id, t.name AS tenant_name, a.user_id, a.username,
                   a.action, a.resource_type, a.resource_id, a.detail, a.ip, a.created_at
            FROM audit_logs a
            LEFT JOIN tenants t ON t.id = a.tenant_id
            {where}
            ORDER BY a.id DESC LIMIT %s OFFSET %s""",
        params + [page_size, (page - 1) * page_size],
    )
    from app.repositories.base import keys_to_camel
    return {'success': True, 'data': {
        'data': keys_to_camel(rows), 'total': total,
        'page': page, 'pageSize': page_size}}
