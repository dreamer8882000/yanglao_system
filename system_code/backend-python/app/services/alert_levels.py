"""Alert-level persistence mapping (single source of truth).

The detection pipeline emits five levels: NORMAL / LOW / MEDIUM / HIGH / URGENT.
Only LOW/MEDIUM/HIGH/URGENT are persisted as alerts; NORMAL is not an alert.

The previous implementation collapsed URGENT into HIGH when writing to the
alerts table, silently downgrading emergencies in the alert history. This
module exists so that mapping lives in one testable place and URGENT survives
persistence intact.
"""

# Levels that are persisted into the alerts table.
STORABLE_LEVELS = {"LOW", "MEDIUM", "HIGH", "URGENT"}


def stored_risk_level(risk_level) -> str | None:
    """Return the level to persist for a detection risk level, or None.

    - URGENT/HIGH/MEDIUM/LOW are returned as-is (case-normalised to upper).
    - NORMAL and anything unrecognised/blank/None return None (not persisted).
    """
    level = str(risk_level or "").strip().upper()
    return level if level in STORABLE_LEVELS else None
