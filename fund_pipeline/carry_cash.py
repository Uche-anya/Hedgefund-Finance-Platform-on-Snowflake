"""Carry settled cash and open trade obligations into the next weekday close."""

import argparse
from datetime import date
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from uuid import uuid4

from fund_pipeline.build_positions import build_positions, positive_quantity, read_events
from fund_pipeline.business_calendar import calendar_policy, validate_close_dates
from fund_pipeline.cash_settlement import cash_amount
from fund_pipeline.daily_close import pounds
from fund_pipeline.landing import verify_delivery
from fund_pipeline.publication import current, now, show


def roll_cash(opening, folder, previous_date, business_date, calendar=None):
    previous, today = validate_close_dates(previous_date, business_date, calendar)
    currency = opening["currency"]
    if currency not in ("USD", "GBP"):
        raise ValueError("Expected a single USD or GBP cash ledger")
    cash = cash_amount(opening["cash"])
    known = set(opening["known_execution_ids"])
    if len(known) != len(opening["known_execution_ids"]):
        raise ValueError("Duplicate opening execution history")
    obligations = {}
    for item in opening["obligations"]:
        execution_id = item["execution_id"]
        if execution_id in obligations or execution_id not in known:
            raise ValueError("Opening obligations must have unique known execution IDs")
        if item["type"] not in ("PAYABLE", "RECEIVABLE"):
            raise ValueError("Invalid opening obligation type")
        amount = cash_amount(item["amount"])
        if amount <= 0:
            raise ValueError("Obligation amount must be positive")
        date.fromisoformat(item["due"])
        obligations[execution_id] = {**item, "amount": amount}
    for field, kind in (("payables", "PAYABLE"), ("receivables", "RECEIVABLE")):
        total = sum((row["amount"] for row in obligations.values() if row["type"] == kind), Decimal(0))
        if total != cash_amount(opening[field]):
            raise ValueError(f"Opening {field} do not match the obligation details")

    build_positions(folder, business_date)  # Reject incomplete or conflicting allocations.
    executions, _ = read_events(folder / "executions.csv",
        ["business_date", "execution_id", "instrument", "side", "quantity"], "execution_id", business_date)
    terms, _ = read_events(folder / "execution_terms.csv",
        ["business_date", "execution_id", "currency", "execution_price", "settlement_due"], "execution_id", business_date)
    settlements, repeats = read_events(folder / "settlements.csv",
        ["business_date", "settlement_id", "execution_id", "currency", "amount", "settled_on"], "settlement_id", business_date)
    if set(terms) != set(executions):
        raise ValueError("Execution terms must match today's executions exactly")
    for execution_id, trade in executions.items():
        if execution_id in known:
            raise ValueError(f"Execution already exists in opening history: {execution_id}")
        term = terms[execution_id]
        if term["currency"] != currency:
            raise ValueError(f"Expected {currency} execution terms")
        if date.fromisoformat(term["settlement_due"]) < today:
            raise ValueError("Settlement due date cannot precede today's trade")
        amount = cash_amount(positive_quantity(trade["quantity"]) * positive_quantity(term["execution_price"]))
        obligations[execution_id] = {"execution_id": execution_id,
            "type": "PAYABLE" if trade["side"] == "BUY" else "RECEIVABLE",
            "amount": amount, "due": term["settlement_due"]}
        known.add(execution_id)

    movements = []
    for confirmation in settlements.values():
        execution_id = confirmation["execution_id"]
        if execution_id not in obligations:
            raise ValueError(f"Settlement has no open obligation (unknown or already settled): {execution_id}")
        obligation = obligations[execution_id]
        if confirmation["currency"] != currency:
            raise ValueError(f"Expected {currency} settlement confirmation")
        if cash_amount(confirmation["amount"]) != obligation["amount"]:
            raise ValueError(f"Settlement amount mismatch: {execution_id}")
        settled_on = date.fromisoformat(confirmation["settled_on"])
        if not previous < settled_on <= today:
            raise ValueError("Settlement date must be after the opening close and on or before this close")
        if execution_id in executions and settled_on < today:
            raise ValueError("Settlement date cannot precede today's new trade")
        change = -obligation["amount"] if obligation["type"] == "PAYABLE" else obligation["amount"]
        cash += change
        movements.append({"settlement_id": confirmation["settlement_id"],
                          "execution_id": execution_id, "cash_change": change,
                          "settled_on": settled_on.isoformat()})
        del obligations[execution_id]
    for row in obligations.values():
        row["status"] = "OVERDUE" if date.fromisoformat(row["due"]) <= today else "OPEN"
    payables = sum((row["amount"] for row in obligations.values() if row["type"] == "PAYABLE"), Decimal(0))
    receivables = sum((row["amount"] for row in obligations.values() if row["type"] == "RECEIVABLE"), Decimal(0))
    return {"currency": currency, "cash": cash, "payables": payables, "receivables": receivables,
            "net_cash_and_obligations": cash + receivables - payables,
            "obligations": [obligations[key] for key in sorted(obligations)],
            "known_execution_ids": sorted(known), "cash_movements": movements,
            "repeated_settlements": repeats}


