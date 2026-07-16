import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QModelIndex
from PySide6.QtGui import QIcon
from PySide6.QtNetwork import QHostAddress, QTcpServer
from PySide6.QtWidgets import QApplication, QFrame, QPushButton, QSlider

from re_oscr.config import OSCRConfig, OSCRSettings
from re_oscr.liveoverlay import LiveOverlayController
from re_oscr.liveparser import LiveParserWindow
from re_oscr.themes.command_console import create_command_console_theme
from re_oscr.views.live import LiveView


class FakeLiveParser:
    def __init__(self, update_callback=None, settings=None):
        self.update_callback = update_callback
        self.settings = dict(settings or {})
        self.start_count = 0
        self.stop_count = 0
        self.log_path = None

    def set_log_path(self, path):
        if not Path(path).is_file():
            return False
        self.log_path = path
        return True

    def start(self):
        self.start_count += 1

    def stop(self):
        self.stop_count += 1


class FakeDialogs:
    def __init__(self):
        self.messages = []

    def show_message(self, title, message, level):
        self.messages.append((title, message, level))


class FakeWidgets:
    def __init__(self):
        self.live_parser_button = QPushButton()
        self.popout_states = []

    def set_live_parser_active(self, active):
        self.popout_states.append(bool(active))


class FakeHotkeyBackend:
    supported = True

    def __init__(self):
        self.callback = None
        self.registered = {}

    def register(self, hotkey_id, hotkey):
        self.registered[hotkey_id] = hotkey
        return True, ""

    def unregister(self, hotkey_id):
        self.registered.pop(hotkey_id, None)

    def shutdown(self):
        self.registered.clear()


class LiveControlCenterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        root = Path(self.temp_dir.name)
        self.log_path = root / "CombatLog.log"
        self.log_path.write_text("", encoding="utf-8")
        self.settings_path = root / "settings.ini"
        self.settings = OSCRSettings(self.settings_path)
        self.settings.sto_log_path = str(self.log_path)
        self.theme = create_command_console_theme(1.0)
        for name in ("oscr", "copy", "close"):
            self.theme.icons[name] = QIcon()
        self.widgets = FakeWidgets()
        self.dialogs = FakeDialogs()

    def make_window(self, command_console=True):
        patcher = patch("re_oscr.liveparser.LiveParser", FakeLiveParser)
        patcher.start()
        self.addCleanup(patcher.stop)
        window = LiveParserWindow(
            self.settings, self.theme, self.dialogs, self.widgets,
            command_console=command_console,
        )
        self.addCleanup(window.close)
        self.addCleanup(window.shutdown)
        return window

    def make_overlay(self, window):
        backend = FakeHotkeyBackend()

        def factory(_app, callback):
            backend.callback = callback
            return backend

        probe = QTcpServer()
        self.assertTrue(probe.listen(QHostAddress("127.0.0.1"), 0))
        self.settings.overlay__feed_port = probe.serverPort()
        probe.close()
        controller = LiveOverlayController(
            app=self.app,
            settings=self.settings,
            config_dir=Path(self.temp_dir.name),
            asset_dir=Path(__file__).resolve().parents[1] / "assets" / "overlay",
            theme=self.theme,
            live_parser=window,
            hotkey_backend_factory=factory,
        )
        self.addCleanup(controller.shutdown)
        return controller

    def test_command_session_survives_popout_hide_until_explicit_stop(self):
        window = self.make_window(command_console=True)

        self.assertTrue(window.start_parser())
        self.assertTrue(window.parser_active)
        self.assertEqual(window._liveparser.start_count, 1)

        window.set_popout_visible(True)
        self.assertTrue(window.popout_visible)
        window.set_popout_visible(False)

        self.assertFalse(window.popout_visible)
        self.assertTrue(window.parser_active)
        self.assertEqual(window._liveparser.stop_count, 0)
        window.stop_parser()
        self.assertFalse(window.parser_active)
        self.assertEqual(window._liveparser.stop_count, 1)

    def test_popout_activate_button_starts_then_stops_on_two_clicks(self):
        window = self.make_window(command_console=True)

        window._activate_button.click()
        self.app.processEvents()
        self.assertTrue(window.parser_active)
        self.assertFalse(window._activate_button._r)
        self.assertEqual(window._liveparser.start_count, 1)

        window._activate_button.click()
        self.app.processEvents()
        self.assertFalse(window.parser_active)
        self.assertTrue(window._activate_button._r)
        self.assertEqual(window._liveparser.stop_count, 1)

    def test_legacy_toggle_still_closes_and_stops_as_one_action(self):
        self.settings.liveparser__auto_enabled = True
        window = self.make_window(command_console=False)

        window.toggle_window(True)
        self.assertTrue(window.popout_visible)
        self.assertTrue(window.parser_active)
        self.assertEqual(window._liveparser.start_count, 1)

        window.toggle_window(False)
        self.assertFalse(window.popout_visible)
        self.assertFalse(window.parser_active)
        self.assertEqual(window._liveparser.stop_count, 1)
        self.assertFalse(self.widgets.live_parser_button.isChecked())

    def test_direct_close_synchronizes_popout_without_stopping_command_parser(self):
        window = self.make_window(command_console=True)
        self.assertTrue(window.start_parser())
        window.set_popout_visible(True)

        window.close()
        self.app.processEvents()

        self.assertFalse(window.popout_visible)
        self.assertFalse(window.isVisible())
        self.assertTrue(window.parser_active)
        self.assertEqual(window._liveparser.stop_count, 0)
        self.assertEqual(self.widgets.popout_states[-1], False)

    def test_direct_close_preserves_legacy_close_and_stop_contract(self):
        window = self.make_window(command_console=False)
        self.assertTrue(window.start_parser())
        window.set_popout_visible(True)

        window.close()
        self.app.processEvents()

        self.assertFalse(window.popout_visible)
        self.assertFalse(window.parser_active)
        self.assertEqual(window._liveparser.stop_count, 1)

    def test_invalid_log_rejects_start_without_changing_visibility(self):
        self.settings.sto_log_path = str(Path(self.temp_dir.name) / "missing.log")
        window = self.make_window(command_console=True)

        self.assertFalse(window.start_parser())
        self.assertFalse(window.parser_active)
        self.assertFalse(window.popout_visible)
        self.assertEqual(window._liveparser.start_count, 0)
        self.assertEqual(len(self.dialogs.messages), 1)

    def test_preview_uses_normalized_snapshots_and_clears_stale_rows(self):
        window = self.make_window(command_console=True)
        parent = QFrame()
        self.addCleanup(parent.close)
        view = LiveView(
            self.theme, self.settings, OSCRConfig(), self.widgets, window)
        view.build(parent)
        player_data = {
            ("Raman", "@ramanwaleczny"): {
                "dps": 523_401.12,
                "combat_time": 72.5,
                "local_debuff": 75.21,
                "local_attacks_in_share": 18.4,
                "hps": 1_250.0,
                "kills": 48,
                "deaths": 0,
            }
        }

        window.update_live_display(player_data, 72.5)
        self.app.processEvents()

        self.assertEqual(
            self.widgets.live_parser_preview_model.rowCount(QModelIndex()), 1)
        self.assertEqual(self.widgets.live_parser_preview_status.text(), "1 OPERATOR")
        self.assertEqual(self.widgets.live_parser_preview_duration.text(), "72.5S")
        self.assertGreaterEqual(view._preview_curves[0].opts["pen"].widthF(), 2.0)

        window.update_live_display({}, 0.0)
        self.app.processEvents()
        self.assertEqual(
            self.widgets.live_parser_preview_model.rowCount(QModelIndex()), 0)
        self.assertEqual(self.widgets.live_parser_preview_status.text(), "NO TELEMETRY")
        self.assertEqual(self.widgets.live_parser_preview_duration.text(), "0.0S")

    def test_preview_curve_colours_follow_operator_ids_after_table_sort(self):
        window = self.make_window(command_console=True)
        parent = QFrame()
        self.addCleanup(parent.close)
        view = LiveView(
            self.theme, self.settings, OSCRConfig(), self.widgets, window)
        view.build(parent)
        player_data = {
            ("Lower", "@lower"): {
                "dps": 100.0, "combat_time": 10.0, "local_debuff": 0.0,
                "local_attacks_in_share": 0.0, "hps": 0.0, "kills": 0, "deaths": 0,
            },
            ("Higher", "@higher"): {
                "dps": 500.0, "combat_time": 10.0, "local_debuff": 0.0,
                "local_attacks_in_share": 0.0, "hps": 0.0, "kills": 0, "deaths": 0,
            },
        }

        window.update_live_display(player_data, 10.0)
        self.app.processEvents()

        self.assertEqual(self.widgets.live_parser_preview_model._data[0][0][0], "Higher")
        self.assertEqual(self.widgets.live_parser_preview_model._data[0][8], 1)
        self.assertEqual(view._preview_buffers[0][-1], 100.0)
        self.assertEqual(view._preview_buffers[1][-1], 500.0)

    def test_live_column_controls_write_existing_settings_and_both_views(self):
        window = self.make_window(command_console=True)
        parent = QFrame()
        self.addCleanup(parent.close)
        view = LiveView(
            self.theme, self.settings, OSCRConfig(), self.widgets, window)
        view.build(parent)

        button = self.widgets.live_parser_column_buttons[1]
        self.assertFalse(self.settings.liveparser__columns[1])
        button.click()
        self.app.processEvents()

        self.assertTrue(self.settings.liveparser__columns[1])
        self.assertFalse(self.widgets.live_parser_preview_table.isColumnHidden(1))
        self.assertFalse(window._table.isColumnHidden(1))

    def test_live_page_controls_round_trip_every_existing_setting(self):
        window = self.make_window(command_console=True)
        parent = QFrame()
        self.addCleanup(parent.close)
        view = LiveView(
            self.theme, self.settings, OSCRConfig(), self.widgets, window)
        view.build(parent)

        self.widgets.live_parser_graph_toggle.click()
        self.widgets.live_parser_graph_field.setCurrentIndex(3)
        self.widgets.live_parser_player_display.setCurrentText("Name")
        parent.findChild(QPushButton, "settingsLiveDefault").click()
        parent.findChild(QPushButton, "settingsLiveCopyKills").click()
        parent.findChild(QSlider, "settingsLiveOpacity").setValue(12)
        parent.findChild(QSlider, "settingsLiveScale").setValue(60)
        self.widgets.live_parser_column_buttons[1].click()
        self.settings.store_settings()
        self.settings._settings.sync()

        restored = OSCRSettings(self.settings_path)
        self.assertIs(restored.liveparser__graph_active, True)
        self.assertEqual(restored.liveparser__graph_field, 3)
        self.assertEqual(restored.liveparser__player_display, "Name")
        self.assertIs(restored.liveparser__auto_enabled, True)
        self.assertIs(restored.liveparser__copy_kills, True)
        self.assertEqual(restored.liveparser__window_opacity, 0.6)
        self.assertEqual(restored.liveparser__window_scale, 1.2)
        self.assertEqual(
            restored.liveparser__columns,
            [True, True, True, False, False, False, False],
        )

    def test_overlay_controls_start_local_feed_and_publish_generated_obs_file(self):
        window = self.make_window(command_console=True)
        controller = self.make_overlay(window)
        parent = QFrame()
        self.addCleanup(parent.close)
        view = LiveView(
            self.theme, self.settings, OSCRConfig(), self.widgets, window, controller)
        view.build(parent)
        controller.start_services()

        self.assertEqual(self.widgets.live_overlay_status_chip.text(), "FEED STOPPED")
        self.widgets.live_overlay_feed_button.click()
        self.app.processEvents()

        self.assertTrue(controller.feed.active)
        self.assertTrue(self.settings.overlay__feed_enabled)
        self.assertEqual(self.widgets.live_overlay_status_chip.text(), "FEED LIVE")
        self.assertTrue(controller.feed.output_path.is_file())
        self.assertEqual(
            self.widgets.live_overlay_output.text(), str(controller.feed.output_path))

    def test_global_visibility_modes_never_stop_parser(self):
        window = self.make_window(command_console=True)
        controller = self.make_overlay(window)
        self.assertTrue(window.start_parser())
        window.set_popout_visible(True)
        self.assertTrue(controller.set_feed_enabled(True))

        controller.set_hide_mode("all")
        controller.toggle_global_visibility()
        self.assertFalse(window.popout_visible)
        self.assertFalse(controller.feed.presentation_visible)
        self.assertTrue(window.parser_active)
        controller.toggle_global_visibility()
        self.assertTrue(window.popout_visible)
        self.assertTrue(controller.feed.presentation_visible)

        controller.set_hide_mode("popout")
        controller.toggle_global_visibility()
        self.assertFalse(window.popout_visible)
        self.assertTrue(controller.feed.presentation_visible)
        self.assertTrue(window.parser_active)

    def test_persisted_lan_feed_never_auto_starts_and_manual_start_requires_confirmation(self):
        window = self.make_window(command_console=True)
        controller = self.make_overlay(window)
        self.settings.overlay__feed_bind = "192.168.1.50"
        self.settings.overlay__feed_enabled = True

        controller.start_services()

        self.assertFalse(controller.feed.active)
        self.assertFalse(self.settings.overlay__feed_enabled)
        self.assertEqual(controller.feed.current_state()["status"], "warning")
        with patch.object(controller.feed, "start", return_value=True) as start:
            self.assertFalse(controller.set_feed_enabled(True))
            start.assert_not_called()
            self.assertTrue(controller.set_feed_enabled(True, lan_confirmed=True))
            start.assert_called_once_with("192.168.1.50", self.settings.overlay__feed_port)


if __name__ == "__main__":
    unittest.main()
