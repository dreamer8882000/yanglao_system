"""FaceTracker.smooth_single must never substitute a stale face box.

Root cause under test: ``FaceExtractor.extract`` passes exactly ONE detection to
``FaceTracker.update([face_box])`` and then takes ``smoothed[0]``. When the new
face does not overlap the previous one (IoU < threshold), ``update`` appends the
HELD previous box first and the new box second, so ``smoothed[0]`` is the
PREVIOUS image's face. Every single-image /detect request therefore reported the
face box of the first image it ever saw. ``smooth_single`` fixes this.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'third_party' / 'ultralytics'))

from expression_recognition.system import FaceTracker


def test_update_holds_stale_box_for_single_detection():
    """Documents the old buggy behaviour that smooth_single replaces."""
    tracker = FaceTracker(iou_threshold=0.3)
    tracker.update([(402, 128, 464, 215)])          # image A
    out = tracker.update([(10, 10, 60, 60)])        # image B, no overlap
    assert out[0] == (402, 128, 464, 215), "update() 仍会先把旧框放在首位（旧行为）"


def test_smooth_single_does_not_substitute_stale_box():
    tracker = FaceTracker(iou_threshold=0.3)
    tracker.smooth_single((402, 128, 464, 215))     # image A
    out = tracker.smooth_single((10, 10, 60, 60))   # image B, no overlap
    assert out == (10, 10, 60, 60), f"应返回当前框，实际 {out}"


def test_smooth_single_smooths_when_overlapping():
    tracker = FaceTracker(iou_threshold=0.3, smooth_alpha=0.5)
    tracker.smooth_single((100, 100, 200, 200))
    out = tracker.smooth_single((110, 110, 210, 210))
    assert out != (110, 110, 210, 210), "重叠时应做 EMA 平滑"
    for v in out:
        assert 100 <= v <= 210


def test_smooth_single_is_consistent_across_images():
    """Each new image's box must be reported, regardless of request order."""
    tracker = FaceTracker(iou_threshold=0.3)
    boxes = [(402, 128, 464, 215), (10, 10, 60, 60), (300, 20, 340, 70)]
    reported = [tracker.smooth_single(b) for b in boxes]
    assert reported == boxes, f"应逐个返回各自当前框，实际 {reported}"
