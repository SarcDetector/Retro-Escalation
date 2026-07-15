import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from re_oscr.console.tables import LeagueStandingsTableView
from re_oscr.console.tokens import ConsoleTokens
from re_oscr.datamodels import LeagueTableModel, SortingProxy
from re_oscr.leagueconnector import LEAGUE_TABLE_HEADER


class LeagueStandingsTableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.model = LeagueTableModel(LEAGUE_TABLE_HEADER)
        font = QFont("Roboto Mono", 10)
        self.model.init_fonts(font, font)
        self.model.set_data(
            [
                ["Aster", "Aster@one", 3400.0, 68000.0, 0, 20.0, "today", 9000.0, 0.2, "Beam"],
                ["Beryl", "Beryl@two", 1700.0, 34000.0, 1, 20.0, "today", 5000.0, 0.1, "Cannon"],
            ],
            LEAGUE_TABLE_HEADER,
            [1, 2],
        )
        self.sorter = SortingProxy()
        self.sorter.setSourceModel(self.model)
        self.table = LeagueStandingsTableView(ConsoleTokens(1.0, ["#FF8A2A"] * 5))
        self.table.setModel(self.sorter)
        self.table.resize(900, 300)
        self.table.show()
        self.app.processEvents()

    def tearDown(self):
        self.table.close()
        self.table.deleteLater()
        self.app.processEvents()

    def test_frozen_identity_uses_the_existing_sorter_and_selection(self):
        frozen = self.table.frozen_view
        self.assertIs(frozen.model(), self.sorter)
        self.assertIs(frozen.selectionModel(), self.table.selectionModel())
        self.assertFalse(frozen.isColumnHidden(0))
        self.assertFalse(frozen.isColumnHidden(1))
        self.assertTrue(frozen.isColumnHidden(2))
        self.assertFalse(self.table.verticalHeader().isHidden())

        self.table.selectRow(1)
        self.app.processEvents()
        self.assertTrue(frozen.selectionModel().isSelected(self.sorter.index(1, 0)))

    def test_meter_mode_changes_presentation_only(self):
        self.assertTrue(self.table.meter_mode())
        self.table.set_meter_mode(False)
        self.assertFalse(self.table.meter_mode())
        self.assertIs(self.table.model(), self.sorter)
        self.assertIs(self.sorter.sourceModel(), self.model)


if __name__ == "__main__":
    unittest.main()
