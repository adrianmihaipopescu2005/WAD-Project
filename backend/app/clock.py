"""The current date, in one place, so tests can pin it (see tests/conftest.py)."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

# The reporting deadline ("the day before, until 23:59") is meant in Romanian time,
# whatever time zone the server runs in.
TIMEZONE = ZoneInfo("Europe/Bucharest")


def today() -> date:
    return datetime.now(TIMEZONE).date()
