from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from app.core.database import db
from app.core.security import get_current_user
from app.core.tenant import require_same_tenant, tenant_id_of
from app.repositories.base import BaseRepository, keys_to_camel

router = APIRouter(tags=['compat'])


def _own_elder(elder_id: int, user: dict[str, Any]) -> dict[str, Any]:
    """确认该老人属于当前租户，否则 404。"""
    row = db.query_one('SELECT id, tenant_id FROM elders WHERE id=%s', [elder_id])
    return require_same_tenant(row, user)


@router.get('/user')
def current_user(user: dict[str, Any] = Depends(get_current_user)):
    """返回当前登录人，并附带所属机构信息（多租户下的机构名称需在界面可见）。"""
    payload = dict(user)
    tid = user.get('tenantId')
    if tid is not None:
        tenant = db.query_one('SELECT id, code, name FROM tenants WHERE id=%s', [int(tid)])
        if tenant:
            payload['tenant'] = keys_to_camel(tenant)
    return {'success': True, 'data': payload}


@router.get('/schedules/on-duty')
def on_duty(user: dict[str, Any] = Depends(get_current_user)):
    """当前时点真正在岗的人。

    原实现只按 shift_date=CURDATE() 过滤，**完全不看当前时间**：下午三点查"当班"
    会把当天夜班（20:00-08:00）一并返回，于是"当前谁在岗"这个最基础的问题答错了，
    夜间巡查的派单对象也就无从确定。

    跨夜班次（end_time < start_time，如 20:00-08:00）在库里记在班次**开始**那一天，
    所以凌晨 0-8 点要回溯到前一天去匹配。
    """
    rows = db.query('''
        SELECT s.*, u.name AS user_name, u.username, u.role
        FROM schedules s
        LEFT JOIN users u ON s.user_id = u.id AND u.tenant_id = s.tenant_id
        WHERE s.tenant_id = %s AND (
                /* 当日班次：当前时间落在 [start, end) 内 */
                (s.shift_date = CURDATE()
                 AND s.start_time <= s.end_time
                 AND CURTIME() >= s.start_time AND CURTIME() < s.end_time)
              OR (
                /* 当日跨夜班次：当前时间已过开始时间 */
                s.shift_date = CURDATE()
                AND s.start_time > s.end_time
                AND CURTIME() >= s.start_time
              ) OR (
                /* 前一天的跨夜班次：当前时间仍在结束时间之前 */
                s.shift_date = DATE_SUB(CURDATE(), INTERVAL 1 DAY)
                AND s.start_time > s.end_time
                AND CURTIME() < s.end_time
              )
        )
        ORDER BY s.start_time
    ''', [tenant_id_of(user)])
    return {'success': True, 'data': keys_to_camel(rows)}


@router.get('/messages/unread')
def unread_messages(user: dict[str, Any] = Depends(get_current_user)):
    rows = db.query('SELECT COUNT(*) AS count FROM messages '
                    'WHERE tenant_id=%s AND user_id=%s AND is_read=0',
                    [tenant_id_of(user), user.get('id')])
    return {'success': True, 'data': {'count': int(rows[0].get('count') or 0)}}


@router.put('/messages/{message_id}/read')
@router.post('/messages/{message_id}/read')
def mark_message_read(message_id: int, user: dict[str, Any] = Depends(get_current_user)):
    db.execute('UPDATE messages SET is_read=1 WHERE id=%s AND tenant_id=%s AND user_id=%s',
               [message_id, tenant_id_of(user), user.get('id')])
    return {'success': True, 'message': '已读'}


@router.post('/messages/read-all')
def mark_all_read(user: dict[str, Any] = Depends(get_current_user)):
    db.execute('UPDATE messages SET is_read=1 WHERE tenant_id=%s AND user_id=%s',
               [tenant_id_of(user), user.get('id')])
    return {'success': True, 'message': '全部已读'}


