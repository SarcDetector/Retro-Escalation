import gzip
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from re_oscr.leagueconnector import OSCRLeagueConnector
from re_oscr.sidebar import OSCRLeftSidebar


class _PathEntry:
    def __init__(self, value: str = ""):
        self.value = value

    def text(self) -> str:
        return self.value

    def setText(self, value: str):
        self.value = value


class LeagueDownloadTests(unittest.TestCase):
    def make_connector(self, temp_dir: str) -> tuple[OSCRLeagueConnector, Mock, Mock]:
        widgets = SimpleNamespace(ladder_table=Mock())
        dialogs = Mock()
        parser = Mock()
        config = SimpleNamespace(
            templog_folder_path=Path(temp_dir),
            home_dir=temp_dir,
        )
        settings = SimpleNamespace(
            league_table_rows=50,
            log_path=temp_dir,
        )
        connector = OSCRLeagueConnector(
            widgets=widgets,
            dialogs=dialogs,
            theme=Mock(),
            config=config,
            settings=settings,
            parser=parser,
            upload_dialog=Mock(),
        )
        return connector, parser, dialogs

    def test_download_decompresses_to_log_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            connector, _, _ = self.make_connector(temp_dir)
            expected = b"24:01:01:00:00:00.0::sample combat line\n"
            connector._api = SimpleNamespace(
                download_combatlog=lambda _log_id: gzip.compress(expected))

            downloaded = connector.download(46434)

            self.assertIsNotNone(downloaded)
            self.assertEqual(downloaded.suffix, ".log")
            self.assertEqual(downloaded.read_bytes(), expected)

    def test_downloaded_parse_opens_through_existing_parser_bridge(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            connector, parser, _ = self.make_connector(temp_dir)
            log_path = Path(temp_dir, "league.log")
            log_path.write_bytes(b"sample")

            connector._handle_download_for_view(log_path, 46434)

            parser.analyze_log_file.assert_called_once_with(log_path, hidden_path=True)

    def test_failed_download_does_not_call_parser(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            connector, parser, _ = self.make_connector(temp_dir)

            connector._handle_download_for_view(None, 46434)

            parser.analyze_log_file.assert_not_called()

    def test_downloaded_parse_can_be_saved_permanently(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            connector, _, _ = self.make_connector(temp_dir)
            downloaded = Path(temp_dir, "temporary.log")
            target = Path(temp_dir, "saved.log")
            downloaded.write_bytes(b"downloaded parse")

            with patch("re_oscr.leagueconnector.browse_path", return_value=target):
                connector._handle_download_for_save(downloaded, 46434)

            self.assertEqual(target.read_bytes(), b"downloaded parse")

    def test_missing_league_selection_explains_required_action(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            connector, _, dialogs = self.make_connector(temp_dir)
            connector._widgets.ladder_table.selectedIndexes.return_value = []

            self.assertIsNone(connector._selected_combatlog_id())

            dialogs.show_message.assert_called_once()


class LocalLogLoadingTests(unittest.TestCase):
    def test_league_local_log_action_passes_path_to_parser(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir, "local.log")
            log_path.write_bytes(b"sample")
            parser = Mock()
            sidebar = OSCRLeftSidebar.__new__(OSCRLeftSidebar)
            sidebar._parser = parser
            sidebar._settings = SimpleNamespace(
                auto_scan=False,
                log_path=temp_dir,
            )
            sidebar._config = SimpleNamespace(home_dir=temp_dir)
            sidebar.log_path_widget = _PathEntry(temp_dir)

            with patch("re_oscr.sidebar.browse_path", return_value=log_path):
                selected = sidebar.browse_log(analyze=True)

            self.assertEqual(selected, log_path)
            self.assertEqual(sidebar.log_path_widget.text(), str(log_path))
            parser.analyze_log_file.assert_called_once_with(log_path)


if __name__ == "__main__":
    unittest.main()
