"""Set the daily producer's GitHub variable and secrets from local stores."""

import base64
from pathlib import Path
import subprocess

from keyring.backends.Windows import WinVaultKeyring


REPO = "Uche-anya/Hedgefund-Finance-Platform-on-Snowflake"
ACCOUNT = "gxmgyta-fq45953"
KEY_FILE = Path(__file__).resolve().parents[1] / ".secrets" / "northbridge_loader.p8"


def set_value(kind, name, value):
    command = ["gh", kind, "set", name, "--repo", REPO]
    result = subprocess.run(command, input=value, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError("Could not set GitHub {} {}. Check gh auth status.".format(kind, name))
    print("Set {} {}".format(kind, name))


def main():
    api_key = WinVaultKeyring().get_password("northbridge/massive-api", "massive")
    if not api_key:
        raise SystemExit("Massive API key is missing from Windows Credential Manager")
    if not KEY_FILE.is_file():
        raise SystemExit("Loader private key is missing: {}".format(KEY_FILE))

    key = base64.b64encode(KEY_FILE.read_bytes()).decode("ascii")
    set_value("variable", "SNOWFLAKE_ACCOUNT", ACCOUNT)
    set_value("secret", "MASSIVE_API_KEY", api_key)
    set_value("secret", "NORTHBRIDGE_LOADER_KEY_B64", key)


if __name__ == "__main__":
    main()
