import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from retro_escalation import RetroEscalationLauncher


class RetroEscalationLauncherTests(unittest.TestCase):
    def test_source_checkout_uses_isolated_config_directory(self):
        config_dir = Path(RetroEscalationLauncher.default_config_dir())

        self.assertEqual(config_dir.name, ".re-oscr-settings")
        self.assertNotEqual(config_dir.name, "OSCR_UI")

    def test_development_build_version_identifies_fork(self):
        self.assertEqual(RetroEscalationLauncher.__version__, "11.1.0.dev11")

    def test_wheel_install_uses_durable_per_user_settings(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            app_data = root / "AppData"
            xdg_config = root / "config"
            installed_package = root / "site-packages"
            installed_package.mkdir()
            with patch("retro_escalation.Launcher.base_path", return_value=str(installed_package)), \
                    patch.dict(os.environ, {
                        "APPDATA": str(app_data),
                        "XDG_CONFIG_HOME": str(xdg_config),
                    }, clear=False):
                config_dir = Path(RetroEscalationLauncher.default_config_dir())

        expected_root = app_data if sys.platform == "win32" else xdg_config
        self.assertEqual(config_dir, expected_root / "RE-OSCR")

    def test_legacy_retro_escalation_config_directory_migrates(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            legacy_dir = temp_path / "Retro-Escalation" / "settings"
            legacy_dir.mkdir(parents=True)
            (legacy_dir / "OSCR_UI_settings.ini").write_text("[General]\n", encoding="utf-8")
            config_dir = temp_path / "RE-OSCR" / "settings"

            RetroEscalationLauncher.migrate_legacy_config_dir(config_dir, (legacy_dir,))

            self.assertTrue((config_dir / "OSCR_UI_settings.ini").is_file())

    def test_startup_check_exits_cleanly(self):
        project_root = Path(__file__).resolve().parents[1]
        environment = os.environ.copy()
        environment["QT_QPA_PLATFORM"] = "offscreen"
        with tempfile.TemporaryDirectory() as config_dir:
            result = subprocess.run(
                [
                    sys.executable,
                    str(project_root / "retro_escalation.py"),
                    "--config_dir",
                    config_dir,
                    "--startup-check",
                ],
                cwd=project_root,
                env=environment,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
