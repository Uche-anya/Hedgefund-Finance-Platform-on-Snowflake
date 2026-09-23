"""Make a learning reference through USD -> EUR -> GBP arithmetic."""

import argparse
import csv
from decimal import Decimal, localcontext
import hashlib
from pathlib import Path
import tempfile

from data_extraction.fx_rates import verify_fx
from fund_pipeline.landing import land_delivery, verify_delivery
from fund_pipeline.reconcile import read_reference


COLUMNS = ["business_date", "fund", "currency", "component", "amount"]


def fingerprint(folder):
    return hashlib.sha256((folder / "manifest.json").read_bytes()).hexdigest()


def raw_legs(folder, as_of):
    # verify_fx checks completeness, units and checksums first. Read the original
    # EUR legs here, not the derived GBP-per-USD number used by translation.
    rates = verify_fx(folder)
    if as_of not in rates:
        raise ValueError(f"Missing FX rate for {as_of}")
    with (folder / "ecb_rates.csv").open(encoding="utf-8-sig", newline="") as file:
        return {row["CURRENCY"]: Decimal(row["OBS_VALUE"])
                for row in csv.DictReader(file) if row["TIME_PERIOD"] == as_of}


def build_reference(reference_folder, fx_folder, as_of, root):
    verify_delivery(reference_folder, as_of, "references")
    legs = raw_legs(fx_folder, as_of)
    context = {"business_date": as_of, "fund": "NORTHBRIDGE", "currency": "USD"}
    nav = read_reference(reference_folder / "administrator_nav.csv",
                         ["business_date", "fund", "currency", "nav"],
                         ["currency"], "nav", context)
    cash = read_reference(reference_folder / "broker_cash.csv",
                          ["business_date", "fund", "currency", "basis", "balance"],
                          ["currency"], "balance", {**context, "basis": "SETTLED"})
    if set(nav) != {("USD",)} or set(cash) != {("USD",)}:
        raise ValueError("Reference needs one USD NAV and cash balance")
    with tempfile.TemporaryDirectory() as temporary:
        source = Path(temporary)
        with (source / "gbp_reference.csv").open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(COLUMNS)
            with localcontext() as context:
                context.prec = 40
                for component, amount in (("nav", nav[("USD",)]), ("cash", cash[("USD",)])):
                    writer.writerow([as_of, "NORTHBRIDGE", "GBP", component,
                                     amount / legs["USD"] * legs["GBP"]])
        return land_delivery(source, root, as_of, "gbp_references",
                             "synthetic_gbp_comparison_not_external_administrator",
                             {"usd_reference_manifest_sha256": fingerprint(reference_folder),
                              "fx_manifest_sha256": fingerprint(fx_folder),
                              "method": "USD reference amount / USD per EUR * GBP per EUR"})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--references", type=Path, required=True)
    parser.add_argument("--fx-delivery", type=Path, required=True)
    parser.add_argument("--as-of", required=True)
    args = parser.parse_args()
    print(build_reference(args.references, args.fx_delivery, args.as_of,
                          Path(__file__).resolve().parents[1] / "data" / "landing"))
