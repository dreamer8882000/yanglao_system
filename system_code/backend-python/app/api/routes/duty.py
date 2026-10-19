"""排班值守：调班、冲突检测、巡查任务派发、告警派单。

为什么单独成模块而不复用 crud_router：
  通用 CRUD 只会原样写库，而这里每一个写操作都需要**业务校验与联动** ——
    * 排班冲突要在接口层给出可读的 409，而不是让唯一索引抛 500；
    * 拖拽调班要同时改日期、班次、人员三件事并重新校验冲突；
    * 巡查任务要能按房间批量生成、指派给当班护理员、完成后回写记录；
    * 告警派单的默认对象应当是**此刻真正在岗的人**，而不是随手挑一个。

注册顺序很关键：本模块必须先于 crud_router('/schedules') 注册，
否则通用路由的 POST/PUT 会先匹配上，冲突检测就被绕过了。
"""
from datetime import date, datetime, time as dtime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.core.database import db
from app.core.security import get_current_user, require_admin
from app.core.tenant import require_same_tenant, tenant_id_of
from app.repositories.base import keys_to_camel
from app.services.audit import record_audit

router = APIRouter(tags=['duty'])


# ── 内部工具 ───────────────────────────────────────────────────────────────

def _fmt_time(value: Any) -> Any:
    """把 PyMySQL 返回的 TIME 转成 'HH:MM' 字符串。

    PyMySQL 会把 MySQL 的 TIME 列读成**秒数**（如 08:00 → 28800.0），而前端
    模板在做 `startTime.slice(0,5)` —— 对数字调用 .slice() 会抛 TypeError，
    导致整个组件渲染失败、页面**一片空白**。此前该页面因为数据源字段对不上
    一直是空的，所以这个类型问题从未暴露；修好数据源后它立刻显现。
    在接口层统一格式化，比让每个模板各自防御更可靠。
    """
    if value is None:
        return None
    if isinstance(value, timedelta):
        total = int(value.total_seconds())
    elif isinstance(value, dtime):
        return value.strftime('%H:%M')
    elif isinstance(value, (int, float)):
        total = int(value)
    else:
        text = str(value)
        return text[:5] if len(text) >= 5 else text
    total %= 86400
    return f'{total // 3600:02d}:{(total % 3600) // 60:02d}'


def _fmt_row_time(row: dict[str, Any], *fields: str) -> dict[str, Any]:
    out = dict(row)
    for f in fields:
        if f in out:
            out[f] = _fmt_time(out[f])
    return out


def _shift_row(shift_type: str) -> dict[str, Any]:
    rows = db.query('SELECT * FROM shifts WHERE shift_type=%s', [shift_type])
    if not rows:
        raise HTTPException(status_code=400,
                            detail=f'未知班次「{shift_type}」，可用值见 /duty/shifts')
    return rows[0]


def _to_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace('Z', '')).date()
        except ValueError:
            pass
    raise HTTPException(status_code=400, detail=f'日期格式无法解析: {value!r}')


def _conflict(user_id: int, shift_date: date, exclude_id: int | None = None,
              tenant_id: int | None = None) -> dict[str, Any] | None:
    """返回造成冲突的既有排班；无冲突返回 None。

    冲突定义：同一位护理员在同一天已有班次。夜班本身就横跨午夜（20:00-08:00），
    所以"同一天两班"在现实中等于连续 24 小时在岗，一律视为冲突。
    """
    sql = ('SELECT s.id, s.shift_type, s.start_time, s.end_time, u.name AS user_name '
           'FROM schedules s LEFT JOIN users u ON u.id = s.user_id AND u.tenant_id = s.tenant_id '
           'WHERE s.user_id=%s AND s.shift_date=%s')
    params: list[Any] = [user_id, shift_date]
    if tenant_id is not None:
        sql += ' AND s.tenant_id=%s'
        params.append(tenant_id)
    if exclude_id is not None:
        sql += ' AND s.id <> %s'
        params.append(exclude_id)
    rows = db.query(sql, params)
    return rows[0] if rows else None


