"""Tests for the /python/statistics helpers (previously empty stubs)."""
from app.services.statistics import (
    detect_anomalies,
    linear_trend,
    predict_linear,
)


def test_linear_trend_rising():
    out = linear_trend([{'value': v} for v in (1, 2, 3, 4, 5)])
    assert out['trend'] == 'rising'
    assert out['slope'] == 1.0
    assert out['confidence'] == 1.0


def test_linear_trend_falling():
    out = linear_trend([5, 4, 3, 2, 1])
    assert out['trend'] == 'falling'
    assert out['slope'] == -1.0


def test_linear_trend_flat_and_short():
    assert linear_trend([3, 3, 3])['trend'] == 'flat'
    assert linear_trend([3])['trend'] == 'flat'
    assert linear_trend([])['confidence'] == 0.0


def test_detect_anomalies_finds_outlier():
    out = detect_anomalies([1, 1, 1, 1, 1, 1, 100], threshold=2.0)
    assert len(out['anomalies']) == 1
    assert out['anomalies'][0]['index'] == 6
    assert out['anomalies'][0]['zscore'] > 2


def test_detect_anomalies_ignores_uniform_series():
    out = detect_anomalies([5, 5, 5, 5, 5])
    assert out['anomalies'] == []


def test_predict_linear_extrapolates():
    out = predict_linear([1, 2, 3, 4], periods=3)
    assert out['predictions'] == [5.0, 6.0, 7.0]
    assert out['method'] == 'linear'


def test_predict_linear_clamps_negative():
    out = predict_linear([10, 5, 0], periods=4)
    assert all(p >= 0 for p in out['predictions'])


def test_predict_linear_short_series():
    out = predict_linear([7], periods=3)
    assert out['predictions'] == [7.0, 7.0, 7.0]
    assert out['method'] == 'flat'
