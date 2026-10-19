import base64
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fastapi import HTTPException
from pydantic import BaseModel

from app.core.config import Settings


class DetectionRequest(BaseModel):
    imageUrl: str | None = None
    imageBase64: str | None = None
    streamUrl: str | None = None
    cameraId: int | None = None
    conf: float | None = None


class ImageInputLoader:
    @staticmethod
    def load(body: DetectionRequest | dict[str, Any], settings: Settings) -> Any:
        request = body if isinstance(body, DetectionRequest) else DetectionRequest(**body)
        if request.imageBase64:
            return ImageInputLoader._load_base64(request.imageBase64)
        if request.imageUrl:
            return ImageInputLoader._load_image_url(request.imageUrl, settings)
        if request.streamUrl:
            return ImageInputLoader.load_stream_frame(request.streamUrl, settings)
        raise HTTPException(status_code=400, detail='缺少图片输入')

    @staticmethod
    def _load_base64(value: str) -> Any:
        try:
            payload = value.split(',', 1)[1] if ',' in value and value.lower().startswith('data:') else value
            data = base64.b64decode(payload, validate=True)
        except Exception as exc:
            raise HTTPException(status_code=400, detail='图片 base64 解码失败') from exc
        return ImageInputLoader._decode_image(data)

    @staticmethod
    def _load_image_url(value: str, settings: Settings) -> Any:
        parsed = urlparse(value)
        if parsed.scheme in {'http', 'https'}:
            if not settings.ai_allow_remote_image:
                raise HTTPException(status_code=400, detail='远程图片访问未开启')
            return ImageInputLoader._load_remote(value)
        if parsed.scheme:
            raise HTTPException(status_code=400, detail='不支持的图片地址协议')
        return ImageInputLoader._load_local(value, settings)

    @staticmethod
    def _load_remote(url: str) -> Any:
        try:
            import httpx
        except ImportError as exc:
            raise HTTPException(status_code=503, detail='缺少 httpx 依赖，无法读取远程图片') from exc
        try:
            response = httpx.get(url, timeout=10, follow_redirects=False)
            response.raise_for_status()
        except Exception as exc:
            raise HTTPException(status_code=400, detail='远程图片读取失败') from exc
        return ImageInputLoader._decode_image(response.content)

    @staticmethod
    def _load_local(value: str, settings: Settings) -> Any:
        root = Path(settings.ai_allowed_image_root).expanduser().resolve()
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = root / path
        try:
            resolved = path.resolve(strict=True)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=400, detail='图片文件不存在') from exc
        if resolved != root and root not in resolved.parents:
            raise HTTPException(status_code=400, detail='图片路径不在允许目录内')
        try:
            data = resolved.read_bytes()
        except Exception as exc:
            raise HTTPException(status_code=400, detail='图片文件读取失败') from exc
        return ImageInputLoader._decode_image(data)

    @staticmethod
    def load_stream_frame(stream_url: str, settings: Settings) -> Any:
        parsed = urlparse(stream_url)
        if parsed.scheme not in {'rtsp', 'http', 'https'}:
            raise HTTPException(status_code=400, detail='不支持的摄像头流地址协议')
        if not settings.ai_allow_remote_image:
            raise HTTPException(status_code=400, detail='远程摄像头流访问未开启')
        try:
            import cv2
        except ImportError as exc:
            raise HTTPException(status_code=503, detail='缺少 opencv-python 依赖，无法读取摄像头流') from exc
        cap = cv2.VideoCapture(stream_url)
        try:
            if not cap.isOpened():
                raise HTTPException(status_code=400, detail='无法打开摄像头视频流')
            ok, frame = cap.read()
            if not ok or frame is None:
                raise HTTPException(status_code=400, detail='无法从摄像头视频流读取画面')
            return frame
        finally:
            cap.release()

    @staticmethod
    def _decode_image(data: bytes) -> Any:
        try:
            import cv2
            import numpy as np
        except ImportError as exc:
            raise HTTPException(status_code=503, detail='缺少 numpy 或 opencv-python 依赖，无法解码图片') from exc
        array = np.frombuffer(data, dtype=np.uint8)
        frame = cv2.imdecode(array, cv2.IMREAD_COLOR)
        if frame is None:
            raise HTTPException(status_code=400, detail='图片解码失败')
        return frame
