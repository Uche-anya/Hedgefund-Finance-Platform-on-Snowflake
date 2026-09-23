"""Save a lesson's input files as one local delivery."""

import argparse
import csv
import hashlib
import json
import shutil
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4


FILES = ("positions.csv", "prices.csv", "cash.csv")
BUNDLES = {"valuation": FILES, "trades": ("executions.csv", "allocations.csv")}
BUNDLES["settlement"] = (
    "executions.csv", "allocations.csv", "execution_terms.csv", "opening_cash.csv", "settlements.csv"
)
BUNDLES["nav"] = BUNDLES["settlement"] + ("closing_prices.csv",)
BUNDLES["references"] = ("broker_positions.csv", "broker_cash.csv", "administrator_nav.csv")
BUNDLES["gbp_references"] = ("gbp_reference.csv",)
BUNDLES["daily_cash"] = ("executions.csv", "allocations.csv", "execution_terms.csv", "settlements.csv")
BUNDLES["daily_prices"] = ("closing_prices.csv",)
BUNDLES["daily_references"] = BUNDLES["references"] + ("open_obligations.csv",)


def describe_file(path):
    checksum = hashlib.sha256(path.read_bytes()).hexdigest()
    with path.open(newline="", encoding="utf-8") as file:
        row_count = sum(1 for row in csv.DictReader(file))
    return {"sha256": checksum, "row_count": row_count}


def land_delivery(source_folder, landing_root, business_date, bundle="valuation",
                  source_label="synthetic_lesson_bundle", provenance=None):
    business_date = date.fromisoformat(business_date).isoformat()
    names = BUNDLES[bundle]
    delivery_id = uuid4().hex
    folder = landing_root / business_date / delivery_id
    folder.mkdir(parents=True, exist_ok=False)

    files = {}
    for name in names:
        # Copy bytes unchanged. A later correction gets a new delivery folder.
        shutil.copyfile(source_folder / name, folder / name)
        files[name] = describe_file(folder / name)

    manifest = {
        "schema_version": 1,
        "bundle": bundle,
        "delivery_id": delivery_id,
        "source": source_label,
        "provenance": provenance,
        "source_folder": str(source_folder.resolve()),
        "business_date": business_date,
        "received_at_utc": datetime.now(timezone.utc).isoformat(),
        "files": files,
    }
    # The final name appears only after the complete receipt has been written.
    temporary = folder / "manifest.json.tmp"
    temporary.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    temporary.rename(folder / "manifest.json")
    return folder


def verify_delivery(folder, business_date, bundle="valuation"):
    manifest_path = folder / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError("Incomplete delivery: manifest.json is missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1:
        raise ValueError("Unsupported manifest schema version")
    if manifest.get("business_date") != business_date:
        raise ValueError("Delivery business date does not match the requested close")
    # Older Part 2 manifests describe the valuation bundle without naming it.
    if manifest.get("bundle", "valuation") != bundle:
        raise ValueError(f"Expected a {bundle} delivery")
    names = BUNDLES[bundle]
    if set(manifest.get("files", {})) != set(names):
        raise ValueError(f"Manifest must list {', '.join(names)}")

    for name in names:
        path = folder / name
        if not path.is_file():
            raise ValueError(f"Delivery file is missing: {name}")
        if describe_file(path) != manifest["files"][name]:
            raise ValueError(f"Delivery file changed: {name}")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--business-date", required=True, type=date.fromisoformat)
    parser.add_argument("--bundle", choices=BUNDLES, default="valuation")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    business_date = args.business_date.isoformat()
    source = root / "fixtures" / business_date
    if args.bundle != "valuation":
        fixture_name = "settlement" if args.bundle == "nav" else args.bundle
        source = root / "fixtures" / fixture_name / business_date
    folder = land_delivery(source, root / "data" / "landing", business_date, args.bundle)
    # Only the path goes to stdout so PowerShell can store it in a variable.
    print(folder)


if __name__ == "__main__":
    main()