def _guard_conflict(user_id: int, shift_date: date, shift_type: str, exclude_id: int | None = None,
                    tenant_id: int | None = None) -> None:
    hit = _conflict(user_id, shift_date, exclude_id, tenant_id)
    if hit:
        who = hit.get('user_name') or f'用户#{user_id}'
        raise HTTPException(
            status_code=409,
            detail=f'{who} 在 {shift_date} 已排「{hit["shift_type"]}」班'
                   f'（{hit["start_time"]}~{hit["end_time"]}），同一人同一天不能排两班',
        )


def _require_tenant_user(user_id: Any, user: dict[str, Any]) -> int:
    """把外部传入的 userId 当作授权约束：不存在/跨机构统一 404。"""
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail='userId 必须为整数')
    require_same_tenant(db.query_one('SELECT id, tenant_id FROM users WHERE id=%s', [uid]), user)
    return uid


# ── 班次字典 ───────────────────────────────────────────────────────────────

@router.get('/duty/shifts')
def list_shifts(user: dict[str, Any] = Depends(get_current_user)):
    rows = [_fmt_row_time(r, 'start_time', 'end_time')
            for r in db.query('SELECT * FROM shifts ORDER BY sort_order')]
    return {'success': True, 'data': keys_to_camel(rows)}


@router.get('/duty/overview')
def duty_overview(weekStart: str | None = None, user: dict[str, Any] = Depends(get_current_user)):
    """排班值守页一次取全：本周网格 + 当班 + 巡查任务完成情况。"""
    anchor = _to_date(weekStart) if weekStart else date.today()
    start = anchor - timedelta(days=anchor.weekday())      # 周一
    end = start + timedelta(days=6)

    schedules = [_fmt_row_time(r, 'start_time', 'end_time') for r in db.query('''
        SELECT s.id, s.user_id, u.name AS user_name, u.role,
               s.shift_date, s.shift_type, sh.label AS shift_label,
               s.start_time, s.end_time, sh.crosses_midnight, s.note
        FROM schedules s
        LEFT JOIN users  u  ON u.id = s.user_id AND u.tenant_id = s.tenant_id
        LEFT JOIN shifts sh ON sh.shift_type = s.shift_type
        WHERE s.tenant_id = %s AND s.shift_date BETWEEN %s AND %s
        ORDER BY s.shift_date, sh.sort_order
    ''', [tenant_id_of(user), start, end])]

    # 本周每人已排班次数，用于均衡提示
    load: dict[int, int] = {}
    for s in schedules:
        load[s['user_id']] = load.get(s['user_id'], 0) + 1

    nurses = db.query("SELECT id, name, username, role, dept_name FROM users "
                      "WHERE tenant_id=%s AND role IN ('nurse','admin') ORDER BY id",
                      [tenant_id_of(user)])

    tasks = [_fmt_row_time(r, 'start_time', 'end_time') for r in db.query('''
        SELECT t.id, t.room_no, t.task_date, t.window_start, t.window_end, t.status,
               t.notes, t.completed_at, t.alert_id,
               e.name AS elder_name, u.name AS assignee_name
        FROM patrol_tasks t
        LEFT JOIN elders e ON e.id = t.elder_id AND e.tenant_id = t.tenant_id
        LEFT JOIN users  u ON u.id = t.assigned_to AND u.tenant_id = t.tenant_id
        WHERE t.tenant_id = %s AND t.task_date BETWEEN %s AND %s
        ORDER BY t.window_start DESC
    ''', [tenant_id_of(user), start, end])]

    return {'success': True, 'data': {
        'weekStart': start.isoformat(),
        'weekEnd': end.isoformat(),
        'schedules': keys_to_camel(schedules),
        'nurses': keys_to_camel(nurses),
        'workload': load,
        'tasks': keys_to_camel(tasks),
    }}


