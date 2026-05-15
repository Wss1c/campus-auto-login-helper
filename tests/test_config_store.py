import tempfile
import unittest
from pathlib import Path

from campus_auto_login.config_store import ConfigStore
from campus_auto_login.models import Profile


def make_profile(profile_id: str, name: str) -> Profile:
    return Profile(
        id=profile_id,
        name=name,
        login_url="http://192.0.2.1/",
        adapter_id="drcom_eportal",
        adapter_name="Dr.COM / ePortal",
        gateway="http://192.0.2.1:801",
        login_endpoint="http://192.0.2.1:801/eportal/portal/login",
        logout_endpoint="http://192.0.2.1:801/eportal/portal/logout",
        username="user",
        encrypted_password="encrypted",
    )


class ConfigStoreTests(unittest.TestCase):
    def test_selected_profile_id_is_persisted_and_validated(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ConfigStore(Path(temp_dir))
            first = make_profile("p1", "first")
            second = make_profile("p2", "second")

            store.save_profiles([first, second])
            self.assertEqual(store.load_selected_profile_id(), "p1")

            store.save_selected_profile_id("p2")
            self.assertEqual(store.load_selected_profile_id(), "p2")

            store.save_profiles([first, second])
            self.assertEqual(store.load_selected_profile_id(), "p2")

            store.delete_profile("p2")
            self.assertEqual(store.load_selected_profile_id(), "p1")


if __name__ == "__main__":
    unittest.main()
