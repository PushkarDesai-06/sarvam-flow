import sys
import unittest
import uuid
from unittest.mock import MagicMock, patch

import credentials


class CredentialTests(unittest.TestCase):
    def test_save_read_replace_and_remove(self):
        values = {}
        store = MagicMock()
        store.set_password.side_effect = lambda service, account, key: values.update({(service, account): key})
        store.get_password.side_effect = lambda service, account: values.get((service, account))
        store.delete_password.side_effect = lambda service, account: values.pop((service, account))
        with patch.object(credentials, "credential_store", return_value=store):
            credentials.save_key("first-test-key")
            self.assertEqual(credentials.read_key(), "first-test-key")
            credentials.save_key("replacement-test-key")
            self.assertEqual(credentials.read_key(), "replacement-test-key")
            credentials.remove_key()
            self.assertIsNone(credentials.read_key())
            credentials.remove_key()

    @unittest.skipUnless(sys.platform == "win32", "Requires Windows Credential Manager")
    def test_windows_credential_round_trip(self):
        with patch.object(credentials, "SERVICE", "SarvamFlow-test-" + uuid.uuid4().hex):
            try:
                credentials.save_key("non-secret-test-value")
                self.assertEqual(credentials.read_key(), "non-secret-test-value")
            finally:
                credentials.remove_key()
            self.assertIsNone(credentials.read_key())


if __name__ == "__main__":
    unittest.main()