# ── 排班：新建 / 调班（拖拽）/ 删除 ────────────────────────────────────────

@router.post('/schedules/')
def create_schedule(body: dict[str, Any], user: dict[str, Any] = Depends(require_admin)):
    user_id = body.get('userId') or body.get('user_id')
    shift_type = body.get('shiftType') or body.get('shift_type')
    if not user_id or not shift_type or not (body.get('shiftDate') or body.get('shift_date')):
        raise HTTPException(status_code=400, detail='缺少 userId / shiftDate / shiftType')
    shift_date = _to_date(body.get('shiftDate') or body.get('shift_date'))
    tid = tenant_id_of(user)
    user_id = _require_tenant_user(user_id, user)
    _guard_conflict(user_id, shift_date, shift_type, tenant_id=tid)

    # 班次时间一律取自字典，避免每行各写一份、写歪了无人察觉
    shift = _shift_row(shift_type)
    with db.transaction() as conn:
        with conn.cursor() as cur:
            cur.execute('''INSERT INTO schedules
                (tenant_id, user_id, shift_date, shift_type, start_time, end_time, note, created_by)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)''',
                [tid, int(user_id), shift_date, shift_type,
                 shift['start_time'], shift['end_time'],
                 body.get('note') or '', user.get('id')])
            new_id = cur.lastrowid
    record_audit('新增排班', user=user, resource_type='schedules', resource_id=new_id,
                 detail=f'{shift_date} {shift_type} → 用户#{user_id}')
    return {'success': True, 'data': {'id': new_id}, 'message': '排班已创建'}


@router.put('/schedules/{item_id}')
def update_schedule(item_id: int, body: dict[str, Any], user: dict[str, Any] = Depends(require_admin)):
    """拖拽调班：可改日期、班次、人员，先做冲突检测再落库。"""
    tid = tenant_id_of(user)
    current = require_same_tenant(db.query_one('SELECT * FROM schedules WHERE id=%s', [item_id]), user)

    user_id = int(body.get('userId') or body.get('user_id') or current['user_id'])
    shift_type = body.get('shiftType') or body.get('shift_type') or current['shift_type']
    shift_date = _to_date(body.get('shiftDate') or body.get('shift_date') or current['shift_date'])

    user_id = _require_tenant_user(user_id, user)
    unchanged = (user_id == current['user_id'] and shift_type == current['shift_type']
                 and shift_date == current['shift_date'])
    if not unchanged:
        _guard_conflict(user_id, shift_date, shift_type, exclude_id=item_id, tenant_id=tid)

    shift = _shift_row(shift_type)
    db.execute('''UPDATE schedules SET user_id=%s, shift_date=%s, shift_type=%s,
                                         start_time=%s, end_time=%s, note=%s
                  WHERE id=%s AND tenant_id=%s''',
               [user_id, shift_date, shift_type, shift['start_time'], shift['end_time'],
                body.get('note', current.get('note') or ''), item_id, tid])
    record_audit('调整排班', user=user, resource_type='schedules', resource_id=item_id,
                 detail=f'→ {shift_date} {shift_type} 用户#{user_id}')
    return {'success': True, 'message': '排班已调整'}


@router.delete('/schedules/{item_id}')
def delete_schedule(item_id: int, user: dict[str, Any] = Depends(require_admin)):
    require_same_tenant(db.query_one('SELECT id, tenant_id FROM schedules WHERE id=%s', [item_id]), user)
    db.execute('DELETE FROM schedules WHERE id=%s AND tenant_id=%s', [item_id, tenant_id_of(user)])
    record_audit('删除排班', user=user, resource_type='schedules', resource_id=item_id)
    return {'success': True, 'message': '排班已删除'}


# ── 巡查任务：生成 / 派发 / 完成回写 ───────────────────────────────────────