def carry_cash(database, previous_date, folder, business_date, calendar=None):
    if not database.is_file():
        raise ValueError("Opening publication database does not exist")
    publication = current(database, previous_date)
    candidate = show(database, publication["publication"]["candidate_id"])["candidate"]
    report = candidate["reconciliation"]
    # GBP is a reporting translation in this scenario. Cash actually settles in USD.
    opening = dict(report.get("local_close", report["close"]))
    if candidate.get("kind") == "daily_usd":
        # Daily publications freeze the complete history, including settled trades.
        # Never rebuild it from only the latest day's activity.
        if "known_execution_ids" not in opening:
            raise ValueError("Daily opening is missing its execution history")
    else:
        nav_folder = Path(report["nav_delivery"])
        verify_delivery(nav_folder, candidate["trade_batch_date"], "nav")
        executions, _ = read_events(nav_folder / "executions.csv",
            ["business_date", "execution_id", "instrument", "side", "quantity"],
            "execution_id", candidate["trade_batch_date"])
        opening["known_execution_ids"] = sorted(executions)
    manifest = verify_delivery(folder, business_date, "daily_cash")
    result = roll_cash(opening, folder, previous_date, business_date, calendar)
    return {"run_id": uuid4().hex, "created_at": now(), "business_date": business_date,
            "status": "CASH ONLY - NOT APPROVED", "opening_date": previous_date,
            "calendar_policy": calendar_policy(calendar), "calendar": calendar,
            "opening_publication": publication["publication"], "opening_database": str(database.resolve()),
            "opening_cash": opening["cash"], "delivery": str(folder.resolve()),
            "delivery_id": manifest["delivery_id"],
            "manifest_sha256": hashlib.sha256((folder / "manifest.json").read_bytes()).hexdigest(),
            "cash_close": result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--previous-date", required=True)
    parser.add_argument("--business-date", required=True)
    parser.add_argument("--delivery", type=Path, required=True)
    args = parser.parse_args()
    report = carry_cash(args.database, args.previous_date, args.delivery, args.business_date)
    folder = Path(__file__).resolve().parents[1] / "data" / "cash"
    folder.mkdir(parents=True, exist_ok=True)
    output = folder / f"{report['run_id']}.json"
    temporary = output.with_suffix(".tmp")
    with temporary.open("x", encoding="utf-8") as file:
        json.dump(report, file, indent=2, default=str)
        file.write("\n")
    temporary.rename(output)
    close = report["cash_close"]
    print(f"{report['business_date']} | {close['currency']} | {report['status']}")
    print(f"Opening cash: {pounds(Decimal(report['opening_cash']))}")
    for field in ("cash", "payables", "receivables", "net_cash_and_obligations"):
        print(f"{field}: {pounds(close[field])}")
    print(f"Repeated settlement rows ignored: {close['repeated_settlements']}")
    print(f"Report: {output}")


if __name__ == "__main__":
    main()
