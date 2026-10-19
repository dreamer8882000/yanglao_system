"""Tests for the alert dedup-query construction.

Root cause under test: browser/manual detections carry ``camera_id=None``,
and the previous code dropped them entirely (returning None from
``maybe_create_alert``) -- so testing through VideoDetect or the single-image
API produced no alert history at all. The fix allows NULL-camera alerts and
builds a dedup query that treats ``camera_id IS NULL`` correctly instead of
``camera_id = NULL`` (which never matches).

Run:  cd system_code/backend-python && .venv/bin/python -m pytest tests/test_ai_alerts.py
"""

from app.services.ai_alerts import _dedup_query, _should_escalate, build_prediction


def test_should_escalate_higher_level():
    assert _should_escalate("HIGH", 90, "URGENT", 90) is True


def test_should_escalate_same_level_higher_confidence():
    assert _should_escalate("HIGH", 80, "HIGH", 90) is True


def test_should_escalate_lower_level_is_false():
    assert _should_escalate("URGENT", 90, "HIGH", 95) is False


def test_should_escalate_same_level_lower_confidence_is_false():
    assert _should_escalate("HIGH", 90, "HIGH", 80) is False


def test_build_prediction_truncates_fall_event_to_second():
    """fall_event_at 存 DATETIME（秒精度），写入时 MySQL 截断微秒；
    若不去微秒，同事件去重查询会带上微秒与已存秒级行不相等 -> 重复告警。"""
    result = {
        'alertLevel': 'URGENT',
        'fallScore': 0.9,
        'painScore': 0.0,
        'fallInfo': {
            'fallState': 'confirmed_fall',
            'postureType': 'fall_like',
            'confirmedFallAt': 1760000000.123456,
        },
    }
    pred = build_prediction(result)
    assert pred['riskLevel'] == 'URGENT'
    assert pred['fallEventAt'] is not None
    assert pred['fallEventAt'].microsecond == 0, \
        f'fallEventAt 应截断到秒，实际 {pred["fallEventAt"]}'


def test_dedup_query_with_real_camera():
    sql, args = _dedup_query(42)
    assert "camera_id=%s" in sql
    assert args == [42]


def test_dedup_query_with_null_camera_uses_is_null():
    sql, args = _dedup_query(None)
    assert "camera_id IS NULL" in sql, f"应为 IS NULL，得到: {sql}"
    assert "camera_id=%s" not in sql
    assert args == []


def test_dedup_query_window_and_status():
    for sql, _ in (_dedup_query(1), _dedup_query(None)):
        assert "status=0" in sql
        assert "60 SECOND" in sql


def test_dedup_query_with_fall_event_uses_event_identity():
    """同一跌倒事件（同一 fall_event_at）应去重，而不是靠 60 秒窗口。"""
    sql, args = _dedup_query(42, "2026-01-01 10:00:00")
    assert "fall_event_at=%s" in sql, f"应包含 fall_event_at 条件，得到: {sql}"
    assert "60 SECOND" not in sql, "事件级去重不应再依赖 60 秒窗口"
    assert args == [42, "2026-01-01 10:00:00"]


def test_dedup_query_fall_event_with_null_camera():
    sql, args = _dedup_query(None, "2026-01-01 10:00:00")
    assert "camera_id IS NULL" in sql
    assert "fall_event_at=%s" in sql
    assert args == ["2026-01-01 10:00:00"]


def test_dedup_query_without_fall_event_keeps_window():
    """无跌倒事件（pain-only/suspected）仍走 60 秒限流。"""
    sql, _ = _dedup_query(42, None)
    assert "60 SECOND" in sql
    assert "fall_event_at" not in sql


def test_build_prediction_exposes_structured_fields():
    """结构化字段（姿态/证据模式/分数）必须随预测一并产出，供反馈闭环分析。"""
    result = {
        'alertLevel': 'HIGH',
        'fallScore': 0.82,
        'painScore': 0.31,
        'fallInfo': {
            'fallState': 'confirmed_fall',
            'postureType': 'fall_like',
            'evidenceMode': 'pose_expression',
            'confirmedFallAt': 1760000000.0,
        },
    }
    pred = build_prediction(result)
    assert pred['postureType'] == 'fall_like'
    assert pred['evidenceMode'] == 'pose_expression'
    assert pred['fallScore'] == 0.82
    assert pred['painScore'] == 0.31


def test_unknown_posture_does_not_override_state_machine():
    """回归护栏：姿态 'unknown' 不得推翻状态机已得出的 normal 结论。

    之前这是用正则匹配源码实现的，一旦判定逻辑重构就失效。改为行为断言：
    直接驱动真实的 _decide_alert_by_state，验证开关的两种行为。
    """
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(root / 'third_party' / 'ultralytics'))
    sys.path.insert(0, str(root))
    from expression_recognition.system import AlertLevel, SmartElderlyCareSystem

    sysm = SmartElderlyCareSystem()          # 不加载权重：只验证决策路径
    belief = {'fall': 0.55, 'unknown': 0.02, 'normal': 0.43}
    fall_info = {
        'status': 'body_detected',
        'posture_type': 'unknown',
        'evidence_mode': 'pose_expression',
        'fall_state': 'normal',
        'fall_like_duration': 0.0,
    }

    sysm.fix_unknown_safe = True
    assert sysm._decide_alert_by_state(belief, fall_info, 0.1, True) == AlertLevel.NORMAL

    # 关掉该修复（消融档位）时必须复现旧行为：落回融合信念回退分支并升到 MEDIUM
    sysm.fix_unknown_safe = False
    assert sysm._decide_alert_by_state(belief, fall_info, 0.1, True) != AlertLevel.NORMAL


def test_motion_features_are_idempotent_within_a_frame():
    """回归护栏：同帧内重复调用 _add_motion_features 不得把速度算成 0。

    process_frame 会先对每个候选人体调用一次、再对选中的人体调用一次，两次
    `now` 相同。修复前第二次调用与第一次刚写入的 track 状态自我求差，恒为 0，
    导致主路径上 rapid_descent 永远为 False（实测 497 帧跌倒证据中 0 帧触发）。
    """
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(root / 'third_party' / 'ultralytics'))
    sys.path.insert(0, str(root))
    import expression_recognition.system as sysmod
    from expression_recognition.system import SmartElderlyCareSystem

    sysm = SmartElderlyCareSystem()
    # 固定时钟：模拟 process_frame 在一帧内用同一个 now 调用两次
    real_time = sysmod.time.time
    sysmod.time.time = lambda: 12345.0
    try:
        track = {
            'body_box': [0, 0, 10, 10], 'center_y': 0.20, 'torso_angle': 0.0,
            'last_seen': 12345.0 - 0.2,      # 上一帧在 0.2s 前
        }

        first = {'status': 'body_detected', 'body_box': [0, 0, 10, 10],
                 'center_y_ratio': 0.80, 'torso_angle': 80.0}
        sysm._add_motion_features(first, track)
        assert first['center_y_velocity'] > 0.05, '首次调用应算出真实下坠速度'
        assert first['rapid_descent'] is True

        # 同一帧内（now 不变）的第二次调用必须复用同一结论，而不是算成 0
        second = {'status': 'body_detected', 'body_box': [0, 0, 10, 10],
                  'center_y_ratio': 0.80, 'torso_angle': 80.0}
        sysm._add_motion_features(second, track)
        assert second['center_y_velocity'] == first['center_y_velocity']
        assert second['rapid_descent'] is True
    finally:
        sysmod.time.time = real_time
