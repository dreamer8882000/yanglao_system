"""回归护栏：状态机确认路径 + 遮挡存活（M2 根因修复的守卫）。"""
import sys
from pathlib import Path

import pytest


@pytest.fixture()
def sysmod():
    root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(root / 'third_party' / 'ultralytics'))
    sys.path.insert(0, str(root))
    import expression_recognition.system as m
    return m


@pytest.fixture()
def system(sysmod):
    return sysmod.SmartElderlyCareSystem()


def _drive(system, sysmod, frames, start=1000.0, clock=None):
    """按冻结证据的形态驱动真实状态机。frames: list of (dt, dict)。"""
    state = {'t': start}
    sysmod.time.time = lambda: state['t']
    track = {}
    seen = []
    belief = {'fall': 0.9, 'unknown': 0.1}
    for dt, fi in frames:
        state['t'] += dt
        base = {'status': 'body_detected', 'pose_quality': 0.95, 'fall_score': 0.0,
                'rapid_descent': False, 'posture_type': 'sitting'}
        base.update(fi)
        st, _, _ = system._update_fall_state(
            base, base['fall_score'], 0.0, True, track, fused=belief)
        seen.append(st)
    return seen


def test_confirmation_is_reachable(system, sysmod):
    """一次真实的跌倒转移必须能走到 confirmed_fall。

    修复前，rapid_descent 恒为 False、且不确定度阈值数学上不可达，
    全部 30 段 URFD 跌倒片段确认率恒为 0。
    """
    # 快速下坠 -> 倒地姿态持续
    seen = _drive(system, sysmod, [
        (0.1, {'posture_type': 'sitting', 'fall_score': 0.2}),
        (0.1, {'posture_type': 'fall_like', 'fall_score': 0.9, 'rapid_descent': True}),
        (0.2, {'posture_type': 'fall_like', 'fall_score': 0.95, 'rapid_descent': True}),
        (0.2, {'posture_type': 'fall_like', 'fall_score': 0.97}),
        (0.2, {'posture_type': 'fall_like', 'fall_score': 0.97}),
        (0.2, {'posture_type': 'fall_like', 'fall_score': 0.97}),
        (0.2, {'posture_type': 'fall_like', 'fall_score': 0.97}),
        (0.2, {'posture_type': 'fall_like', 'fall_score': 0.97}),
    ])
    assert 'confirmed_fall' in seen, f'确认路径不可达: {seen}'


def test_body_loss_does_not_erase_a_strong_episode(system, sysmod):
    """强证据 episode 在身体丢失后必须存活（受护栏约束）。

    实测：URFD 跌倒后 7 帧里 5 帧 insufficient_body，旧逻辑在此清空 episode，
    使状态机在关键时刻判定 normal。
    """
    seen = _drive(system, sysmod, [
        (0.1, {'posture_type': 'fall_like', 'fall_score': 0.95, 'rapid_descent': True}),
        (0.2, {'posture_type': 'fall_like', 'fall_score': 0.98}),
        # 人躺在地上，姿态模型丢失人体框
        (0.2, {'status': 'insufficient_body', 'posture_type': 'insufficient_body',
               'pose_quality': 0.0, 'fall_score': 0.0}),
        (0.2, {'status': 'insufficient_body', 'posture_type': 'insufficient_body',
               'pose_quality': 0.0, 'fall_score': 0.0}),
        (0.2, {'status': 'insufficient_body', 'posture_type': 'insufficient_body',
               'pose_quality': 0.0, 'fall_score': 0.0}),
        (0.2, {'status': 'insufficient_body', 'posture_type': 'insufficient_body',
               'pose_quality': 0.0, 'fall_score': 0.0}),
        (0.2, {'status': 'insufficient_body', 'posture_type': 'insufficient_body',
               'pose_quality': 0.0, 'fall_score': 0.0}),
        (0.2, {'status': 'insufficient_body', 'posture_type': 'insufficient_body',
               'pose_quality': 0.0, 'fall_score': 0.0}),
    ])
    assert 'confirmed_fall' in seen, f'身体丢失后 episode 被清空: {seen}'


def test_weak_evidence_does_not_survive_body_loss(system, sysmod):
    """护栏：弱证据不得在身体丢失后继续存活（否则人走出画面也会锁存）。"""
    seen = _drive(system, sysmod, [
        (0.1, {'posture_type': 'bending', 'fall_score': 0.30}),
        (0.2, {'posture_type': 'bending', 'fall_score': 0.35}),
        (0.2, {'status': 'insufficient_body', 'posture_type': 'insufficient_body',
               'pose_quality': 0.0, 'fall_score': 0.0}),
        (0.2, {'status': 'insufficient_body', 'posture_type': 'insufficient_body',
               'pose_quality': 0.0, 'fall_score': 0.0}),
    ])
    assert 'confirmed_fall' not in seen, f'弱证据不应确认: {seen}'


def test_standing_up_ends_the_episode(system, sysmod):
    """护栏：起身必须立即终止 episode。"""
    seen = _drive(system, sysmod, [
        (0.1, {'posture_type': 'fall_like', 'fall_score': 0.9, 'rapid_descent': True}),
        (0.2, {'posture_type': 'fall_like', 'fall_score': 0.9}),
        (0.2, {'posture_type': 'standing', 'fall_score': 0.1}),
        (0.2, {'posture_type': 'standing', 'fall_score': 0.1}),
    ])
    assert seen[-1] in ('normal', 'recovered'), f'起身未终止: {seen}'


def test_unknown_posture_single_spike_does_not_open_episode(system, sysmod):
    """护栏：单帧 fall_score 尖峰 + 非倒地姿态不得开启 episode。

    5 段 ADL 误报中有 3 段正是这样开的（fs 0.72-0.74, posture unknown, 无下坠）。
    """
    seen = _drive(system, sysmod, [
        (0.1, {'posture_type': 'sitting', 'fall_score': 0.2}),
        (0.2, {'posture_type': 'unknown', 'fall_score': 0.74, 'rapid_descent': False}),
        (0.2, {'posture_type': 'sitting', 'fall_score': 0.2}),
        (0.2, {'posture_type': 'sitting', 'fall_score': 0.2}),
    ])
    assert 'confirmed_fall' not in seen and 'suspected_fall' not in seen, \
        f'单帧尖峰不应开启 episode: {seen}'


def test_confirmed_fall_is_not_downgraded_by_missing_evidence(system, sysmod):
    """回归护栏：证据缺失不得推翻状态机已得出的 confirmed_fall 结论。"""
    from expression_recognition.system import AlertLevel
    fall_info = {
        'status': 'insufficient_body',
        'posture_type': 'insufficient_body',
        'evidence_mode': 'no_evidence',
        'fall_state': 'confirmed_fall',
        'fall_like_duration': 2.0,
    }
    lvl = system._decide_alert_by_state({'fall': 0.9, 'unknown': 0.1},
                                        fall_info, 0.0, False)
    assert lvl != AlertLevel.NORMAL, '已确认跌倒被降级为 NORMAL'
    assert lvl in (AlertLevel.HIGH, AlertLevel.URGENT)
