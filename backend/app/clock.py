"""The current date, in one place, so tests can pin it (see tests/conftest.py)."""

from datetime import date


def today():
    return date.today()
