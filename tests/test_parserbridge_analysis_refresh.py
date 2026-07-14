import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel

from OSCR.parser import analyze_combat

from re_oscr.parserbridge import ParserBridge
from tests.test_workbench import make_combat, make_line


class ParserBridgeAnalysisRefreshTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        settings = SimpleNamespace(
            combats_to_parse=1,
            seconds_between_combats=45,
            graph_resolution=0.2,
            combat_min_lines=20,
        )
        config = SimpleNamespace(
            excluded_event_ids=[],
            templog_folder_path=Path(self.temp_dir.name),
        )
        self.widgets = SimpleNamespace(
            log_duration_value=QLabel(),
            player_duration_value=QLabel(),
            update_overview_telemetry=Mock(),
        )
        self.bridge = ParserBridge(settings, config, self.widgets, Mock())
        self.bridge._tables = Mock()
        self.bridge._graphs = Mock()
        self.combat = analyze_combat(make_combat([
            make_line(0, owner_name="Alice"),
            make_line(1, owner_name="Bob"),
        ], end_seconds=1))

    def test_official_combat_keeps_complete_overview_and_analysis_refresh(self):
        self.bridge.show_combat(combat=self.combat)

        self.bridge._tables.refresh_tables.assert_called_once_with(
            self.bridge.damage_out_model.player_index,
            self.bridge.damage_in_model.player_index,
            self.bridge.heal_out_model.player_index,
            self.bridge.heal_in_model.player_index,
        )
        self.bridge._tables.refresh_analysis_tables.assert_not_called()

    def test_display_only_workbench_refresh_does_not_touch_overview(self):
        self.bridge.display_analysis(self.combat)

        self.bridge._tables.refresh_analysis_tables.assert_called_once_with(
            self.bridge.damage_out_model.player_index,
            self.bridge.damage_in_model.player_index,
            self.bridge.heal_out_model.player_index,
            self.bridge.heal_in_model.player_index,
        )
        self.bridge._tables.refresh_tables.assert_not_called()


if __name__ == "__main__":
    unittest.main()
