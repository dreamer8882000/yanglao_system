from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Request
from app.core.security import get_current_user, require_admin
from app.repositories.base import BaseRepository
from app.core.tenant import require_same_tenant, tenant_id_of, tenant_scope
from app.services.audit import record_audit

#: 排序必须带**唯一列兜底**（id DESC）。
#:
#: 只按时间列排序时，时间并列的行之间**没有确定顺序** —— MySQL 每次可以给它们
#: 不同的次序，于是 LIMIT/OFFSET 分页会重复返回某些行、同时漏掉另一些。
#: 实测：巡查记录 142 条里有 28 组 patrol_time 并列（种子数据是按天批量生成的），
#: 逐页取完只得到 **131 条唯一记录、重复 11 条**，第 1 页与第 2 页的主键还重叠。
#: 护理员一页页翻会看到重复行，并且永远看不到被跳过的 11 条。
#:
#: 这不是"显示小瑕疵"：审计、用药、巡查这类记录一旦漏读，就是合规问题。
DEFAULT_ORDER_BY = {
    'patrol_records': 'patrol_time DESC, id DESC',
    'medication_records': 'scheduled_time DESC, id DESC',
    'vital_signs': 'record_time DESC, id DESC',
}

# ── 每张表能用什么条件查 ────────────────────────────────────────────────────
# 列表页若只有"翻页"而没有条件查询，数据一多就没法用：护理员要找"李桂芳上周
# 的用药记录"，只能一页页翻。这里把「可搜索列 / 日期列 / 状态列」按表登记一次，
# 六个资源共用同一套查询参数（keyword / startDate / endDate / status），
# 前端也就只需要一套工具栏 —— 而不是每个页面各自发明一套筛选。
#
# 列名全部来自这份**代码内的固定配置**，不接受客户端传入，因此拼接是安全的；
# 参数一律走 %s 占位符。
FILTER_CONFIG: dict[str, dict[str, Any]] = {
    'audit_logs':         {'search': ('action', 'resource_type', 'username', 'resource_id'),
                           'date': 'created_at'},
    'medications':        {'search': ('medication_name', 'dosage', 'frequency'),
                           'date': 'created_at', 'status': 'status', 'elder': True},
    'medication_records': {'search': ('notes',), 'date': 'scheduled_time',
                           'status': 'status', 'elder': True},
    'messages':           {'search': ('title', 'content'), 'date': 'created_at',
                           'status': 'is_read'},
    'patrol_records':     {'search': ('location', 'notes'), 'date': 'patrol_time',
                           'elder': True},
    'vital_signs':        {'search': ('notes',), 'date': 'record_time', 'elder': True},
    'schedules':          {'search': ('shift_type', 'note'), 'date': 'shift_date'},
}


def _build_filters(table: str, keyword: str | None, start_date: str | None,
                   end_date: str | None, status: str | None,
                   elder_id: str | None = None) -> tuple[str, list[Any]]:
    """把查询条件拼成 WHERE 片段（不含 tenant_id，由调用方负责）。

    日期用 `>= start` / `<= end` 而不是 `=`，这样前端给一个"起止日期"区间就够了；
    传单天时前端只需两边都填同一天。
    """
    cfg = FILTER_CONFIG.get(table, {})
    where: list[str] = []
    params: list[Any] = []

    kw = (keyword or '').strip()
    if kw and cfg.get('search'):
        # 多列 OR：任一列命中即算命中。LIKE 的 % 交给参数，不拼进 SQL
        cols = ' OR '.join(f'{c} LIKE %s' for c in cfg['search'])
        where.append(f'({cols})')
        params.extend([f'%{kw}%'] * len(cfg['search']))

    date_col = cfg.get('date')
    if start_date and date_col:
        where.append(f'{date_col} >= %s')
        params.append(start_date)
    if end_date and date_col:
        # 结束日期按"当天 23:59:59"理解，否则 DATETIME 列会把当天全部漏掉。
        # 字符串字面量一律用**单引号**：双引号在 MySQL 里也是字符串，
        # 但一旦服务端开启 ANSI_QUOTES（常见的加固配置）就会被当成标识符而报错。
        # 单引号在任何 sql_mode 下都是字符串，没有这个歧义。
        where.append(f"{date_col} <= CONCAT(%s, ' 23:59:59')" if _is_datetime_column(date_col)
                     else f'{date_col} <= %s')
        params.append(end_date)

    # 按老人筛选：列表页上最常用的条件之一（"李桂芳这周的用药/体征/巡查"）。
    # 它以前被漏掉了 —— 页面上那个「全部老人」下拉把 elderId 传上来，
    # 而接口签名里没有这个参数，FastAPI 会**静默丢弃**未知的 query 参数，
    # 于是下拉看着能用、实际不过滤。这类"静默无效"的控件比报错更难发现。
    if elder_id not in (None, '') and cfg.get('elder'):
        try:
            where.append('elder_id = %s')
            params.append(int(elder_id))
        except (TypeError, ValueError):
            pass

    status_col = cfg.get('status')
    if status not in (None, '') and status_col:
        where.append(f'{status_col} = %s')
        params.append(int(status) if str(status).lstrip('-').isdigit() else status)

    return ' AND '.join(where), params


#: 需要按"当天 23:59:59"上界的列（DATETIME）；DATE 列直接比较即可
_DATETIME_COLUMNS = {'created_at', 'updated_at', 'scheduled_time', 'patrol_time',
                     'record_time', 'actual_time'}


def _is_datetime_column(col: str) -> bool:
    return col in _DATETIME_COLUMNS


