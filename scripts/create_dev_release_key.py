"""Create a separate Snowflake key for the DEV release job."""

from pathlib import Path

from scripts.create_ci_test_key import create_key


ROOT = Path(__file__).resolve().parents[1]


if __name__ == "__main__":
    create_key(ROOT / ".secrets" / "northbridge_release_dev.p8",
               ROOT / ".secrets" / "northbridge_release_dev.pub")
