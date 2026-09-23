"""Save dated security details for the three merger cases under review."""

from getpass import getpass
import os
from pathlib import Path

from data_extraction.check_bny_identity import check_identities


CHECKS = (
    ("CHK", "2024-10-01"),
    ("EXE", "2024-10-02"),
    ("EQR", "2026-08-17"),
    ("VMRK", "2026-08-18"),
    # PARA and PSKY are separate securities in our dataset, not a rename repair.
    ("PARA", "2025-08-06"),
    ("PSKY", "2025-08-07"),
)


def main():
    key = os.environ.get("MASSIVE_API_KEY")
    if not key:
        key = getpass("Massive API key (hidden): ")
    root = Path(__file__).resolve().parents[1] / "data" / "reference_checks"
    try:
        check_identities(root, key, checks=CHECKS)
    except (ValueError, RuntimeError, OSError) as error:
        raise SystemExit(f"Merger identity check stopped: {error}") from None
    print("Review CHK/EXE and EQR/VMRK against the merger filings.")
    print("Keep PARA/PSKY separate. No prices have been changed.")


if __name__ == "__main__":
    main()
