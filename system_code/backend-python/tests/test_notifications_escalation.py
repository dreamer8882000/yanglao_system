"""Tests for notifications hub, escalation rule and audit payload handling."""
import json
import queue

from app.services import audit as audit_mod
from app.services.escalation import next_level, RISK_ORDER
from app.services.notifications import NotificationHub, notify_alert, notify_confirmed

#: hub 现在**按租户分发**（原实现是全局广播，会把 A 机构的告警推给 B 机构 —— 实测确认过的泄露）。
#: 因此订阅与发布都必须带租户；不带租户的 publish 默认不送达任何人。
TENANT = 1


# ── notifications ───────────────────────────────────────────────────────────
def test_hub_publish_only_reaches_subscribers():
    hub = NotificationHub()
    q = hub.subscribe(TENANT)
    assert hub.subscriber_count == 1
    delivered = hub.publish('alert', {'id': 1}, tenant_id=TENANT)
    assert delivered == 1
    event, data = q.get_nowait()
    assert event == 'alert'
    assert data == {'id': 1}


def test_hub_unsubscribe_stops_delivery():
    hub = NotificationHub()
    q = hub.subscribe(TENANT)
    hub.unsubscribe(q)
    assert hub.subscriber_count == 0
    assert hub.publish('alert', {'id': 2}, tenant_id=TENANT) == 0


def test_hub_full_queue_does_not_raise():
    """A stuck client must not break the alert path."""
    hub = NotificationHub()
    hub.subscribe(TENANT)          # never drained
    for i in range(200):
        hub.publish('alert', {'id': i}, tenant_id=TENANT)   # must not raise


def test_notify_helpers_publish_expected_events():
    hub = NotificationHub()
    q = hub.subscribe(TENANT)
    # module-level helpers use the module-level hub; publish directly to compare shape
    hub.publish('confirmed', {'alert': {'id': 3}}, tenant_id=TENANT)
    event, data = q.get_nowait()
    assert event == 'confirmed'
    assert data['alert']['id'] == 3


# ── escalation rule ─────────────────────────────────────────────────────────
def test_next_level_steps_up():
    assert next_level('LOW') == 'MEDIUM'
    assert next_level('MEDIUM') == 'HIGH'
    assert next_level('HIGH') == 'URGENT'


def test_next_level_caps_at_urgent():
    assert next_level('URGENT') == 'URGENT'


def test_next_level_handles_unknown():
    assert next_level(None) == 'MEDIUM'
    assert next_level('garbage') == 'MEDIUM'


def test_risk_order_is_monotone():
    assert RISK_ORDER == ['LOW', 'MEDIUM', 'HIGH', 'URGENT']


# ── audit payload ───────────────────────────────────────────────────────────
def test_client_ip_prefers_forwarded_header(monkeypatch):
    monkeypatch.setenv('TRUST_PROXY_HEADERS', 'true')
    class Headers(dict):
        def get(self, k, d=None):
            return super().get(k.lower(), d)

    class Req:
        headers = Headers({'x-forwarded-for': '1.2.3.4, 5.6.7.8'})
        client = type('C', (), {'host': '9.9.9.9'})()

    assert audit_mod.client_ip(Req()) == '1.2.3.4'


def test_client_ip_ignores_forwarded_by_default(monkeypatch):
    monkeypatch.delenv('TRUST_PROXY_HEADERS', raising=False)

    class Headers(dict):
        def get(self, k, d=None):
            return super().get(k.lower(), d)

    class Req:
        headers = Headers({'x-forwarded-for': '1.2.3.4, 5.6.7.8'})
        client = type('C', (), {'host': '9.9.9.9'})()

    assert audit_mod.client_ip(Req()) == '9.9.9.9'


def test_client_ip_none_request():
    assert audit_mod.client_ip(None) is None


def test_record_audit_swallows_db_failure(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError('db down')

    monkeypatch.setattr(audit_mod.db, 'insert', boom)
    assert audit_mod.record_audit('测试', user={'id': 1, 'username': 'u'}) is False


def test_record_audit_serialises_detail(monkeypatch):
    captured = {}

    def fake_insert(sql, params):
        captured['params'] = params
        return 1

    monkeypatch.setattr(audit_mod.db, 'insert', fake_insert)
    ok = audit_mod.record_audit('登录成功', user={'id': 7, 'username': 'admin', 'tenantId': 3},
                                resource_type='auth', detail={'role': 'admin'})
    assert ok is True
    # 参数顺序：tenant_id 在最前（多租户后新增的首列）
    tid, _uid, uname, action, rtype, rid, detail, ip = captured['params']
    assert tid == 3, '审计行必须带上发起者所属机构'
    assert _uid == 7 and uname == 'admin' and action == '登录成功'
    assert json.loads(detail) == {'role': 'admin'}


def test_record_audit_falls_back_to_explicit_tenant(monkeypatch):
    """登录失败这类尚无登录用户的审计，必须靠显式 tenant_id 落库。

    否则 tenant_id 为 NULL，而审计列表是按 tenant_id 过滤的 ——
    那条"有人在反复试密码"的记录任何机构都看不到。
    """
    captured = {}

    def fake_insert(sql, params):
        captured['params'] = params
        return 1

    monkeypatch.setattr(audit_mod.db, 'insert', fake_insert)
    assert audit_mod.record_audit('登录失败', username='ghost', tenant_id=5) is True
    assert captured['params'][0] == 5


def test_tenant_of_username_resolves_org(monkeypatch):
    monkeypatch.setattr(audit_mod.db, 'query_one',
                        lambda sql, params=None: {'tenant_id': 2})
    assert audit_mod.tenant_of_username('hx_admin') == 2
    assert audit_mod.tenant_of_username(None) is None
