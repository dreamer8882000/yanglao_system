import asyncio
import json
import queue
import json
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from app.core.database import db
from app.core.security import get_current_user, require_admin
from app.core.tenant import require_same_tenant, tenant_id_of, tenant_scope
from app.repositories.base import BaseRepository
from app.services.audit import record_audit
from app.services.notifications import hub, notify_alert, notify_confirmed

router = APIRouter(prefix='/alerts', tags=['alerts'])


def _expand_identity(rows):
    """把 identity_candidates 从 JSON 字符串展开成对象。

    PyMySQL 不会自动解析 JSON 列，返回的是**字符串**。如果原样发给前端，
    前端就得写 `JSON.parse(a.identityCandidates || '[]')` —— 而这类"顺手 parse"
    正是历史 bug 的来源（sessionStorage 里那条坏数据就是这么来的）。
    序列化形状在接口层收口，前端只拿到它可以直接用的东西。
    """
    if isinstance(rows, dict):
        rows = [rows]
        single = True
    else:
        single = False
    out = []
    for r in rows or []:
        if isinstance(r, dict):
            cand = r.get('identityCandidates')
            if isinstance(cand, str) and cand:
                try:
                    r = dict(r)
                    r['identityCandidates'] = json.loads(cand)
                except (json.JSONDecodeError, TypeError):
                    r = dict(r)
                    r['identityCandidates'] = None
            elif cand == '':
                r = dict(r)
                r['identityCandidates'] = None
        out.append(r)
    return (out[0] if out else None) if single else out
repo = BaseRepository('alerts')


def _clean(value: Any) -> str | None:
    """Normalise an optional query value: '' / whitespace / None -> None.

    The frontend sends its filter form verbatim, so an unset filter arrives as
    an empty string. Declaring ``status: int | None`` made FastAPI reject '' with
    422, breaking the whole alert list whenever a filter was left blank.
    """
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _alert_filters(status: Any = None, risk_level: Any = None,
                   start_date: Any = None, end_date: Any = None,
                   tenant_id: int | None = None,
                   keyword: Any = None,
                   identity: Any = None) -> tuple[str, list[Any]]:
    where: list[str] = []
    params: list[Any] = []
    # 租户条件放在最前且不可省略：这是在**唯一的过滤入口**上加的，
    # 列表与导出因此同时受控；若分散到各调用点，漏一处就是跨租户泄露。
    if tenant_id is not None:
        where.append('a.tenant_id=%s')
        params.append(int(tenant_id))
    status_val = _clean(status)
    if status_val is not None:
        try:
            status_int: int | None = int(status_val)
        except (TypeError, ValueError):
            status_int = None
        if status_int is not None:
            where.append('a.status=%s')
            params.append(status_int)
    risk_val = _clean(risk_level)
    if risk_val:
        where.append('a.risk_level=%s')
        params.append(risk_val.upper())
    start_val = _clean(start_date)
    if start_val:
        where.append('a.alert_time >= %s')
        params.append(f'{start_val} 00:00:00')
    end_val = _clean(end_date)
    if end_val:
        where.append('a.alert_time <= %s')
        params.append(f'{end_val} 23:59:59')

    # 关键词：告警列表上最常用的检索是"哪个老人 / 哪个房间 / 哪路摄像头"。
    # 这三样分散在三张表里，所以必须联表搜索；不联表的话护理员只能靠翻页找人。
    kw = _clean(keyword)
    if kw:
        # 房间号取自 cameras 联表：alerts 表本身**没有** room_no 列，
        # 而 camera_id 是允许为空的（浏览器手动检测没有摄像头），
        # 所以两类都要能搜到 —— 漏掉哪一边都会让"搜房间号搜不到"。
        where.append('(e.name LIKE %s OR c.room_no LIKE %s OR c.name LIKE %s '
                     'OR a.expression_top LIKE %s OR a.posture_type LIKE %s)')
        params.extend([f'%{kw}%'] * 5)

    # 身份状态：护理员最需要的一个筛选项就是"哪些告警还不知道是谁"——
    # 那是必须人工处理的一批，混在几十条里只能靠翻页找。
    ident = _clean(identity)
    if ident:
        where.append('a.identity_method=%s')
        params.append(ident)

    return (' WHERE ' + ' AND '.join(where) if where else ''), params


