import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from campus_auto_login.diagnostic_bundle import export_diagnostic_bundle
from campus_auto_login.models import Profile


class DiagnosticBundleTests(unittest.TestCase):
    def test_export_accepts_positional_arguments_and_redacts_profile(self):
        profile = Profile(
            id="p1",
            name="test",
            login_url="http://192.0.2.1/",
            adapter_id="drcom_eportal",
            adapter_name="Dr.COM / ePortal",
            gateway="http://192.0.2.1:801",
            login_endpoint="http://192.0.2.1:801/eportal/portal/login",
            logout_endpoint="http://192.0.2.1:801/eportal/portal/logout",
            username="20260000000",
            encrypted_password="secret-cipher-text",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            log_dir = root / "logs"
            output_dir = root / "diagnostics"
            log_dir.mkdir()
            (log_dir / "campus_auto_login.log").write_text(
                "token=abc password=123 cookie=sessionid\n",
                encoding="utf-8",
            )

            bundle = export_diagnostic_bundle(
                output_dir,
                [profile],
                log_dir,
                "user=20260000000 password=123",
            )

            self.assertTrue(bundle.exists())
            with zipfile.ZipFile(bundle) as archive:
                summary = json.loads(archive.read("summary.json").decode("utf-8"))
                self.assertNotIn("encrypted_password", summary["profiles"][0])
                self.assertEqual(summary["profiles"][0]["username"], "20*******00")
                log_text = archive.read("logs/campus_auto_login.log").decode("utf-8")
                self.assertNotIn("password=123", log_text)


if __name__ == "__main__":
    unittest.main()
