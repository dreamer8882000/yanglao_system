"""告警通知不得阻塞检测循环

这是一次**实测定位到的性能事故**的回归测试。

现象：视频检测页骨架完全不动。
实测：AI 推理只要 48ms（约 20 FPS），但每个检测帧都会经
`ai_alerts.maybe_create_alert` 调 `notify_alert`，而它**同步**调用
`notify_channels.dispatch` —— 那一步要往外部渠道发 HTTP。

当时库里还留着两个端到端测试建的渠道（webhook 指向已关闭的本地端口），
于是每个检测帧都要等连接超时。日志表现：

    notify failed via E2E好渠道(wecom): HTTP 502
    ALL notification channels failed for alert 240 (level=MEDIUM)

**根因不是测试数据，而是"外部投递同步执行"这个设计本身**：任何一个慢的 webhook
（真实网络完全可能）都会把视频管线堵死。所以修法是把外部投递丢到后台线程，
并在这里钉住"调用方耗时与渠道快慢无关"。
"""
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def sloth_channel(monkeypatch):
    """把外部投递换成一个睡 2 秒的假渠道。"""
    calls = []

    def slow_dispatch(alert, reason='new'):
        calls.append((alert, reason))
        time.sleep(2.0)
        return 1

    import app.services.notify_channels as nc
    monkeypatch.setattr(nc, 'dispatch', slow_dispatch)
    return calls


def test_notify_alert_returns_before_dispatch_finishes(sloth_channel):
    """核心断言：渠道睡 2 秒，notify_alert 必须立刻返回。"""
    from app.services.notifications import notify_alert
    alert = {'id': 1, 'tenantId': 1, 'riskLevel': 'HIGH'}
    t0 = time.perf_counter()
    notify_alert(alert, reason='new')
    elapsed = time.perf_counter() - t0
    assert elapsed < 0.5, f'notify_alert 阻塞了 {elapsed:.2f}s，外部投递没有被异步化'


def test_notify_confirmed_also_async(sloth_channel):
    from app.services.notifications import notify_confirmed
    alert = {'id': 2, 'tenantId': 1, 'riskLevel': 'HIGH'}
    t0 = time.perf_counter()
    notify_confirmed(alert)
    elapsed = time.perf_counter() - t0
    assert elapsed < 0.5, f'notify_confirmed 阻塞了 {elapsed:.2f}s'


def test_dispatch_still_happens_in_background(sloth_channel):
    """异步不等于不投递 —— 通知最终必须真的发出去。"""
    from app.services.notifications import flush_notifications, notify_alert
    alert = {'id': 3, 'tenantId': 1, 'riskLevel': 'URGENT'}
    notify_alert(alert, reason='new')
    assert flush_notifications(timeout=10.0)
    assert sloth_channel, '后台投递没有执行'
    assert sloth_channel[0][0]['id'] == 3


def test_a_dead_channel_cannot_stall_the_detection_loop(sloth_channel):
    """模拟"每个检测帧都触发告警"：连发 20 次也不该累积成几十秒。"""
    from app.services.notifications import notify_alert
    alert = {'id': 4, 'tenantId': 1, 'riskLevel': 'HIGH'}
    t0 = time.perf_counter()
    for _ in range(20):
        notify_alert(alert, reason='new')
    elapsed = time.perf_counter() - t0
    # 同步实现下这里是 20 × 2s = 40s
    assert elapsed < 1.0, f'20 次告警耗时 {elapsed:.2f}s，说明投递仍同步在检测路径上'


def test_dispatch_entry_failure_does_not_break_alerting(monkeypatch):
    """渠道模块整个不可用时，告警本身仍要成功返回（SSE 那一半不受影响）。"""
    import app.services.notify_channels as nc

    def boom(*a, **k):
        raise RuntimeError('渠道模块炸了')

    monkeypatch.setattr(nc, 'dispatch', boom)
    from app.services.notifications import flush_notifications, notify_alert
    alert = {'id': 5, 'tenantId': 1, 'riskLevel': 'HIGH'}
    assert notify_alert(alert, reason='new') >= 0
    flush_notifications(timeout=5.0)
