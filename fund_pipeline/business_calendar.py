"""Teaching calendar: Monday-Friday closes, with no holiday exclusions yet."""

from datetime import date, timedelta
import hashlib
import json

from fund_pipeline.run_config import unique_fields


POLICY = "WEEKDAYS_ONLY_NO_HOLIDAYS"


def next_close_date(previous):
    result = previous + timedelta(days=1)
    while result.weekday() >= 5:  # Python numbers Monday 0 through Sunday 6.
        result += timedelta(days=1)
    return result


def read_calendar(path, expected_sha256):
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected_sha256:
        raise ValueError("Calendar fingerprint changed; select a reviewed calendar version")
    data = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique_fields)
    required = {"calendar_id", "version", "coverage_start", "coverage_end", "reviewed_on", "sources", "days"}
    if not isinstance(data, dict) or set(data) != required:
        raise ValueError("Unexpected calendar fields")
    for name in required - {"sources", "days"}:
        if not isinstance(data[name], str) or not data[name].strip():
            raise ValueError(f"Missing calendar metadata: {name}")
    if not isinstance(data["sources"], list) or not data["sources"] or any(
            not isinstance(source, str) or not source.startswith("https://") for source in data["sources"]):
        raise ValueError("Calendar needs its source URLs")
    start, end = date.fromisoformat(data["coverage_start"]), date.fromisoformat(data["coverage_end"])
    date.fromisoformat(data["reviewed_on"])
    if end < start or not isinstance(data["days"], list):
        raise ValueError("Invalid calendar coverage")
    expected = start
    for row in data["days"]:
        if (not isinstance(row, dict) or set(row) != {"date", "is_open", "reason"}
                or row["date"] != expected.isoformat() or type(row["is_open"]) is not bool
                or not isinstance(row["reason"], str) or not row["reason"].strip()):
            raise ValueError("Calendar must list every date once in order with status and reason")
        if expected.weekday() >= 5 and row["is_open"]:
            raise ValueError("This US equity calendar cannot mark a weekend open")
        expected += timedelta(days=1)
    if expected != end + timedelta(days=1):
        raise ValueError("Calendar coverage is incomplete")
    return {"path": str(path.resolve()), "sha256": digest, "snapshot": data}


def calendar_policy(calendar):
    return calendar["snapshot"]["calendar_id"] if calendar is not None else POLICY


def validate_close_dates(previous_date, business_date, calendar=None):
    previous = date.fromisoformat(previous_date)
    today = date.fromisoformat(business_date)
    if calendar is not None:
        rows = {row["date"]: row for row in calendar["snapshot"]["days"]}
        if previous.isoformat() not in rows or today.isoformat() not in rows:
            raise ValueError("Requested date is outside the saved calendar coverage")
        if not rows[previous.isoformat()]["is_open"] or not rows[today.isoformat()]["is_open"]:
            raise ValueError("Opening and valuation dates must both be open in the saved calendar")
        following = [day for day, row in rows.items() if day > previous.isoformat() and row["is_open"]]
        if not following or today.isoformat() != min(following):
            raise ValueError("Use the next open valuation date; do not skip a required close")
        return previous, today
    if previous.weekday() >= 5 or today != next_close_date(previous):
        raise ValueError(f"Expected next weekday close {next_close_date(previous)} after a weekday opening; "
                         "consecutive weekdays are required (holidays not implemented)")
    return previous, today
