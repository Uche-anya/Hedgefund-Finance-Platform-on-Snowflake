"""Stage a checked daily delivery and ask Snowpipe to load it."""

import argparse
import hashlib
import os
import re
from datetime import date
from pathlib import Path

from pipeline.check_day import closing_prices, read_delivery


STAGE = "NORTHBRIDGE_DEV.RAW.DAILY_LANDING"
REGISTRY = "NORTHBRIDGE_DEV.RAW.DAILY_DELIVERIES"
PIPE = {
    "oms": "NORTHBRIDGE_DEV.RAW.DAILY_OMS_PIPE",
    "settlements": "NORTHBRIDGE_DEV.RAW.DAILY_SETTLEMENT_PIPE",
}


def delivery(data_dir, scenario, business_date, source):
    if source == "oms":
        folder = data_dir / "daily_oms" / scenario / business_date
        file_name, date_field = "oms.jsonl", "business_date"
    else:
        folder = data_dir / "daily_settlements" / scenario / business_date
        file_name, date_field = "settlements.jsonl", "settlement_date"

    manifest, records = read_delivery(folder, file_name, date_field,
                                      business_date, scenario)
    delivery_id = manifest["delivery_id"]
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", delivery_id):
        raise ValueError("Unsafe delivery ID: {}".format(delivery_id))
    path = "{}/business_date={}/delivery_id={}/{}".format(
        source, business_date, delivery_id, file_name
    )
    return {
        "source": source,
        "file": folder / file_name,
        "path": path,
        "id": delivery_id,
        "date": business_date,
        "scenario": scenario,
        "rows": len(records),
        "sha256": hashlib.sha256((folder / file_name).read_bytes()).hexdigest(),
        "records": records,
    }


def snowflake_connection():
    names = ("SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_PRIVATE_KEY_FILE",
             "SNOWFLAKE_ROLE")
    missing = [name for name in names if not os.environ.get(name)]
    if missing:
        raise ValueError("Missing environment settings: {}".format(", ".join(missing)))

    import snowflake.connector

    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        authenticator="SNOWFLAKE_JWT",
        private_key_file=os.environ["SNOWFLAKE_PRIVATE_KEY_FILE"],
        private_key_file_pwd=os.environ.get("SNOWFLAKE_PRIVATE_KEY_PASSWORD"),
        role=os.environ["SNOWFLAKE_ROLE"],
        database="NORTHBRIDGE_DEV",
        schema="RAW",
    )


def request_snowpipe(item):
    from cryptography.hazmat.primitives.serialization import (
        Encoding, NoEncryption, PrivateFormat, load_pem_private_key
    )
    from snowflake.ingest import SimpleIngestManager, StagedFile

    key_path = Path(os.environ["SNOWFLAKE_PRIVATE_KEY_FILE"])
    password = os.environ.get("SNOWFLAKE_PRIVATE_KEY_PASSWORD")
    key = load_pem_private_key(key_path.read_bytes(),
                               password.encode() if password else None)
    pem = key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8,
                            NoEncryption()).decode("ascii")
    account = os.environ["SNOWFLAKE_ACCOUNT"]
    manager = SimpleIngestManager(
        account=account,
        host=account + ".snowflakecomputing.com",
        user=os.environ["SNOWFLAKE_USER"],
        pipe=PIPE[item["source"]],
        private_key=pem,
    )
    # The pipe starts at @DAILY_LANDING/oms/ or /settlements/.
    file_in_pipe = item["path"].split("/", 1)[1]
    result = manager.ingest_files([StagedFile(file_in_pipe, item["file"].stat().st_size)])
    if result.get("responseCode") != "SUCCESS":
        raise RuntimeError("Snowpipe did not accept {}".format(item["path"]))


def stage_has_file(cursor, stage_file, path):
    cursor.execute("LIST '{}'".format(stage_file))
    return any(row[0].endswith("/" + path) for row in cursor.fetchall())


def submit(cursor, item):
    cursor.execute(
        "SELECT source_name, business_date, scenario_id, expected_rows, "
        "file_sha256, stage_path, status FROM " + REGISTRY + " WHERE delivery_id = %s",
        (item["id"],)
    )
    saved = cursor.fetchone()
    expected = (item["source"], item["date"], item["scenario"],
                item["rows"], item["sha256"], item["path"])
    was_registered = saved is not None
    if saved:
        if tuple(str(value) for value in saved[:6]) != tuple(str(value) for value in expected):
            raise ValueError("Delivery ID already used for different content: {}".format(item["id"]))
        if saved[6] in ("SUBMITTED", "EMPTY"):
            print("Already submitted: {}".format(item["id"]))
            return
    else:
        cursor.execute(
            "INSERT INTO " + REGISTRY + " (delivery_id, source_name, business_date, "
            "scenario_id, expected_rows, file_sha256, stage_path, status) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, 'PREPARED')",
            (item["id"],) + expected
        )

    if item["rows"] == 0:
        cursor.execute("UPDATE " + REGISTRY + " SET status = 'EMPTY', "
                       "submitted_at = CURRENT_TIMESTAMP() WHERE delivery_id = %s",
                       (item["id"],))
        print("Registered empty delivery: {}".format(item["id"]))
        return

    stage_file = "@{}/{}".format(STAGE, item["path"])
    staged = stage_has_file(cursor, stage_file, item["path"])
    if staged and not was_registered:
        raise ValueError("Stage path exists without a registry entry: {}".format(stage_file))
    if not staged:
        uri = "file://" + item["file"].resolve().as_posix()
        stage_dir = stage_file.rsplit("/", 1)[0] + "/"
        cursor.execute("PUT '{}' '{}' AUTO_COMPRESS = FALSE OVERWRITE = FALSE".format(
            uri.replace("'", "''"), stage_dir
        ))
    request_snowpipe(item)
    cursor.execute("UPDATE " + REGISTRY + " SET status = 'SUBMITTED', "
                   "submitted_at = CURRENT_TIMESTAMP() WHERE delivery_id = %s",
                   (item["id"],))
    print("Submitted to Snowpipe: {}".format(item["id"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("business_date", help="YYYY-MM-DD")
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--prices", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--submit", action="store_true", help="Connect and write to Snowflake")
    args = parser.parse_args()
    try:
        date.fromisoformat(args.business_date)
    except ValueError:
        parser.exit(2, "Business date must be YYYY-MM-DD.\n")

    items = [delivery(args.data_dir, args.scenario, args.business_date, source)
             for source in ("oms", "settlements")]
    tickers = {trade["market_ticker"] for trade in items[0]["records"]}
    if closing_prices(args.prices, args.business_date, tickers) != tickers:
        parser.exit(1, "Closing prices are incomplete.\n")
    for item in items:
        print("{}: {} rows, {}".format(item["source"], item["rows"], item["path"]))

    if args.submit:
        try:
            with snowflake_connection() as connection:
                with connection.cursor() as cursor:
                    for item in items:
                        submit(cursor, item)
        except (ValueError, ModuleNotFoundError) as error:
            parser.exit(1, "Cannot submit: {}\n".format(error))


if __name__ == "__main__":
    main()
