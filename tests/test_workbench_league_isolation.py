"""Integration guard for Command Console Workbench and League boundaries."""

from collections import deque
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch

from PySide6.QtCore import QObject, Signal

from OSCR.combat import Combat
from OSCR.datamodels import LogLine
from OSCR.parser import analyze_combat

from re_oscr.leagueconnector import OSCRLeagueConnector
from re_oscr.workbench import WorkbenchState
from re_oscr.workbenchcontroller import AnalysisWorkbenchController


class _ParserBoundary(QObject):
    """Small ParserBridge-shaped object with an immutable parser-owned combat list."""

    combat_displayed = Signal(Combat)

    def __init__(self, source: Combat):
        super().__init__()
        self._combats = [source]
        self.current_combat_id = 0
        self.analysis_display = None

    @property
    def combat_list(self):
        return self._combats

    @property
    def current_combat(self):
        return self._combats[self.current_combat_id]

    def display_analysis(self, combat: Combat):
        self.analysis_display = combat


class _Tables:
    def __init__(self):
        self.modified = False

    def set_analysis_modified(self, modified: bool):
        self.modified = modified


class _CapturingFetchThread:
    """Avoid starting a QThread while retaining the exact League upload arguments."""

    def __init__(self, target, args=tuple(), kwargs=None, callback=None):
        self.target = target
        self.args = args
        self.kwargs = kwargs or {}
        self.callback = callback
        self.started = False

    def isRunning(self):
        return False

    def start(self):
        self.started = True


def _line(seconds: float, owner: str, event: str) -> LogLine:
    origin = datetime(2026, 7, 14, 12, 0, 0)
    return LogLine(
        timestamp=origin + timedelta(seconds=seconds),
        owner_name=owner,
        owner_id=f"P[1@{owner}]",
        source_name="",
        source_id="",
        target_name="Target",
        target_id="C[1 Target]",
        event_name=event,
        event_id=event,
        type="HitPoints",
        flags="",
        magnitude=100.0,
        magnitude2=100.0,
    )


def _source_combat(log_path: Path) -> Combat:
    origin = datetime(2026, 7, 14, 12, 0, 0)
    combat = Combat(id=0, log_file=str(log_path))
    combat.start_time = origin
    combat.end_time = origin + timedelta(seconds=2)
    combat.map = "Infected Space"
    combat.log_data = deque([
        _line(0, "Alice", "Beam"),
        _line(1, "Bob", "Torpedo"),
        _line(2, "Alice", "Cannon"),
    ])
    analyze_combat(combat)
    combat.map = "Infected Space"
    combat.file_pos = [111, 222]
    return combat


def _widgets():
    return SimpleNamespace(
        analysis_filter_scope=None,
        analysis_filter_entry=None,
        analysis_start_entry=None,
        analysis_end_entry=None,
        analysis_truth_chip=None,
        analysis_modified_chip=None,
        analysis_event_count_chip=None,
        analysis_reset_button=None,
        analysis_plots=[],
        ladder_table=Mock(),
    )


class WorkbenchLeagueIsolationTests(unittest.TestCase):
    def test_modified_analysis_never_replaces_parser_or_league_upload_source(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir, "official.log")
            log_path.write_bytes(b"official parser-owned log segment")
            source = _source_combat(log_path)
            source_lines = tuple(source.log_data)
            source_positions = list(source.file_pos)

            parser = _ParserBoundary(source)
            widgets = _widgets()
            tables = _Tables()
            controller = AnalysisWorkbenchController(parser, tables, widgets)
            parser.combat_displayed.emit(source)

            applied = controller.apply_state(WorkbenchState(text_query="Alice"))

            self.assertTrue(applied)
            self.assertTrue(tables.modified)
            self.assertIsNot(parser.analysis_display, source)
            self.assertIs(controller.current_view.combat, parser.analysis_display)
            self.assertEqual(parser.analysis_display.log_file, "")
            self.assertEqual(parser.analysis_display.file_pos, [None, None])
            self.assertIs(parser.current_combat, source)
            self.assertEqual(parser.combat_list, [source])
            self.assertEqual(tuple(source.log_data), source_lines)
            self.assertEqual(source.file_pos, source_positions)

            connector = OSCRLeagueConnector(
                widgets=widgets,
                dialogs=Mock(),
                theme=Mock(),
                config=SimpleNamespace(
                    templog_folder_path=Path(temp_dir),
                    home_dir=temp_dir,
                ),
                settings=SimpleNamespace(
                    league_table_rows=50,
                    log_path=temp_dir,
                ),
                parser=parser,
                upload_dialog=Mock(),
            )
            with patch(
                    "re_oscr.leagueconnector.FetchThread",
                    _CapturingFetchThread):
                connector.upload_callback()

            self.assertTrue(connector._thread.started)
            self.assertEqual(
                connector._thread.args,
                ((str(log_path), source_positions[0], source_positions[1]),),
            )


if __name__ == "__main__":
    unittest.main()
