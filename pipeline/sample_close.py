"""Make one isolated fictional fund day from a saved prior close."""

import argparse
import csv
import hashlib
import json
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


TRADES = (
    ("SIM-ACCOUNT-01", "AAPL", "BUY", 10, 8),
    ("SIM-ACCOUNT-01", "AMZN", "SELL", 5, -6),
    ("SIM-ACCOUNT-02", "MSFT", "BUY", 8, 5),
    ("SIM-ACCOUNT-02", "KO", "SELL", 20, -4),
)


def previous_closes(path, opening_date):
    wanted = {trade[1] for trade in TRADES}
    found = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            ticker = row["universe_ticker"]
            if ticker not in wanted or row["valuation_date"] != opening_date:
                continue
            if ticker in found or row["source_system"] != "massive":
                raise ValueError("Repeated or unexpected price for {}".format(ticker))
            if row["currency"] != "USD" or row["price_basis"] != "unadjusted":
                raise ValueError("Wrong price basis for {}".format(ticker))
            close = Decimal(row["close_price"])
            if not close.is_finite() or close <= 0:
                raise ValueError("Bad prior close for {}".format(ticker))
            found[ticker] = close
    if found.keys() != wanted:
        raise ValueError("Missing prior closes: {}".format(", ".join(sorted(wanted - found.keys()))))
    return found


def save(folder, filename, rows, manifest):
    content = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows).encode("utf-8")
    manifest["record_count"] = len(rows)
    manifest["files"] = {filename: hashlib.sha256(content).hexdigest()}
    details = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    data_file = folder / filename
    manifest_file = folder / "manifest.json"
    if folder.exists():
        if (not data_file.is_file() or not manifest_file.is_file()
                or data_file.read_bytes() != content or manifest_file.read_bytes() != details):
            raise ValueError("Saved delivery differs: {}".format(folder))
        return
    folder.mkdir(parents=True)
    data_file.write_bytes(content)
    manifest_file.write_bytes(details)


def make_day(business_date, opening_date, settlement_due, scenario, reference, data_dir):
    day = date.fromisoformat(business_date)
    opened = date.fromisoformat(opening_date)
    due = date.fromisoformat(settlement_due)
    if opened >= day or due <= day:
        raise ValueError("Opening must precede the trade; settlement must follow it")
    closes = previous_closes(reference, opening_date)
    price_hash = hashlib.sha256(reference.read_bytes()).hexdigest()

    bank = []
    admin = []
    for account in ("SIM-ACCOUNT-01", "SIM-ACCOUNT-02"):
        common = {"account_id": account, "currency": "USD", "scenario_id": scenario,
                  "is_simulated": True}
        bank.append(dict(common, statement_date=opening_date, closing_balance="5000000.00",
                         source_system="simulated_bank", record_id="BANK-{}-{}".format(opening_date, account)))
        admin.append(dict(common, event_date=opening_date, event_type="INVESTOR_SUBSCRIPTION",
                          amount="5000000.00", source_system="simulated_fund_administrator",
                          record_id="ADMIN-{}-{}".format(opening_date, account)))

    opening_root = data_dir / "daily_opening" / scenario / opening_date
    base = {"business_date": opening_date, "scenario_id": scenario, "is_simulated": True}
    save(opening_root / "bank_cash", "balances.jsonl", bank,
         dict(base, delivery_id="bank-{}-{}".format(scenario, opening_date)))
    save(opening_root / "fund_admin", "events.jsonl", admin,
         dict(base, delivery_id="admin-{}-{}".format(scenario, opening_date)))

    oms = []
    for number, (account, ticker, side, quantity, offset_bps) in enumerate(TRADES, 1):
        reference_close = closes[ticker]
        price = (reference_close * (Decimal(1) + Decimal(offset_bps) / 10000)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP)
        executed = datetime.combine(day, time(15, number), timezone.utc)
        event_id = "SIM-EVENT-{}-{:02d}".format(day.strftime("%Y%m%d"), number)
        oms.append({
            "schema_version": 1, "event_id": event_id,
            "event_type": "EXECUTION_REPORTED", "source_system": "simulated_oms",
            "scenario_id": scenario, "is_simulated": True,
            "occurred_at": executed.isoformat(), "published_at": (executed + timedelta(milliseconds=60)).isoformat(),
            "executed_at": executed.isoformat(), "business_date": business_date,
            "execution_id": "SIM-EXEC-{}-{:02d}".format(day.strftime("%Y%m%d"), number),
            "execution_version": 1, "execution_status": "ACTIVE",
            "order_id": "SIM-ORDER-{}-{:02d}".format(day.strftime("%Y%m%d"), number),
            "fund_id": "NORTHBRIDGE", "account_id": account, "broker_id": "SIM-BROKER-01",
            "instrument_id": ticker + ".US", "market_ticker": ticker, "side": side,
            "quantity": str(quantity), "execution_price": str(price), "currency": "USD",
            "settlement_due": settlement_due, "price_method": "prior_close_with_fictional_offset",
            "reference_price_date": opening_date, "reference_close_price": str(reference_close),
            "price_offset_bps": offset_bps,
        })

    save(data_dir / "daily_oms" / scenario / business_date, "oms.jsonl", oms,
         {"business_date": business_date, "scenario_id": scenario, "is_simulated": True,
          "source_system": "simulated_oms", "delivery_id": "oms-{}-{}".format(scenario, business_date),
          "reference_price_date": opening_date, "price_snapshot_sha256": price_hash,
          "settlement_due": settlement_due})
    save(data_dir / "daily_settlements" / scenario / business_date,
         "settlements.jsonl", [],
         {"business_date": business_date, "settlement_date": business_date,
          "scenario_id": scenario, "is_simulated": True,
          "source_system": "simulated_custodian",
          "source_note": "First trade day; no prior trades are due",
          "delivery_id": "settlement-{}-{}-empty".format(scenario, business_date)})
    print("Ready: 4 fictional trades, 2 opening balances, 2 subscriptions and 0 settlements")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("business_date")
    parser.add_argument("--opening-date", required=True)
    parser.add_argument("--settlement-due", required=True)
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    args = parser.parse_args()
    make_day(args.business_date, args.opening_date, args.settlement_due,
             args.scenario, args.reference, args.data_dir)


if __name__ == "__main__":
    main()
