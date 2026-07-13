import unittest
from pathlib import Path

from retro_escalation import RetroEscalationLauncher


class RetroEscalationLauncherTests(unittest.TestCase):
    def test_source_checkout_uses_isolated_config_directory(self):
        config_dir = Path(RetroEscalationLauncher.default_config_dir())

        self.assertEqual(config_dir.name, ".retro-escalation-settings")
        self.assertNotEqual(config_dir.name, "OSCR_UI")

    def test_development_build_version_identifies_fork(self):
        self.assertEqual(RetroEscalationLauncher.__version__, "11.1.0-re.1-dev")


if __name__ == "__main__":
    unittest.main()
