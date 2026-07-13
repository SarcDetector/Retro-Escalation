from pathlib import Path
import tempfile
import unittest

from retro_escalation import RetroEscalationLauncher


class RetroEscalationLauncherTests(unittest.TestCase):
    def test_source_checkout_uses_isolated_config_directory(self):
        config_dir = Path(RetroEscalationLauncher.default_config_dir())

        self.assertEqual(config_dir.name, ".re-oscr-settings")
        self.assertNotEqual(config_dir.name, "OSCR_UI")

    def test_development_build_version_identifies_fork(self):
        self.assertEqual(RetroEscalationLauncher.__version__, "11.1.0.dev5+re.oscr")

    def test_legacy_retro_escalation_config_directory_migrates(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            legacy_dir = temp_path / "Retro-Escalation" / "settings"
            legacy_dir.mkdir(parents=True)
            (legacy_dir / "OSCR_UI_settings.ini").write_text("[General]\n", encoding="utf-8")
            config_dir = temp_path / "RE-OSCR" / "settings"

            RetroEscalationLauncher.migrate_legacy_config_dir(config_dir, (legacy_dir,))

            self.assertTrue((config_dir / "OSCR_UI_settings.ini").is_file())


if __name__ == "__main__":
    unittest.main()
