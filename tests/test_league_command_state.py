import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel, QListWidgetItem

from re_oscr.views.league import LeagueView


class LeagueCommandStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.view = LeagueView.__new__(LeagueView)
        self.view._command_status = QLabel()

    def test_season_and_ladder_selection_replace_the_placeholder_with_real_state(self):
        self.view._season_selected("Season 32")
        self.assertEqual(self.view._command_status.text(), "SEASON // SEASON 32")

        ladder = QListWidgetItem("Infected Space")
        ladder.difficulty = "Elite"
        self.view._ladder_selected(ladder)

        self.assertEqual(
            self.view._command_status.text(),
            "LADDER // INFECTED SPACE // ELITE",
        )
        self.assertEqual(
            self.view._command_status.toolTip(),
            "LADDER: INFECTED SPACE: ELITE",
        )


if __name__ == "__main__":
    unittest.main()
