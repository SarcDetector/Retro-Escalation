import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from re_oscr.config import OSCRSettings


class ApplicationStartupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.project_root = Path(__file__).resolve().parents[1]

    def set_stored_theme(self, config_dir: str, theme_id: str):
        settings = OSCRSettings(Path(config_dir, "RE_OSCR_settings.ini"))
        settings.theme_id = theme_id
        settings.store_settings()
        settings._settings.sync()

    def assert_startup_succeeds(
            self, config_dir: str, expected_theme_id: str, select_theme_id: str = "-"):
        environment = os.environ.copy()
        environment["QT_QPA_PLATFORM"] = "offscreen"
        process = subprocess.run(
            [
                sys.executable,
                "-m",
                "tests.startup_probe",
                config_dir,
                expected_theme_id,
                select_theme_id,
            ],
            cwd=self.project_root,
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        details = f"stdout:\n{process.stdout}\nstderr:\n{process.stderr}"
        self.assertEqual(process.returncode, 0, details)

    def test_default_application_startup(self):
        with tempfile.TemporaryDirectory() as config_dir:
            self.set_stored_theme(config_dir, "default")
            self.assert_startup_succeeds(config_dir, "default")

    def test_command_console_application_startup(self):
        with tempfile.TemporaryDirectory() as config_dir:
            self.set_stored_theme(config_dir, "command_console")
            self.assert_startup_succeeds(config_dir, "command_console")

    def test_unknown_theme_application_startup_falls_back(self):
        with tempfile.TemporaryDirectory() as config_dir:
            self.set_stored_theme(config_dir, "unknown-theme")
            self.assert_startup_succeeds(config_dir, "default")
            restored = OSCRSettings(Path(config_dir, "RE_OSCR_settings.ini"))
            self.assertEqual(restored.theme_id, "default")

    def test_legacy_frontend_settings_migrate_to_re_oscr_filename(self):
        with tempfile.TemporaryDirectory() as config_dir:
            legacy_path = Path(config_dir, "OSCR_UI_settings.ini")
            legacy = OSCRSettings(legacy_path)
            legacy.theme_id = "command_console"
            legacy.store_settings()
            legacy._settings.sync()

            self.assert_startup_succeeds(config_dir, "command_console")

            migrated_path = Path(config_dir, "RE_OSCR_settings.ini")
            self.assertTrue(migrated_path.is_file())
            migrated = OSCRSettings(migrated_path)
            self.assertEqual(migrated.theme_id, "command_console")

    def test_selector_changes_apply_across_real_restarts(self):
        with tempfile.TemporaryDirectory() as config_dir:
            self.set_stored_theme(config_dir, "default")
            self.assert_startup_succeeds(config_dir, "default", "command_console")
            self.assert_startup_succeeds(config_dir, "command_console", "default")
            self.assert_startup_succeeds(config_dir, "default")


if __name__ == "__main__":
    unittest.main()