@router.get('/patrols/pending-rooms')
def pending_rooms(user: dict[str, Any] = Depends(get_current_user)):
    rows = db.query('SELECT room_no, name AS elder_name FROM elders '
                    'WHERE tenant_id=%s AND status=1 ORDER BY room_no',
                    [tenant_id_of(user)])
    return {'success': True, 'data': keys_to_camel(rows)}


@router.get('/patrols/stats')
def patrol_stats(user: dict[str, Any] = Depends(get_current_user)):
    """巡查统计：既要**逐日明细**，也要页面顶部三个统计卡要的**汇总值**。

    这个接口此前只返回 `[{date, count}]`（逐日条数），而巡查页顶部三个统计卡读的是
    `{todayTotal, completionRate, avgInterval}` —— 字段名完全对不上，三个卡片
    的数字**全是空的**，页面上只显示"今日巡查 / % | 完成率 / 分钟 | 平均间隔"这些
    标签。接口通了（HTTP 200）所以一直没被发现，属于"接口存在但契约不一致"。

    这里把两种形状一起返回：`daily` 保留原数组（向后兼容），同时把汇总值摊平到
    顶层，两种读法都能拿到数据。
    """
    tid = tenant_id_of(user)
    rows = db.query("SELECT DATE(patrol_time) AS date, COUNT(*) AS count FROM patrol_records "
                    "WHERE tenant_id=%s GROUP BY DATE(patrol_time) ORDER BY date DESC LIMIT 30",
                    [tid])

    today_total = db.query_one(
        "SELECT COUNT(*) AS c FROM patrol_records WHERE tenant_id=%s AND DATE(patrol_time)=CURDATE()",
        [tid])
    today = int((today_total or {}).get('c') or 0)

    # 完成率按**巡查任务**算（有任务才有"完成"可言）：已完成 / 今日全部任务。
    # 用记录数当分母是错的 —— 记录只反映"已经巡过的"，没有任务就无从判断漏没漏。
    task_row = db.query_one(
        'SELECT COUNT(*) AS total, SUM(status=1) AS done FROM patrol_tasks '
        'WHERE tenant_id=%s AND task_date=CURDATE()', [tid])
    task_total = int((task_row or {}).get('total') or 0)
    task_done = int((task_row or {}).get('done') or 0)

    # 分母只取**窗口已过**的任务。夜班任务是 22:00/00:30/02:00/04:00 四轮批量生成的，
    # 傍晚打开页面时后三轮压根还没到点 —— 把它们算进分母，会得到一个恒低于实际的
    # 完成率（实测 2/617 = 0.3%），看起来像"巡查全部没做"，而事实是"还没轮到"。
    # 「已完成的 / 应该已完成的」才是这个数字想表达的意思。
    due_row = db.query_one(
        'SELECT COUNT(*) AS total, SUM(status=1) AS done FROM patrol_tasks '
        'WHERE tenant_id=%s AND task_date=CURDATE() AND window_end <= NOW()', [tid])
    due_total = int((due_row or {}).get('total') or 0)
    due_done = int((due_row or {}).get('done') or 0)
    completion = round(due_done / due_total * 100, 1) if due_total else 0.0

    # 间隔：近 24 小时相邻两次巡查记录之间的分钟数。
    # 同一分钟内为不同房间登记的记录不算"间隔"（差值为 0，已排除）。
    recent = db.query(
        'SELECT patrol_time FROM patrol_records WHERE tenant_id=%s '
        'AND patrol_time >= DATE_SUB(NOW(), INTERVAL 1 DAY) ORDER BY patrol_time DESC LIMIT 50',
        [tid])
    avg_interval = 0.0
    max_interval = 0.0
    if len(recent) >= 2:
        gaps = []
        for a, b in zip(recent, recent[1:]):
            delta = (a['patrol_time'] - b['patrol_time']).total_seconds() / 60.0
            if delta > 0:
                gaps.append(delta)
        if gaps:
            avg_interval = round(sum(gaps) / len(gaps), 1)
            # 最大间隔才是真正有行动价值的那个数：它直接回答
            # 「最久有多长时间没有任何人去看一眼」。平均值会被夜间轮次拉低，
            # 掩盖掉白天那段长长的空档。
            max_interval = round(max(gaps), 1)

    daily = keys_to_camel(rows)
    return {'success': True, 'data': {
        # 汇总值（页面顶部统计卡直接读这三个）
        'todayTotal': today,
        'completionRate': completion,
        'avgInterval': avg_interval,
        'maxInterval': max_interval,
        'taskTotal': task_total,
        'taskDone': task_done,
        'dueTotal': due_total,
        'dueDone': due_done,
        # 逐日明细：既摊平在顶层，也保留原有的数组形状
        'daily': daily,
        # 向后兼容：旧调用方把 data 当数组用（例如直接遍历取 date/count）
        'items': daily,
    }}


