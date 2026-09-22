"""Produce five fictional executions, two seconds apart, and save them locally."""

import json
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re
import time
from uuid import uuid4


def create_execution(instrument="AAPL.US", side="BUY", quantity="10",
                     price="244.00", seconds_after_start=0):
    # Each call represents a new fill. A delivery retry must reuse the saved event.
    trade_id = uuid4().hex
    executed_at = datetime.fromisoformat("2025-01-06T15:00:01.120+00:00")
    executed_at += timedelta(seconds=seconds_after_start)
    published_at = executed_at + timedelta(milliseconds=60)

    return {
        "schema_version": 1,
        "event_id": f"sim-event-{trade_id}",
        "event_type": "EXECUTION_REPORTED",
        "source_system": "simulated_oms",
        "scenario_id": "simulator_lesson_001",
        "is_simulated": True,
        # These are invented historical source times, not today's receipt times.
        "occurred_at": executed_at.isoformat(timespec="milliseconds"),
        "published_at": published_at.isoformat(timespec="milliseconds"),
        "executed_at": executed_at.isoformat(timespec="milliseconds"),
        "business_date": "2025-01-06",
        "execution_id": f"SIM-EXEC-{trade_id}",
        "execution_version": 1,
        "supersedes_event_id": None,
        "correction_reason": None,
        "order_id": f"SIM-ORDER-{trade_id}",
        "fund_id": "NORTHBRIDGE",
        "account_id": "SIM-ACCOUNT-01",
        "broker_id": "SIM-BROKER-01",
        "instrument_id": instrument,
        "side": side,
        "quantity": quantity,
        "execution_price": price,
        "currency": "USD",
        "settlement_due": "2025-01-07",
        "execution_status": "ACTIVE",
    }


def validate_execution(event):
    """Check the first-report format used by this simulator lesson."""
    if not isinstance(event, dict):
        raise ValueError("event must be a JSON object")

    for field in (
        "event_id", "execution_id", "order_id", "fund_id", "account_id",
        "broker_id", "instrument_id", "source_system", "scenario_id",
    ):
        value = event.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} must be a non-empty string")

    # The event ID becomes a filename, so disallow path characters.
    if not re.fullmatch(r"[A-Za-z0-9_-]+", event["event_id"]):
        raise ValueError("event_id must contain only letters, digits, underscores or hyphens")

    if event.get("side") not in ("BUY", "SELL"):
        raise ValueError("side must be BUY or SELL")

    for field in ("quantity", "execution_price"):
        value = event.get(field)
        if not isinstance(value, str):
            raise ValueError(f"{field} must be a decimal string")
        try:
            number = Decimal(value)
        except InvalidOperation:
            raise ValueError(f"{field} must be a decimal string") from None
        if not number.is_finite() or number <= 0:
            raise ValueError(f"{field} must be a finite number greater than zero")

    times = {}
    for field in ("executed_at", "occurred_at", "published_at"):
        value = event.get(field)
        try:
            timestamp = datetime.fromisoformat(value)
        except (ValueError, TypeError):
            raise ValueError(f"{field} must be an ISO timestamp with a timezone") from None
        if timestamp.utcoffset() is None:
            raise ValueError(f"{field} must include a timezone, such as Z or +00:00")
        times[field] = timestamp
    if not times["executed_at"] <= times["occurred_at"] <= times["published_at"]:
        raise ValueError("timestamps must follow executed_at <= occurred_at <= published_at")

    dates = {}
    for field in ("business_date", "settlement_due"):
        value = event.get(field)
        try:
            parsed = date.fromisoformat(value)
        except (ValueError, TypeError):
            raise ValueError(f"{field} must be a date in YYYY-MM-DD format") from None
        if parsed.isoformat() != value:
            raise ValueError(f"{field} must be a date in YYYY-MM-DD format")
        dates[field] = parsed
    if dates["settlement_due"] < dates["business_date"]:
        raise ValueError("settlement_due cannot be before business_date")

    # Keep this lesson limited to simulated USD fills, before adding corrections.
    for field, expected in (
        ("event_type", "EXECUTION_REPORTED"), ("execution_status", "ACTIVE"),
        ("source_system", "simulated_oms"), ("currency", "USD"),
        ("is_simulated", True), ("schema_version", 1), ("execution_version", 1),
        ("supersedes_event_id", None), ("correction_reason", None),
    ):
        if (field not in event or type(event[field]) is not type(expected)
                or event[field] != expected):
            raise ValueError(f"{field} must be {expected!r} for this first-report lesson")


def save_event(event, folder):
    validate_execution(event)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{event['event_id']}.jsonl"
    # Exclusive creation prevents accidentally overwriting a saved message.
    with path.open("x", encoding="utf-8") as file:
        file.write(json.dumps(event) + "\n")
    return path


def produce_trades(folder):
    # A small, hand-written scenario: all prices and trades are fictional.
    trades = [
        ("AAPL.US", "BUY", "10", "244.00"),
        ("AMZN.US", "SELL", "5", "227.00"),
        ("AAPL.US", "BUY", "8", "244.05"),
        ("AMZN.US", "BUY", "2", "226.95"),
        ("AAPL.US", "SELL", "3", "244.10"),
    ]

    for index, (instrument, side, quantity, price) in enumerate(trades):
        if index > 0:
            time.sleep(2)
        event = create_execution(instrument, side, quantity, price,
                                 seconds_after_start=index * 2)
        path = save_event(event, folder)
        print(f"{index + 1}/{len(trades)}: {side} {quantity} {instrument} "
              f"at USD {price} | saved {path.name}", flush=True)

    print(f"Finished. Five fictional events saved in {folder}", flush=True)


if __name__ == "__main__":
    output_folder = Path(__file__).resolve().parent / "data" / "simulator"
    produce_trades(output_folder)
