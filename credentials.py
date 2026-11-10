import sys

import keyring

SERVICE = "SarvamFlow"
ACCOUNT = "SARVAM_API_KEY"


def credential_store():
    if sys.platform == "win32":
        from keyring.backends.Windows import WinVaultKeyring

        return WinVaultKeyring()
    return keyring.get_keyring()


def read_key():
    return credential_store().get_password(SERVICE, ACCOUNT)


def save_key(key):
    credential_store().set_password(SERVICE, ACCOUNT, key)


def remove_key():
    store = credential_store()
    if store.get_password(SERVICE, ACCOUNT) is not None:
        store.delete_password(SERVICE, ACCOUNT)
