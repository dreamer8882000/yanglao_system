from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from app.core.config import get_settings
from app.core.database import db
from app.core.security import get_current_user
from app.core.tenant import require_same_tenant, tenant_id_of
from app.services.ai_alerts import attach_prediction, maybe_create_alert
from app.services.ai_engine import get_ai_engine
from app.services.image_loader import DetectionRequest, ImageInputLoader
from app.services.statistics import (
    detect_anomalies,
    elder_risk_score,
    linear_trend,
    predict_linear,
)

router = APIRouter(prefix='/python', tags=['python'])


def _detect_local(body: dict[str, Any], tenant_id: int | None = None) -> dict[str, Any]:
    settings = get_settings()
    request = DetectionRequest(**body)
    frame = ImageInputLoader.load(request, settings)
    engine = get_ai_engine()
    try:
        result = engine.predict(frame, request.cameraId, reset_state=True)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    attach_prediction(result)
    # 必须带上**调用者所属机构**：cameraId 来自请求体，是客户端可控的。
    # 不带的话 maybe_create_alert 会按摄像头推导机构，等于允许任何人
    # 通过伪造 cameraId 往别的机构写告警（yolo.py 那条路径一直是传的，
    # 只有这里漏了）。
    alert = maybe_create_alert(result, request.cameraId, tenant_id=tenant_id)
    if alert:
        result['alert'] = alert
    return {'success': True, 'data': result}


@router.post('/detect')
@router.post('/yolo/detect')
def detect(body: dict[str, Any], user: dict[str, Any] = Depends(get_current_user)):
    return _detect_local(body, tenant_id=tenant_id_of(user))


@router.post('/detect/batch')
@router.post('/yolo/batch')
def detect_batch(body: dict[str, Any], user: dict[str, Any] = Depends(get_current_user)):
    items = body.get('imageUrls') or body.get('images') or []
    if not isinstance(items, list):
        raise HTTPException(status_code=400, detail='批量图片输入必须是数组')
    # 同样必须传调用者机构：批量接口的每一项都可能自带 cameraId（客户端可控），
    # 不传就等于开了一个"一次请求往多个机构写告警"的口子。
    tid = tenant_id_of(user)
    results = []
    for image_url in items:
        payload = {'imageUrl': image_url} if isinstance(image_url, str) else image_url
        results.append(_detect_local(payload, tenant_id=tid)['data'])
    return {'success': True, 'data': {'results': results, 'count': len(results)}}


@router.get('/statistics/trends')
@router.get('/statistics/trend')
def trends(days: int = 30, user: dict[str, Any] = Depends(get_current_user)):
    days = max(1, min(int(days or 30), 365))
    # 这里原先没有租户条件：仪表盘的"告警趋势"曲线会把**所有机构**的告警
    # 加在一起画出来。接口鉴权没问题、页面也没显示别人的明细，
    # 只是数字悄悄变大了 —— 多租户里最难被发现的一类泄露。
    rows = db.query(
        'SELECT DATE(alert_time) AS day, risk_level, COUNT(*) AS count FROM alerts '
        'WHERE tenant_id = %s AND alert_time >= DATE_SUB(CURDATE(), INTERVAL %s DAY) '
        'GROUP BY DATE(alert_time), risk_level ORDER BY day',
        [tenant_id_of(user), days],
    )
    return {'success': True, 'data': {'days': days, 'items': [
        {'date': str(r['day']), 'riskLevel': r['risk_level'], 'count': int(r['count'])} for r in rows
    ]}}


@router.post('/statistics/heatmap')
def heatmap(body: dict[str, Any], user: dict[str, Any] = Depends(get_current_user)):
    days = max(1, min(int(body.get('days') or 30), 365))
    rows = db.query(
        'SELECT HOUR(alert_time) AS hour, COUNT(*) AS count FROM alerts '
        'WHERE tenant_id = %s AND alert_time >= DATE_SUB(NOW(), INTERVAL %s DAY) '
        'GROUP BY HOUR(alert_time)',
        [tenant_id_of(user), days],
    )
    by_hour = {int(r['hour']): int(r['count']) for r in rows}
    return {'success': True, 'data': {'items': [
        {'hour': h, 'count': by_hour.get(h, 0)} for h in range(24)
    ]}}


@router.get('/statistics/predict/{elder_id}')
def predict(elder_id: int, days: int = 7, user: dict[str, Any] = Depends(get_current_user)):
    # elder_id 是自增整数，不校验归属的话可以逐个猜出**别家机构**老人的告警曲线
    require_same_tenant(db.query_one('SELECT id, tenant_id FROM elders WHERE id=%s', [elder_id]), user)
    history = db.query(
        'SELECT DATE(alert_time) AS day, COUNT(*) AS count FROM alerts '
        'WHERE tenant_id = %s AND elder_id=%s '
        'AND alert_time >= DATE_SUB(CURDATE(), INTERVAL 30 DAY) '
        'GROUP BY DATE(alert_time) ORDER BY day',
        [tenant_id_of(user), elder_id],
    )
    values = [int(r['count']) for r in history]
    forecast = predict_linear(values, periods=max(1, min(int(days or 7), 30)))
    return {'success': True, 'data': {
        'elderId': elder_id,
        'history': [{'date': str(r['day']), 'count': int(r['count'])} for r in history],
        'predictions': forecast['predictions'],
        'method': forecast['method'],
    }}


@router.post('/yolo/switch-model')
def switch_model(body: dict[str, Any], user: dict[str, Any] = Depends(get_current_user)):
    return {'success': True, 'data': {'modelName': body.get('modelName')}, 'message': '本地 AI 引擎使用环境变量配置模型'}


@router.post('/statistics/trend')
def analyze_trend(body: dict[str, Any], user: dict[str, Any] = Depends(get_current_user)):
    return {'success': True, 'data': linear_trend(body.get('data') or [])}


@router.get('/statistics/anomaly')
@router.post('/statistics/anomaly')
def anomaly(body: dict[str, Any] | None = None, user: dict[str, Any] = Depends(get_current_user)):
    payload = body or {}
    return {'success': True, 'data': detect_anomalies(
        payload.get('data') or [], payload.get('threshold') or 2.0)}


@router.post('/statistics/predict')
def predict_body(body: dict[str, Any], user: dict[str, Any] = Depends(get_current_user)):
    return {'success': True, 'data': predict_linear(
        body.get('data') or [], body.get('periods') or 7)}


@router.get('/statistics/risk-score')
@router.post('/statistics/risk-score')
def risk_score(body: dict[str, Any] | None = None, user: dict[str, Any] = Depends(get_current_user)):
    payload = body or {}
    elder_id = payload.get('elderId') or payload.get('elder_id')
    if not elder_id:
        raise HTTPException(status_code=400, detail='elderId 不能为空')
    try:
        elder_id = int(elder_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail='elderId 必须为整数')
    return {'success': True, 'data': elder_risk_score(
        elder_id, payload.get('days') or 30, tenant_id=tenant_id_of(user))}


@router.get('/health')
def health(user: dict[str, Any] = Depends(get_current_user)):
    return {'success': True, 'data': get_ai_engine().status()}
