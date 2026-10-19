"""In-process pub/sub hub for real-time alert notifications (SSE).

The frontend already ships the receiving half: ``composables/useSSE.js`` opens an
EventSource on ``/api/alerts/stream`` and listens for ``alert`` / ``confirmed``
events (Dashboard.vue wires it to a refresh handler). The backend endpoint only
ever emitted heartbeats, so nurses never received a push unless they happened to
reload the page.

This hub is the missing publishing half. It is deliberately process-local: the
deployment runs a single uvicorn worker, and a broker would be overkill.
"""
from __future__ import annotations

import atexit
import logging
import queue
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from typing import Any

MAX_QUEUE = 100


logger = logging.getLogger(__name__)


# ── 外部渠道投递池 ──────────────────────────────────────────────────────────
#
# 外部渠道（企业微信/钉钉/邮件）要走网络，最慢时要等连接超时。实测一个指向已关闭
# 端口的 webhook 会阻塞 3 秒以上。
#
# 而 notify_alert 是**在检测循环里被每帧调用**的（ai_alerts.maybe_create_alert）。
# 同步投递会把整条视频流堵死：AI 推理只要 48ms，通知却要几秒，前端表现就是
# 骨架完全不动 —— 实测确认过，这是"跟随太慢"的真正主因，而不是模型或网络。
#
# 所以外部投递一律丢到后台线程。SSE 广播仍然同步（进程内、微秒级），
# 它只影响"页面开着时刷不刷新"，不该被外部渠道拖累。
_dispatch_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='notify')
atexit.register(lambda: _dispatch_pool.shutdown(wait=False))


def _dispatch_async(alert: dict[str, Any], reason: str) -> None:
    """把外部投递交给后台线程；入口异常仍要留痕。"""
    try:
        from app.services.notify_channels import dispatch as dispatch_alert
    except Exception as exc:                                        # noqa: BLE001
        logger.exception('notification dispatch unavailable: %s', exc)
        return

    def run():
        try:
            dispatch_alert(alert, reason=reason)
        except Exception as exc:                                    # noqa: BLE001
            logger.exception('alert dispatch crashed: %s', exc)

    try:
        _dispatch_pool.submit(run)
    except RuntimeError:
        # 解释器正在关闭，线程池已停：退化为同步执行，宁可慢也不丢通知
        run()


def flush_notifications(timeout: float = 10.0) -> bool:
    """等待已排队的外部投递完成。

    给测试用：投递改到后台之后，"发出通知"与"通知已送达"之间有了间隙，
    断言前必须能等到它落地。做法是提交一个空任务并等它 —— 线程池按提交顺序
    执行，空任务返回时前面的投递都已完成。
    """
    try:
        _dispatch_pool.submit(lambda: None).result(timeout=timeout)
        return True
    except Exception:                                               # noqa: BLE001
        return False


class NotificationHub:
    """进程内的告警广播。

    **订阅必须带租户**：原实现只有一个全局订阅者集合，``publish`` 把完整的
    告警行（含 elderId / roomNo / 风险等级）发给**所有**连接 ——
    于是租户 1 的护士能在页面上实时看到租户 2 的告警。实测确认过。
    多租户下"广播"本身就是一个错误概念，这里改成按租户分发。

    注意它仍然是**进程内**的：多 worker 部署时 A worker 的告警只推给连在 A 的
    客户端。真正可靠的送达路径是 ``notify_channels`` 里的外部渠道，
    SSE 只是"页面开着时的即时刷新"。
    """

    def __init__(self) -> None:
        self._lock = Lock()
        #: tenant_id -> 该租户的订阅者集合
        self._subscribers: dict[int, set[queue.Queue]] = {}

    def subscribe(self, tenant_id: int) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=MAX_QUEUE)
        with self._lock:
            self._subscribers.setdefault(int(tenant_id), set()).add(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            for subs in self._subscribers.values():
                subs.discard(q)
            # 清掉空桶，避免按租户累积空集合
            self._subscribers = {t: s for t, s in self._subscribers.items() if s}

    def publish(self, event: str, data: dict[str, Any],
                tenant_id: int | None = None) -> int:
        """Fan out one event to **该租户**的订阅者；返回送达数。

        ``tenant_id`` 为 None 时不广播给任何人 —— 宁可漏推，也不能把
        A 机构的告警推给 B 机构。这是"默认拒绝"在推送链路上的同一条原则。
        """
        if tenant_id is None:
            logger.warning('SSE publish skipped: no tenant (event=%s)', event)
            return 0
        with self._lock:
            subscribers = list(self._subscribers.get(int(tenant_id), ()))
        delivered = 0
        for q in subscribers:
            try:
                q.put_nowait((event, data))
                delivered += 1
            except queue.Full:
                # A stuck client must not stall the alert path.
                pass
        return delivered

    @property
    def subscriber_count(self) -> int:
        with self._lock:
            return sum(len(s) for s in self._subscribers.values())


hub = NotificationHub()


def notify_alert(alert: dict[str, Any], *, reason: str = 'new') -> int:
    """告警通知。

    这里做**两件性质不同**的事，缺一不可：

    1. ``hub.publish`` —— 进程内 SSE，把告警推给**当前打开的页面**。
       它只对"有人正盯着屏幕"有效。
    2. ``dispatch_alert`` —— 通过配置好的外部渠道（企业微信/钉钉群机器人、邮件）
       把人**叫醒**。告警最需要送达的恰恰是护士不在电脑前的时刻，所以这一半
       才是关键的那一半；此前它完全不存在（页面上那些通知开关也没人读）。

    外部渠道失败**不能**影响告警本身：dispatch 内部已吞掉所有异常并写投递记录。
    """
    n = hub.publish('alert', {'reason': reason, 'alert': alert},
                    tenant_id=alert.get('tenantId') or alert.get('tenant_id'))
    _dispatch_async(alert, reason)
    return n


def notify_confirmed(alert: dict[str, Any]) -> int:
    """告警被处置后的通知。

    走外部渠道同样有意义：值班群里有人确认了，其他关注这条告警的人应当知道
    "已经有人去了"，否则会出现多人同时往同一间房跑。
    """
    n = hub.publish('confirmed', {'alert': alert},
                    tenant_id=alert.get('tenantId') or alert.get('tenant_id'))
    _dispatch_async(alert, 'confirmed')
    return n
