"""Pure statistical helpers for the /python/statistics endpoints.

These four endpoints previously returned hard-coded empty results
(``{'items': []}`` / ``{'score': 0}``), so any UI that used them showed fake
empty charts. They now compute real values.
"""
from __future__ import annotations

import math
from typing import Any

from app.core.database import db


def _extract_values(data: Any) -> list[float]:
    values: list[float] = []
    for item in data or []:
        raw = item.get('value') if isinstance(item, dict) else item
        try:
            values.append(float(raw))
        except (TypeError, ValueError):
            values.append(0.0)
    return values


def _fit(values: list[float]) -> tuple[float, float]:
    """Least-squares (slope, intercept) of values against their index."""
    n = len(values)
    mean_x = sum(range(n)) / n
    mean_y = sum(values) / n
    sxx = sum((x - mean_x) ** 2 for x in range(n))
    sxy = sum((x - mean_x) * (y - mean_y) for x, y in enumerate(values))
    slope = sxy / sxx if sxx else 0.0
    return slope, mean_y - slope * mean_x


def linear_trend(data: Any) -> dict[str, Any]:
    """Trend direction + slope + R² confidence."""
    values = _extract_values(data)
    n = len(values)
    if n < 2:
        return {'trend': 'flat', 'slope': 0.0, 'confidence': 0.0, 'points': n}
    slope, intercept = _fit(values)
    mean_y = sum(values) / n
    ss_tot = sum((y - mean_y) ** 2 for y in values)
    ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in enumerate(values))
    r2 = 1 - ss_res / ss_tot if ss_tot > 1e-12 else 0.0
    trend = 'rising' if slope > 1e-9 else 'falling' if slope < -1e-9 else 'flat'
    return {
        'trend': trend,
        'slope': round(slope, 4),
        'confidence': round(max(0.0, min(1.0, r2)), 4),
        'points': n,
    }


def detect_anomalies(data: Any, threshold: float = 2.0) -> dict[str, Any]:
    """Z-score outliers."""
    values = _extract_values(data)
    n = len(values)
    if n < 3:
        return {'anomalies': [], 'mean': 0.0, 'std': 0.0, 'points': n}
    mean = sum(values) / n
    std = math.sqrt(sum((v - mean) ** 2 for v in values) / n)
    anomalies = []
    if std > 1e-9:
        for i, v in enumerate(values):
            z = (v - mean) / std
            if abs(z) >= float(threshold):
                anomalies.append({'index': i, 'value': round(v, 4), 'zscore': round(z, 3)})
    return {'anomalies': anomalies, 'mean': round(mean, 4), 'std': round(std, 4), 'points': n}


def predict_linear(data: Any, periods: int = 7) -> dict[str, Any]:
    """Linear extrapolation of the series."""
    values = _extract_values(data)
    n = len(values)
    periods = max(0, min(int(periods or 0), 365))
    if n < 2:
        base = values[-1] if values else 0.0
        return {'predictions': [round(base, 4)] * periods, 'method': 'flat', 'slope': 0.0}
    slope, intercept = _fit(values)
    predictions = [round(max(0.0, slope * (n + i) + intercept), 4) for i in range(periods)]
    return {'predictions': predictions, 'method': 'linear', 'slope': round(slope, 4)}


_RISK_WEIGHTS = {'LOW': 1, 'MEDIUM': 2, 'HIGH': 3, 'URGENT': 4}
_RISK_LEVELS = [(0.75, 'URGENT'), (0.55, 'HIGH'), (0.30, 'MEDIUM'), (0.0, 'LOW')]


def elder_risk_score(elder_id: int, days: int = 30, *,
                     tenant_id: int) -> dict[str, Any]:
    """Risk score for one elder from their alert history (weighted by severity).

    ``tenant_id`` 是**必填的关键字参数**，没有默认值 —— 让"忘记传租户"在调用点
    直接抛 TypeError，而不是静默地跨机构统计。给一个 ``None`` 默认值看起来更
    兼容，但它把一次编译期能发现的错误变成了运行期的静默错误。
    """
    where = 'elder_id=%s AND tenant_id=%s'
    params: list[Any] = [elder_id, tenant_id, max(1, min(int(days or 30), 365))]
    rows = db.query(
        'SELECT risk_level, COUNT(*) AS c FROM alerts '
        f'WHERE {where} AND alert_time >= DATE_SUB(NOW(), INTERVAL %s DAY) '
        'GROUP BY risk_level',
        params,
    )
    counts = {str(r['risk_level']).upper(): int(r['c']) for r in rows}
    total = sum(counts.values())
    if total == 0:
        return {'score': 0.0, 'level': 'LOW', 'factors': [], 'alertCount': 0, 'days': days}

    weighted = sum(_RISK_WEIGHTS.get(level, 1) * c for level, c in counts.items())
    # normalise: 1 urgent alert alone -> 4/4 = 1.0 only if all are urgent
    severity = weighted / (4 * total)          # 0..1
    volume = min(1.0, total / 10.0)            # 10+ alerts saturates
    score = round(min(1.0, 0.75 * severity + 0.25 * volume), 4)
    level = next(name for floor, name in _RISK_LEVELS if score >= floor)
    factors = [
        {'name': f'{lvl} 告警', 'count': c, 'weight': _RISK_WEIGHTS.get(lvl, 1)}
        for lvl, c in sorted(counts.items(), key=lambda kv: -_RISK_WEIGHTS.get(kv[0], 1))
    ]
    return {'score': score, 'level': level, 'factors': factors,
            'alertCount': total, 'days': days}
