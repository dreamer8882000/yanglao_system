import asyncio
import base64
import json
import time
from typing import Any

import cv2
import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.database import db
from app.core.security import decode_token
from app.core.tenant import bind_tenant, tenant_id_of
from app.repositories.base import keys_to_camel
from app.services.ai_alerts import attach_prediction, maybe_create_alert
from app.services.ai_engine import get_ai_engine

router = APIRouter(prefix='/yolo', tags=['yolo-stream'])


def _unauthorized() -> str:
    return json.dumps({'success': False, 'message': '未登录'}, ensure_ascii=False)


def _auth_user(token: str | None) -> dict[str, Any] | None:
    """WebSocket 无法使用 Depends，所以这里手工完成 get_current_user 的等效工作。"""
    if not token:
        return None
    try:
        payload = decode_token(token)
    except Exception:
        return None
    user_id = payload.get('sub')
    if not user_id:
        return None
    rows = db.query('SELECT id, username, name, role, tenant_id FROM users WHERE id=%s LIMIT 1', [user_id])
    if not rows:
        return None
    user = keys_to_camel(rows[0])
    # 平台账号没有机构上下文，不能进入业务视频流（否则后续租户推导会抛 403）。
    if user.get('tenantId') is None:
        return None
    # 与 HTTP 侧一致：WebSocket 也要绑定租户上下文，
    # 否则这条链路里的工具/仓库调用拿不到机构。
    bind_tenant(user.get('tenantId'))
    return user


def _camera_row(camera_id: int, tenant_id: int | None = None) -> dict[str, Any] | None:
    """取摄像头；带 tenant_id 时同时校验归属（跨机构返回 None → 前端表现为 404）。"""
    sql = ('''SELECT id, name, stream_url, source_type, yolo_enabled, yolo_model, yolo_models, inference_fps
              FROM cameras WHERE id=%s''')
    params: list[Any] = [camera_id]
    if tenant_id is not None:
        sql += ' AND tenant_id=%s'
        params.append(tenant_id)
    sql += ' LIMIT 1'
    rows = db.query(sql, params)
    return keys_to_camel(rows[0]) if rows else None


def _enabled(camera: dict[str, Any]) -> bool:
    models = camera.get('yoloModels') or []
    if isinstance(models, str):
        try:
            models = json.loads(models)
        except Exception:
            models = [models]
    return camera.get('yoloEnabled') != 0 and camera.get('yoloModel') != 'none' and 'none' not in models


def _open_capture(stream_url: str):
    source = int(stream_url) if str(stream_url).isdigit() else stream_url
    return cv2.VideoCapture(source)


async def _send_json(websocket: WebSocket, payload: dict[str, Any]) -> bool:
    """Send JSON to the client; returns False if the client disconnected.

    The camera stream opens an RTSP source which can block for ~30s before
    failing; the client may disconnect during that time, so pre-loop sends
    (e.g. '视频流打开失败') must not raise an unhandled WebSocketDisconnect.
    """
    try:
        await websocket.send_text(json.dumps(payload, ensure_ascii=False, default=str))
        return True
    except WebSocketDisconnect:
        return False


