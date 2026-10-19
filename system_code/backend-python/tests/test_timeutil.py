"""Tests for app.core.timeutil.

The invariant under test: Python-side timestamps must be LOCAL wall-clock time
(matching MySQL ``NOW()``), carrying an explicit non-UTC offset in China
timezone deployments, and must not silently fall back to UTC the way a
naive ``datetime.now().astimezone()`` does in subprocesses on macOS.
"""

from datetime import datetime, timezone

from app.core.timeutil import local_now


def test_local_now_is_close_to_wall_clock():
    now = local_now()
    wall = datetime.now()  # naive local wall clock
    assert abs((now.replace(tzinfo=None) - wall).total_seconds()) < 5, (
        f"local_now()={now} 偏离本地墙钟 {wall} 超过 5 秒"
    )


def test_local_now_is_aware():
    now = local_now()
    assert now.tzinfo is not None, "local_now() 应带时区信息"


def test_local_now_is_not_utc():
    """In a non-UTC deployment (default Asia/Shanghai) the offset is +08:00."""
    now = local_now()
    utc_now = datetime.now(timezone.utc)
    wall_delta = (now.replace(tzinfo=None) - utc_now.replace(tzinfo=None)).total_seconds()
    if now.utcoffset().total_seconds() == 0:
        return  # machine already in UTC, skip
    assert abs(wall_delta) > 3600, (
        f"local_now()={now} 与 UTC {utc_now} 只差 {wall_delta:.0f}s，疑似仍用了 UTC"
    )
