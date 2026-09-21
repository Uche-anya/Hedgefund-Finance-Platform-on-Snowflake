"""Run the daily USD close from configuration and leave its candidate for review."""

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
from uuid import uuid4

from prepare_daily import prepare_daily_candidate
from business_calendar import POLICY, calendar_policy, read_calendar, validate_close_dates
from publication import check_eligible, now, show
from run_config import unique_fields
from run_pipeline import save_run


PATHS = ("opening_database", "database", "delivery", "prices", "references", "run_root")
DATES = ("previous_date", "business_date")


def read_daily_config(path):
    path = path.resolve()
    raw = path.read_bytes()
    settings = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique_fields)
    required = set(PATHS + DATES)
    if not isinstance(settings, dict) or set(settings) not in (required, required | {"calendar", "calendar_sha256"}):
        raise ValueError("Daily configuration must contain exactly: " + ", ".join(PATHS + DATES))
    if any(not isinstance(value, str) or not value.strip() for value in settings.values()):
        raise ValueError("Daily settings must be nonempty text")
    for name in DATES:
        if date.fromisoformat(settings[name]).isoformat() != settings[name]:
            raise ValueError(f"Use YYYY-MM-DD for {name}")
    calendar = None
    if "calendar" in settings:
        calendar = read_calendar((path.parent / settings["calendar"]).resolve(), settings["calendar_sha256"])
    validate_close_dates(settings["previous_date"], settings["business_date"], calendar)
    resolved = dict(settings)
    for name in PATHS:
        resolved[name] = (path.parent / settings[name]).resolve()
    if "calendar" in settings:
        resolved["calendar"] = (path.parent / settings["calendar"]).resolve()
    return resolved, {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(), "settings": settings}


def run_daily(settings, evidence=None):
    run_id = uuid4().hex
    settings["run_root"].mkdir(parents=True, exist_ok=True)
    path = settings["run_root"] / f"{run_id}.json"
    record = {"run_id": run_id, "workflow": "daily_usd", "started_at": now(), "finished_at": None,
              "business_date": settings["business_date"], "previous_date": settings["previous_date"],
              "status": "RUNNING", "stage": "prepare_candidate", "candidate_id": None,
              "candidate_reused": False, "run_record": str(path.resolve()),
              "paths": {name: str(settings[name].resolve()) for name in PATHS},
              "configuration": evidence, "calendar_policy": POLICY,
              "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    save_run(path, record)
    try:
        calendar = None
        if "calendar" in settings:
            calendar = read_calendar(settings["calendar"], settings["calendar_sha256"])
        record.update(calendar_policy=calendar_policy(calendar), calendar=calendar)
        save_run(path, record)
        candidate_id, reused = prepare_daily_candidate(
            settings["database"], settings["opening_database"], settings["previous_date"],
            settings["delivery"], settings["prices"], settings["references"], settings["business_date"],
            reuse=True, calendar=calendar)
        record.update(candidate_id=candidate_id, candidate_reused=reused, stage="check_candidate")
        save_run(path, record)
        review = show(settings["database"], candidate_id)
        candidate = review["candidate"]
        report = candidate["reconciliation"]
        record.update(input_key=candidate["input_key"], opening_publication=report["opening_publication"],
                      controls=report["controls"], approval=review["approval"], publication=review["publication"],
                      manifests={"activity": report["manifest_sha256"], "prices": report["price_manifest_sha256"],
                                 "references": report["reference_manifest_sha256"]})
        check_eligible(candidate)
        record["status"] = ("ALREADY_PUBLISHED" if review["publication"] else
                            "ALREADY_APPROVED" if review["approval"] else "READY_FOR_REVIEW")
    except Exception as error:
        record["status"] = "FAILED"
        record["error"] = {"type": type(error).__name__, "message": str(error)}
    record["finished_at"] = now()
    save_run(path, record)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    try:
        settings, evidence = read_daily_config(args.config)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    record = run_daily(settings, evidence)
    print(f"{record['status']} | {record['business_date']} | daily USD close")
    if record["candidate_id"]:
        action = "Reused" if record["candidate_reused"] else "Created"
        print(f"{action} candidate: {record['candidate_id']}")
    if record["status"] == "FAILED":
        print(f"Stopped at {record['stage']}: {record['error']['message']}")
    print(f"Run record: {record['run_record']}")
    return 1 if record["status"] == "FAILED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
