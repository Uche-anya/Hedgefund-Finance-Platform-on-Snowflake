"""Load one file that Snowpipe registered as failed.

Use this only after checking the pipe error. A failed filename cannot simply
be sent to Snowpipe again.
"""

import argparse
from datetime import date
from pathlib import Path

from pipeline.check_raw import RAW_TABLE
from pipeline.load_day import REGISTRY, STAGE, delivery, snowflake_connection, stage_has_file


def recover(cursor, item):
    cursor.execute(
        "SELECT source_name, business_date, scenario_id, expected_rows, "
        "file_sha256, stage_path, status FROM " + REGISTRY + " WHERE delivery_id = %s",
        (item["id"],)
    )
    saved = cursor.fetchone()
    expected = (item["source"], item["date"], item["scenario"],
                item["rows"], item["sha256"], item["path"])
    if not saved or tuple(str(v) for v in saved[:6]) != tuple(str(v) for v in expected):
        raise ValueError("Delivery registry does not match the local file")
    if saved[6] != "SUBMITTED" or item["rows"] == 0:
        raise ValueError("Only a submitted, nonempty delivery can be recovered")

    table = RAW_TABLE[item["source"]]
    cursor.execute("SELECT COUNT(*) FROM " + table + " WHERE ENDSWITH(source_file, %s)",
                   (item["path"],))
    if cursor.fetchone()[0] != 0:
        raise ValueError("RAW already contains rows for this file; inspect before recovery")

    stage_file = "@{}/{}".format(STAGE, item["path"])
    if stage_has_file(cursor, stage_file, item["path"]):
        raise ValueError("Expected stage path already exists; inspect before recovery")

    uri = "file://" + item["file"].resolve().as_posix()
    stage_dir = stage_file.rsplit("/", 1)[0] + "/"
    cursor.execute("PUT '{}' '{}' AUTO_COMPRESS = FALSE OVERWRITE = FALSE".format(
        uri.replace("'", "''"), stage_dir
    ))
    if not stage_has_file(cursor, stage_file, item["path"]):
        raise RuntimeError("Upload did not put the file at the expected path")

    cursor.execute(
        "COPY INTO " + table + " (payload, source_file, source_row_number) "
        "FROM (SELECT t.$1, METADATA$FILENAME, METADATA$FILE_ROW_NUMBER "
        "FROM " + stage_file + " t) "
        "FILE_FORMAT = (FORMAT_NAME = NORTHBRIDGE_DEV.RAW.DAILY_JSON) "
        "ON_ERROR = ABORT_STATEMENT"
    )
    cursor.execute("SELECT COUNT(*) FROM " + table + " WHERE ENDSWITH(source_file, %s)",
                   (item["path"],))
    count = cursor.fetchone()[0]
    if count != item["rows"]:
        raise RuntimeError("Expected {} rows, found {}".format(item["rows"], count))
    print("Recovered {} rows for {}".format(count, item["id"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("business_date")
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--source", choices=("oms", "settlements"), required=True)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    args = parser.parse_args()
    try:
        date.fromisoformat(args.business_date)
    except ValueError:
        parser.exit(2, "Business date must be YYYY-MM-DD.\n")
    item = delivery(args.data_dir, args.scenario, args.business_date, args.source)
    with snowflake_connection() as connection:
        with connection.cursor() as cursor:
            recover(cursor, item)


if __name__ == "__main__":
    main()
