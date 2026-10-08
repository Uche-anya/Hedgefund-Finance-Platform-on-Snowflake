"""Load one checked daily price package into Snowflake RAW."""

import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.load_oms_snowpipe import connect, SAFE_DELIVERY


STAGE = "NORTHBRIDGE_DEV.RAW.HISTORICAL_PRICES_STAGE"
TABLE = "NORTHBRIDGE_DEV.RAW.HISTORICAL_PRICES"
FORMAT = "NORTHBRIDGE_DEV.RAW.HISTORICAL_PRICES_CSV"


def checked_package(folder):
    folder = folder.resolve()
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    delivery_id = manifest["delivery_id"]
    if not SAFE_DELIVERY.fullmatch(delivery_id):
        raise ValueError("Invalid price delivery ID")
    csv_path = folder / "prices.csv"
    digest = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    if digest != manifest["files"]["prices.csv"]:
        raise ValueError("Price file changed after packaging")
    with csv_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    day = manifest["valuation_date"]
    if (len(rows) != manifest["record_count"]
            or len({row["universe_ticker"] for row in rows}) != len(rows)
            or any(row["valuation_date"] != day for row in rows)):
        raise ValueError("Price count, ticker or date differs from manifest")
    return csv_path, manifest, digest


def check_replacement(existing, manifest):
    """A second price file must name a price file already held for that day."""
    old = manifest.get('replaces_delivery_id')
    if old and old not in existing:
        raise ValueError('The price delivery being replaced is not in RAW')
    if existing and manifest['delivery_id'] not in existing and old not in existing:
        raise ValueError('Another price delivery exists; name it in replaces_delivery_id')


def load(folder):
    csv_path, manifest, digest = checked_package(folder)
    delivery_id = manifest["delivery_id"]
    day = manifest["valuation_date"]
    expected = manifest["record_count"]
    connection = connect("northbridge_daily_prices")
    try:
        with connection.cursor() as cursor:
            cursor.execute("USE SECONDARY ROLES NONE")
            cursor.execute(
                f"SELECT DISTINCT delivery_id FROM {TABLE} WHERE valuation_date = %s",
                (day,))
            check_replacement({row[0] for row in cursor.fetchall()}, manifest)

            local = csv_path.as_posix().replace("'", "''")
            cursor.execute(
                f"PUT 'file:///{local}' @{STAGE}/{delivery_id}/ "
                "AUTO_COMPRESS=TRUE OVERWRITE=FALSE")
            put = cursor.fetchone()
            if not put or str(put[6]).upper() not in ("UPLOADED", "SKIPPED"):
                raise RuntimeError(f"Price upload failed: {put}")
            staged_name = put[1]

            cursor.execute(f"""
                COPY INTO {TABLE} (
                    valuation_date, universe_ticker, instrument_id, share_class_figi,
                    source_ticker, currency, open_price, high_price, low_price,
                    close_price, volume, price_basis, identity_status, source_system,
                    input_file, input_row_number, delivery_id, source_file,
                    source_row_number
                )
                FROM (
                    SELECT t.$1, t.$2, t.$3, t.$4, t.$5, t.$6, t.$7, t.$8,
                           t.$9, t.$10, t.$11, t.$12, t.$13, t.$14, t.$15, t.$16,
                           '{delivery_id}', METADATA$FILENAME, METADATA$FILE_ROW_NUMBER
                    FROM @{STAGE}/{delivery_id}/ t
                )
                FILES = ('{staged_name}')
                FILE_FORMAT = (FORMAT_NAME = '{FORMAT}')
                ON_ERROR = ABORT_STATEMENT
                FORCE = FALSE
            """)
            cursor.fetchall()

            cursor.execute(
                f"SELECT COUNT(*), COUNT(DISTINCT universe_ticker), "
                f"MIN(valuation_date), MAX(valuation_date), "
                f"MIN(loaded_at), MAX(loaded_at) FROM {TABLE} "
                "WHERE delivery_id = %s", (delivery_id,))
            count, tickers, first, last, first_loaded, last_loaded = cursor.fetchone()
            if (count, tickers, first, last) != (expected, expected, day, day):
                raise ValueError("Loaded price rows differ from the package")

            cursor.execute("""
                SELECT manifest_sha256, expected_rows, received_rows, delivery_status
                FROM NORTHBRIDGE_DEV.OPERATIONS.DELIVERIES
                WHERE source_name = 'daily_prices' AND delivery_id = %s
            """, (delivery_id,))
            receipts = cursor.fetchall()
            evidence = (digest, expected, expected, "READY")
            if len(receipts) > 1 or (receipts and tuple(receipts[0]) != evidence):
                raise ValueError("Conflicting price delivery receipt")
            if not receipts:
                cursor.execute("""
                    INSERT INTO NORTHBRIDGE_DEV.OPERATIONS.DELIVERIES
                        (source_name, delivery_id, manifest_sha256, expected_rows,
                         received_rows, delivery_status, first_loaded_at, last_loaded_at)
                    VALUES ('daily_prices', %s, %s, %s, %s, 'READY', %s, %s)
                """, (delivery_id, digest, expected, expected,
                      first_loaded, last_loaded))
        print(f"{day}: {expected} prices loaded; delivery {delivery_id} READY")
    finally:
        connection.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    args = parser.parse_args()
    load(args.folder)