def _csv_escape(value: Any) -> str:
    # Excel/Sheets 会把以 = + - @ 开头的单元格当公式执行；老人姓名/备注
    # 是外部可控文本，必须加前导单引号把它降级成普通字符串。
    text = str(value or '')
    if isinstance(value, str) and text[:1] in ('=', '+', '-', '@'):
        text = "'" + text
    return '"' + text.replace('"', '""') + '"'


def _ensure_pending(existing: dict[str, Any]) -> None:
    """告警状态机：只允许从「待处置(0)」进入处置/误报，防止终态被反复改写。"""
    if int(existing.get('status', 0) or 0) != 0:
        raise HTTPException(status_code=409, detail='该告警已处置或已标记误报，不能重复变更状态')


@router.get('/dashboard')
def dashboard(user: dict[str, Any] = Depends(get_current_user)):
    # 误报（status=2）不计入风险统计，否则真实风险会被历史误报稀释
    tid = tenant_id_of(user)
    counts = repo.query(
        '''SELECT
               COUNT(*) AS total,
               SUM(DATE(alert_time)=CURDATE()) AS today_total,
               SUM(DATE(alert_time)=CURDATE() AND risk_level IN ('HIGH', 'URGENT') AND status<>2) AS today_high,
               SUM(status=0) AS pending,
               SUM(risk_level IN ('HIGH', 'URGENT') AND status<>2) AS high_risk,
               SUM(status=2) AS false_alarms
           FROM alerts WHERE tenant_id=%s''',
        [tid], camel=False,
    )
    elders = repo.query('SELECT COUNT(*) AS elder_count FROM elders WHERE status=1 AND tenant_id=%s', [tid], camel=False)
    row = counts[0] if counts else {}
    elder_row = elders[0] if elders else {}
    recent = _expand_identity(repo.query(
        'SELECT * FROM alerts WHERE tenant_id=%s ORDER BY alert_time DESC LIMIT 10', [tid]))
    data = {
        'total': int(row.get('total') or 0),
        'todayTotal': int(row.get('today_total') or 0),
        'todayHigh': int(row.get('today_high') or 0),
        'pending': int(row.get('pending') or 0),
        'highRisk': int(row.get('high_risk') or 0),
        'falseAlarms': int(row.get('false_alarms') or 0),
        'elderCount': int(elder_row.get('elder_count') or 0),
        'recent': recent,
    }
    return {'success': True, 'data': data}


@router.get('/stream')
async def stream(request: Request, user: dict[str, Any] = Depends(get_current_user)):
    """Push real alert events to connected clients.

    The frontend (``composables/useSSE.js``) listens for ``alert`` and
    ``confirmed`` events; previously this endpoint only emitted heartbeats, so
    no push ever arrived. Real events are now published by the alert write path
    and by the escalation scheduler.
    """
    # 订阅必须绑定租户：hub 只把该租户的告警推给这个连接。
    # 原实现是全局广播 —— 租户 1 的护士能在页面上实时看到租户 2 的告警。
    subscription = hub.subscribe(tenant_id_of(user))

    async def events():
        try:
            yield 'event: connected\ndata: {}\n\n'
            idle = 0
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event, data = subscription.get_nowait()
                    idle = 0
                    yield f'event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n'
                except queue.Empty:
                    idle += 1
                    if idle >= 20:      # ~20s heartbeat
                        idle = 0
                        yield 'event: ping\ndata: {}\n\n'
                    await asyncio.sleep(1)
        finally:
            hub.unsubscribe(subscription)

    return StreamingResponse(events(), media_type='text/event-stream')