@router.get('/medications/elder/{elder_id}')
def elder_medications(elder_id: int, user: dict[str, Any] = Depends(get_current_user)):
    _own_elder(elder_id, user)
    rows = db.query('SELECT * FROM medications WHERE tenant_id=%s AND elder_id=%s ORDER BY id DESC LIMIT 100',
                    [tenant_id_of(user), elder_id])
    return {'success': True, 'data': keys_to_camel(rows)}


@router.get('/medications/records')
def medication_records(page: int = 1, pageSize: int = 20,
                       keyword: str | None = None, startDate: str | None = None,
                       endDate: str | None = None, status: str | None = None,
                       elderId: int | None = None,
                       user: dict[str, Any] = Depends(get_current_user)):
    """服药记录，分页契约与其它列表一致（{data,total,page,pageSize}）。

    这个接口不走 crud_router，所以它**不在**通用筛选那一套里 ——
    前端传 keyword/日期 上来会被 FastAPI 静默丢弃（未知 query 参数不报错），
    表现为"筛选栏能用、点了一点反应没有"。这里补齐与其它列表一致的筛选，
    让护理员能查"某位老人某段时间的服药记录"。
    """
    tid = tenant_id_of(user)
    page = max(1, int(page or 1))
    page_size = min(200, max(1, int(pageSize or 20)))

    # 所有列都带 r. 前缀：下面 JOIN 了 elders，而它也有 tenant_id / elder_id 等列，
    # 不加前缀会直接报 "Column 'tenant_id' in where clause is ambiguous"。
    where = ['r.tenant_id=%s']
    params: list[Any] = [tid]

    kw = (keyword or '').strip()
    if kw:
        # 服药记录本身没几个可读字段，按备注搜之外，也允许按老人姓名搜 ——
        # 护理员想的是"查李桂芳的服药记录"，不是"查某条备注"。
        where.append('(r.notes LIKE %s OR e.name LIKE %s)')
        params.extend([f'%{kw}%'] * 2)
    if elderId not in (None, ''):
        where.append('r.elder_id=%s')
        params.append(int(elderId))
    if startDate:
        where.append('r.scheduled_time >= %s')
        params.append(f'{startDate} 00:00:00')
    if endDate:
        where.append('r.scheduled_time <= %s')
        params.append(f'{endDate} 23:59:59')
    if status not in (None, ''):
        where.append('r.status=%s')
        params.append(int(status))

    clause = ' AND '.join(where)
    joins = ('FROM medication_records r LEFT JOIN elders e '
             'ON e.id = r.elder_id AND e.tenant_id = r.tenant_id')
    rows = db.query(f'SELECT r.* {joins} WHERE {clause} '
                    'ORDER BY r.scheduled_time DESC LIMIT %s OFFSET %s',
                    params + [page_size, (page - 1) * page_size])
    total = db.query(f'SELECT COUNT(*) AS cnt {joins} WHERE {clause}', params)
    return {'success': True, 'data': {
        'data': keys_to_camel(rows),
        'total': int(total[0].get('cnt') or 0),
        'page': page,
        'pageSize': page_size,
    }}


