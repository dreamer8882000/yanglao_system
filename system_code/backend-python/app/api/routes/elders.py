from datetime import date
from typing import Any
import os
from fastapi import APIRouter, Depends, HTTPException, File, Form, UploadFile
from app.core.database import db
from app.core.security import get_current_user
from app.core.tenant import require_same_tenant, tenant_id_of, tenant_scope
from app.repositories.base import BaseRepository

router = APIRouter(prefix='/elders', tags=['elders'])
repo = BaseRepository('elders')


@router.get('/')
def list_elders(page: int = 1, pageSize: int = 20, keyword: str | None = None, status: int | None = None, user: dict[str, Any] = Depends(get_current_user)):
    # 租户条件是第一个、也是不可省略的条件
    where = ['tenant_id=%s']
    params: list[Any] = [tenant_id_of(user)]
    if keyword:
        where.append('(name LIKE %s OR room_no LIKE %s)')
        params.extend([f'%{keyword}%', f'%{keyword}%'])
    if status is not None:
        where.append('status=%s')
        params.append(status)
    return {'success': True, 'data': repo.paginate(page, pageSize, ' AND '.join(where), params)}


@router.get('/{elder_id}/health-trend')
def health_trend(elder_id: int, days: int = 7, user: dict[str, Any] = Depends(get_current_user)):
    rows = repo.query(
        "SELECT DATE(alert_time) AS date, risk_level, COUNT(*) AS count FROM alerts "
        "WHERE elder_id=%s AND tenant_id=%s AND alert_time >= DATE_SUB(CURDATE(), INTERVAL %s DAY) "
        "GROUP BY DATE(alert_time), risk_level ORDER BY date",
        [elder_id, tenant_id_of(user), max(1, min(days, 90))],
    )
    return {'success': True, 'data': {'trend': rows, 'totalAlerts': sum(int(r.get('count') or 0) for r in rows)}}


@router.get('/{elder_id}')
def elder_detail(elder_id: int, user: dict[str, Any] = Depends(get_current_user)):
    elder = require_same_tenant(repo.find_by_id(elder_id), user)
    return {'success': True, 'data': elder}


MAX_BEDS_PER_ROOM = 4


def _assign_bed(payload: dict[str, Any], tenant_id: int,
                exclude_elder_id: int | None = None) -> None:
    """确定床位号；未指定时自动分配该房间的空床位。

    背景：``elders`` 上有 ``UNIQUE(tenant_id, room_no, bed_no)`` —— 数据库层保证
    「同房内床位号不重复」，这是多人同房最基础的约束。副作用是：往一间已有老人的
    房间再加一位时，如果床位号仍是默认的 1，就会直接撞唯一键、报一句与业务
    毫无关系的 500。而"双人间加第二位老人"恰恰是最常见的操作。

    所以这里主动分床：
      * 前端显式指定了床位 → 占用则返回 409 并说明被谁占了（可执行的错误信息）；
      * 未指定 → 取该房间最小的空闲床位号；房间满员则 409。
    """
    room_no = payload.get('roomNo') or payload.get('room_no')
    if not room_no:
        return
    room_no = str(room_no)

    # ⚠ 不能加 `AND status=1`。唯一键是 UNIQUE(tenant_id, room_no, bed_no)，
    # 覆盖**所有行**（含已停档的）。原实现只把在册老人算作"已占用"，
    # 于是"停档 → 同房间再入住"这条最常规的床位流转会直接 500：
    # 应用层认为 1 号床空着，数据库却认为它被那位已停档的老人占着，
    # 撞唯一键后抛出一句与业务毫无关系的 "服务器内部错误"。
    # 正确语义是：**床位号只要被任何一位老人用过就不能重复使用**，
    # 要腾出床位应当先删除或改派那条历史记录。
    params: list[Any] = [tenant_id, room_no]
    sql = 'SELECT bed_no, name, status FROM elders WHERE tenant_id=%s AND room_no=%s'
    if exclude_elder_id is not None:
        sql += ' AND id<>%s'
        params.append(exclude_elder_id)
    rows = db.query(sql, params)
    taken = {int(r['bed_no'] or 1) for r in rows}
    occupant = {int(r['bed_no'] or 1): r for r in rows}

    raw = payload.get('bedNo')
    if raw in (None, ''):
        raw = payload.pop('bed_no', None)
    if raw in (None, ''):
        free = next((b for b in range(1, MAX_BEDS_PER_ROOM + 1) if b not in taken), None)
        if free is None:
            raise HTTPException(
                status_code=409,
                detail=f'{room_no} 室的 {MAX_BEDS_PER_ROOM} 张床位已满，无法再新增老人')
        payload['bedNo'] = free
        return

    try:
        bed = int(raw)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail='bedNo 必须为整数')
    if bed < 1 or bed > MAX_BEDS_PER_ROOM:
        raise HTTPException(status_code=400, detail=f'床位号必须在 1~{MAX_BEDS_PER_ROOM} 之间')
    if bed in taken:
        row = occupant.get(bed) or {}
        who = row.get('name') or ''
        # 已停档的老人仍占着床位号 —— 错误信息必须说清这一点，
        # 否则用户会看到"已被占用"但列表里找不到那位老人（他已停档），无从处理。
        state = '（已停档，需先删除该档案或改派床位）' if row.get('status') == 0 else ''
        raise HTTPException(
            status_code=409,
            detail=f'{room_no} 室的 {bed} 号床已被 {who}{state} 占用，请选择其它床位')
    payload['bedNo'] = bed


