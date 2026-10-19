"""frame-stream 二进制帧协议的回归测试

为什么值得单独测
----------------
这条协议是"骨架跟随"的关键：帧必须带着**视频时间戳**一起去服务端，回来时原样
带回，前端才能把结果按时间轴对齐回放。协议一旦悄悄退化成"只有 JPEG、没有时间戳"，
界面上不会报任何错 —— 只是骨架重新变回"贴在已经走远的画面上"，
也就是用户报的那个"跟随太慢"。这类**静默退化**必须有测试钉住。

同时要保证旧格式（base64 + JSON）继续可用：HTTP 降级通道和旧客户端还在用。
"""
import base64
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(scope="module")
def jpeg_bytes():
    frame = np.zeros((48, 64, 3), dtype=np.uint8)
    frame[10:30, 15:45] = 200
    ok, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
    assert ok
    return np.asarray(buf).tobytes()


@pytest.fixture(scope="module")
def parse():
    from app.api.routes.yolo_stream import _parse_frame_message
    return _parse_frame_message


def test_binary_carries_video_timestamp(parse, jpeg_bytes):
    vt = 12.345
    payload = np.frombuffer(np.float64(vt).tobytes(), dtype=np.uint8).tobytes() + jpeg_bytes
    frame, got = parse({'bytes': payload})
    assert frame is not None
    assert got == pytest.approx(vt, abs=1e-9)


def test_binary_pixels_match_base64_path(parse, jpeg_bytes):
    """两条通道必须解出同一张图，否则"换传输不影响精度"这句话不成立。"""
    payload = np.frombuffer(np.float64(1.0).tobytes(), dtype=np.uint8).tobytes() + jpeg_bytes
    fb, _ = parse({'bytes': payload})
    ft, _ = parse({'text': json.dumps({'imageBase64': base64.b64encode(jpeg_bytes).decode()})})
    assert np.array_equal(fb, ft)


def test_legacy_text_without_vt_still_works(parse, jpeg_bytes):
    """旧客户端不带 vt：不能报错，vt 返回 None，前端自然会退回"用当前时间"。"""
    frame, vt = parse({'text': json.dumps({
        'imageBase64': base64.b64encode(jpeg_bytes).decode()})})
    assert frame is not None
    assert vt is None


def test_legacy_text_with_vt(parse, jpeg_bytes):
    frame, vt = parse({'text': json.dumps({
        'imageBase64': base64.b64encode(jpeg_bytes).decode(), 'vt': 7.5})})
    assert frame is not None
    assert vt == pytest.approx(7.5)


def test_truncated_binary_is_ignored_not_crashing(parse, jpeg_bytes):
    """半包/烂包必须返回 None 而不是抛异常 —— 否则整条 WebSocket 会被一句 except 关掉。"""
    assert parse({'bytes': b'\x00' * 4}) is None
    assert parse({'bytes': b''}) is None
    assert parse({'bytes': np.frombuffer(np.float64(1.0).tobytes(),
                                         dtype=np.uint8).tobytes() + b'notajpeg'}) is None


def test_empty_message_returns_none(parse):
    assert parse({}) is None
    assert parse({'text': ''}) is None


def test_missing_frame_raises_so_the_client_is_told(parse):
    """只有明确"缺帧"才抛错：这样前端能收到 error 事件，而不是静默无回包。"""
    with pytest.raises(ValueError):
        parse({'text': json.dumps({'ts': 123})})


def test_binary_is_smaller_than_base64(jpeg_bytes):
    """二进制通道的收益要能被量化，不能只是"感觉更快"。"""
    vt = 1.0
    bin_len = 8 + len(jpeg_bytes)
    b64_len = len(json.dumps({'imageBase64': base64.b64encode(jpeg_bytes).decode(),
                              'vt': vt}))
    assert bin_len < b64_len * 0.8