@router.get('/medications/records/pending')
def pending_medication_records(user: dict[str, Any] = Depends(get_current_user)):
    rows = db.query('SELECT * FROM medication_records WHERE tenant_id=%s AND status=0 '
                    'ORDER BY scheduled_time LIMIT 100', [tenant_id_of(user)])
    # 待办类列表是一次性全量（护理员当班要看全），保持数组形状，
    # 且不在 LIST_CONTRACT 的范围内 —— 它的消费方直接遍历数组。
    return {'success': True, 'data': keys_to_camel(rows)}


def _own_medication_record(record_id: int, user: dict[str, Any]) -> None:
    row = db.query_one('SELECT id, tenant_id FROM medication_records WHERE id=%s', [record_id])
    require_same_tenant(row, user)


@router.post('/medications/records/{record_id}/confirm')
def confirm_medication(record_id: int, body: dict[str, Any] | None = None, user: dict[str, Any] = Depends(get_current_user)):
    _own_medication_record(record_id, user)
    db.execute('UPDATE medication_records SET status=1, actual_time=NOW(), nurse_id=%s, notes=%s '
               'WHERE id=%s AND tenant_id=%s',
               [user.get('id'), (body or {}).get('notes', ''), record_id, tenant_id_of(user)])
    return {'success': True, 'message': '已确认服药'}


@router.post('/medications/records/{record_id}/skip')
def skip_medication(record_id: int, body: dict[str, Any] | None = None, user: dict[str, Any] = Depends(get_current_user)):
    _own_medication_record(record_id, user)
    db.execute('UPDATE medication_records SET status=2, nurse_id=%s, notes=%s '
               'WHERE id=%s AND tenant_id=%s',
               [user.get('id'), (body or {}).get('notes', ''), record_id, tenant_id_of(user)])
    return {'success': True, 'message': '已跳过'}


@router.get('/vital-signs/trend')
def vital_trend(elderId: int | None = None, vitalType: str | None = None, user: dict[str, Any] = Depends(get_current_user)):
    where = ['tenant_id=%s']
    params: list[Any] = [tenant_id_of(user)]
    if elderId:
        _own_elder(elderId, user)
        where.append('elder_id=%s')
        params.append(elderId)
    sql = 'SELECT * FROM vital_signs WHERE ' + ' AND '.join(where)
    sql += ' ORDER BY record_time DESC LIMIT 100'
    return {'success': True, 'data': keys_to_camel(db.query(sql, params))}