@router.get('/recent')
def recent(limit: int = 10, user: dict[str, Any] = Depends(get_current_user)):
    limit = min(50, max(1, limit))
    return {'success': True, 'data': _expand_identity(repo.query(
        'SELECT * FROM alerts WHERE tenant_id=%s ORDER BY alert_time DESC LIMIT %s',
        [tenant_id_of(user), limit]))}


@router.get('/statistics')
def statistics(range: str = '7d', user: dict[str, Any] = Depends(get_current_user)):
    """告警统计聚合。

    此前只返回 {range, items}（按等级×状态的计数），而「数据统计」页要的是
    trend / levelDist / hourlyHeat / roomRank 四个聚合 —— **字段对不上**，
    于是页面上四个图全部是空的（实测趋势图只画出坐标轴、区域频次几乎无像素）。
    这里把缺失的聚合补齐，让图表有真实数据可用。

    hourlyHeat 的取值维度是「星期 × 小时」：跌倒高发时段是这个系统最值得看的
    分布之一，直接决定了夜班巡查该怎么排。
    """
    _RANGE_MAP = {'1d': 1, '7d': 7, '30d': 30, '90d': 90}
    days = _RANGE_MAP.get(range, 7)
    since = f'DATE_SUB(NOW(), INTERVAL {days} DAY)'
    tid = tenant_id_of(user)

    # 1) 等级 × 状态 计数（原有口径，保留兼容）
    items = repo.query(
        'SELECT risk_level, status, COUNT(*) AS count FROM alerts '
        f'WHERE tenant_id=%s AND alert_time >= {since} GROUP BY risk_level, status', [tid])

    # 2) 逐日趋势（按等级）
    trend = repo.query(
        'SELECT DATE(alert_time) AS dt, UPPER(risk_level) AS risk_level, COUNT(*) AS cnt '
        f'FROM alerts WHERE tenant_id=%s AND alert_time >= {since} '
        'GROUP BY DATE(alert_time), risk_level ORDER BY dt', [tid])

    # 3) 星期 × 小时 热力：WEEKDAY() 是 0=周一，与前端展示的周一起始一致
    hourly = repo.query(
        'SELECT WEEKDAY(alert_time) AS dw, HOUR(alert_time) AS hr, COUNT(*) AS cnt '
        f'FROM alerts WHERE tenant_id=%s AND alert_time >= {since} '
        'GROUP BY WEEKDAY(alert_time), HOUR(alert_time)', [tid])

    # 4) 房间频次：经由 rooms 主数据把告警落到具体房间
    room_rank = repo.query(
        'SELECT e.room_no AS room_no, COUNT(*) AS cnt '
        'FROM alerts a JOIN elders e ON e.id = a.elder_id AND e.tenant_id = a.tenant_id '
        f'WHERE a.tenant_id=%s AND a.alert_time >= {since} '
        'GROUP BY e.room_no ORDER BY cnt DESC LIMIT 12', [tid])

    return {'success': True, 'data': {
        'range': range,
        'items': items,          # 兼容旧调用方
        'levelDist': items,
        'trend': trend,
        'hourlyHeat': hourly,
        'roomRank': room_rank,
    }}


@router.get('/export')
def export_alerts(status: str | None = None, riskLevel: str | None = None,
                  startDate: str | None = None, endDate: str | None = None,
                  user: dict[str, Any] = Depends(get_current_user)):
    where_sql, params = _alert_filters(status, riskLevel, startDate, endDate,
                                       tenant_id=tenant_id_of(user))
    rows = repo.query(
        f'''SELECT a.id, a.alert_time, a.risk_level, a.confidence, a.status,
                   e.name AS elder_name, e.room_no, c.name AS camera_name, a.handler_notes
            FROM alerts a
            LEFT JOIN elders e ON a.elder_id=e.id AND e.tenant_id=a.tenant_id
            LEFT JOIN cameras c ON a.camera_id=c.id AND c.tenant_id=a.tenant_id
            {where_sql}
            ORDER BY a.alert_time DESC LIMIT 1000''',
        params,
    )
    header = 'ID,告警时间,风险等级,置信度,状态,老人,房间,摄像头,处置备注\n'
    lines = [header]
    for row in rows:
        values = [
            row.get('id'), row.get('alertTime'), row.get('riskLevel'), row.get('confidence'), row.get('status'),
            row.get('elderName'), row.get('roomNo'), row.get('cameraName'), row.get('handlerNotes'),
        ]
        lines.append(','.join(_csv_escape(v) for v in values) + '\n')
    content = '\ufeff' + ''.join(lines)
    return Response(content=content, media_type='text/csv; charset=utf-8', headers={'Content-Disposition': 'attachment; filename="alerts.csv"'})


