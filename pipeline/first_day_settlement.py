"""Record that the opening trade day has no settlements due."""

import argparse
import hashlib
import json
from pathlib import Path

from pipeline.check_day import read_delivery


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("business_date", help="First trade date, YYYY-MM-DD")
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--opening-date", required=True)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    args = parser.parse_args()

    oms_root = args.data_dir / "daily_oms" / args.scenario
    trade_dates = sorted(p.name for p in oms_root.iterdir() if p.is_dir())
    if not trade_dates or trade_dates[0] != args.business_date:
        parser.exit(1, "This is not the first saved trade day.\n")
    if args.opening_date >= args.business_date:
        parser.exit(1, "Opening date must come before the trade date.\n")

    opening = args.data_dir / "daily_opening" / args.scenario / args.opening_date
    opening_files = (
        ("fund_admin", "events.jsonl", "event_date"),
        ("bank_cash", "balances.jsonl", "statement_date"),
    )
    for source, file_name, record_date_field in opening_files:
        try:
            read_delivery(opening / source, file_name, "business_date",
                          args.opening_date, args.scenario, record_date_field)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            parser.exit(1, "Opening delivery is not ready: {}\n".format(error))

    folder = args.data_dir / "daily_settlements" / args.scenario / args.business_date
    if folder.exists():
        parser.exit(1, "Settlement delivery already exists: {}\n".format(folder))

    folder.mkdir(parents=True)
    (folder / "settlements.jsonl").write_bytes(b"")
    manifest = {
        "business_date": args.business_date,
        "delivery_id": "settlement-{}-{}-empty".format(args.scenario, args.business_date.replace("-", "")),
        "files": {"settlements.jsonl": hashlib.sha256(b"").hexdigest()},
        "is_simulated": True,
        "record_count": 0,
        "scenario_id": args.scenario,
        "settlement_date": args.business_date,
        "source_system": "simulated_custodian",
        "source_note": "First trade day; opening contains cash but no prior trades",
    }
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("Saved zero-settlement delivery: {}".format(folder))


if __name__ == "__main__":
    main()
