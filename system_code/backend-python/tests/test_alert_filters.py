"""Alert-list filter parsing + request metrics.

Root cause under test: the Alerts page sends its filter form verbatim, so unset
filters arrive as empty strings (``?status=&startDate=&endDate=``). The route
declared ``status: int | None``, so '' failed int parsing and FastAPI returned
422 for the ENTIRE list. The date filters were also silently ignored.
"""
from app.api.routes.alerts import _alert_filters, _clean
from app.core.metrics import RequestMetrics


def test_clean_normalises_empty_to_none():
    assert _clean('') is None
    assert _clean('   ') is None
    assert _clean(None) is None
    assert _clean('HIGH') == 'HIGH'


def test_empty_filters_produce_no_where_clause():
    sql, args = _alert_filters('', '', '', '')
    assert sql == '', f"空筛选不应生成 WHERE，实际 {sql!r}"
    assert args == []


def test_status_parsed_from_string():
    sql, args = _alert_filters('0')
    assert 'a.status=%s' in sql
    assert args == [0]


def test_invalid_status_is_ignored_not_fatal():
    sql, args = _alert_filters('abc')
    assert sql == ''
    assert args == []


def test_date_range_filter():
    sql, args = _alert_filters(None, None, '2026-01-01', '2026-01-31')
    assert 'a.alert_time >= %s' in sql
    assert 'a.alert_time <= %s' in sql
    assert args == ['2026-01-01 00:00:00', '2026-01-31 23:59:59']


def test_risk_level_is_upper_cased():
    sql, args = _alert_filters(None, 'high')
    assert 'a.risk_level=%s' in sql
    assert args == ['HIGH']


def test_request_metrics_counts_success_and_error():
    m = RequestMetrics()
    m.record(200, 10.0)
    m.record(404, 20.0)
    m.record(500, 30.0)
    snap = m.snapshot()
    assert snap['total'] == 3
    assert snap['success'] == 1
    assert snap['error'] == 2
    assert snap['avgResponseTime'] == 20.0
