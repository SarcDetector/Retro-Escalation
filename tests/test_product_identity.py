"""Product identity checks for the frontend/parser boundary."""

from pathlib import Path
import tomllib
import unittest

from main import Launcher
from retro_escalation import RetroEscalationLauncher


class ProductIdentityTests(unittest.TestCase):
    def test_re_oscr_is_the_frontend_and_oscr_remains_the_parser(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        with (project_root / "pyproject.toml").open("rb") as project_file:
            pyproject = tomllib.load(project_file)

        project = pyproject["project"]
        self.assertEqual(project["name"], "RE-OSCR")
        self.assertIn("STO-OSCR==11.0.0", project["dependencies"])
        self.assertEqual(
            project["scripts"],
            {"re-oscr": "retro_escalation:RetroEscalationLauncher.launch"},
        )
        self.assertEqual(RetroEscalationLauncher.__version__, "11.1.0.dev9+re.oscr")
        self.assertEqual(Launcher.__version__, RetroEscalationLauncher.__version__)

    def test_cla_credit_uses_an_original_logo_safe_badge(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        badge_path = project_root / "assets" / "cla_credit.svg"

        self.assertTrue(badge_path.is_file())
        badge = badge_path.read_text(encoding="utf-8")
        self.assertIn(">CLA</text>", badge)
        self.assertNotIn("STO_CombatLogAnalyzer-master", badge)


if __name__ == "__main__":
    unittest.main()
