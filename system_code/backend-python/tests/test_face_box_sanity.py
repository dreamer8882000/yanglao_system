"""回归护栏：Tier-1 头部关键点推导的人脸框必须有合理性上限。

原实现 size = max(head_span*3.2, ...) 没有任何上限。当两个"头部关键点"
相距很远时（人贴近摄像头、侧躺、或关键点抖到耳朵上），推导出的框会超过
整幅画面并被裁剪成整个画面，而系统仍认为它是合法人脸，于是表情模型被
喂了整张图。实测：头跨 160px → 88.0%，双耳相距 300px → 95.6%。
"""
import sys
from pathlib import Path

import numpy as np
import pytest


@pytest.fixture()
def fx():
    root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(root / 'third_party' / 'ultralytics'))
    sys.path.insert(0, str(root))
    from expression_recognition.system import FaceExtractor
    return FaceExtractor()


def _kpts(head, shoulders=None):
    k = np.zeros((17, 3))
    for i, (x, y) in head.items():
        k[i] = (x, y, 0.9)
    for i, (x, y) in (shoulders or {}).items():
        k[i] = (x, y, 0.9)
    return k


W, H = 640, 480
FRAME = np.zeros((H, W, 3), np.uint8)


def _ratio(box):
    x1, y1, x2, y2 = box
    return (x2 - x1) * (y2 - y1) / (W * H)


def test_normal_face_box_is_small(fx):
    """正常人脸框应远小于画面。"""
    k = _kpts({0: (320, 100), 1: (300, 90), 2: (340, 90)})
    _, ok, method, box = fx.extract(FRAME, k[:, :2], keypoint_conf=k[:, 2])
    assert box is not None and ok
    assert _ratio(box) < 0.15, f'正常人脸框过大: {box} → {_ratio(box)*100:.1f}%'


def test_implausible_head_span_is_rejected(fx):
    """双耳相距 300px 不构成一个头，必须放弃 Tier-1（回退 Tier-2/3）。"""
    k = _kpts({3: (170, 180), 4: (470, 180)})
    _, _, method, box = fx.extract(FRAME, k[:, :2], keypoint_conf=k[:, 2])
    assert method != 'keypoint', '异常头点仍被当作合法人脸'


def test_head_span_larger_than_shoulders_is_rejected(fx):
    """头宽不可能超过肩宽本身。"""
    k = _kpts({3: (170, 180), 4: (470, 180)}, {5: (285, 260), 6: (355, 260)})
    _, _, method, _ = fx.extract(FRAME, k[:, :2], keypoint_conf=k[:, 2])
    assert method != 'keypoint', '头跨 300px > 肩宽 70px，仍被接受'


@pytest.mark.parametrize('head', [
    {0: (320, 150), 1: (240, 140), 2: (400, 140)},   # 近景大脸
    {0: (250, 200), 4: (450, 200)},                  # 侧躺：鼻+耳相距 200px
    {3: (70, 200), 4: (570, 200)},                   # 极端
])
def test_face_box_never_covers_the_whole_frame(fx, head):
    """无论关键点多离谱，接受的人脸框都不得接近整幅画面。"""
    k = _kpts(head)
    _, _, method, box = fx.extract(FRAME, k[:, :2], keypoint_conf=k[:, 2])
    if method == 'keypoint' and box is not None:
        assert _ratio(box) <= 0.35, (
            f'人脸框退化为整幅画面: {box} → {_ratio(box)*100:.1f}%')