def _on_duty_nurse(now: datetime | None = None, tenant_id: int | None = None) -> dict[str, Any] | None:
    """此刻真正在岗的护理员（含跨夜班次），且必须属于同一机构。"""
    now = now or datetime.now()
    scope = ' AND s.tenant_id = %s' if tenant_id is not None else ''
    scope_params = [tenant_id] if tenant_id is not None else []
    # ⚠ 三个班次分支必须**整体**被一对括号包住，租户条件才能作用于全部三个。
    # 原写法是  `WHERE (A) OR (B) OR (C)  AND tenant_id=?`
    # 而 MySQL 里 AND 的优先级高于 OR，它等价于 `(A) OR (B) OR (C AND tenant_id=?)`
    # —— 租户条件只绑到了最后一个分支，前两个分支完全不受约束。
    # 实测：传一个**不存在**的 tenant_id=999 仍会返回租户 1 的当班护理员。
    # 后果不是"查不到"，而是**查到别人家的人**：告警派单与巡查任务生成都会把
    # 本机构的工作派给另一个机构的护士（两边列表都按 tenant_id 过滤，所以
    # 被派单的人根本看不到这条任务）。
    rows = db.query(f'''
        SELECT s.user_id, u.name AS user_name
        FROM schedules s JOIN users u ON u.id = s.user_id AND u.tenant_id = s.tenant_id
        WHERE ((
                s.shift_date = CURDATE() AND s.start_time <= s.end_time
                AND %s >= s.start_time AND %s < s.end_time
              ) OR (
                s.shift_date = CURDATE() AND s.start_time > s.end_time
                AND %s >= s.start_time
              ) OR (
                s.shift_date = DATE_SUB(CURDATE(), INTERVAL 1 DAY) AND s.start_time > s.end_time
                AND %s < s.end_time
              )
        ){scope}
        ORDER BY s.start_time LIMIT 1
    ''', [now.time(), now.time(), now.time(), now.time()] + scope_params)
    return rows[0] if rows else None


@router.get('/patrols/tasks')
def list_patrol_tasks(status: int | None = None, taskDate: str | None = None,
                      user: dict[str, Any] = Depends(get_current_user)):
    where, params = ['t.tenant_id=%s'], [tenant_id_of(user)]
    if status is not None:
        where.append('t.status=%s')
        params.append(status)
    if taskDate:
        where.append('t.task_date=%s')
        params.append(_to_date(taskDate))
    sql = '''SELECT t.*, e.name AS elder_name, u.name AS assignee_name,
                    c.name AS completer_name, a.risk_level AS alert_level
             FROM patrol_tasks t
             LEFT JOIN elders e ON e.id = t.elder_id AND e.tenant_id = t.tenant_id
             LEFT JOIN users  u ON u.id = t.assigned_to AND u.tenant_id = t.tenant_id
             LEFT JOIN users  c ON c.id = t.completed_by AND c.tenant_id = t.tenant_id
             LEFT JOIN alerts a ON a.id = t.alert_id AND a.tenant_id = t.tenant_id'''
    sql += ' WHERE ' + ' AND '.join(where)
    sql += ' ORDER BY t.window_start DESC LIMIT 200'
    rows = [_fmt_row_time(r, 'start_time', 'end_time') for r in db.query(sql, params)]
    return {'success': True, 'data': keys_to_camel(rows)}