@router.get('/')
def list_alerts(page: int = 1, pageSize: int = 20, status: str | None = None,
                riskLevel: str | None = None, startDate: str | None = None,
                endDate: str | None = None, keyword: str | None = None,
                identity: str | None = None,
                user: dict[str, Any] = Depends(get_current_user)):
    where_sql, params = _alert_filters(status, riskLevel, startDate, endDate,
                                       tenant_id=tenant_id_of(user),
                                       keyword=keyword, identity=identity)
    page = max(1, page)
    page_size = min(100, max(1, pageSize))
    sql = f'''SELECT a.*, e.name AS elder_name, e.room_no, c.name AS camera_name
              FROM alerts a
              LEFT JOIN elders e ON a.elder_id=e.id AND e.tenant_id=a.tenant_id
              LEFT JOIN cameras c ON a.camera_id=c.id AND c.tenant_id=a.tenant_id
              {where_sql}
              ORDER BY a.alert_time DESC LIMIT %s OFFSET %s'''
    data = _expand_identity(repo.query(sql, params + [page_size, (page - 1) * page_size]))
    # count 必须和列表用**同一套 JOIN**：关键词要搜老人姓名/摄像头名，
    # 只在列表的 SQL 里联表而 count 不联，会让 total 与条数对不上
    # （分页条算出错误的页数，最后一页点进去是空的）。
    total = repo.query(
        f'SELECT COUNT(*) AS cnt FROM alerts a '
        f'LEFT JOIN elders e ON a.elder_id=e.id AND e.tenant_id=a.tenant_id '
        f'LEFT JOIN cameras c ON a.camera_id=c.id AND c.tenant_id=a.tenant_id{where_sql}', params)[0].get('cnt', 0)
    return {'success': True, 'data': {'data': data, 'total': total, 'page': page, 'pageSize': page_size}}


@router.get('/{alert_id}/timeline')
def timeline(alert_id: int, user: dict[str, Any] = Depends(get_current_user)):
    alert = require_same_tenant(repo.find_by_id(alert_id), user)
    return {'success': True,
            'data': [{'time': alert.get('alertTime'), 'action': '告警产生',
                      'detail': _expand_identity(alert)}]}


@router.post('/{alert_id}/false-alarm')
def mark_false_alarm(alert_id: int, body: dict[str, Any] | None = None, request: Request = None,
                     user: dict[str, Any] = Depends(get_current_user)):
    """Nurse feedback: this alert was a false alarm (status=2).

    Closes the loop the product was missing — without it there is no way to know
    the real false-alarm rate, and no data to tune the detector against.
    """
    notes = (body or {}).get('notes', '')
    existing = require_same_tenant(repo.find_by_id(alert_id), user)
    if not existing:
        raise HTTPException(status_code=404, detail='告警不存在')
    _ensure_pending(existing)
    affected = db.execute(
        "UPDATE alerts SET status=2, handler_id=%s, handler_notes=LEFT(CONCAT(COALESCE(handler_notes,''), %s), 200), "
        'handled_at=NOW() WHERE id=%s AND tenant_id=%s AND status=0',
        [user.get('id'), f'[误报标注] {notes}'.strip(), alert_id, tenant_id_of(user)],
    )
    if not affected:
        raise HTTPException(status_code=409, detail='该告警已被其他用户处置，请刷新后重试')
    alert = _expand_identity(repo.find_by_id(alert_id))
    record_audit('标记误报', user=user, resource_type='alert', resource_id=alert_id,
                 detail={'notes': notes, 'riskLevel': (alert or {}).get('riskLevel'),
                         'postureType': (alert or {}).get('postureType')},
                 request=request)
    return {'success': True, 'data': alert, 'message': '已标记为误报'}