@router.get('/vital-signs/alerts')
def vital_alerts(user: dict[str, Any] = Depends(get_current_user)):
    """按**每位老人自己配置的**体征阈值判定告警。

    原实现把阈值硬编码在 SQL 里（收缩压 <90 或 >160 等），而 vital_alert_rules
    表里按老人配置的规则**完全没有被读取** —— 也就是说「生命体征规则」页面上改的
    阈值只存进了库，对判定毫无影响；同时 blood_glucose 与 spo2 两类规则存在却从未
    被检查。实测库里血糖 9.5（规则上限 8.0）、收缩压 160，页面却显示 0 条告警。

    现在改为：取该老人 status=1 的规则逐条判定，并回报**违反了哪条规则**，
    前端因此可以解释"为什么报警"。没有配置规则的老人回退到通用默认值。
    """
    # vital_alert_rules.vital_type 与 vital_signs 的列名一一对应
    VITAL_COLUMNS = ('systolic_pressure', 'diastolic_pressure', 'heart_rate',
                     'temperature', 'blood_glucose', 'spo2')
    DEFAULTS = {                      # 未配置规则时的通用兜底
        'systolic_pressure': (90.0, 140.0),
        'diastolic_pressure': (60.0, 90.0),
        'heart_rate': (50.0, 100.0),
        'temperature': (36.0, 37.5),
        'blood_glucose': (4.0, 8.0),
        'spo2': (92.0, 100.0),
    }

    tid = tenant_id_of(user)
    rules: dict[int, dict[str, tuple[float | None, float | None]]] = {}
    for r in db.query('SELECT elder_id, vital_type, min_value, max_value '
                      'FROM vital_alert_rules WHERE tenant_id=%s AND status=1', [tid]):
        rules.setdefault(r['elder_id'], {})[r['vital_type']] = (
            float(r['min_value']) if r['min_value'] is not None else None,
            float(r['max_value']) if r['max_value'] is not None else None,
        )

    rows = db.query('''
        SELECT v.*, e.name AS elder_name, e.room_no
        FROM vital_signs v
        JOIN elders e ON v.elder_id = e.id AND e.tenant_id = v.tenant_id
        WHERE v.tenant_id = %s
        ORDER BY v.record_time DESC LIMIT 500
    ''', [tid])

    alerts = []
    for row in rows:
        elder_rules = rules.get(row['elder_id'], {})
        breached = []
        for column in VITAL_COLUMNS:
            value = row.get(column)
            if value is None:
                continue
            lo, hi = elder_rules.get(column) or DEFAULTS[column]
            value = float(value)
            if lo is not None and value < lo:
                breached.append({'vitalType': column, 'value': value,
                                 'min': lo, 'max': hi, 'direction': 'low'})
            elif hi is not None and value > hi:
                breached.append({'vitalType': column, 'value': value,
                                 'min': lo, 'max': hi, 'direction': 'high'})
        if not breached:
            continue
        # 风险等级由**越界幅度相对该老人自己的允许区间**决定，而不是一刀切
        worst = 0.0
        for b in breached:
            span = (b['max'] - b['min']) if (b['min'] is not None and b['max'] is not None) else 0.0
            span = span or 1.0
            ratio = abs(b['value'] - b['min']) / span if b['direction'] == 'low' \
                else abs(b['value'] - b['max']) / span
            worst = max(worst, ratio)
        item = keys_to_camel(row)
        item['breachedRules'] = breached
        item['riskLevel'] = 'HIGH' if worst > 0.25 else ('MEDIUM' if worst > 0.1 else 'LOW')
        alerts.append(item)

    order = {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}
    alerts.sort(key=lambda a: (order[a['riskLevel']], str(a.get('recordTime') or '')))
    return {'success': True, 'data': alerts[:100]}


@router.get('/vital-signs/rules/{elder_id}')
def vital_rules(elder_id: int, user: dict[str, Any] = Depends(get_current_user)):
    _own_elder(elder_id, user)
    rows = db.query('SELECT * FROM vital_alert_rules WHERE tenant_id=%s AND elder_id=%s '
                    'ORDER BY vital_type', [tenant_id_of(user), elder_id])
    return {'success': True, 'data': keys_to_camel(rows)}


@router.put('/vital-signs/rules/{elder_id}')
def update_vital_rules(elder_id: int, body: dict[str, Any], user: dict[str, Any] = Depends(get_current_user)):
    _own_elder(elder_id, user)
    tid = tenant_id_of(user)
    rules = body.get('rules') if isinstance(body.get('rules'), list) else []
    with db.transaction() as conn:
        with conn.cursor() as cur:
            cur.execute('DELETE FROM vital_alert_rules WHERE elder_id=%s AND tenant_id=%s',
                        [elder_id, tid])
            for rule in rules:
                vital_type = rule.get('vitalType') or rule.get('vital_type')
                if vital_type:
                    cur.execute(
                        'INSERT INTO vital_alert_rules (tenant_id, elder_id, vital_type, min_value, max_value, status) '
                        'VALUES (%s,%s,%s,%s,%s,%s)',
                        [tid, elder_id, vital_type, rule.get('minValue'), rule.get('maxValue'), rule.get('status', 1)],
                    )
    return {'success': True, 'data': rules, 'message': '规则已保存'}
