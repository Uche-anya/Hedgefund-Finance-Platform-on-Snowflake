"""Save Massive identity evidence around the 2026 Exxon reorganization."""

import csv
from getpass import getpass
import json
import os
from pathlib import Path

from data_extraction.check_bny_identity import check_identities, read_identity


CHECKS = (("XOM", "2026-06-30"), ("XOM", "2026-07-02"))


def inspect(root, key):
    folder = check_identities(root, key, checks=CHECKS)
    before = read_identity((folder / "XOM_2026-06-30.json").read_bytes(), *CHECKS[0])
    after = read_identity((folder / "XOM_2026-07-02.json").read_bytes(), *CHECKS[1])
    row = {
        "ticker": "XOM",
        "last_old_date": CHECKS[0][1],
        "first_new_date": CHECKS[1][1],
        "old_name": before["name"],
        "new_name": after["name"],
        "old_cik": before["cik"],
        "new_cik": after["cik"],
        "old_share_class_figi": before["share_class_figi"],
        "new_share_class_figi": after["share_class_figi"],
        "review_status": "PENDING_EFFECTIVE_DATE_REVIEW",
        "notes": "Expected issuer change after the July 1, 2026 redomiciliation; no mapping applied",
    }
    with (folder / "xom_transition.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)
    (folder / "xom_transition_review.json").write_text(json.dumps({
        "expected_old_cik": "0000034088",
        "expected_new_cik": "0002115436",
        "observed_old_cik": before["cik"],
        "observed_new_cik": after["cik"],
        "status": row["review_status"],
        "note": "Inspection only. SEC merger evidence must be retained with the approved mapping.",
    }, indent=2) + "\n", encoding="utf-8")
    print(f"Old XOM: CIK {before['cik']} | FIGI {before['share_class_figi'] or 'missing'}")
    print(f"New XOM: CIK {after['cik']} | FIGI {after['share_class_figi'] or 'missing'}")
    print(f"Review file: {folder / 'xom_transition.csv'}")
    return folder


def main():
    key = os.environ.get("MASSIVE_API_KEY") or getpass("Massive API key (hidden): ")
    root = Path(__file__).resolve().parents[1] / "data" / "instrument_reference"
    try:
        inspect(root, key)
    except (OSError, RuntimeError, ValueError) as error:
        raise SystemExit(f"XOM identity check stopped: {error}") from None


if __name__ == "__main__":
    main()
