"""Tests for the alert-level persistence mapping.

Root cause under test: the detection pipeline emits five levels
(NORMAL / LOW / MEDIUM / HIGH / URGENT), but the alert-storage path used to
collapse URGENT into HIGH, silently downgrading an emergency in the alert
history. ``stored_risk_level`` is the single source of truth that must NOT
collapse URGENT.

Run:  cd system_code/backend-python && .venv/bin/python -m pytest tests/test_alert_levels.py
"""

from app.services.alert_levels import stored_risk_level


def test_urgent_is_preserved_not_downgraded():
    """The core regression: URGENT must survive persistence as URGENT."""
    assert stored_risk_level("URGENT") == "URGENT"


def test_high_medium_low_pass_through():
    assert stored_risk_level("HIGH") == "HIGH"
    assert stored_risk_level("MEDIUM") == "MEDIUM"
    assert stored_risk_level("LOW") == "LOW"


def test_normal_is_not_stored():
    """NORMAL events are not alerts and must not be persisted."""
    assert stored_risk_level("NORMAL") is None


def test_case_insensitive():
    assert stored_risk_level("urgent") == "URGENT"
    assert stored_risk_level("High") == "HIGH"


def test_blank_and_none_are_not_stored():
    assert stored_risk_level("") is None
    assert stored_risk_level(None) is None


def test_unknown_level_is_not_stored():
    assert stored_risk_level("CRITICAL") is None
    assert stored_risk_level("EXTREME") is None
