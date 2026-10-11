"""Reviewed trading and settlement dates for the daily equity example."""

from datetime import date, timedelta
import json
from pathlib import Path


CALENDAR_FILE = Path(__file__).resolve().parents[1] / "config" / "us_equity_calendar_2026.json"


def closed_dates():
    calendar = json.loads(CALENDAR_FILE.read_text(encoding="utf-8"))
    market = {date.fromisoformat(value) for value in calendar["market_closed"]}
    settlement = market | {date.fromisoformat(value)
                           for value in calendar["settlement_closed_extra"]}
    return calendar["year"], market, settlement


def is_market_day(day):
    year, market_closed, _ = closed_dates()
    if day.year != year:
        raise ValueError("No reviewed US equity calendar for {}".format(day.year))
    return day.weekday() < 5 and day not in market_closed


def is_settlement_day(day):
    year, _, settlement_closed = closed_dates()
    if day.year != year:
        raise ValueError("No reviewed US settlement calendar for {}".format(day.year))
    return day.weekday() < 5 and day not in settlement_closed


def previous_market_day(day):
    candidate = day - timedelta(days=1)
    while not is_market_day(candidate):
        candidate -= timedelta(days=1)
    return candidate


def next_settlement_day(day):
    candidate = day + timedelta(days=1)
    while not is_settlement_day(candidate):
        candidate += timedelta(days=1)
    return candidate
