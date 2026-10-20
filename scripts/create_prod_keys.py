"""Create separate local keys for PROD ingestion and dbt releases."""

from pathlib import Path

from scripts.create_ci_test_key import create_key


ROOT = Path(__file__).resolve().parents[1]
SECRETS = ROOT / ".secrets"


def main():
    for name in ("northbridge_ingest_prod", "northbridge_release_prod"):
        create_key(SECRETS / (name + ".p8"), SECRETS / (name + ".pub"))


if __name__ == "__main__":
    main()
