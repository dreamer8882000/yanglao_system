import re
from typing import Any
import json
from fastapi import APIRouter, Depends, HTTPException
from app.core.config import get_settings
from app.core.database import db
from app.core.security import get_current_user, require_admin
from app.core.tenant import tenant_id_of
from app.repositories.base import keys_to_camel
from app.services.ai_alerts import attach_prediction, maybe_create_alert
from app.services.ai_engine import get_ai_engine
from app.services.image_loader import DetectionRequest, ImageInputLoader

router = APIRouter(prefix='/yolo', tags=['yolo'])

MODELS = [
    {'id': 'smart-elderly-cascade', 'name': '姿态+表情 D-S 融合模型', 'type': 'cascade', 'description': '复用 smart_elderly_care 的姿态估计、表情识别和风险融合 Pipeline'},
    {'id': 'none', 'name': '不启用', 'type': 'none', 'description': '关闭检测'},
]

_WEIGHTS_RE = re.compile(r'^[\w\-]+\.pt$')


def _safe_weights(value: str | None) -> str | None:
    if value and _WEIGHTS_RE.match(value):
        return value
    return None


def _normalize_config(body: dict[str, Any]) -> dict[str, Any]:
    model = body.get('model') or body.get('yoloModel') or 'smart-elderly-cascade'
    models = body.get('models') or body.get('yoloModels')
    if isinstance(models, str):
        try:
            models = json.loads(models)
        except Exception:
            models = [models]
    if not isinstance(models, list):
        models = [model]
    return {
        'model': model,
        'models_json': json.dumps(models, ensure_ascii=False),
        'confidence': body.get('confidence') or body.get('confidenceThreshold') or 0.5,
        'fps': body.get('fps') or body.get('inferenceFps') or 1,
        'weights': _safe_weights(body.get('customWeights') or body.get('modelWeights')),
    }


@router.get('/models')
def models(user: dict[str, Any] = Depends(get_current_user)):
    data = [dict(item) for item in MODELS]
    data[0]['engineStatus'] = get_ai_engine().status()
    return {'success': True, 'data': data}


@router.get('/models/{model_id}')
def model(model_id: str, user: dict[str, Any] = Depends(get_current_user)):
    item = next((m for m in MODELS if m['id'] == model_id), None)
    if not item:
        raise HTTPException(status_code=404, detail='模型不存在')
    return {'success': True, 'data': item}


@router.get('/cameras/{camera_id}/config')
def camera_config(camera_id: int, user: dict[str, Any] = Depends(get_current_user)):
    rows = db.query('SELECT yolo_model,yolo_models,confidence_threshold,inference_fps,model_weights '
                    'FROM cameras WHERE id=%s AND tenant_id=%s LIMIT 1',
                    [camera_id, tenant_id_of(user)])
    if not rows:
        raise HTTPException(status_code=404, detail='摄像头不存在')
    row = keys_to_camel(rows[0])
    row.update({
        'model': row.get('yoloModel'),
        'models': row.get('yoloModels'),
        'confidence': row.get('confidenceThreshold'),
        'fps': row.get('inferenceFps'),
        'customWeights': row.get('modelWeights'),
    })
    return {'success': True, 'data': row}


@router.put('/cameras/{camera_id}/config')
def update_camera_config(camera_id: int, body: dict[str, Any], user: dict[str, Any] = Depends(require_admin)):
    conf = _normalize_config(body)
    db.execute(
        'UPDATE cameras SET yolo_model=%s, yolo_models=%s, confidence_threshold=%s, '
        'inference_fps=%s, model_weights=%s WHERE id=%s AND tenant_id=%s',
        [conf['model'], conf['models_json'], conf['confidence'], conf['fps'], conf['weights'],
         camera_id, tenant_id_of(user)],
    )
    return {'success': True, 'data': camera_config(camera_id, user)['data'], 'message': '配置更新成功'}


@router.post('/cameras/batch-config')
def batch_config(body: dict[str, Any], user: dict[str, Any] = Depends(require_admin)):
    configs = body.get('configs') or []
    results = []
    for conf in configs:
        try:
            update_camera_config(int(conf.get('cameraId')), conf, user)
            results.append({'cameraId': conf.get('cameraId'), 'success': True})
        except Exception as exc:
            results.append({'cameraId': conf.get('cameraId'), 'success': False, 'message': str(exc)})
    return {'success': all(r['success'] for r in results), 'data': results, 'message': '批量配置完成'}


@router.post('/cameras/{camera_id}/test')
def test_camera(camera_id: int, body: dict[str, Any] | None = None, user: dict[str, Any] = Depends(get_current_user)):
    settings = get_settings()
    payload = dict(body or {})
    rows = db.query('SELECT id,stream_url,source_type,yolo_enabled,yolo_model,yolo_models '
                    'FROM cameras WHERE id=%s AND tenant_id=%s LIMIT 1',
                    [camera_id, tenant_id_of(user)])
    if not rows:
        raise HTTPException(status_code=404, detail='摄像头不存在')
    camera = keys_to_camel(rows[0])
    models = camera.get('yoloModels') or []
    if isinstance(models, str):
        try:
            models = json.loads(models)
        except Exception:
            models = [models]
    if camera.get('yoloEnabled') == 0 or camera.get('yoloModel') == 'none' or 'none' in models:
        raise HTTPException(status_code=400, detail='该摄像头未启用 AI 级联检测，请在设置中开启')
    if not payload.get('imageUrl') and not payload.get('imageBase64') and camera.get('streamUrl'):
        payload['streamUrl'] = camera.get('streamUrl')
    payload['cameraId'] = camera_id
    request = DetectionRequest(**payload)
    frame = ImageInputLoader.load(request, settings)
    try:
        result = get_ai_engine().predict(frame, camera_id, reset_state=True)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f'AI 引擎调用失败: {exc}') from exc
    attach_prediction(result)
    # 显式传本机构：手动测试检测没有经过引擎自动链路，
    # 但同样只能在本机构的摄像头上产生告警。
    alert = maybe_create_alert(result, camera_id, tenant_id_of(user))
    if alert:
        result['alert'] = alert
    result['camera'] = camera
    return {'success': True, 'data': result}


@router.get('/stats')
def stats(user: dict[str, Any] = Depends(get_current_user)):
    # 原实现是全表 GROUP BY：会把**其它机构**的摄像头型号分布一起统计进来
    rows = db.query('SELECT yolo_model, COUNT(*) AS count FROM cameras '
                    'WHERE tenant_id=%s GROUP BY yolo_model', [tenant_id_of(user)])
    return {'success': True, 'data': keys_to_camel(rows)}