@router.get('/feedback-stats')
def feedback_stats(days: int = 30, user: dict[str, Any] = Depends(require_admin)):
    """Real-world effectiveness metrics derived from nurse feedback.

    This is the closed half of the loop: the offline evaluation measures the
    model, this measures how the model behaves on this site's own traffic.
    """
    days = max(1, min(int(days or 30), 365))
    # 真实运行指标必须是"本机构自己的"数据 —— 混入其它机构会直接污染结论
    tid = tenant_id_of(user)
    window = 'tenant_id=%s AND alert_time >= DATE_SUB(NOW(), INTERVAL %s DAY)'

    totals = db.query(f'SELECT status, COUNT(*) AS c FROM alerts WHERE {window} GROUP BY status', [tid, days])
    by_status = {int(r['status']): int(r['c']) for r in totals}
    handled = by_status.get(1, 0)
    false_alarms = by_status.get(2, 0)
    reviewed = handled + false_alarms
    pending = by_status.get(0, 0)

    # ── 归因：每一维都算**误报率**，而不只是误报条数 ──────────────────────
    # 知道"12 条误报是 fall_like"没有任何行动价值；要知道
    # "fall_like 类告警里 60% 被护士判为误报"才能决定该收紧什么。
    # 分母只取**已复核**（已处理 + 误报）的告警 —— 待处理的还没结论，
    # 计入分母会把误报率稀释成无意义的数字。
    def _rate_rows(sql: str, key: str) -> list[dict[str, Any]]:
        rows = db.query(sql, [tid, days])
        out = []
        for r in rows:
            total = int(r['total'] or 0)
            fp = int(r['fp'] or 0)
            out.append({
                key: r[key] if r[key] not in (None, '') else '未知',
                'total': total, 'handled': total - fp, 'falseAlarms': fp,
                'falseAlarmRate': round(fp / total, 4) if total else 0.0,
            })
        out.sort(key=lambda x: (-x['falseAlarmRate'], -x['total']))
        return out

    reviewed_clause = f'{window} AND status IN (1, 2)'

    by_posture = _rate_rows(
        "SELECT COALESCE(posture_type, 'unknown') AS posture, "
        '       COUNT(*) AS total, SUM(status=2) AS fp '
        f'FROM alerts WHERE {reviewed_clause} '
        'GROUP BY posture', 'posture')

    by_evidence = _rate_rows(
        "SELECT COALESCE(evidence_mode, 'unknown') AS mode, "
        '       COUNT(*) AS total, SUM(status=2) AS fp '
        f'FROM alerts WHERE {reviewed_clause} '
        'GROUP BY mode', 'mode')

    # 表情维度是新增的：有了 expression_top 才能回答"哪类表情最容易误报"
    by_expression = _rate_rows(
        "SELECT COALESCE(expression_top, '未识别') AS expression, "
        '       COUNT(*) AS total, SUM(status=2) AS fp '
        f'FROM alerts WHERE {reviewed_clause} '
        'GROUP BY expression', 'expression')

    # 别名要与返回体的其余键保持同一种风格：_rate_rows 直接用 SQL 别名做输出键，
    # 而这里其它维度都没有下划线，因此别名写 cameraName 而不是 camera_name，
    # 否则前端拿 r.cameraName 永远是 undefined。
    by_camera = _rate_rows(
        "SELECT COALESCE(c.name, '未绑定') AS cameraName, "
        '       COUNT(*) AS total, SUM(a.status=2) AS fp '
        'FROM alerts a LEFT JOIN cameras c ON a.camera_id = c.id AND c.tenant_id = a.tenant_id '
        f'WHERE a.tenant_id=%s AND a.alert_time >= DATE_SUB(NOW(), INTERVAL %s DAY) '
        'AND a.status IN (1,2) GROUP BY cameraName', 'cameraName')

    # 时段：只按误报条数看没意义，要看"该时段告警的误报率"
    by_hour = db.query(
        'SELECT HOUR(alert_time) AS hour, COUNT(*) AS total, SUM(status=2) AS fp '
        f'FROM alerts WHERE {reviewed_clause} '
        'GROUP BY HOUR(alert_time) ORDER BY hour', [tid, days])

    # ── 机器与人的一致率 ────────────────────────────────────────────────
    # 这是最有业务含义的一个指标：在护士复核过的告警里，AI 给的风险等级
    # 与人的最终判断是否一致。不一致集中在哪个等级，就说明那个等级的阈值需要调。
    by_level = _rate_rows(
        'SELECT UPPER(risk_level) AS level, COUNT(*) AS total, SUM(status=2) AS fp '
        f'FROM alerts WHERE {reviewed_clause} '
        'GROUP BY level', 'level')

    return {'success': True, 'data': {
        'days': days,
        'reviewed': reviewed,
        'handled': handled,
        'falseAlarms': false_alarms,
        'pending': pending,
        'falseAlarmRate': round(false_alarms / reviewed, 4) if reviewed else 0.0,
        # 复核覆盖率：多少告警已经有了人的结论。太低时上面所有比率都不可信。
        'reviewCoverage': round(reviewed / (reviewed + pending), 4) if (reviewed + pending) else 0.0,
        'byPosture': by_posture,
        'byEvidenceMode': by_evidence,
        'byExpression': by_expression,
        'byLevel': by_level,
        'byCamera': by_camera,
        'byHour': [{'hour': int(r['hour']), 'total': int(r['total'] or 0),
                    'falseAlarms': int(r['fp'] or 0),
                    'falseAlarmRate': round(int(r['fp'] or 0) / int(r['total'] or 1), 4)}
                   for r in by_hour],
    }}


