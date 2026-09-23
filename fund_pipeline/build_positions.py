"""Part 3: rebuild share quantities from one complete day's allocated trades."""

import argparse
import csv
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from fund_pipeline.landing import verify_delivery


def read_events(path, columns, key, business_date):
    events = {}
    duplicates = 0
    with path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames != columns:
            raise ValueError(f"{path.name}: expected columns {columns}")
        for row in reader:
            if None in row or any(value is None or not value.strip() for value in row.values()):
                raise ValueError(f"{path.name}: blank field or malformed record")
            if row["business_date"] != business_date:
                raise ValueError(f"{path.name}: expected business date {business_date}")
            event_id = row[key]
            if event_id in events:
                if events[event_id] != row:
                    raise ValueError(f"Conflicting {key} {event_id}; corrections are not supported yet")
                duplicates += 1
            else:
                events[event_id] = row
    return events, duplicates


def positive_quantity(value):
    try:
        quantity = Decimal(value)
    except InvalidOperation as error:
        raise ValueError(f"Invalid share quantity: {value}") from error
    if not quantity.is_finite() or quantity <= 0:
        raise ValueError(f"Share quantity must be finite and positive: {value}")
    return quantity


def build_positions(folder, business_date):
    executions, repeated_executions = read_events(
        folder / "executions.csv",
        ["business_date", "execution_id", "instrument", "side", "quantity"],
        "execution_id", business_date,
    )
    allocations, repeated_allocations = read_events(
        folder / "allocations.csv",
        ["business_date", "allocation_id", "execution_id", "portfolio", "quantity"],
        "allocation_id", business_date,
    )

    executed = {}
    allocated = {}
    for execution_id, execution in executions.items():
        if execution["side"] not in ("BUY", "SELL"):
            raise ValueError(f"Unknown side for {execution_id}: {execution['side']}")
        executed[execution_id] = positive_quantity(execution["quantity"])
        allocated[execution_id] = Decimal("0")

    positions = {}
    for allocation in allocations.values():
        execution_id = allocation["execution_id"]
        if execution_id not in executions:
            raise ValueError(f"Allocation references unknown execution {execution_id}")
        execution = executions[execution_id]
        quantity = positive_quantity(allocation["quantity"])
        allocated[execution_id] += quantity
        change = quantity if execution["side"] == "BUY" else -quantity
        key = (allocation["portfolio"], execution["instrument"])
        positions[key] = positions.get(key, Decimal("0")) + change

    # Never release positions unless every execution is fully allocated.
    for execution_id in executions:
        if allocated[execution_id] != executed[execution_id]:
            raise ValueError(
                f"Allocation mismatch for {execution_id}: "
                f"executed {executed[execution_id]}, allocated {allocated[execution_id]}"
            )

    return {
        "positions": [
            {"portfolio": portfolio, "instrument": instrument, "quantity": quantity}
            for (portfolio, instrument), quantity in sorted(positions.items())
        ],
        "repeated_executions": repeated_executions,
        "repeated_allocations": repeated_allocations,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--business-date", required=True, type=date.fromisoformat)
    parser.add_argument("--delivery", required=True, type=Path)
    args = parser.parse_args()
    business_date = args.business_date.isoformat()
    manifest = verify_delivery(args.delivery, business_date, bundle="trades")
    result = build_positions(args.delivery, business_date)
    print(f"Input delivery: {manifest['delivery_id']}")
    print(f"Positions | {business_date} | zero opening holdings | NOT APPROVED")
    for row in result["positions"]:
        print(f"{row['portfolio']} / {row['instrument']}: {row['quantity']} shares")
    print(f"Repeated executions ignored: {result['repeated_executions']}")
    print(f"Repeated allocations ignored: {result['repeated_allocations']}")
    print("Cash, settlement and NAV are not calculated in this lesson.")


if __name__ == "__main__":
    main()
