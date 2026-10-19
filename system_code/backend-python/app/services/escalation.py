"""Timeout escalation for unhandled alerts.

``alerts.escalated_at`` existed in the schema but no code ever wrote it, and
``APScheduler`` was a declared dependency with no scheduler running — so the
"unhandled alert auto-escalates" promise was never implemented. This module
provides the escalation rule and the periodic job that applies it.
"""
from __future__ import annotations

import logging
from typing import Any

from app.core.database import db
from app.repositories.base import keys_to_camel
from app.services.notifications import notify_alert

logger = logging.getLogger(__name__)

RISK_ORDER = ['LOW', 'MEDIUM', 'HIGH', 'URGENT']
ESCALATION_NOTE_MAX = 60


def next_level(level: str | None) -> str:
    """One severity step up, capped at URGENT."""
    current = str(level or '').upper()
    if current not in RISK_ORDER:
        return 'MEDIUM'
    return RISK_ORDER[min(RISK_ORDER.index(current) + 1, len(RISK_ORDER) - 1)]


def escalate_stale_alerts(after_minutes: int = 10, lookback_hours: int = 24) -> list[dict[str, Any]]:
    """Escalate every still-unhandled alert older than ``after_minutes``.

    Escalation happens at most once per alert (``escalated_at IS NULL`` guard),
    so a long-ignored alert is not bumped to URGENT on every tick.

    ``lookback_hours`` bounds how far back the job reaches, so that enabling the
    scheduler does not retro-escalate years of historical rows on first run.
    """
    minutes = max(1, int(after_minutes or 10))
    hours = max(1, int(lookback_hours or 24))
    rows = db.query(
        'SELECT id, risk_level, camera_id, confidence FROM alerts '
        'WHERE status=0 AND escalated_at IS NULL '
        'AND alert_time <= DATE_SUB(NOW(), INTERVAL %s MINUTE) '
        'AND alert_time >= DATE_SUB(NOW(), INTERVAL %s HOUR)',
        [minutes, hours],
    )
    escalated: list[dict[str, Any]] = []
    for row in rows:
        new_level = next_level(row.get('risk_level'))
        note = f'[超时{minutes}分钟未处理，自动升级为{new_level}]'
        db.execute(
            'UPDATE alerts SET risk_level=%s, escalated_at=NOW(), '
            'handler_notes=LEFT(CONCAT(COALESCE(handler_notes, ''), %s), 200) WHERE id=%s',
            [new_level, note, row['id']],
        )
        updated = db.query('SELECT * FROM alerts WHERE id=%s LIMIT 1', [row['id']])
        if updated:
            payload = keys_to_camel(updated[0])
            escalated.append(payload)
            notify_alert(payload, reason='escalated_timeout')
    if escalated:
        logger.info('escalated %d stale alert(s) (threshold %d min)', len(escalated), minutes)
    return escalated


_scheduler = None


def start_scheduler(interval_minutes: int = 5, after_minutes: int = 10,
                    lookback_hours: int = 24):
    """Start the periodic escalation job (idempotent)."""
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    try:
        from apscheduler.schedulers.background import BackgroundScheduler

        scheduler = BackgroundScheduler()
        scheduler.add_job(
            escalate_stale_alerts,
            'interval',
            minutes=max(1, int(interval_minutes or 5)),
            args=[after_minutes, lookback_hours],
            id='escalate_stale_alerts',
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        scheduler.start()
        _scheduler = scheduler
        logger.info('escalation scheduler started (every %s min, threshold %s min, lookback %s h)',
                    interval_minutes, after_minutes, lookback_hours)
    except Exception as exc:  # noqa: BLE001 - never block startup
        logger.warning('escalation scheduler unavailable: %s', exc)
    return _scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        try:
            _scheduler.shutdown(wait=False)
        except Exception:
            pass
        _scheduler = None
