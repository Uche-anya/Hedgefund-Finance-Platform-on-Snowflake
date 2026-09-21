"""Part 7: review and publish complete local closes using SQLite transactions."""

import argparse
from contextlib import contextmanager
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

from reconcile import reconcile


SCHEMA = """
CREATE TABLE IF NOT EXISTS candidates (
    id TEXT PRIMARY KEY,
    as_of TEXT NOT NULL,
    payload TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS approvals (
    candidate_id TEXT PRIMARY KEY REFERENCES candidates(id),
    reviewer TEXT NOT NULL,
    note TEXT NOT NULL,
    approved_at TEXT NOT NULL,
    expected_version INTEGER NOT NULL CHECK (expected_version >= 0)
);
CREATE TABLE IF NOT EXISTS publications (
    as_of TEXT NOT NULL,
    version INTEGER NOT NULL,
    candidate_id TEXT UNIQUE NOT NULL REFERENCES approvals(candidate_id),
    published_at TEXT NOT NULL,
    PRIMARY KEY (as_of, version)
);
CREATE TABLE IF NOT EXISTS candidate_reuse (
    input_key TEXT PRIMARY KEY,
    candidate_id TEXT UNIQUE NOT NULL REFERENCES candidates(id)
);
"""


def now():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def database(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(SCHEMA)
        for table in ("candidates", "approvals", "publications", "candidate_reuse"):
            for action in ("UPDATE", "DELETE"):
                # These identifiers are fixed here, never supplied by a user.
                connection.execute(f"""
                    CREATE TRIGGER IF NOT EXISTS keep_{table}_{action}
                    BEFORE {action} ON {table}
                    BEGIN SELECT RAISE(ABORT, 'History is immutable'); END
                """)
        connection.execute("BEGIN IMMEDIATE")
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def read_candidate(connection, candidate_id):
    row = connection.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    if row is None:
        raise ValueError("Unknown candidate")
    if hashlib.sha256(row["payload"].encode()).hexdigest() != row["sha256"]:
        raise ValueError("Candidate checksum mismatch")
    return json.loads(row["payload"])


def check_eligible(candidate):
    report = candidate["reconciliation"]
    if report["status"] != "PASS" or not report["controls"] or any(
        row["status"] != "PASS" for row in report["controls"]
    ):
        raise ValueError("Approval/publication blocked: reconciliation did not pass")
    if any(row["status"] == "OVERDUE" for row in report["close"]["obligations"]):
        raise ValueError("Approval/publication blocked: overdue settlement obligations")


def current_version(connection, as_of):
    row = connection.execute(
        "SELECT COALESCE(MAX(version), 0) FROM publications WHERE as_of = ?", (as_of,)
    ).fetchone()
    return row[0]


def prepare(db_path, nav_folder, reference_folder, business_date, as_of, currency="GBP",
            fx_folder=None, gbp_reference_folder=None):
    candidate_id, _ = prepare_candidate(db_path, nav_folder, reference_folder, business_date,
                                      as_of, currency, fx_folder, gbp_reference_folder)
    return candidate_id


def prepare_candidate(db_path, nav_folder, reference_folder, business_date, as_of, currency="GBP",
                      fx_folder=None, gbp_reference_folder=None, reuse=False):
    business_date = date.fromisoformat(business_date).isoformat()
    as_of = date.fromisoformat(as_of).isoformat()
    root = Path(__file__).resolve().parent
    sources = ("build_positions.py", "cash_settlement.py", "fund_nav.py", "reconcile.py", "landing.py", "daily_close.py", "publication.py")
    if (fx_folder is None) != (gbp_reference_folder is None):
        raise ValueError("Supply both FX and GBP reference deliveries")
    if fx_folder is not None:
        if currency != "GBP":
            raise ValueError("FX reporting requires GBP output currency")
        sources += ("fx_rates.py", "market_prices.py", "report_gbp.py", "gbp_reference.py", "reconcile_gbp.py")
    code = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in sources}
    input_key = None
    if reuse:
        # Verify current files even when a previous result may be reusable.
        from landing import verify_delivery
        from fx_rates import verify_fx
        verify_delivery(nav_folder, business_date, "nav")
        verify_delivery(reference_folder, as_of, "references")
        folders = {"nav": nav_folder, "references": reference_folder}
        if fx_folder is not None:
            rates = verify_fx(fx_folder)
            if as_of not in rates:
                raise ValueError(f"Missing FX rate for {as_of}")
            verify_delivery(gbp_reference_folder, as_of, "gbp_references")
            folders.update(fx=fx_folder, gbp_references=gbp_reference_folder)
        identity = {"business_date": business_date, "as_of": as_of, "currency": currency,
                    "code": code, "manifests": {
                        name: hashlib.sha256((folder / "manifest.json").read_bytes()).hexdigest()
                        for name, folder in folders.items()}}
        input_key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    def calculate_report():
        if fx_folder is None:
            return reconcile(nav_folder, reference_folder, business_date, as_of, currency)
        from reconcile_gbp import reconcile_gbp
        return reconcile_gbp(nav_folder, reference_folder, fx_folder, gbp_reference_folder, business_date, as_of)

    # Ordinary preparation keeps its original behaviour: invalid inputs do not
    # create a database. Reusable preparation calculates under the retry lock.
    report = None if reuse else calculate_report()
    with database(db_path) as connection:
        # One transaction covers lookup, creation and registration. Two overlapping
        # retries cannot both create a successful candidate for the same key.
        if input_key:
            previous = connection.execute(
                "SELECT candidate_id FROM candidate_reuse WHERE input_key = ?", (input_key,)
            ).fetchone()
            if previous:
                candidate = read_candidate(connection, previous["candidate_id"])
                check_eligible(candidate)
                return previous["candidate_id"], True
        existing = connection.execute("SELECT payload FROM candidates LIMIT 1").fetchone()
        if existing:
            previous = json.loads(existing["payload"])["reconciliation"]["close"].get("currency", "GBP")
            if previous != currency:
                raise ValueError("Use a separate publication database for each currency scenario")
        if report is None:
            report = calculate_report()
        # Freeze the exact calculation checked by reconcile(), not a second one.
        candidate_id = uuid4().hex
        candidate = {"candidate_id": candidate_id, "trade_batch_date": business_date,
                     "as_of": as_of, "created_at": now(), "code_sha256": code,
                     "reconciliation": report}
        if input_key:
            candidate["input_key"] = input_key
        payload = json.dumps(candidate, sort_keys=True, default=str)
        digest = hashlib.sha256(payload.encode()).hexdigest()
        connection.execute("INSERT INTO candidates VALUES (?, ?, ?, ?, ?)",
                           (candidate_id, as_of, payload, digest, candidate["created_at"]))
        if input_key:
            try:
                check_eligible(candidate)
            except ValueError:
                pass  # Failed candidates remain inspectable, but aren't reusable successes.
            else:
                connection.execute("INSERT INTO candidate_reuse VALUES (?, ?)", (input_key, candidate_id))
    return candidate_id, False


