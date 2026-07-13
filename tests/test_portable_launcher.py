import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from retro_escalation import RetroEscalationLauncher


class RetroEscalationLauncherTests(unittest.TestCase):
    def test_source_checkout_uses_isolated_config_directory(self):
        config_dir = Path(RetroEscalationLauncher.default_config_dir())

        self.assertEqual(config_dir.name, ".re-oscr-settings")
        self.assertNotEqual(config_dir.name, "OSCR_UI")

    def test_development_build_version_identifies_fork(self):
        self.assertEqual(RetroEscalationLauncher.__version__, "11.1.0.dev6+re.oscr")

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
