"""Translate a USD close into GBP for reporting; no actual currency exchange."""

import argparse
from datetime import date, datetime, timezone
from decimal import Decimal, localcontext
import hashlib
import json
from pathlib import Path
from uuid import uuid4

from daily_close import pounds
from fund_nav import calculate_nav
from fx_rates import verify_fx, SOURCE
from landing import verify_delivery


def translate(usd_close, fx):
    if usd_close["currency"] != "USD" or fx["from_currency"] != "USD" or fx["to_currency"] != "GBP":
        raise ValueError("Expected USD balances and a GBP-per-USD rate")
    rate = Decimal(fx["gbp_per_usd"])
    if not rate.is_finite() or rate <= 0:
        raise ValueError("FX rate must be finite and positive")
    with localcontext() as context:
        context.prec = 40
        gbp = {"currency": "GBP"}
        for field in ("cash", "receivables", "payables", "long_assets", "short_obligations"):
            gbp[field] = usd_close[field] * rate
        gbp["holdings"] = [{**row, "market_value": row["market_value"] * rate} for row in usd_close["holdings"]]
        gbp["obligations"] = [{**row, "amount": row["amount"] * rate} for row in usd_close["obligations"]]
        gbp["nav"] = gbp["cash"] + gbp["receivables"] - gbp["payables"] + gbp["long_assets"] - gbp["short_obligations"]
        if gbp["nav"] != usd_close["nav"] * rate:
            raise ValueError("Translated components do not agree with translated USD NAV")
    return gbp


def calculate_gbp(nav_folder, fx_folder, business_date, as_of):
    as_of = date.fromisoformat(as_of).isoformat()
    nav_manifest = verify_delivery(nav_folder, business_date, "nav")
    rates = verify_fx(fx_folder)
    if as_of not in rates:
        raise ValueError(f"Missing FX rate for {as_of}; GBP valuation stopped")
    usd = calculate_nav(nav_folder, business_date, as_of, "USD")
    gbp = translate(usd, rates[as_of])
    return {
        "run_id": uuid4().hex, "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "as_of": as_of, "status": "NOT APPROVED", "fx": rates[as_of], "fx_source": SOURCE,
        "nav_delivery": str(nav_folder.resolve()), "nav_delivery_id": nav_manifest["delivery_id"],
        "fx_delivery": str(fx_folder.resolve()),
        "fx_manifest_sha256": hashlib.sha256((fx_folder / "manifest.json").read_bytes()).hexdigest(),
        "local_close": usd, "reporting_close": gbp,
        "policy": "Same-date ECB reference cross rate; not US-close spot or an executed FX trade",
        "gbp_reconciliation": "NOT IMPLEMENTED", "publication_status": "NOT APPROVED",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--delivery", type=Path, required=True)
    parser.add_argument("--fx-delivery", type=Path, required=True)
    parser.add_argument("--business-date", type=date.fromisoformat, required=True)
    parser.add_argument("--as-of", type=date.fromisoformat, required=True)
    args = parser.parse_args()
    report = calculate_gbp(args.delivery, args.fx_delivery, args.business_date.isoformat(), args.as_of.isoformat())
    root = Path(__file__).resolve().parent / "data" / "reporting"
    root.mkdir(parents=True, exist_ok=True)
    output = root / f"{report['run_id']}.json"
    temporary = output.with_suffix(".json.tmp")
    with temporary.open("x", encoding="utf-8") as file:
        json.dump(report, file, indent=2, default=str)
        file.write("\n")
    temporary.rename(output)
    print(f"GBP reporting close | {report['as_of']} | NOT APPROVED")
    print(f"Rate: {report['fx']['gbp_per_usd']} GBP per USD")
    print(f"{'Component':24} {'USD':>16} {'GBP':>16}")
    for field in ("cash", "receivables", "payables", "long_assets", "short_obligations", "nav"):
        print(f"{field:24} {pounds(report['local_close'][field]):>16} {pounds(report['reporting_close'][field]):>16}")
    print("Amounts are rounded for display only; no cash was exchanged.")
    print(f"Report: {output}")


if __name__ == "__main__":
    main()