def approve(db_path, candidate_id, reviewer, note, expected_version):
    if not reviewer.strip() or not note.strip() or expected_version < 0:
        raise ValueError("Supply a reviewer, review note and nonnegative expected version")
    with database(db_path) as connection:
        candidate = read_candidate(connection, candidate_id)
        check_eligible(candidate)
        if current_version(connection, candidate["as_of"]) != expected_version:
            raise ValueError("Published version changed; review a new candidate against the current version")
        if connection.execute("SELECT 1 FROM approvals WHERE candidate_id = ?", (candidate_id,)).fetchone():
            raise ValueError("Candidate already has recorded approval")
        connection.execute("INSERT INTO approvals VALUES (?, ?, ?, ?, ?)",
                           (candidate_id, reviewer.strip(), note.strip(), now(), expected_version))


def publish(db_path, candidate_id):
    with database(db_path) as connection:
        candidate = read_candidate(connection, candidate_id)
        check_eligible(candidate)
        existing = connection.execute(
            "SELECT version FROM publications WHERE candidate_id = ?", (candidate_id,)
        ).fetchone()
        if existing:
            return existing["version"]
        approval = connection.execute(
            "SELECT * FROM approvals WHERE candidate_id = ?", (candidate_id,)
        ).fetchone()
        if approval is None:
            raise ValueError("Publication blocked: no recorded approval")
        version = current_version(connection, candidate["as_of"])
        if version != approval["expected_version"]:
            raise ValueError("Stale approval: another version was published; prepare and review a new candidate")
        connection.execute("INSERT INTO publications VALUES (?, ?, ?, ?)",
                           (candidate["as_of"], version + 1, candidate_id, now()))
        return version + 1


