"""Save the reconciled next-day USD close for the existing approval workflow."""

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
from uuid import uuid4

from publication import check_eligible, database, now, read_candidate
from reconcile_daily import reconcile_daily


def prepare_daily(db_path, opening_database, previous_date, activity, prices, references, business_date):
    candidate_id, _ = prepare_daily_candidate(db_path, opening_database, previous_date,
                                             activity, prices, references, business_date)
    return candidate_id


def prepare_daily_candidate(db_path, opening_database, previous_date, activity, prices, references,
                            business_date, reuse=False, calendar=None):
    previous_date = date.fromisoformat(previous_date).isoformat()
    business_date = date.fromisoformat(business_date).isoformat()
    report = reconcile_daily(opening_database, previous_date, activity, prices, references, business_date, calendar)
    if report["close"]["currency"] != "USD":
        raise ValueError("Daily publication currently supports USD closes only")
    root = Path(__file__).resolve().parent
    sources = ("prepare_daily.py", "reconcile_daily.py", "daily_nav.py", "carry_cash.py",
               "build_positions.py", "cash_settlement.py", "fund_nav.py", "daily_close.py",
               "landing.py", "reconcile.py", "publication.py", "business_calendar.py", "run_config.py")
    candidate_id = uuid4().hex
    candidate = {"candidate_id": candidate_id, "kind": "daily_usd", "as_of": business_date,
                 "trade_batch_date": business_date, "created_at": now(), "reconciliation": report,
                 "code_sha256": {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in sources}}
    identity = {"kind": "daily_usd", "previous_date": previous_date, "business_date": business_date,
                "opening_database": str(opening_database.resolve()),
                "opening_publication": report["opening_publication"],
                "activity": report["manifest_sha256"], "prices": report["price_manifest_sha256"],
                "references": report["reference_manifest_sha256"], "code": candidate["code_sha256"],
                "calendar": calendar["sha256"] if calendar else report["calendar_policy"]}
    input_key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    if reuse:
        candidate["input_key"] = input_key
    payload = json.dumps(candidate, sort_keys=True, default=str)
    with database(db_path) as connection:
        if reuse:
            existing = connection.execute("SELECT candidate_id FROM candidate_reuse WHERE input_key = ?",
                                          (input_key,)).fetchone()
            if existing:
                check_eligible(read_candidate(connection, existing["candidate_id"]))
                return existing["candidate_id"], True
        existing = connection.execute("SELECT payload FROM candidates LIMIT 1").fetchone()
        if existing and json.loads(existing["payload"])["reconciliation"]["close"]["currency"] != "USD":
            raise ValueError("Use a separate USD publication database")
        connection.execute("INSERT INTO candidates VALUES (?, ?, ?, ?, ?)",
                           (candidate_id, business_date, payload, hashlib.sha256(payload.encode()).hexdigest(),
                            candidate["created_at"]))
        if reuse:
            try:
                check_eligible(candidate)
            except ValueError:
                pass
            else:
                connection.execute("INSERT INTO candidate_reuse VALUES (?, ?)", (input_key, candidate_id))
    # Failed controls are saved for inspection. approve() and publish() still
    # enforce eligibility against this frozen report.
    return candidate_id, False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True, help="Destination USD review database")
    parser.add_argument("--opening-database", type=Path, required=True)
    parser.add_argument("--previous-date", required=True)
    parser.add_argument("--business-date", required=True)
    parser.add_argument("--delivery", type=Path, required=True)
    parser.add_argument("--prices", type=Path, required=True)
    parser.add_argument("--references", type=Path, required=True)
    args = parser.parse_args()
    print(prepare_daily(args.database, args.opening_database, args.previous_date,
                        args.delivery, args.prices, args.references, args.business_date))
