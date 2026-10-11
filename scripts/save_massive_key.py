"""Save the Massive API key in this Windows user's Credential Manager."""

import argparse
from getpass import getpass

from keyring.backends.Windows import WinVaultKeyring


SERVICE = "northbridge/massive-api"
USERNAME = "massive"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replace", action="store_true", help="replace the saved key")
    args = parser.parse_args()
    vault = WinVaultKeyring()
    if vault.get_password(SERVICE, USERNAME) and not args.replace:
        print("A Massive key is already saved. Use --replace to change it.")
        return
    key = getpass("Massive API key (hidden): ").strip()
    if not key:
        raise SystemExit("No key entered")
    if any(character.isspace() for character in key):
        raise SystemExit("The key contains spaces. Copy only the API key value.")
    vault.set_password(SERVICE, USERNAME, key)
    print("Massive key saved in Windows Credential Manager.")


if __name__ == "__main__":
    main()