def _apply_context_defaults(table: str, body: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
    data = dict(body)
    if table == 'patrol_records':
        data.setdefault('nurseId', user.get('id'))
    elif table == 'medications':
        data.setdefault('createdBy', user.get('id'))
        if isinstance(data.get('timeSlots'), list):
            import json
            data['timeSlots'] = json.dumps(data['timeSlots'], ensure_ascii=False)
    elif table == 'vital_signs':
        data.setdefault('recorderId', user.get('id'))
    return data


def _is_admin(user: dict[str, Any]) -> bool:
    return str(user.get('role') or '').lower() == 'admin'


def _message_scope(table: str, user: dict[str, Any], where: str,
                   params: list[Any]) -> tuple[str, list[Any]]:
    """私信只能看自己的；管理员保留机构级审计/运营视角。"""
    if table == 'messages' and not _is_admin(user):
        where += ' AND user_id=%s'
        params.append(user.get('id'))
    return where, params


def _message_visible(table: str, item: dict[str, Any], user: dict[str, Any]) -> bool:
    if table != 'messages' or _is_admin(user):
        return True
    owner = item.get('user_id')
    if owner is None:
        owner = item.get('userId')
    return str(owner) == str(user.get('id'))


def crud_router(prefix: str, table: str, tag: str, admin_write: bool = False,
                admin_read: bool = False) -> APIRouter:
    router = APIRouter(prefix=prefix, tags=[tag])
    repo = BaseRepository(table)

    # 读权限可以直接收紧（admin_read=True）：审计日志是机构级的合规视图，
    # 只有管理员需要看。前端路由守卫只是"别让人误入半空白页"，真正的
    # 权限边界必须在这里 —— 实测护理员直接 curl /api/audit/ 原本返回 200。
    read_dep = require_admin if admin_read else get_current_user

    # ── 多租户：本表所有读写都限定在当前用户所属机构 ──────────────────────
    # 在 crud_router 这一层统一加，一处即覆盖 schedules / messages / audit /
    # patrols / medications / vital-signs 六个资源；若分散到各路由去加，
    # 漏掉任何一处都会造成跨租户数据泄露。
    @router.get('/')
    def list_items(page: int = 1, pageSize: int = 20,
                   keyword: str | None = None, startDate: str | None = None,
                   endDate: str | None = None, status: str | None = None,
                   elderId: int | None = None,
                   user: dict[str, Any] = Depends(read_dep)):
        # 租户条件永远是第一个，不可省略
        where, params = tenant_scope(user)
        where, params = _message_scope(table, user, where, params)
        extra, extra_params = _build_filters(table, keyword, startDate, endDate, status,
                                             elder_id=elderId)
        if extra:
            where = f'{where} AND {extra}'
            params.extend(extra_params)
        return {'success': True, 'data': repo.paginate(
            page, pageSize, where=where, params=params,
            order_by=DEFAULT_ORDER_BY.get(table, 'id DESC'))}

    @router.get('/{item_id}')
    def get_item(item_id: int, user: dict[str, Any] = Depends(read_dep)):
        # require_same_tenant 对"不存在"与"属于别的机构"返回同样的 404，
        # 不泄露该记录是否存在。
        item = require_same_tenant(repo.find_by_id(item_id), user)
        if not _message_visible(table, item, user):
            raise HTTPException(status_code=404, detail='数据不存在')
        return {'success': True, 'data': item}

    def write_dep(user: dict[str, Any] = Depends(require_admin if admin_write else get_current_user)):
        return user

    @router.post('/')
    def create_item(body: dict[str, Any], request: Request = None,
                    user: dict[str, Any] = Depends(write_dep)):
        payload = _apply_context_defaults(table, body, user)
        # 私信只有管理员能代发；普通用户无论传什么 userId 都只能写给自己。
        if table == 'messages' and not _is_admin(user):
            payload.pop('userId', None)
            payload['user_id'] = user.get('id')
        # 强制以当前用户的租户落库，忽略客户端传来的 tenantId
        payload['tenant_id'] = tenant_id_of(user)
        item = repo.insert(payload)
        record_audit(f'新增 {table}', user=user, resource_type=table,
                     resource_id=(item or {}).get('id') if isinstance(item, dict) else None,
                     detail=body, request=request)
        return {'success': True, 'data': item, 'message': '创建成功'}

    @router.put('/{item_id}')
    def update_item(item_id: int, body: dict[str, Any], request: Request = None,
                    user: dict[str, Any] = Depends(write_dep)):
        # 先确认目标属于本租户，再更新；同时禁止改动 tenant_id（防越权转移）
        existing = require_same_tenant(repo.find_by_id(item_id), user)
        if not _message_visible(table, existing, user):
            raise HTTPException(status_code=404, detail='数据不存在')
        payload = _apply_context_defaults(table, body, user)
        if table == 'messages' and not _is_admin(user):
            payload.pop('userId', None)
            payload['user_id'] = user.get('id')
        payload.pop('tenant_id', None)
        item = repo.update(item_id, payload)
        record_audit(f'修改 {table}', user=user, resource_type=table,
                     resource_id=item_id, detail=body, request=request)
        return {'success': True, 'data': item, 'message': '更新成功'}

    @router.delete('/{item_id}')
    def delete_item(item_id: int, request: Request = None,
                    user: dict[str, Any] = Depends(write_dep)):
        existing = require_same_tenant(repo.find_by_id(item_id), user)
        if not _message_visible(table, existing, user):
            raise HTTPException(status_code=404, detail='数据不存在')
        repo.delete(item_id)
        record_audit(f'删除 {table}', user=user, resource_type=table,
                     resource_id=item_id, request=request)
        return {'success': True, 'message': '删除成功'}

    return router