def _normalize_elder_payload(body: dict[str, Any], tenant_id: int | None = None,
                             exclude_elder_id: int | None = None) -> dict[str, Any]:
    """补齐 NOT NULL / 唯一约束相关的字段。

    ``elders.admission_date`` 是 NOT NULL 且没有默认值，而前端日期输入框在未选择时
    提交的是空串 —— 结果是新建老人直接 500「服务器内部错误」。未填入院日期时按
    **今天**处理：老人档案刚建立的那一刻就是入院日，这个默认值符合业务语义，
    比报错让管理员回头补填更合理。
    """
    payload = dict(body)
    if not str(payload.get('admissionDate') or payload.get('admission_date') or '').strip():
        payload['admissionDate'] = date.today().isoformat()
    if tenant_id is not None:
        _assign_bed(payload, tenant_id, exclude_elder_id)
    return payload


@router.post('/')
def create_elder(body: dict[str, Any], user: dict[str, Any] = Depends(get_current_user)):
    tid = tenant_id_of(user)
    payload = _normalize_elder_payload(body, tenant_id=tid)
    # 强制以当前用户的机构落库，忽略客户端传来的 tenantId
    payload['tenant_id'] = tid
    return {'success': True, 'data': repo.insert(payload), 'message': '创建成功'}


@router.put('/{elder_id}')
def update_elder(elder_id: int, body: dict[str, Any], user: dict[str, Any] = Depends(get_current_user)):
    require_same_tenant(repo.find_by_id(elder_id), user)
    payload = {k: v for k, v in body.items() if k not in ('tenantId', 'tenant_id')}
    # 空串会让 DATE 列报 1292 —— 编辑时未改动日期字段也要兜底
    if 'admissionDate' in payload and not str(payload.get('admissionDate') or '').strip():
        payload.pop('admissionDate')
    # 转房/换床同样要避免撞床位唯一键（排除自己，否则原地保存也会被判定为占用）
    if payload.get('roomNo') or payload.get('room_no') or payload.get('bedNo'):
        current = repo.find_by_id(elder_id) or {}
        merged = {**current, **payload}
        _assign_bed(merged, tenant_id_of(user), exclude_elder_id=elder_id)
        if 'bedNo' in merged:
            payload['bedNo'] = merged['bedNo']
    return {'success': True, 'data': repo.update(elder_id, payload), 'message': '更新成功'}


@router.post('/{elder_id}/avatar')
async def update_avatar(
    elder_id: int,
    avatar: str | None = Form(default=None),
    url: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
    user: dict[str, Any] = Depends(get_current_user),
):
    avatar_url = avatar or url
    if file and not avatar_url:
        avatar_url = f'/uploads/avatars/{elder_id}_{os.path.basename(file.filename or "")}'
    require_same_tenant(repo.find_by_id(elder_id), user)
    if not avatar_url:
        raise HTTPException(status_code=400, detail='缺少头像地址或文件')
    return {'success': True, 'data': repo.update(elder_id, {'avatar': avatar_url}), 'message': '头像更新成功'}


@router.post('/{elder_id}/archive')
def archive_elder(elder_id: int, user: dict[str, Any] = Depends(get_current_user)):
    require_same_tenant(repo.find_by_id(elder_id), user)
    repo.update(elder_id, {'status': 0})
    return {'success': True, 'message': '停档成功'}
