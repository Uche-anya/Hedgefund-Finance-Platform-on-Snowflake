"""Load the saved opening bank and fund-admin deliveries."""

import argparse
import hashlib
import re
from datetime import date
from decimal import Decimal
from pathlib import Path

from pipeline.check_day import read_delivery
from pipeline.load_day import REGISTRY, STAGE, snowflake_connection, stage_has_file


TABLE = "NORTHBRIDGE_DEV.RAW.DAILY_OPENING_EVENTS"
SOURCES = {
    "opening_bank": ("bank_cash", "balances.jsonl", "statement_date", "closing_balance", "simulated_bank"),
    "opening_admin": ("fund_admin", "events.jsonl", "event_date", "amount", "simulated_fund_administrator"),
}


def delivery(data_dir, scenario, opening_date, source):
    subfolder, filename, date_field, amount_field, source_system = SOURCES[source]
    folder = data_dir / "daily_opening" / scenario / opening_date / subfolder
    manifest, records = read_delivery(folder, filename, "business_date",
                                      opening_date, scenario, date_field)
    delivery_id = manifest["delivery_id"]
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", delivery_id):
        raise ValueError("Unsafe delivery ID")
    accounts = set()
    for row in records:
        account = row.get("account_id")
        if (not account or account in accounts or row.get("currency") != "USD"
                or row.get("source_system") != source_system):
            raise ValueError("Bad opening account or currency")
        if source == "opening_admin" and row.get("event_type") != "INVESTOR_SUBSCRIPTION":
            raise ValueError("Unexpected fund-admin opening event")
        amount = Decimal(row[amount_field])
        if not amount.is_finite() or amount < 0:
            raise ValueError("Negative opening amount")
        accounts.add(account)
    if not records:
        raise ValueError("Opening delivery is empty")

    file_path = folder / filename
    return {
        "id": delivery_id,
        "source": source,
        "scenario": scenario,
        "date": opening_date,
        "rows": len(records),
        "sha256": hashlib.sha256(file_path.read_bytes()).hexdigest(),
        "path": "{}/business_date={}/delivery_id={}/{}".format(
            source, opening_date, delivery_id, filename
        ),
        "file": file_path,
    }


def submit(cursor, item):
    cursor.execute(
        "SELECT delivery_id, expected_rows, file_sha256, stage_path, status "
        "FROM " + REGISTRY + " WHERE source_name = %s AND business_date = %s "
        "AND scenario_id = %s",
        (item["source"], item["date"], item["scenario"])
    )
    saved = cursor.fetchall()
    if len(saved) > 1:
        raise ValueError("Multiple opening deliveries for {}".format(item["source"]))
    expected = (item["id"], item["rows"], item["sha256"], item["path"])
    if saved:
        if tuple(str(v) for v in saved[0][:4]) != tuple(str(v) for v in expected):
            raise ValueError("Opening delivery changed; review it before replacing")
        if saved[0][4] == "LOADED":
            print("Already loaded:", item["id"])
            return
    else:
        cursor.execute(
            "INSERT INTO " + REGISTRY + " (delivery_id, source_name, business_date, "
            "scenario_id, expected_rows, file_sha256, stage_path, status) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, 'PREPARED')",
            (item["id"], item["source"], item["date"], item["scenario"],
             item["rows"], item["sha256"], item["path"])
        )

    stage_file = "@{}/{}".format(STAGE, item["path"])
    if not stage_has_file(cursor, stage_file, item["path"]):
        uri = "file://" + item["file"].resolve().as_posix()
        stage_dir = stage_file.rsplit("/", 1)[0] + "/"
        cursor.execute("PUT '{}' '{}' AUTO_COMPRESS = FALSE OVERWRITE = FALSE".format(
            uri.replace("'", "''"), stage_dir
        ))
    if not stage_has_file(cursor, stage_file, item["path"]):
        raise RuntimeError("Opening file is not at the expected stage path")

    cursor.execute(
        "COPY INTO " + TABLE + " (payload, source_file, source_row_number) "
        "FROM (SELECT t.$1, METADATA$FILENAME, METADATA$FILE_ROW_NUMBER "
        "FROM " + stage_file + " t) "
        "FILE_FORMAT = (FORMAT_NAME = NORTHBRIDGE_DEV.RAW.DAILY_JSON) "
        "ON_ERROR = ABORT_STATEMENT"
    )
    cursor.execute("SELECT COUNT(*) FROM " + TABLE + " WHERE ENDSWITH(source_file, %s)",
                   (item["path"],))
    if cursor.fetchone()[0] != item["rows"]:
        raise RuntimeError("Opening RAW count does not match the manifest")
    cursor.execute("UPDATE " + REGISTRY + " SET status = 'LOADED', "
                   "submitted_at = CURRENT_TIMESTAMP() WHERE delivery_id = %s",
                   (item["id"],))
    print("Loaded {} opening rows from {}".format(item["rows"], item["source"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("opening_date")
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--submit", action="store_true")
    args = parser.parse_args()
    date.fromisoformat(args.opening_date)
    items = [delivery(args.data_dir, args.scenario, args.opening_date, source)
             for source in SOURCES]
    for item in items:
        print("{}: {} rows, {}".format(item["source"], item["rows"], item["path"]))
    if args.submit:
        with snowflake_connection() as connection:
            with connection.cursor() as cursor:
                for item in items:
                    submit(cursor, item)


if __name__ == "__main__":
    main()
