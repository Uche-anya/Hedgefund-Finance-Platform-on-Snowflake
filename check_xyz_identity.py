"""Compare Block's security identifiers before and after SQ became XYZ."""

from getpass import getpass
import os
from pathlib import Path

from check_bny_identity import check_identities


CHECKS = (
    ("SQ", "2025-01-17"),
    ("XYZ", "2025-01-21"),
)


def main():
    key = os.environ.get("MASSIVE_API_KEY")
    if not key:
        key = getpass("Massive API key (hidden): ")
    root = Path(__file__).resolve().parent / "data" / "reference_checks"
    try:
        check_identities(root, key, checks=CHECKS)
    except (ValueError, RuntimeError) as error:
        raise SystemExit(f"Identity check stopped: {error}") from None


if __name__ == "__main__":
    main()
