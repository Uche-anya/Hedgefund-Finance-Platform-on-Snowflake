"""Save the Massive API key in this Windows user's Credential Manager."""

from getpass import getpass

from keyring.backends.Windows import WinVaultKeyring


SERVICE = "northbridge/massive-api"
USERNAME = "massive"


def main():
    vault = WinVaultKeyring()
    if vault.get_password(SERVICE, USERNAME):
        print("A Massive key is already saved. No change made.")
        return
    key = getpass("Massive API key (hidden): ").strip()
    if not key:
        raise SystemExit("No key entered")
    vault.set_password(SERVICE, USERNAME, key)
    print("Massive key saved in Windows Credential Manager.")


if __name__ == "__main__":
    main()