@router.post('/patrols/tasks/generate')
def generate_patrol_tasks(body: dict[str, Any] | None = None,
                          user: dict[str, Any] = Depends(require_admin)):
    """为某个夜班生成全部房间的巡查任务。

    这是「巡查」此前缺失的一环：过去只有**已完成**的记录，没有任务本身，
    于是没人知道"今晚还有哪几间房没巡"。生成时自动指派给此刻在岗的护理员，
    查不到当班人就留空，由管理员手工指派，而不是静默失败。
    """
    body = body or {}
    tid = tenant_id_of(user)
    night = _to_date(body.get('taskDate')) if body.get('taskDate') else date.today()
    assignee = body.get('assignedTo') or body.get('assigned_to')
    auto = None
    if not assignee:
        duty = _on_duty_nurse(tenant_id=tid)
        if duty:
            assignee, auto = duty['user_id'], duty['user_name']
    if assignee not in (None, ''):
        assignee = _require_tenant_user(assignee, user)

    rooms = db.query('''SELECT e.id AS elder_id, e.name AS elder_name, e.room_no
                        FROM elders e WHERE e.tenant_id=%s AND e.status = 1 ORDER BY e.room_no''',
                     [tid])
    if not rooms:
        raise HTTPException(status_code=400, detail='没有在册老人，无法生成巡查任务')

    # 夜班分四轮：22:00 / 00:30 / 02:00 / 04:00
    rounds = [dtime(22, 0), dtime(0, 30), dtime(2, 0), dtime(4, 0)]
    created = skipped = 0
    with db.transaction() as conn:
        with conn.cursor() as cur:
            for room in rooms:
                for rt in rounds:
                    day = night if rt.hour >= 12 else night + timedelta(days=1)
                    start = datetime.combine(day, rt)
                    end = start + timedelta(minutes=45)
                    cur.execute('''INSERT IGNORE INTO patrol_tasks
                        (tenant_id, elder_id, room_no, assigned_to, task_date, window_start, window_end,
                         status, created_by)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,0,%s)''',
                        [tid, room['elder_id'], room['room_no'], assignee, night,
                         start, end, user.get('id')])
                    if cur.rowcount:
                        created += 1
                    else:
                        skipped += 1
    record_audit('生成巡查任务', user=user, resource_type='patrol_tasks',
                 detail=f'{night} 夜班：新建 {created} 条，已存在 {skipped} 条')
    return {'success': True,
            'data': {'created': created, 'skipped': skipped,
                     'assignedTo': assignee, 'assignedName': auto},
            'message': f'已生成 {created} 条巡查任务'
                       + (f'，指派给当班护理员 {auto}' if auto else '（未找到当班人员，请手工指派）')}


@router.post('/patrols/tasks/{task_id}/complete')
def complete_patrol_task(task_id: int, body: dict[str, Any] | None = None,
                         user: dict[str, Any] = Depends(get_current_user)):
    """完成巡查任务，并回写一条巡逻记录 —— 派发→完成→留痕的闭环。"""
    body = body or {}
    tid = tenant_id_of(user)
    task = require_same_tenant(db.query_one('SELECT * FROM patrol_tasks WHERE id=%s', [task_id]), user)
    if task['status'] == 1:
        raise HTTPException(status_code=409, detail='该任务已完成')

    status = int(body.get('status', 1))          # 1 完成 / 2 跳过
    if status not in (1, 2):
        raise HTTPException(status_code=400, detail='status 只能是 1(完成) 或 2(跳过)')
    notes = body.get('notes') or ('已巡查，无异常' if status == 1 else '已跳过')

    with db.transaction() as conn:
        with conn.cursor() as cur:
            cur.execute('''UPDATE patrol_tasks
                           SET status=%s, completed_at=NOW(), completed_by=%s, notes=%s
                           WHERE id=%s AND tenant_id=%s AND status=0''',
                        [status, user.get('id'), notes, task_id, tid])
            if cur.rowcount == 0:
                raise HTTPException(status_code=409, detail='该任务已被其他用户处理，请刷新后重试')
            record_id = None
            if status == 1:
                cur.execute('''INSERT INTO patrol_records
                    (tenant_id, elder_id, patrol_time, nurse_id, location, notes, task_id)
                    VALUES (%s, %s, NOW(), %s, %s, %s, %s)''',
                    [tid, task['elder_id'], user.get('id'), task['room_no'], notes, task_id])
                record_id = cur.lastrowid
    record_audit('完成巡查', user=user, resource_type='patrol_tasks', resource_id=task_id,
                 detail=f'{task["room_no"]} {notes}')
    return {'success': True, 'data': {'taskId': task_id, 'recordId': record_id},
            'message': '巡查已完成' if status == 1 else '已标记跳过'}