def _decode_base64_frame(image_base64: str):
    if ',' in image_base64:
        image_base64 = image_base64.split(',', 1)[1]
    raw = base64.b64decode(image_base64)
    arr = np.frombuffer(raw, dtype=np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError('视频帧解码失败')
    return frame


async def _predict_payload(frame, camera_id: int | None = None, camera: dict[str, Any] | None = None) -> dict[str, Any]:
    result = await asyncio.to_thread(get_ai_engine().predict, frame, camera_id)
    attach_prediction(result)
    alert = await asyncio.to_thread(maybe_create_alert, result, camera_id)
    if alert:
        result['alert'] = alert
    if camera:
        result['camera'] = camera
    return result


@router.websocket('/cameras/{camera_id}/stream')
async def camera_stream(websocket: WebSocket, camera_id: int, token: str | None = None):
    await websocket.accept()
    user = _auth_user(token)
    if not user:
        await websocket.send_text(_unauthorized())
        await websocket.close(code=1008)
        return

    camera = _camera_row(camera_id, tenant_id_of(user))
    if not camera:
        await _send_json(websocket, {'success': False, 'message': '摄像头不存在'})
        await websocket.close(code=1008)
        return
    if not _enabled(camera):
        await _send_json(websocket, {'success': False, 'message': '该摄像头未启用 AI 级联检测'})
        await websocket.close(code=1008)
        return
    stream_url = camera.get('streamUrl')
    if not stream_url:
        await _send_json(websocket, {'success': False, 'message': '摄像头未配置视频流地址'})
        await websocket.close(code=1008)
        return

    cap = _open_capture(stream_url)
    if not cap.isOpened():
        if await _send_json(websocket, {'success': False, 'message': '视频流打开失败'}):
            await websocket.close(code=1011)
        return

    # Fall detection needs enough temporal samples to observe the *transition*
    # (rapid descent + torso rotation), not just the static end pose: a typical
    # fall takes 0.6-1.2 s, so 2 FPS can land one sample before and one after
    # it and miss the transition entirely, which is precisely the signal that
    # separates a fall from lying down to rest.
    #
    # 8 FPS is the new default: it gives ~5-9 samples across a fall while
    # remaining inside the single-frame budget released by lowering the pose
    # input resolution to 640 (~66 ms/frame -> ~15 FPS headroom).
    # 实测整条 process_frame 中位 48ms（约 20 FPS），姿态 @640 约 29ms，
    # 时序跌倒模型只占 2.2ms —— 算力有余量，8 FPS 是白白压低了跟随性
    # （摄像头端表现为骨架框每 125ms 才动一次）。
    # 提到 12 FPS（83ms 间隔）仍在余量内，而且给跌倒过程留了更多采样点。
    _DEFAULT_INFERENCE_FPS = 12.0
    _MAX_INFERENCE_FPS = 15.0
    fps = float(camera.get('inferenceFps') or _DEFAULT_INFERENCE_FPS)
    interval = 1.0 / max(0.5, min(_MAX_INFERENCE_FPS, fps))
    await _send_json(websocket, {
        'success': True,
        'event': 'connected',
        'camera': camera,
        'interval': interval,
        'engineStatus': get_ai_engine().status(),
    })

    try:
        while True:
            started = time.time()
            ok, frame = await asyncio.to_thread(cap.read)
            if not ok or frame is None:
                cap.release()
                await asyncio.sleep(0.5)
                cap = _open_capture(stream_url)
                if not cap.isOpened():
                    if not await _send_json(websocket, {'success': False, 'event': 'stream_error', 'message': '视频流中断，重连失败'}):
                        break
                    break
                continue

            try:
                result = await _predict_payload(frame, camera_id, camera)
                await _send_json(websocket, {'success': True, 'event': 'result', 'data': result})
            except Exception as exc:
                await _send_json(websocket, {'success': False, 'event': 'error', 'message': str(exc)})

            elapsed = time.time() - started
            await asyncio.sleep(max(0.0, interval - elapsed))
    except WebSocketDisconnect:
        pass
    finally:
        cap.release()


# 二进制帧协议：前 8 字节是小端 float64 的**视频时间戳**（秒），其后是 JPEG。
#
# 为什么要走二进制而不是原来的 base64+JSON：
#   1. base64 把体积放大 4/3，还要在浏览器主线程上做一次同步 toDataURL 编码 ——
#      那个编码会阻塞 rAF，直接把画面和叠加层一起冻住，是"跟随慢"的主因之一；
#   2. 100KB 量级的字符串再套一层 JSON，服务端还要解析回来，纯浪费；
#   3. 视频时间戳跟着帧一起走，前端才能把结果**按时间轴对齐**回放，
#      而不是"把最新结果贴到当前画面"（后者天然滞后一个往返延迟）。
_BIN_HEADER = 8


def _parse_frame_message(message: dict[str, Any]):
    """把一条 WebSocket 消息解析成 (frame, vt)。

    同时支持两种格式：
      * 二进制：8 字节 float64 视频时间戳 + JPEG 字节
      * 文本  ：原来的 {"imageBase64": ..., "vt": ...}（HTTP 降级/旧客户端仍可用）
    """
    raw = message.get('bytes')
    if raw:
        if len(raw) < _BIN_HEADER + 16:
            return None
        vt = float(np.frombuffer(raw[:_BIN_HEADER], dtype='<f8')[0])
        arr = np.frombuffer(raw[_BIN_HEADER:], dtype=np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is None:
            return None
        return frame, vt

    text = message.get('text')
    if not text:
        return None
    payload = json.loads(text)
    image_base64 = payload.get('imageBase64') or payload.get('frame')
    if not image_base64:
        raise ValueError('缺少视频帧')
    vt = payload.get('vt')
    return _decode_base64_frame(image_base64), (float(vt) if vt is not None else None)


@router.websocket('/frame-stream')
async def frame_stream(websocket: WebSocket, token: str | None = None, cameraId: int | None = None):
    await websocket.accept()
    user = _auth_user(token)
    if not user:
        await websocket.send_text(_unauthorized())
        await websocket.close(code=1008)
        return

    camera = None
    if cameraId is not None:
        camera = _camera_row(cameraId, tenant_id_of(user))
        if not camera:
            await _send_json(websocket, {'success': False, 'message': '摄像头不存在'})
            await websocket.close(code=1008)
            return
    await _send_json(websocket, {
        'success': True,
        'event': 'connected',
        'mode': 'frame-stream',
        'camera': camera,
        'engineStatus': get_ai_engine().status(),
    })
    # 不再用 busy 丢帧：那样前端把帧算作"在途"却永远等不到回包，在途计数只增不减，
    # 几秒后就彻底卡死。现在**每一条收到的帧都处理并回包**，
    # 并发深度由前端自己的在途上限（2 帧）控制，队列长度因此天然有界。
    try:
        while True:
            message = await websocket.receive()
            if message.get('type') == 'websocket.disconnect':
                break
            try:
                parsed = _parse_frame_message(message)
                if parsed is None:
                    continue
                frame, vt = parsed
                result = await _predict_payload(frame, cameraId, camera)
                if vt is not None:
                    # 原样回传，前端据此把结果对齐到它真正对应的视频时刻
                    result['vt'] = float(vt)
                await _send_json(websocket, {'success': True, 'event': 'result', 'data': result})
            except Exception as exc:
                await _send_json(websocket, {'success': False, 'event': 'error', 'message': str(exc)})
    except WebSocketDisconnect:
        pass