@router.post('/{alert_id}/confirm')
def confirm(alert_id: int, body: dict[str, Any] | None = None, request: Request = None,
            user: dict[str, Any] = Depends(get_current_user)):
    notes = (body or {}).get('notes', '')
    existing = require_same_tenant(repo.find_by_id(alert_id), user)
    _ensure_pending(existing)
    # UPDATE 自带 tenant + status 条件：仅靠上面那次读取会有 TOCTOU 窗口
    affected = db.execute('UPDATE alerts SET status=1, handler_id=%s, handler_notes=%s, handled_at=NOW() '
                          'WHERE id=%s AND tenant_id=%s AND status=0',
                          [user.get('id'), notes, alert_id, tenant_id_of(user)])
    if not affected:
        raise HTTPException(status_code=409, detail='该告警已被其他用户处置，请刷新后重试')
    alert = _expand_identity(repo.find_by_id(alert_id))
    record_audit('告警处置', user=user, resource_type='alert', resource_id=alert_id,
                 detail={'notes': notes, 'riskLevel': (alert or {}).get('riskLevel')}, request=request)
    if alert:
        notify_confirmed(alert)
    return {'success': True, 'data': alert, 'message': '处置成功'}


@router.post('/{alert_id}/identity')
def confirm_identity(alert_id: int, body: dict[str, Any], request: Request = None,
                     user: dict[str, Any] = Depends(get_current_user)):
    """护士确认这条告警属于哪位老人。

    为什么需要这个接口：多人同房时系统**不给答案**（`identity_method='ambiguous'`），
    但仅说"不确定"是不够的 —— 护理员是现场唯一能判断的人。她在告警详情里从
    床位列选一位，这个判断要落回库里：
      * 告警从此有了正确的 elder_id，历史统计与老人健康趋势才是对的；
      * 记录 `identity_method='manual'` 和确认人，让"这个身份是人给的"可追溯 ——
        否则它和"系统自己推出来的"在数据里长得一样。
    """
    alert = require_same_tenant(repo.find_by_id(alert_id), user)
    raw = body.get('elderId') if body.get('elderId') is not None else body.get('elder_id')
    if raw in (None, ''):
        raise HTTPException(status_code=400, detail='elderId 不能为空')
    try:
        elder_id = int(raw)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail='elderId 必须为整数')

    tid = tenant_id_of(user)
    elder = db.query_one('SELECT id, name, room_no, bed_no FROM elders '
                         'WHERE id=%s AND tenant_id=%s', [elder_id, tid])
    if not elder:
        raise HTTPException(status_code=404, detail='老人档案不存在')

    # 首选人必须真的住在该摄像头对应的房间里 —— 否则就是"把 A 房的告警挂到 B 房
    # 的老人身上"，那是另一种错误归属。摄像头缺失（浏览器手动检测）时跳过这项校验。
    if alert.get('cameraId') or alert.get('camera_id'):
        cam = db.query_one('SELECT room_no FROM cameras WHERE id=%s AND tenant_id=%s',
                           [alert.get('cameraId') or alert.get('camera_id'), tid])
        if cam and cam.get('room_no') and elder.get('room_no') != cam['room_no']:
            raise HTTPException(
                status_code=400,
                detail=f"该告警来自 {cam['room_no']} 室，而 {elder['name']} 住在 "
                       f"{elder['room_no']} 室，不能指定为这条告警的当事人")

    db.execute('UPDATE alerts SET elder_id=%s, identity_method=%s, identity_confidence=%s '
               'WHERE id=%s AND tenant_id=%s',
               [elder_id, 'manual', 1.0, alert_id, tid])
    record_audit('确认告警当事人', user=user, resource_type='alert', resource_id=alert_id,
                 detail={'elderId': elder_id, 'elderName': elder.get('name'),
                         'roomNo': elder.get('room_no'), 'bedNo': elder.get('bed_no')},
                 request=request)
    return {'success': True,
            'data': {'elderId': elder_id, 'elderName': elder.get('name'),
                     'method': 'manual', 'confidence': 1.0},
            'message': f"已确认为 {elder.get('name')}"}


