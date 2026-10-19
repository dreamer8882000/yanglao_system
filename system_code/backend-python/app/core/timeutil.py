"""Time helpers — one canonical source for Python-side timestamps.

The operational timebase of this system is the machine's LOCAL timezone
(MySQL ``CURRENT_TIMESTAMP`` / ``NOW()`` stores local wall-clock time without
an offset, and the frontend parses those strings as local time).

macOS Python often fails to detect the system timezone in subprocesses
(``datetime.now().astimezone()`` returns UTC), which would make every
Python-side timestamp 8 hours behind the database in China-timezone
deployments. ``local_now()`` therefore uses an *explicit* timezone from
``TIMEZONE`` (default ``Asia/Shanghai``), so the result is deterministic and
independent of the process environment.
"""

import os
from datetime import datetime
from zoneinfo import ZoneInfo

DEFAULT_TIMEZONE = "Asia/Shanghai"


def configured_tz() -> ZoneInfo:
    """Resolve the deployment timezone (configurable via TIMEZONE env)."""
    name = os.getenv("TIMEZONE", DEFAULT_TIMEZONE).strip() or DEFAULT_TIMEZONE
    return ZoneInfo(name)


def local_now() -> datetime:
    """Current wall-clock time in the configured timezone, with offset."""
    return datetime.now(configured_tz())
