import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from campus_auto_login import paths


class PathTests(unittest.TestCase):
    def test_data_dir_uses_user_appdata_and_migrates_old_portable_data(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            app = root / "app"
            old_data = app / "data"
            user_root = root / "roaming"
            old_data.mkdir(parents=True)
            (old_data / "profiles.json").write_text('{"profiles":[]}', encoding="utf-8")

            with patch.dict(
                os.environ,
                {"APPDATA": str(user_root), "CAMPUS_AUTO_LOGIN_PORTABLE": ""},
                clear=False,
            ), patch("campus_auto_login.paths.app_dir", return_value=app):
                result = paths.data_dir()

            self.assertEqual(result, user_root / "CampusAutoLogin")
            self.assertTrue((result / "profiles.json").exists())

    def test_data_dir_can_stay_portable_with_flag_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            app = Path(temp_dir) / "app"
            app.mkdir()
            (app / "portable.flag").write_text("", encoding="utf-8")

            with patch.dict(os.environ, {"CAMPUS_AUTO_LOGIN_PORTABLE": ""}, clear=False), patch(
                "campus_auto_login.paths.app_dir",
                return_value=app,
            ):
                result = paths.data_dir()

            self.assertEqual(result, app / "data")


if __name__ == "__main__":
    unittest.main()