@router.post('/batch-confirm')
def batch_confirm(body: dict[str, Any], request: Request = None,
                  user: dict[str, Any] = Depends(get_current_user)):
    ids = [int(i) for i in body.get('ids', []) if str(i).isdigit()]
    if not ids:
        raise HTTPException(status_code=400, detail='ids 不能为空')
    placeholders = ','.join(['%s'] * len(ids))
    # 带上 tenant_id：否则只要猜到 id 就能改动其它机构的告警
    affected = db.execute(
        f'UPDATE alerts SET status=1, handler_id=%s, handled_at=NOW(), handler_notes=%s '
        f'WHERE id IN ({placeholders}) AND tenant_id=%s AND status=0',
        [user.get('id'), body.get('notes', '')] + ids + [tenant_id_of(user)])
    # resource_id 是 varchar(50)：ids 一多，逗号拼接的列表必然超长，
    # 而审计写入失败是被吞掉的 —— 结果就是"批量处置了 200 条告警"
    # 这件事在审计页上完全不存在。所以这里只放一个有界的摘要，
    # 完整 id 列表进 detail（TEXT，不截断）。
    summary = (str(ids[0]) if len(ids) == 1
               else f'{ids[0]}..{ids[-1]}({len(ids)})')
    record_audit('批量处置告警', user=user, resource_type='alert', resource_id=summary,
                 detail={'count': len(ids), 'affected': affected, 'ids': ids}, request=request)
    # affected 用数据库返回的 rowcount，而不是请求里 ids 的个数：
    # 请求里有别的机构的 id 或不存在的 id 时，后者是**假数字**
    # —— 界面会显示"成功处置 5 条"，实际只改了 3 条。
    missed = len(ids) - affected
    message = (f'成功处置 {affected} 条告警' if missed <= 0
               else f'已处置 {affected} 条，另有 {missed} 条无需变更或不在本机构')
    return {'success': True,
            'data': {'affected': affected, 'requested': len(ids), 'ids': ids},
            'message': message}