@router.post('/patrols/tasks/{task_id}/assign')
def assign_patrol_task(task_id: int, body: dict[str, Any],
                       user: dict[str, Any] = Depends(require_admin)):
    assignee = body.get('assignedTo') or body.get('assigned_to')
    if not assignee:
        raise HTTPException(status_code=400, detail='缺少 assignedTo')
    require_same_tenant(db.query_one('SELECT id, tenant_id FROM patrol_tasks WHERE id=%s', [task_id]), user)
    assignee = _require_tenant_user(assignee, user)
    db.execute('UPDATE patrol_tasks SET assigned_to=%s WHERE id=%s AND tenant_id=%s',
               [assignee, task_id, tenant_id_of(user)])
    return {'success': True, 'message': '已指派'}


# ── 告警派单：默认派给此刻在岗的人 ─────────────────────────────────────────

@router.post('/alerts/{alert_id}/assign')
def assign_alert(alert_id: int, body: dict[str, Any] | None = None,
                 user: dict[str, Any] = Depends(get_current_user)):
    """把告警派给护理员；不指定人时自动选**此刻真正在岗**的那位。

    此前告警有 assigned_to 字段却没有任何接口能写入它，于是"派单"名存实亡：
    告警只能被确认，无法被指派，值班表与告警处理之间没有连接。
    """
    body = body or {}
    tid = tenant_id_of(user)
    alert = require_same_tenant(db.query_one('SELECT * FROM alerts WHERE id=%s', [alert_id]), user)

    assignee = body.get('assignedTo') or body.get('assigned_to')
    source = 'manual'
    if not assignee:
        duty = _on_duty_nurse(tenant_id=tid)
        if not duty:
            raise HTTPException(status_code=409,
                                detail='当前找不到在岗护理员，请手工指定 assignedTo')
        assignee, source = duty['user_id'], 'on_duty'
    assignee = _require_tenant_user(assignee, user)

    db.execute('''UPDATE alerts SET assigned_to=%s,
                    status = CASE WHEN status = 0 THEN 0 ELSE status END
                  WHERE id=%s AND tenant_id=%s''', [int(assignee), alert_id, tid])

    who = db.query('SELECT name FROM users WHERE id=%s AND tenant_id=%s', [int(assignee), tid])
    name = who[0]['name'] if who else f'用户#{assignee}'

    # 同步生成一条对应房间的巡查任务，让护理员在自己的待办里看到它
    if alert.get('elder_id'):
        room = db.query('SELECT room_no FROM elders WHERE id=%s AND tenant_id=%s',
                        [alert['elder_id'], tid])
        if room:
            now = datetime.now()
            db.execute('''INSERT IGNORE INTO patrol_tasks
                (tenant_id, elder_id, room_no, assigned_to, task_date, window_start, window_end,
                 status, alert_id, notes)
                VALUES (%s,%s,%s,%s,CURDATE(),%s,%s,0,%s,%s)''',
                [tid, alert['elder_id'], room[0]['room_no'], int(assignee), now,
                 now + timedelta(minutes=30), alert_id,
                 f'由告警#{alert_id}触发（{alert.get("risk_level")}）'])
    record_audit('派单', user=user, resource_type='alerts', resource_id=alert_id,
                 detail=f'派给 {name}（{source}）')
    return {'success': True, 'data': {'assignedTo': int(assignee), 'assignedName': name,
                                      'source': source},
            'message': f'已派单给 {name}' + ('（当前在岗）' if source == 'on_duty' else '')}
