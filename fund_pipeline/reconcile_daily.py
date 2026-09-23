"""Compare a next-day close with separately prepared simulated statements."""

import argparse
import csv
from datetime import date
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from fund_pipeline.daily_nav import daily_nav
from fund_pipeline.landing import land_delivery, verify_delivery
from fund_pipeline.publication import check_eligible
from fund_pipeline.reconcile import compare_values, read_reference


def reconcile_daily(database, previous_date, activity, prices, references, business_date, calendar=None):
    manifest = verify_delivery(references, business_date, "daily_references")
    report = daily_nav(database, previous_date, activity, prices, business_date, calendar)
    close = report["close"]
    currency = close["currency"]
    context = {"business_date": business_date, "fund": "NORTHBRIDGE"}
    positions = read_reference(references / "broker_positions.csv",
        ["business_date", "fund", "portfolio", "instrument", "basis", "quantity"],
        ["portfolio", "instrument"], "quantity", {**context, "basis": "TRADE_DATE"})
    cash = read_reference(references / "broker_cash.csv",
        ["business_date", "fund", "currency", "basis", "balance"], ["currency"], "balance",
        {**context, "currency": currency, "basis": "SETTLED"})
    nav = read_reference(references / "administrator_nav.csv",
        ["business_date", "fund", "currency", "nav"], ["currency"], "nav", {**context, "currency": currency})
    obligations = read_reference(references / "open_obligations.csv",
        ["business_date", "fund", "currency", "execution_id", "type", "due", "amount"],
        ["execution_id", "type", "due"], "amount", {**context, "currency": currency})
    seen = set()
    totals = {("PAYABLE",): Decimal(0), ("RECEIVABLE",): Decimal(0)}
    for (execution_id, kind, due), amount in obligations.items():
        if execution_id in seen or kind not in ("PAYABLE", "RECEIVABLE") or amount <= 0:
            raise ValueError("Reference obligations need unique executions, valid types and positive amounts")
        seen.add(execution_id)
        date.fromisoformat(due)
        totals[(kind,)] += amount
    actual_positions = {(row["portfolio"], row["instrument"]): row["quantity"] for row in close["holdings"]}
    actual_obligations = {(row["execution_id"], row["type"], row["due"]): row["amount"]
                          for row in close["obligations"]}
    controls = compare_values("broker_position", actual_positions, positions, Decimal(0), "shares", business_date)
    for name, actual, expected in (
        ("broker_cash", {(currency,): close["cash"]}, cash),
        ("administrator_nav", {(currency,): close["nav"]}, nav),
        ("open_obligation", actual_obligations, obligations),
        ("obligation_total", {("PAYABLE",): close["payables"], ("RECEIVABLE",): close["receivables"]}, totals),
    ):
        controls += compare_values(name, actual, expected, Decimal("0.01"), currency, business_date)
    report.update(status="PASS" if all(row["status"] == "PASS" for row in controls) else "FAIL",
                  controls=controls, reference_delivery=str(references.resolve()),
                  reference_delivery_id=manifest["delivery_id"],
                  reference_manifest_sha256=hashlib.sha256((references / "manifest.json").read_bytes()).hexdigest(),
                  publication_status="NOT APPROVED", reference_kind="SIMULATED STATEMENTS")
    try:
        check_eligible({"reconciliation": report})
    except ValueError as error:
        report["review_eligibility"] = "BLOCKED"
        report["blocked_reason"] = str(error)
    else:
        report["review_eligibility"] = "ELIGIBLE_FOR_REVIEW"
    return report


def make_mismatch(references, root, business_date):
    verify_delivery(references, business_date, "daily_references")
    with tempfile.TemporaryDirectory() as temporary:
        source = Path(temporary) / "apple_12_demo"
        shutil.copytree(references, source)
        path = source / "broker_positions.csv"
        with path.open(newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            columns, rows = reader.fieldnames, list(reader)
        matches = [row for row in rows if row["portfolio"] == "GROWTH" and row["instrument"] == "AAPL.US"]
        if len(matches) != 1 or Decimal(matches[0]["quantity"]) != 13:
            raise ValueError("Mismatch demo expects 13 GROWTH/AAPL.US shares")
        matches[0]["quantity"] = "12"
        with path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
        return land_delivery(source, root, business_date, "daily_references",
            "SIMULATED intentional Apple 12 mismatch", {"original_reference_delivery": str(references.resolve())})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--previous-date", required=True)
    parser.add_argument("--business-date", required=True)
    parser.add_argument("--delivery", type=Path, required=True)
    parser.add_argument("--prices", type=Path, required=True)
    parser.add_argument("--references", type=Path, required=True)
    parser.add_argument("--demo-apple-12", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1] / "data"
    references = args.references
    if args.demo_apple_12:
        references = make_mismatch(references, root / "landing", args.business_date)
    report = reconcile_daily(args.database, args.previous_date, args.delivery, args.prices, references, args.business_date)
    if args.demo_apple_12:
        report["injected_fault"] = "INTENTIONAL TEST: broker says 12 Apple shares instead of 13"
    folder = root / "daily_reconciliation"
    folder.mkdir(parents=True, exist_ok=True)
    output = folder / f"{report['run_id']}.json"
    temporary = output.with_suffix(".tmp")
    with temporary.open("x", encoding="utf-8") as file:
        json.dump(report, file, indent=2, default=str)
        file.write("\n")
    temporary.rename(output)
    for row in report["controls"]:
        print(f"{row['control']} {'/'.join(row['entity'])}: {row['status']} | "
              f"ours={row['actual']} reference={row['expected']} difference={row['difference']}")
    print(f"{report['status']} | {report['review_eligibility']} | NOT APPROVED")
    print(f"Report: {output}")
    return 0 if report["review_eligibility"] == "ELIGIBLE_FOR_REVIEW" else 1


if __name__ == "__main__":
    raise SystemExit(main())
