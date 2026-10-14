
import argparse
import hashlib
import json
from pathlib import Path

from pipeline.load_day import REGISTRY, STAGE, snowflake_connection, stage_has_file


TABLE = "NORTHBRIDGE_DEV.RAW.DAILY_DIVIDEND_EVENTS"


def prepare(folder):
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    data_file = folder / "dividends.jsonl"
    pages_file = folder / "response_pages.json"
    body = data_file.read_bytes()
    evidence = pages_file.read_bytes()
    if (hashlib.sha256(body).hexdigest() != manifest["records_sha256"] or
            hashlib.sha256(evidence).hexdigest() != manifest["response_sha256"]):
        raise ValueError("Saved dividend snapshot changed")
    if manifest["delivery_id"] != folder.name:
        raise ValueError("Dividend folder and delivery ID disagree")
    if len(body.splitlines()) != manifest["record_count"]:
        raise ValueError("Dividend record count changed")
    path = "dividends/business_date={}/delivery_id={}/dividends.jsonl".format(
        manifest["business_date"], manifest["delivery_id"])
    return {"id": manifest["delivery_id"], "date": manifest["business_date"],
            "rows": manifest["record_count"], "sha256": manifest["records_sha256"],
            "path": path, "file": data_file, "folder": folder}


def put(cursor, path, file):
    stage_file = "@{}/{}".format(STAGE, path)
    if stage_has_file(cursor, stage_file, path):
        return
    uri = "file://" + file.resolve().as_posix()
    stage_dir = stage_file.rsplit("/", 1)[0] + "/"
    cursor.execute("PUT '{}' '{}' AUTO_COMPRESS = FALSE OVERWRITE = FALSE".format(
        uri.replace("'", "''"), stage_dir
    ))
    if not stage_has_file(cursor, stage_file, path):
        raise RuntimeError("Dividend file did not reach the stage")


def submit(cursor, item):
    cursor.execute(
        "SELECT source_name, business_date, scenario_id, expected_rows, "
        "file_sha256, stage_path, status FROM " + REGISTRY + " WHERE delivery_id = %s",
        (item["id"],)
    )
    saved = cursor.fetchone()
    expected = ("dividends", item["date"], "massive", item["rows"],
                item["sha256"], item["path"])
    if saved:
        if tuple(str(v) for v in saved[:6]) != tuple(str(v) for v in expected):
            raise ValueError("Dividend delivery ID already used for other content")
        if saved[6] in ("LOADED", "EMPTY"):
            print("Already loaded: {}".format(item["id"]))
            return
    else:
        cursor.execute(
            "INSERT INTO " + REGISTRY + " (delivery_id, source_name, business_date, "
            "scenario_id, expected_rows, file_sha256, stage_path, status) "
            "VALUES (%s, 'dividends', %s, 'massive', %s, %s, %s, 'PREPARED')",
            (item["id"], item["date"], item["rows"], item["sha256"], item["path"])
        )

    for name in ("response_pages.json", "manifest.json"):
        evidence_path = "provider_evidence/dividends/delivery_id={}/{}".format(
            item["id"], name)
        put(cursor, evidence_path, item["folder"] / name)

    if item["rows"]:
        put(cursor, item["path"], item["file"])
        stage_file = "@{}/{}".format(STAGE, item["path"])
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
            raise RuntimeError("Dividend RAW count does not match the manifest")
    cursor.execute("UPDATE " + REGISTRY + " SET status = %s, "
                   "submitted_at = CURRENT_TIMESTAMP() WHERE delivery_id = %s",
                   ("LOADED" if item["rows"] else "EMPTY", item["id"]))
    print("Loaded {} dividend events: {}".format(item["rows"], item["id"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot_folder", type=Path)
    parser.add_argument("--submit", action="store_true")
    args = parser.parse_args()
    try:
        item = prepare(args.snapshot_folder)
        print("{} events prepared from {}".format(item["rows"], item["date"]))
        if args.submit:
            with snowflake_connection() as connection:
                with connection.cursor() as cursor:
                    submit(cursor, item)
    except (ValueError, OSError, RuntimeError, KeyError) as error:
        parser.exit(1, "Dividend load stopped: {}\n".format(error))


if __name__ == "__main__":
    main()
