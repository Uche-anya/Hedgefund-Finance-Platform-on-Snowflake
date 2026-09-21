"""Run the saved-input GBP close and leave a candidate for human review."""

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
from uuid import uuid4

from fx_rates import verify_fx
from landing import verify_delivery
from publication import check_eligible, now, prepare_candidate, show
from run_config import DATE_FIELDS, PATH_FIELDS, read_config


def save_run(path, record):
    # Readers see either the previous complete record or the new complete record.
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def run_pipeline(nav_folder, reference_folder, fx_folder, gbp_folder,
                 business_date, as_of, database, run_root, config_evidence=None):
    run_id = uuid4().hex
    run_root.mkdir(parents=True, exist_ok=True)
    path = run_root / f"{run_id}.json"
    inputs = {"nav": nav_folder, "usd_references": reference_folder,
              "fx": fx_folder, "gbp_references": gbp_folder}
    record = {"run_id": run_id, "business_date": business_date, "as_of": as_of,
              "started_at": now(), "finished_at": None, "status": "RUNNING",
              "stage": "check_inputs", "candidate_id": None, "candidate_reused": False,
              "database": str(database.resolve()), "run_record": str(path.resolve()),
              "inputs": {name: str(folder.resolve()) for name, folder in inputs.items()},
              "manifest_sha256": {}, "steps": [],
              "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    if config_evidence is not None:
        record["configuration"] = config_evidence
    save_run(path, record)
    try:
        date.fromisoformat(business_date)
        date.fromisoformat(as_of)
        if business_date > as_of:
            raise ValueError("Valuation date must be on or after the trade batch date")
        verify_delivery(nav_folder, business_date, "nav")
        verify_delivery(reference_folder, as_of, "references")
        verify_delivery(gbp_folder, as_of, "gbp_references")
        rates = verify_fx(fx_folder)
        if as_of not in rates:
            raise ValueError(f"Missing FX rate for {as_of}")
        record["manifest_sha256"] = {
            name: hashlib.sha256((folder / "manifest.json").read_bytes()).hexdigest()
            for name, folder in inputs.items()}
        record["steps"].append({"stage": "check_inputs", "status": "PASS"})

        record["stage"] = "prepare_candidate"
        save_run(path, record)
        # Preparation calculates and reconciles USD, translates to GBP,
        # checks GBP, then stores that exact calculation. Don't calculate twice.
        candidate_id, reused = prepare_candidate(database, nav_folder, reference_folder, business_date,
                                                as_of, "GBP", fx_folder, gbp_folder, reuse=True)
        record["candidate_id"] = candidate_id
        record["candidate_reused"] = reused
        record["steps"].append({"stage": "prepare_candidate", "status": "PASS"})

        record["stage"] = "check_candidate"
        save_run(path, record)
        review = show(database, candidate_id)
        candidate = review["candidate"]
        record["input_key"] = candidate["input_key"]
        record["approval"] = review["approval"]
        record["publication"] = review["publication"]
        record["controls"] = candidate["reconciliation"]["controls"]
        check_eligible(candidate)
        record["steps"].append({"stage": "check_candidate", "status": "PASS"})
        record["status"] = ("ALREADY_PUBLISHED" if review["publication"] else
                            "ALREADY_APPROVED" if review["approval"] else "READY_FOR_REVIEW")
    except Exception as error:
        # Preserve failed candidates for investigation, but never approve them.
        record["status"] = "FAILED"
        record["error"] = {"type": type(error).__name__, "message": str(error)}
        record["steps"].append({"stage": record["stage"], "status": "FAIL"})
    record["finished_at"] = now()
    save_run(path, record)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, help="JSON file containing dates and paths")
    parser.add_argument("--delivery", type=Path)
    parser.add_argument("--references", type=Path)
    parser.add_argument("--fx-delivery", type=Path)
    parser.add_argument("--gbp-references", type=Path)
    parser.add_argument("--business-date")
    parser.add_argument("--as-of")
    root = Path(__file__).resolve().parent / "data"
    parser.add_argument("--database", type=Path)
    parser.add_argument("--run-root", type=Path)
    args = parser.parse_args()
    evidence = None
    if args.config is not None:
        if any(getattr(args, name) is not None for name in PATH_FIELDS + DATE_FIELDS):
            parser.error("Use --config by itself; do not mix it with date or path options")
        try:
            settings, evidence = read_config(args.config)
        except (OSError, ValueError) as error:
            parser.error(str(error))
        for name, value in settings.items():
            setattr(args, name, value)
    else:
        required = ("delivery", "references", "fx_delivery", "gbp_references") + DATE_FIELDS
        if any(getattr(args, name) is None for name in required):
            parser.error("Supply --config or all four input paths and both dates")
        args.database = args.database or root / "gbp_pipeline.sqlite"
        args.run_root = args.run_root or root / "runs"
    record = run_pipeline(args.delivery, args.references, args.fx_delivery,
                          args.gbp_references, args.business_date, args.as_of,
                          args.database, args.run_root, evidence)
    print(f"{record['status']} | valuation date {record['as_of']}")
    print(f"Run record: {record['run_record']}")
    if record["candidate_id"]:
        print(f"Candidate: {record['candidate_id']}")
        print("Reused existing candidate" if record["candidate_reused"] else "Created new candidate")
    if record["status"] == "FAILED":
        print(f"Stopped at {record['stage']}: {record['error']['message']}")
        return 1
    print("Checks passed. Approval and publication are separate steps.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