def show(db_path, candidate_id):
    with database(db_path) as connection:
        candidate = read_candidate(connection, candidate_id)
        approval = connection.execute("SELECT * FROM approvals WHERE candidate_id = ?", (candidate_id,)).fetchone()
        published = connection.execute("SELECT * FROM publications WHERE candidate_id = ?", (candidate_id,)).fetchone()
        return {"candidate": candidate, "approval": dict(approval) if approval else None,
                "publication": dict(published) if published else None,
                "current_version": current_version(connection, candidate["as_of"])}


def current(db_path, as_of):
    as_of = date.fromisoformat(as_of).isoformat()
    with database(db_path) as connection:
        published = connection.execute(
            "SELECT * FROM publications WHERE as_of = ? ORDER BY version DESC LIMIT 1", (as_of,)
        ).fetchone()
        if published is None:
            raise ValueError("No published close for this date")
        candidate = read_candidate(connection, published["candidate_id"])
        approval = connection.execute("SELECT * FROM approvals WHERE candidate_id = ?", (published["candidate_id"],)).fetchone()
        evidence = {key: candidate["reconciliation"][key] for key in ("local_close", "fx_evidence")
                    if key in candidate["reconciliation"]}
        return {"status": "PUBLISHED (LOCAL SYNTHETIC)", "publication": dict(published),
                **evidence,
                "approval": dict(approval), "close": candidate["reconciliation"]["close"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=Path(__file__).resolve().parent / "data" / "publication.sqlite")
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("prepare")
    create.add_argument("--business-date", required=True, type=date.fromisoformat)
    create.add_argument("--as-of", required=True, type=date.fromisoformat)
    create.add_argument("--delivery", required=True, type=Path)
    create.add_argument("--references", required=True, type=Path)
    create.add_argument("--currency", choices=("GBP", "USD"), default="GBP")
    create.add_argument("--fx-delivery", type=Path)
    create.add_argument("--gbp-references", type=Path)
    for command in ("show", "approve", "publish"):
        action = commands.add_parser(command)
        action.add_argument("--candidate", required=True)
        if command == "approve":
            action.add_argument("--by", required=True)
            action.add_argument("--note", required=True)
            action.add_argument("--expected-version", required=True, type=int)
    read = commands.add_parser("current")
    read.add_argument("--as-of", required=True, type=date.fromisoformat)
    args = parser.parse_args()
    if args.command == "prepare":
        print(prepare(args.database, args.delivery, args.references,
                      args.business_date.isoformat(), args.as_of.isoformat(), args.currency,
                      args.fx_delivery, args.gbp_references))
    elif args.command == "show":
        print(json.dumps(show(args.database, args.candidate), indent=2))
    elif args.command == "approve":
        approve(args.database, args.candidate, args.by, args.note, args.expected_version)
        print("Approval recorded (local asserted identity)")
    elif args.command == "publish":
        print(f"Candidate's published version: {publish(args.database, args.candidate)}")
    else:
        print(json.dumps(current(args.database, args.as_of.isoformat()), indent=2))


if __name__ == "__main__":
    main()
