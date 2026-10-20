"""Make a key for the TEST delivery rehearsal."""

from pathlib import Path

from scripts.create_ci_test_key import create_key


ROOT = Path(__file__).resolve().parents[1]


if __name__ == "__main__":
    create_key(ROOT / ".secrets" / "northbridge_ingest_test.p8",
               ROOT / ".secrets" / "northbridge_ingest_test.pub")
