"""Load a bank statement supplied for one fund day."""

import argparse
import csv
import hashlib
import json
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from pipeline.load_day import REGISTRY, STAGE, snowflake_connection, stage_has_file


TABLE = "NORTHBRIDGE_DEV.RAW.DAILY_BANK_STATEMENTS"


def prepare(csv_file, data_dir, business_date, scenario):
    day = date.fromisoformat(business_date).isoformat()
    rows = []
    seen = set()
    with csv_file.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != ["account_id", "currency", "closing_balance"]:
            raise ValueError("Expected account_id,currency,closing_balance")
        for row in reader:
            account = row["account_id"].strip()
            if not account or account in seen or row["currency"] != "USD":
                raise ValueError("Repeated account, missing account, or non-USD balance")
            try:
                amount = Decimal(row["closing_balance"])
            except InvalidOperation:
                raise ValueError("Invalid balance for {}".format(account))
            if not amount.is_finite() or amount.as_tuple().exponent < -2:
                raise ValueError("Balance must have no more than two decimal places")
            seen.add(account)
            rows.append({
                "statement_date": day,
                "scenario_id": scenario,
                "account_id": account,
                "currency": "USD",
                "closing_balance": format(amount, ".2f"),
                "source_system": "simulated_bank",
                "is_simulated": True,
                "record_id": "BANK-{}-{}".format(day, account),
            })
    if not rows:
        raise ValueError("Bank statement is empty")

    content = "".join(json.dumps(row, sort_keys=True) + "\n"
                      for row in sorted(rows, key=lambda row: row["account_id"])).encode("utf-8")
    digest = hashlib.sha256(content).hexdigest()
    delivery_id = "bank-{}-{}-{}".format(scenario, day, digest[:12])
    folder = data_dir / "daily_bank" / scenario / day
    data_file = folder / "balances.jsonl"
    manifest_file = folder / "manifest.json"
    manifest = {
        "business_date": day, "scenario_id": scenario,
        "delivery_id": delivery_id, "record_count": len(rows),
        "files": {"balances.jsonl": digest},
    }
    manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    if folder.exists():
        if (not data_file.is_file() or not manifest_file.is_file()
                or data_file.read_bytes() != content
                or manifest_file.read_bytes() != manifest_bytes):
            raise ValueError("Saved bank delivery differs: {}".format(folder))
    else:
        folder.mkdir(parents=True)
        data_file.write_bytes(content)
        manifest_file.write_bytes(manifest_bytes)
    return {
        "id": delivery_id, "source": "bank", "date": day,
        "scenario": scenario, "rows": len(rows), "sha256": digest,
        "path": "bank/business_date={}/delivery_id={}/balances.jsonl".format(day, delivery_id),
        "file": data_file,
    }


def submit(cursor, item):
    cursor.execute(
        "SELECT delivery_id, expected_rows, file_sha256, stage_path, status "
        "FROM " + REGISTRY + " WHERE source_name = 'bank' AND business_date = %s "
        "AND scenario_id = %s",
        (item["date"], item["scenario"])
    )
    saved = cursor.fetchall()
    if len(saved) > 1:
        raise ValueError("More than one bank delivery is registered")
    expected = (item["id"], item["rows"], item["sha256"], item["path"])
    if saved:
        if tuple(map(str, saved[0][:4])) != tuple(map(str, expected)):
            raise ValueError("Bank delivery changed; review before replacing it")
        if saved[0][4] == "LOADED":
            print("Already loaded:", item["id"])
            return
    else:
        cursor.execute(
            "INSERT INTO " + REGISTRY + " (delivery_id, source_name, business_date, "
            "scenario_id, expected_rows, file_sha256, stage_path, status) "
            "VALUES (%s, 'bank', %s, %s, %s, %s, %s, 'PREPARED')",
            (item["id"], item["date"], item["scenario"], item["rows"],
             item["sha256"], item["path"])
        )

    staged = "@{}/{}".format(STAGE, item["path"])
    if not stage_has_file(cursor, staged, item["path"]):
        uri = "file://" + item["file"].resolve().as_posix()
        cursor.execute("PUT '{}' '{}' AUTO_COMPRESS = FALSE OVERWRITE = FALSE".format(
            uri.replace("'", "''"), staged.rsplit("/", 1)[0] + "/"))
    if not stage_has_file(cursor, staged, item["path"]):
        raise RuntimeError("Bank file is missing from the stage")

    cursor.execute(
        "COPY INTO " + TABLE + " (payload, source_file, source_row_number) "
        "FROM (SELECT t.$1, METADATA$FILENAME, METADATA$FILE_ROW_NUMBER "
        "FROM " + staged + " t) "
        "FILE_FORMAT = (FORMAT_NAME = NORTHBRIDGE_DEV.RAW.DAILY_JSON) "
        "ON_ERROR = ABORT_STATEMENT"
    )
    cursor.execute("SELECT COUNT(*) FROM " + TABLE + " WHERE ENDSWITH(source_file, %s)",
                   (item["path"],))
    if cursor.fetchone()[0] != item["rows"]:
        raise RuntimeError("Bank RAW count does not match the delivery")
    cursor.execute("UPDATE " + REGISTRY + " SET status = 'LOADED', "
                   "submitted_at = CURRENT_TIMESTAMP() WHERE delivery_id = %s",
                   (item["id"],))
    print("Loaded {} bank balances for {}".format(item["rows"], item["date"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("business_date")
    parser.add_argument("--scenario", default="sim-close-20261008")
    parser.add_argument("--statement", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--submit", action="store_true")
    args = parser.parse_args()
    item = prepare(args.statement, args.data_dir, args.business_date, args.scenario)
    print("{} bank balances prepared: {}".format(item["rows"], item["path"]))
    if args.submit:
        with snowflake_connection() as connection:
            with connection.cursor() as cursor:
                submit(cursor, item)


if __name__ == "__main__":
    main()
