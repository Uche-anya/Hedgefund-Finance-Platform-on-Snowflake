"""Compare our close with separate synthetic broker and administrator records."""

import argparse
import csv
import json
import shutil
import tempfile
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from uuid import uuid4

from fund_nav import calculate_nav
from landing import land_delivery, verify_delivery


def read_reference(path, columns, keys, value_column, required):
    values = {}
    with path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames != columns:
            raise ValueError(f"{path.name}: unexpected columns")
        for row in reader:
            if None in row or any(value is None or not value.strip() for value in row.values()):
                raise ValueError(f"{path.name}: blank field or malformed record")
            for field, expected in required.items():
                if row[field] != expected:
                    raise ValueError(f"{path.name}: expected {field}={expected}")
            key = tuple(row[field] for field in keys)
            if key in values:
                raise ValueError(f"{path.name}: duplicate reference key {key}")
            try:
                value = Decimal(row[value_column])
            except InvalidOperation as error:
                raise ValueError(f"{path.name}: invalid {value_column}") from error
            if not value.is_finite():
                raise ValueError(f"{path.name}: non-finite {value_column}")
            values[key] = value
    return values


def compare_values(control, actual, expected, tolerance, unit, as_of):
    results = []
    for key in sorted(actual.keys() | expected.keys()):
        ours, reference = actual.get(key), expected.get(key)
        difference = None
        if key not in actual:
            reason = "MISSING_INTERNAL"
        elif key not in expected:
            reason = "MISSING_REFERENCE"
        else:
            difference = ours - reference
            reason = "MATCH" if abs(difference) <= tolerance else "OUTSIDE_TOLERANCE"
        results.append({
            "control": control, "entity": list(key), "business_date": as_of,
            "unit": unit, "actual": ours, "expected": reference,
            "difference": difference, "tolerance": tolerance,
            "status": "PASS" if reason == "MATCH" else "FAIL", "reason": reason,
        })
    return results


def reconcile(nav_folder, reference_folder, business_date, as_of, currency="GBP"):
    nav_manifest = verify_delivery(nav_folder, business_date, "nav")
    reference_manifest = verify_delivery(reference_folder, as_of, "references")
    close = calculate_nav(nav_folder, business_date, as_of, currency)
    context = {"business_date": as_of, "fund": "NORTHBRIDGE"}
    positions = read_reference(
        reference_folder / "broker_positions.csv",
        ["business_date", "fund", "portfolio", "instrument", "basis", "quantity"],
        ["portfolio", "instrument"], "quantity", {**context, "basis": "TRADE_DATE"},
    )
    cash = read_reference(
        reference_folder / "broker_cash.csv",
        ["business_date", "fund", "currency", "basis", "balance"],
        ["currency"], "balance", {**context, "currency": currency, "basis": "SETTLED"},
    )
    nav = read_reference(
        reference_folder / "administrator_nav.csv",
        ["business_date", "fund", "currency", "nav"],
        ["currency"], "nav", {**context, "currency": currency},
    )
    our_positions = {}
    for holding in close["holdings"]:
        key = (holding["portfolio"], holding["instrument"])
        if key in our_positions:
            raise ValueError(f"Duplicate internal position key {key}")
        our_positions[key] = holding["quantity"]

    controls = compare_values("broker_position", our_positions, positions, Decimal("0"), "shares", as_of)
    controls += compare_values("broker_cash", {(currency,): close["cash"]}, cash, Decimal("0.01"), currency, as_of)
    controls += compare_values("administrator_nav", {(currency,): close["nav"]}, nav, Decimal("0.01"), currency, as_of)
    return {
        "run_id": uuid4().hex,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "fund": "NORTHBRIDGE", "as_of": as_of,
        "nav_delivery": str(nav_folder.resolve()),
        "reference_delivery": str(reference_folder.resolve()),
        "nav_delivery_id": nav_manifest["delivery_id"],
        "reference_delivery_id": reference_manifest["delivery_id"],
        "status": "PASS" if all(row["status"] == "PASS" for row in controls) else "FAIL",
        "publication_status": "NOT APPROVED", "controls": controls,
        "close": close,
    }


def make_demo_delivery(reference_folder, landing_root, as_of):
    # Make a new delivery from a temporary copy; never edit saved evidence.
    with tempfile.TemporaryDirectory() as temporary:
        source = Path(temporary) / "intentional_alpha_69"
        shutil.copytree(reference_folder, source)
        path = source / "broker_positions.csv"
        with path.open(newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            columns, rows = reader.fieldnames, list(reader)
        matches = [row for row in rows if row["portfolio"] == "GROWTH" and row["instrument"] == "ALPHA"]
        if len(matches) != 1 or Decimal(matches[0]["quantity"]) != Decimal("70"):
            raise ValueError("Demo expects exactly one GROWTH/ALPHA reference holding of 70")
        matches[0]["quantity"] = "69"
        with path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
        return land_delivery(source, landing_root, as_of, "references")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--business-date", required=True, type=date.fromisoformat)
    parser.add_argument("--as-of", required=True, type=date.fromisoformat)
    parser.add_argument("--delivery", required=True, type=Path)
    parser.add_argument("--references", required=True, type=Path)
    parser.add_argument("--currency", choices=("GBP", "USD"), default="GBP")
    parser.add_argument("--demo-alpha-69", action="store_true", help="Inject a labelled mismatch in a new reference delivery")
    args = parser.parse_args()
    business_date, as_of = args.business_date.isoformat(), args.as_of.isoformat()
    root = Path(__file__).resolve().parent / "data"
    reference_folder = args.references
    if args.demo_alpha_69:
        verify_delivery(reference_folder, as_of, "references")
        reference_folder = make_demo_delivery(reference_folder, root / "landing", as_of)
    report = reconcile(args.delivery, reference_folder, business_date, as_of, args.currency)
    if args.demo_alpha_69:
        report["injected_fault"] = "INTENTIONAL TEST: GROWTH/ALPHA broker quantity changed from 70 to 69"
        report["original_reference_delivery"] = str(args.references.resolve())
        print(report["injected_fault"])
    output = root / "reconciliation" / f"{report['run_id']}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as file:
        json.dump(report, file, indent=2, default=str)
        file.write("\n")
    for row in report["controls"]:
        print(f"{row['control']} {'/'.join(row['entity'])}: {row['status']} | "
              f"ours={row['actual']} reference={row['expected']} "
              f"difference={row['difference']} {row['unit']} | {row['reason']}")
    print(f"Reconciliation: {report['status']} | NOT APPROVED")
    print(f"Report: {output}")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
