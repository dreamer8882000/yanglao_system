from datetime import datetime
from typing import Any
from fastapi import APIRouter, Depends
from app.core.database import db
from app.core.security import get_current_user, require_admin
from app.core.tenant import require_same_tenant, tenant_id_of
from app.repositories.base import BaseRepository

router = APIRouter(prefix='/cameras', tags=['cameras'])
repo = BaseRepository('cameras')

# 心跳有效期：超过这个秒数没上报就视为离线。
# 前端在真正使用某个摄像头时会调用 /heartbeat，所以"在线"的含义是
# "最近确实被成功使用过"，而不是数据库里某个写死的值。
HEARTBEAT_TTL_SECONDS = 90


def _is_online(last_heartbeat: Any, now: datetime | None = None) -> bool:
    """判断摄像头是否在线。兼容 datetime 与 ISO 字符串两种形态。

    仓储层会把 datetime 序列化成字符串（实测 last_heartbeat 返回
    '2026-10-09T17:22:46'），因此这里必须两种都认 —— 早期只处理 datetime，
    结果心跳写入成功却仍被判定为离线。
    """
    if last_heartbeat is None:
        return False
    ts = last_heartbeat
    if isinstance(ts, str):
        try:
            ts = datetime.fromisoformat(ts)
        except ValueError:
            return False
    if not isinstance(ts, datetime):
        return False
    now = now or datetime.now()
    delta = (now - ts).total_seconds()
    return 0 <= delta <= HEARTBEAT_TTL_SECONDS


def _apply_online_state(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """把库里的 status 替换为**由心跳推导**的真实在线状态。

    原实现直接把 cameras.status 返回给前端，而它是种子数据里写死的：
    实测 10 台摄像头全部指向不存在的 rtsp://192.168.1.x 地址、last_heartbeat
    全为 NULL（从未真正连上），却有 9 台显示"在线"。这种"假在线"比离线更危险 ——
    看板上会以为监控正在运行。

    现在规则很直白：只有在 HEARTBEAT_TTL_SECONDS 内上报过心跳的才算在线。
    因此新建/导入的摄像头默认都是离线，只有真正被启用过的才会变绿。
    """
    now = datetime.now()
    out = []
    for row in rows:
        item = dict(row)
        # 仓储层会把列名转成驼峰（last_heartbeat → lastHeartbeat），两种都取
        online = _is_online(item.get('last_heartbeat') or item.get('lastHeartbeat'), now)
        item['online'] = online
        # status 的语义保持不变（前端与看板统计都在用），取值改为推导结果
        item['status'] = 1 if online else 0
        out.append(item)
    return out


@router.get('/')
def list_cameras(page: int = 1, pageSize: int = 100,
                 keyword: str | None = None, online: str | None = None,
                 yoloEnabled: str | None = None,
                 user: dict[str, Any] = Depends(get_current_user)):
    """分页返回摄像头。

    统一成 {data, total, page, pageSize} —— 全站列表接口都遵守这个契约，
    前端的分页组件与列表页才能复用同一套读取逻辑。此前这里直接返回数组，
    是仅有的两个"形状不一致"的列表接口之一（另一个是 /medications/records），
    前端不得不为它写 `Array.isArray(x) ? x : x.data` 这种兼容分支。
    """
    where = ['tenant_id=%s']
    params: list[Any] = [tenant_id_of(user)]

    kw = (keyword or '').strip()
    if kw:
        where.append('(name LIKE %s OR room_no LIKE %s)')
        params.extend([f'%{kw}%', f'%{kw}%'])

    if yoloEnabled not in (None, ''):
        where.append('yolo_enabled=%s')
        params.append(1 if str(yoloEnabled) in ('1', 'true', 'True') else 0)

    # 「在线」是**推导出来的**（心跳在 HEARTBEAT_TTL_SECONDS 秒内），不是
    # cameras.status 列。但它的判据完全可以下推到 SQL，而且**必须**下推：
    #
    # 原实现是在应用层过滤的，结果是分页彻底失效 ——
    #   ① 先取一页（还被 repo.paginate 内部夹成最多 100 行），再在内存里筛；
    #   ② 末行 `result['data'] = rows` 又把**已切好的切片覆盖回未切片的整批**，
    #      于是 page=1 与 page=2 返回完全相同的内容，pageSize=1 也返回全部。
    # 实测（修复前）：page1 与 page2 的 id 列表逐项相同。
    # 另外取数上限被夹成 100，在线摄像头超过 100 台时 total 会静默少报。
    #
    # 把判据交给数据库之后，分页、总数、切片全部由 SQL 保证，与其它列表接口一致。
    if online not in (None, ''):
        if str(online) in ('1', 'true', 'True'):
            where.append(f'last_heartbeat >= DATE_SUB(NOW(), INTERVAL {HEARTBEAT_TTL_SECONDS} SECOND)')
        else:
            where.append(f'(last_heartbeat IS NULL OR '
                         f'last_heartbeat < DATE_SUB(NOW(), INTERVAL {HEARTBEAT_TTL_SECONDS} SECOND))')

    result = repo.paginate(page, pageSize, where=' AND '.join(where),
                           params=params, order_by='id DESC')
    result['data'] = _apply_online_state(result['data'])
    return {'success': True, 'data': result}


@router.post('/')
def create_camera(body: dict[str, Any], user: dict[str, Any] = Depends(require_admin)):
    # 新建的摄像头一律先按离线入库：它还没上报过任何心跳，
    # 此时标成在线就是前面说的"假在线"。
    payload = dict(body)
    payload['status'] = 0
    payload['tenant_id'] = tenant_id_of(user)
    return {'success': True, 'data': repo.insert(payload), 'message': '添加成功'}


@router.put('/{camera_id}')
def update_camera(camera_id: int, body: dict[str, Any], user: dict[str, Any] = Depends(require_admin)):
    # 不允许通过编辑接口直接把状态改成在线 —— 在线只能由心跳推导出来
    require_same_tenant(repo.find_by_id(camera_id), user)
    payload = {k: v for k, v in body.items()
               if k not in ('status', 'online', 'tenantId', 'tenant_id')}
    return {'success': True, 'data': repo.update(camera_id, payload), 'message': '更新成功'}


@router.delete('/{camera_id}')
def delete_camera(camera_id: int, user: dict[str, Any] = Depends(require_admin)):
    require_same_tenant(repo.find_by_id(camera_id), user)
    repo.delete(camera_id)
    return {'success': True, 'message': '删除成功'}


@router.post('/{camera_id}/heartbeat')
def heartbeat(camera_id: int, user: dict[str, Any] = Depends(get_current_user)):
    # 加 tenant 条件：否则知道 id 就能给别的机构的摄像头打心跳
    db.execute("UPDATE cameras SET status=1, last_heartbeat=NOW(), offline_notified=0 "
               "WHERE id=%s AND tenant_id=%s", [camera_id, tenant_id_of(user)])
    return {'success': True}