@router.post('/ingest')
def ingest(body: dict[str, Any], request: Request = None,
           user: dict[str, Any] = Depends(require_admin)):
    # 本接口的用途是「把一条带完整证据的告警注入进来」——例如外部引擎、
    # 离线回放、或调试。所以 body 里的**证据字段必须原样转发**给仓库层。
    #
    # 原实现只挑了 6 个字段（elderId/cameraId/riskLevel/confidence/status），
    # 其余全部丢弃：调用方传了 postureType / evidenceMode / fallScore /
    # expressionTop / identityMethod 等，接口回「告警已接收」，
    # 而这些列**全部落成 NULL**。这正是「效果评测要回答哪类几何特征在误报」
    # 所依赖的那批字段（迁移 004/009 专为它们而加）。
    # 仓库白名单已同步补齐（见 base.py TABLE_COLUMNS['alerts']）；
    # 两处缺一不可：白名单决定"能不能写"，这里决定"有没有传"。
    tid = tenant_id_of(user)
    elder_id = body.get('elderId')
    camera_id = body.get('cameraId')
    if elder_id not in (None, ''):
        if not db.query_one('SELECT id FROM elders WHERE id=%s AND tenant_id=%s', [elder_id, tid]):
            raise HTTPException(status_code=404, detail='老人不存在或不属于当前机构')
    if camera_id not in (None, ''):
        if not db.query_one('SELECT id FROM cameras WHERE id=%s AND tenant_id=%s', [camera_id, tid]):
            raise HTTPException(status_code=404, detail='摄像头不存在或不属于当前机构')
    data = repo.insert({
        'tenantId': tid,
        'elderId': body.get('elderId'),
        'cameraId': body.get('cameraId'),
        'riskLevel': body.get('riskLevel') or 'HIGH',
        'confidence': int(body.get('confidence') or 0),
        'status': 0,
        'alertTime': body.get('alertTime'),
        # 姿态证据
        'postureType': body.get('postureType'),
        'evidenceMode': body.get('evidenceMode'),
        'fallScore': body.get('fallScore'),
        'painScore': body.get('painScore'),
        'torsoAngle': body.get('torsoAngle'),
        'kneeHipRatio': body.get('kneeHipRatio'),
        'poseQuality': body.get('poseQuality'),
        'bodyKeypoints': body.get('bodyKeypoints'),
        'rapidDescent': body.get('rapidDescent'),
        'fallState': body.get('fallState'),
        'trackId': body.get('trackId'),
        'fallEventAt': body.get('fallEventAt'),
        # 表情证据
        'expressionTop': body.get('expressionTop'),
        'expressionConfidence': body.get('expressionConfidence'),
        'exprQuality': body.get('exprQuality'),
        'faceAvailable': body.get('faceAvailable'),
        'faceMethod': body.get('faceMethod'),
        # 融合信念
        'beliefFall': body.get('beliefFall'),
        'beliefUnknown': body.get('beliefUnknown'),
        # 身份判定
        'identityMethod': body.get('identityMethod'),
        'identityConfidence': body.get('identityConfidence'),
        'identityCandidates': body.get('identityCandidates'),
    })
    record_audit('手动注入告警', user=user, resource_type='alert',
                 resource_id=(data or {}).get('id') if isinstance(data, dict) else None,
                 detail=body, request=request)
    if isinstance(data, dict):
        notify_alert(data, reason='ingested')
    return {'success': True, 'data': data, 'message': '告警已接收'}
