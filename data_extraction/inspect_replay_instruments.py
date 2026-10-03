"""Collect dated Massive reference records for the 20 replay stocks."""

import csv
from getpass import getpass
import json
import os
from pathlib import Path

from data_extraction.check_bny_identity import check_identities


AS_OF_DATE = "2025-01-10"
TICKERS = (
    "AAPL", "AMZN", "MSFT", "GOOGL", "META", "NVDA", "TSLA", "JPM", "BAC", "GS",
    "V", "MA", "WMT", "COST", "XOM", "CVX", "UNH", "JNJ", "PEP", "KO",
)
CHECKS = tuple((ticker, AS_OF_DATE) for ticker in TICKERS)
REQUIRED_IDS = ("cik", "composite_figi", "share_class_figi")


def review(rows):
    if {row["requested_ticker"] for row in rows} != set(TICKERS):
        raise ValueError("Reference results do not contain the 20 replay tickers exactly once")
    if len(rows) != len(TICKERS):
        raise ValueError("Reference results contain duplicate replay tickers")

    figi_counts = {}
    for row in rows:
        figi = row["share_class_figi"].strip()
        if figi:
            figi_counts[figi] = figi_counts.get(figi, 0) + 1

    reviewed = []
    for row in rows:
        missing = [field for field in REQUIRED_IDS if not row[field].strip()]
        problems = []
        if row["type"] != "CS":
            problems.append("type is not common stock")
        if row["currency_name"].lower() != "usd":
            problems.append("currency is not USD")
        if row["active"].lower() != "true":
            problems.append("security is not active on the review date")
        if not row["primary_exchange"].strip():
            problems.append("primary exchange is missing")
        figi = row["share_class_figi"].strip()
        if figi and figi_counts[figi] > 1:
            problems.append("share-class FIGI is used by another replay ticker")

        if missing:
            status = "MISSING_IDENTIFIER"
            notes = "Missing: " + ", ".join(missing)
        elif problems:
            status = "REVIEW_CONFLICT"
            notes = "; ".join(problems)
        else:
            status = "READY_FOR_REVIEW"
            notes = "Required identifiers and security attributes are present"
        reviewed.append({
            "ticker": row["requested_ticker"],
            "as_of_date": row["as_of_date"],
            "name": row["name"],
            "cik": row["cik"],
            "composite_figi": row["composite_figi"],
            "share_class_figi": row["share_class_figi"],
            "primary_exchange": row["primary_exchange"],
            "security_type": row["type"],
            "currency": row["currency_name"],
            "active": row["active"],
            "review_status": status,
            "review_notes": notes,
        })
    return reviewed


def inspect(root, key):
    folder = check_identities(root, key, checks=CHECKS)
    with (folder / "identities.csv").open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    reviewed = review(rows)
    output = folder / "replay_instruments.csv"
    with output.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(reviewed[0]))
        writer.writeheader()
        writer.writerows(reviewed)

    counts = {}
    for row in reviewed:
        status = row["review_status"]
        counts[status] = counts.get(status, 0) + 1
        print(f"{row['ticker']}: {status} | {row['share_class_figi'] or 'FIGI missing'}")
    summary = {
        "as_of_date": AS_OF_DATE,
        "ticker_count": len(reviewed),
        "status_counts": counts,
        "review_status": "PENDING_MANUAL_APPROVAL",
        "input_file": "identities.csv",
        "output_file": output.name,
        "note": "Inspection only. No warehouse mapping or price row was changed.",
    }
    (folder / "replay_instrument_review.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"Review file: {output}")
    return folder


def main():
    key = os.environ.get("MASSIVE_API_KEY") or getpass("Massive API key (hidden): ")
    root = Path(__file__).resolve().parents[1] / "data" / "instrument_reference"
    try:
        inspect(root, key)
    except (OSError, RuntimeError, ValueError) as error:
        raise SystemExit(f"Instrument inspection stopped: {error}") from None


if __name__ == "__main__":
    main()
