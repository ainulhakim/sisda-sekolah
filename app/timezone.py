"""Timezone helpers — WIB (Waktu Indonesia Barat, UTC+7)."""
from datetime import datetime, timezone, timedelta

WIB = timezone(timedelta(hours=7))

def now_wib():
    """Return current datetime in WIB."""
    return datetime.now(WIB)

def utcnow_wib():
    """Return current datetime in WIB (replaces datetime.utcnow)."""
    return datetime.now(WIB)
