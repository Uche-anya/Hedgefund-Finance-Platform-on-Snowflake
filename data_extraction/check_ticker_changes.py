"""Check the four remaining symbol changes without changing any prices."""

import csv
from getpass import getpass
import json
import os
from pathlib import Path

from data_extraction.check_bny_identity import check_identities, read_identity


# Old ticker, new ticker, last old-date check, first new-date check, exchanges.
PAIRS = (
    ("SATS", "ECHO", "2026-06-23", "2026-06-24", "XNAS", "XNAS"),
    ("PSTG", "P", "2026-04-16", "2026-04-17", "XNYS", "XNYS"),
    ("FI", "FISV", "2025-11-10", "2025-11-11", "XNYS", "XNAS"),
    ("MMC", "MRSH", "2026-01-13", "2026-01-14", "XNYS", "XNYS"),
)


def compare_pair(old, new, old_exchange, new_exchange):
    missing = []
    conflicts = []
    for field in ("cik", "share_class_figi", "composite_figi"):
        before = str(old.get(field) or "").strip()
        after = str(new.get(field) or "").strip()
        if not before or not after:
            missing.append(field)
            continue
        if field == "cik":
            before = before.lstrip("0")
            after = after.lstrip("0")
        if before != after:
            conflicts.append(field)

    for label, row, exchange in (("old", old, old_exchange), ("new", new, new_exchange)):
        for field, expected in (("type", "CS"), ("currency_name", "usd"),
                                ("primary_exchange", exchange), ("active", True)):
            value = row.get(field)
            if value is None or value == "":
                missing.append(f"{label} {field}")
            elif value != expected:
                conflicts.append(f"{label} {field}")

    if conflicts:
        status = "REVIEW_CONFLICT"
    elif missing:
        status = "REVIEW_MISSING"
    else:
        status = "IDENTIFIERS_MATCH"
    notes = []
    if conflicts:
        notes.append("Conflicting fields: " + ", ".join(conflicts))
    if missing:
        notes.append("Missing fields: " + ", ".join(missing))
    if not notes:
        notes.append("Identifiers and expected security details match; review names and source evidence")
    return status, "; ".join(notes)


def run_checks(root, key):
    checks = []
    for old, new, old_day, new_day, old_exchange, new_exchange in PAIRS:
        checks.extend(((old, old_day), (new, new_day)))
    folder = check_identities(root, key, checks=checks)

    comparisons = []
    for old, new, old_day, new_day, old_exchange, new_exchange in PAIRS:
        before = read_identity((folder / f"{old}_{old_day}.json").read_bytes(), old, old_day)
        after = read_identity((folder / f"{new}_{new_day}.json").read_bytes(), new, new_day)
        status, notes = compare_pair(before, after, old_exchange, new_exchange)
        row = {
            "old_ticker": old, "new_ticker": new,
            "old_date": old_day, "new_date": new_day,
            "old_name": before["name"], "new_name": after["name"],
            "status": status, "notes": notes,
        }
        for field in ("cik", "share_class_figi", "composite_figi", "primary_exchange"):
            row["old_" + field] = before[field]
            row["new_" + field] = after[field]
        comparisons.append(row)
        print(f"{old} -> {new}: {status}", flush=True)
        print(f"  {notes}", flush=True)

    with (folder / "comparisons.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(comparisons[0]))
        writer.writeheader()
        writer.writerows(comparisons)
    print(f"Comparison saved: {folder / 'comparisons.csv'}")
    print("Prices unchanged. These results are evidence for review, not an automatic repair.")
    return folder


def main():
    key = os.environ.get("MASSIVE_API_KEY")
    if not key:
        key = getpass("Massive API key (hidden): ")
    root = Path(__file__).resolve().parents[1] / "data" / "reference_checks"
    try:
        run_checks(root, key)
    except (ValueError, RuntimeError, OSError) as error:
        raise SystemExit(f"Ticker check stopped: {error}") from None


if __name__ == "__main__":
    main()
