"""「这是哪位老人」——身份推导必须在不确定时**明确说不确定**。

这个测试守的是一个曾经真实存在的缺陷：
`resolve_elder_by_camera` 用 `ORDER BY e.id LIMIT 1` 推导身份。一人一房时它是
对的；一旦多人同房，它会**永远**挑 id 较小的那位 —— 不报错、不告警、界面上也
看不出来，只是每次告警都可能挂在错误的老人名下。

所以这里的重点不是"能推出身份"，而是**推不出来时不要编一个**：
  * 单人房 → elder_id + method='room_single'
  * 双人/三人房 → **elder_id 为 None** + method='ambiguous' + 候选名单
  * 空房 → method='unmatched'（而不是当成"没人"，那是两回事）
"""
from __future__ import annotations

import json
import time

import pytest

from app.core.database import db
from app.services.ai_alerts import (build_prediction, maybe_create_alert,
                                    resolve_elder_by_camera,
                                    resolve_identity_by_camera)


@pytest.fixture(autouse=True)
def _cleanup_test_alerts():
    """测试产生的告警不能留在库里 —— 它们会出现在「告警中心」，
    也会被误报率等统计算进去，让演示数据变得无法解释。
    """
    yield
    # LIKE 模式必须走参数：直接写在 SQL 里的话，其中的 % 会被 PyMySQL 当成
    # 格式化占位符，抛 "not enough arguments for format string"。
    db.execute("DELETE FROM alerts WHERE identity_method='ambiguous' "
               "AND handler_notes LIKE %s", ['%姿态 fall_like%'])


def _camera_in_room(tenant_id: int, room_no: str) -> dict | None:
    return db.query_one('SELECT id, room_no FROM cameras WHERE tenant_id=%s AND room_no=%s LIMIT 1',
                        [tenant_id, room_no])


def _room_with(tenant_id: int, occupants: int) -> str | None:
    """找一个正好住 ``occupants`` 位在册老人的房间。"""
    row = db.query_one(
        'SELECT room_no FROM elders WHERE tenant_id=%s AND status=1 '
        'GROUP BY room_no HAVING COUNT(*)=%s ORDER BY room_no LIMIT 1',
        [tenant_id, occupants])
    return row['room_no'] if row else None


def test_single_occupancy_resolves_to_that_elder() -> None:
    room = _room_with(1, 1)
    cam = _camera_in_room(1, room) if room else None
    if not cam:
        pytest.skip(f'租户1 的 {room} 室没有摄像头，无法验证')
    res = resolve_identity_by_camera(cam['id'], 1)
    assert res['method'] == 'room_single'
    assert res['elderId'] is not None
    assert res['confidence'] == 1.0
    assert res['candidates'] == []
    # 兼容包装应返回同一个 id
    assert resolve_elder_by_camera(cam['id'], 1) == res['elderId']


@pytest.mark.parametrize('occupants', [2, 3])
def test_multi_occupancy_refuses_to_guess(occupants: int) -> None:
    room = _room_with(1, occupants)
    cam = _camera_in_room(1, room) if room else None
    if not cam:
        pytest.skip(f'租户1 没有 {occupants} 人间的摄像头，无法验证')

    res = resolve_identity_by_camera(cam['id'], 1)

    # 核心断言：**不猜**。老实现会在这里返回 id 最小的那位。
    assert res['elderId'] is None, '多人同房仍然给出了 elder_id —— 又在瞎猜'
    assert res['method'] == 'ambiguous'
    assert res['confidence'] < 1.0, '身份不确定时置信度不能是满分'
    assert len(res['candidates']) == occupants
    assert {c['bedNo'] for c in res['candidates']} == set(range(1, occupants + 1))

    # 兼容包装同样必须返回 None，避免老调用方悄悄拿到一个猜出来的 id
    assert resolve_elder_by_camera(cam['id'], 1) is None


def test_no_camera_returns_no_camera() -> None:
    res = resolve_identity_by_camera(None)
    assert res['elderId'] is None and res['method'] == 'no_camera'


def _fall_result() -> dict:
    return {
        'fallScore': 0.82, 'painScore': 0.61, 'alertLevel': 'HIGH',
        'fallInfo': {'fallState': 'confirmed_fall', 'postureType': 'fall_like',
                     'evidenceMode': 'pose_expression', 'poseQuality': 0.88,
                     'torsoAngle': 71.5, 'kneeHipRatio': 1.35, 'rapidDescent': True,
                     'trackId': 3, 'confirmedFallAt': time.time()},
        'expressionTop': 'Disgust', 'expressionConfidence': 0.74, 'exprQuality': 0.66,
        'faceAvailable': True, 'faceMethod': 'keypoint+aligned',
        'beliefFall': 0.79, 'beliefUnknown': 0.12,
    }


@pytest.mark.parametrize('room,occupants', [(None, 2), (None, 3)])
def test_alert_row_carries_identity_verdict(room, occupants) -> None:
    """告警落库时必须把身份结论一起写进去 —— 否则"不确定"这件事就丢了。"""
    room = _room_with(1, occupants)
    cam = _camera_in_room(1, room) if room else None
    if not cam:
        pytest.skip(f'租户1 没有 {occupants} 人间的摄像头，无法验证')

    result = _fall_result()
    alert = maybe_create_alert(result, cam['id'], tenant_id=1)
    assert alert is not None, '未能生成告警（去重窗口内可能有旧告警，重跑一次）'

    row = db.query_one('SELECT elder_id, identity_method, identity_confidence, '
                       'identity_candidates FROM alerts WHERE id=%s', [alert['id']])
    assert row['elder_id'] is None
    assert row['identity_method'] == 'ambiguous'
    assert float(row['identity_confidence']) == 0.0
    # PyMySQL 把 JSON 列读成字符串，所以这里显式解析
    candidates = json.loads(row['identity_candidates'])
    assert len(candidates) == occupants
    assert all({'id', 'name', 'bedNo'} <= set(c) for c in candidates)
