"""Prepare one saved Massive market day and load it into Snowflake RAW."""

import argparse
import csv
import hashlib
import json
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from pipeline.load_day import REGISTRY, STAGE, snowflake_connection, stage_has_file


TABLE = "NORTHBRIDGE_DEV.RAW.DAILY_PRICE_EVENTS"
MARKET = "massive"


def prepare(price_csv, data_dir, business_date):
    day = date.fromisoformat(business_date).isoformat()
    folder = data_dir / "daily_prices" / MARKET / day
    data_file = folder / "prices.jsonl"
    manifest_file = folder / "manifest.json"
    source_hash = hashlib.sha256(price_csv.read_bytes()).hexdigest()
    delivery_id = "massive-prices-{}-{}".format(day.replace("-", ""), source_hash[:12])

    rows = {}
    with price_csv.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["valuation_date"] != day:
                continue
            ticker = row["universe_ticker"]
            if not ticker or ticker in rows:
                raise ValueError("Missing or repeated ticker on {}: {}".format(day, ticker))
            if row["source_system"] != MARKET or row["currency"] != "USD":
                raise ValueError("Unexpected source or currency for {}".format(ticker))
            if row["price_basis"] != "unadjusted":
                raise ValueError("Unexpected price basis for {}".format(ticker))
            try:
                close = Decimal(row["close_price"])
                if not close.is_finite() or close <= 0:
                    raise ValueError("Nonpositive close for {}".format(ticker))
            except InvalidOperation:
                raise ValueError("Invalid close for {}".format(ticker))
            rows[ticker] = row
    if not rows:
        raise ValueError("No prices for {}".format(day))

    lines = [json.dumps(rows[ticker], sort_keys=True) + "\n" for ticker in sorted(rows)]
    contents = "".join(lines).encode("utf-8")
    file_hash = hashlib.sha256(contents).hexdigest()
    manifest = {
        "business_date": day,
        "delivery_id": delivery_id,
        "source_system": MARKET,
        "source_file": str(price_csv),
        "source_sha256": source_hash,
        "record_count": len(rows),
        "files": {"prices.jsonl": file_hash},
    }
    if folder.exists():
        if not data_file.is_file() or not manifest_file.is_file():
            raise ValueError("Incomplete price delivery in {}".format(folder))
        if data_file.read_bytes() != contents or json.loads(manifest_file.read_text(encoding="utf-8")) != manifest:
            raise ValueError("Saved price delivery differs from current input: {}".format(folder))
    else:
        folder.mkdir(parents=True)
        data_file.write_bytes(contents)
        manifest_file.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    return {
        "id": delivery_id,
        "date": day,
        "rows": len(rows),
        "sha256": file_hash,
        "path": "prices/business_date={}/delivery_id={}/prices.jsonl".format(day, delivery_id),
        "file": data_file,
    }


def submit(cursor, item):
    cursor.execute(
        "SELECT delivery_id, expected_rows, file_sha256, stage_path, status "
        "FROM " + REGISTRY + " WHERE source_name = 'prices' AND business_date = %s "
        "AND scenario_id = %s",
        (item["date"], MARKET)
    )
    saved = cursor.fetchall()
    if len(saved) > 1:
        raise ValueError("More than one price delivery registered for {}".format(item["date"]))
    expected = (item["id"], item["rows"], item["sha256"], item["path"])
    if saved:
        if tuple(str(v) for v in saved[0][:4]) != tuple(str(v) for v in expected):
            raise ValueError("Price delivery changed; review before replacing it")
        if saved[0][4] == "LOADED":
            print("Already loaded: {}".format(item["id"]))
            return
    else:
        cursor.execute(
            "INSERT INTO " + REGISTRY + " (delivery_id, source_name, business_date, "
            "scenario_id, expected_rows, file_sha256, stage_path, status) "
            "VALUES (%s, 'prices', %s, %s, %s, %s, %s, 'PREPARED')",
            (item["id"], item["date"], MARKET, item["rows"], item["sha256"], item["path"])
        )

    stage_file = "@{}/{}".format(STAGE, item["path"])
    if not stage_has_file(cursor, stage_file, item["path"]):
        uri = "file://" + item["file"].resolve().as_posix()
        stage_dir = stage_file.rsplit("/", 1)[0] + "/"
        cursor.execute("PUT '{}' '{}' AUTO_COMPRESS = FALSE OVERWRITE = FALSE".format(
            uri.replace("'", "''"), stage_dir
        ))
    if not stage_has_file(cursor, stage_file, item["path"]):
        raise RuntimeError("Price file is not at the expected stage path")

    cursor.execute(
        "COPY INTO " + TABLE + " (payload, source_file, source_row_number) "
        "FROM (SELECT t.$1, METADATA$FILENAME, METADATA$FILE_ROW_NUMBER "
        "FROM " + stage_file + " t) "
        "FILE_FORMAT = (FORMAT_NAME = NORTHBRIDGE_DEV.RAW.DAILY_JSON) "
        "ON_ERROR = ABORT_STATEMENT"
    )
    cursor.execute("SELECT COUNT(*) FROM " + TABLE + " WHERE ENDSWITH(source_file, %s)",
                   (item["path"],))
    count = cursor.fetchone()[0]
    if count != item["rows"]:
        raise RuntimeError("Expected {} prices in RAW; found {}".format(item["rows"], count))
    cursor.execute("UPDATE " + REGISTRY + " SET status = 'LOADED', "
                   "submitted_at = CURRENT_TIMESTAMP() WHERE delivery_id = %s",
                   (item["id"],))
    print("Loaded {} prices for {}".format(count, item["date"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("business_date")
    parser.add_argument("--prices", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--submit", action="store_true")
    args = parser.parse_args()
    item = prepare(args.prices, args.data_dir, args.business_date)
    print("{} prices prepared: {}".format(item["rows"], item["path"]))
    if args.submit:
        with snowflake_connection() as connection:
            with connection.cursor() as cursor:
                submit(cursor, item)


if __name__ == "__main__":
    main()
