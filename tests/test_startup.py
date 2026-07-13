import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from OSCRUI.app import OSCRUI  # noqa: E402


class ApplicationStartupTests(unittest.TestCase):
    def test_application_builds_with_fresh_settings_and_default_theme(self):
        project_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp_dir:
            ui = OSCRUI(
                args=SimpleNamespace(config_dir=temp_dir),
                app_dir_path=str(project_root),
                version="baseline-test",
            )
            ui.app.processEvents()

            self.assertEqual(ui.window.windowTitle(), "Open Source Combatlog Reader")
            self.assertTrue(ui.window.isVisible())
            self.assertEqual(ui.theme["defaults"]["oscr"], "#c82934")
            self.assertEqual(ui.widgets.main_tabber.count(), 4)

            ui.window.close()
            ui.app.processEvents()
            ui.app.quit()


if __name__ == "__main__":
    unittest.main()
