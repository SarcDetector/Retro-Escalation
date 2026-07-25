import ast
import json
import os
from pathlib import Path
import sys
import tempfile
import tomllib
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from re_oscr.waylandpresenter import (
    MAX_LINE_BYTES,
    MAX_ROWS,
    PROTOCOL_ID,
    StdinCommandReader,
    WaylandPresenterWindow,
    encode_event,
)
from re_oscr import waylandoverlay
from re_oscr.waylandoverlay import (
    LayerShellSupport,
    WaylandPresentationProcess,
    detect_layer_shell_support,
    prepare_environment,
)
from retro_escalation import RetroEscalationLauncher


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class FakeSignal:
    def __init__(self):
        self.callbacks = []

    def connect(self, callback):
        self.callbacks.append(callback)


class FakeProcess:
    class ProcessState:
        NotRunning = 0
        Running = 1

    class ProcessChannelMode:
        SeparateChannels = 0

    def __init__(self, parent=None):
        self.parent = parent
        self.started = FakeSignal()
        self.readyReadStandardOutput = FakeSignal()
        self.readyReadStandardError = FakeSignal()
        self.bytesWritten = FakeSignal()
        self.errorOccurred = FakeSignal()
        self.finished = FakeSignal()
        self._state = self.ProcessState.NotRunning
        self.program = ""
        self.arguments = []
        self.environment = None
        self.working_directory = ""
        self.writes = []

    def state(self):
        return self._state

    def setProcessChannelMode(self, mode):
        self.channel_mode = mode

    def setProcessEnvironment(self, environment):
        self.environment = environment

    def setWorkingDirectory(self, directory):
        self.working_directory = directory

    def start(self, program, arguments):
        self.program = program
        self.arguments = list(arguments)
        self._state = self.ProcessState.Running

    def bytesToWrite(self):
        return 0

    def write(self, data):
        self.writes.append(bytes(data))
        return len(data)

    def waitForBytesWritten(self, _milliseconds):
        return True

    def closeWriteChannel(self):
        pass

    def terminate(self):
        self._state = self.ProcessState.NotRunning

    def kill(self):
        self._state = self.ProcessState.NotRunning


class WaylandProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def make_window(self):
        events = []
        window = WaylandPresenterWindow(event_writer=events.append)
        self.addCleanup(window.deleteLater)
        return window, events

    def test_child_events_use_canonical_bounded_ndjson(self):
        examples = (
            ("ready", {"detail": "layer-shell"}),
            ("parser", {"active": True}),
            (
                "geometry",
                {"left": 12, "top": 34, "width": 480, "height": 180},
            ),
            ("close", {}),
        )
        for event, payload in examples:
            with self.subTest(event=event):
                encoded = encode_event(event, **payload)

                self.assertIsInstance(encoded, bytes)
                self.assertTrue(encoded.endswith(b"\n"))
                self.assertEqual(encoded.count(b"\n"), 1)
                self.assertEqual(
                    json.loads(encoded),
                    {
                        "protocol": PROTOCOL_ID,
                        "type": event,
                        "payload": payload,
                    },
                )

    def test_presenter_module_has_no_parser_config_or_browser_overlay_import(self):
        source = (
            REPOSITORY_ROOT / "re_oscr" / "waylandpresenter.py"
        ).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")

        forbidden = (
            "OSCR",
            "re_oscr.config",
            "re_oscr.liveoverlay",
            "re_oscr.liveparser",
        )
        for module in imported:
            self.assertFalse(
                module.startswith(forbidden),
                f"presentation child must not import {module}",
            )

    def test_reader_accepts_fragmented_canonical_commands_and_rejects_bad_json(self):
        reader = StdinCommandReader(start_notifier=False)
        self.addCleanup(reader.deleteLater)
        commands = []
        errors = []
        reader.command_received.connect(commands.append)
        reader.protocol_error.connect(errors.append)
        encoded = (
            json.dumps(
                {
                    "protocol": PROTOCOL_ID,
                    "type": "hide",
                    "payload": {},
                }
            )
            + "\n"
        ).encode("utf-8")

        reader.feed_bytes(encoded[:7])
        self.assertEqual(commands, [])
        second = (
            json.dumps(
                {
                    "protocol": PROTOCOL_ID,
                    "type": "parser-state",
                    "payload": {"active": True},
                }
            )
            + "\n"
        ).encode("utf-8")
        reader.feed_bytes(encoded[7:] + second + b"{not-json}\n")

        self.assertEqual(
            commands,
            [
                {"protocol": PROTOCOL_ID, "type": "hide", "payload": {}},
                {
                    "protocol": PROTOCOL_ID,
                    "type": "parser-state",
                    "payload": {"active": True},
                },
            ],
        )
        self.assertEqual(errors, ["invalid protocol JSON"])

    def test_reader_bounds_oversized_frames_and_recovers_at_newline(self):
        reader = StdinCommandReader(start_notifier=False)
        self.addCleanup(reader.deleteLater)
        commands = []
        errors = []
        reader.command_received.connect(commands.append)
        reader.protocol_error.connect(errors.append)
        valid = (
            json.dumps(
                {"protocol": PROTOCOL_ID, "type": "hide", "payload": {}}
            )
            + "\n"
        ).encode("utf-8")

        reader.feed_bytes(b"x" * (MAX_LINE_BYTES + 1))
        reader.feed_bytes(b"\n" + valid)

        self.assertEqual(errors, ["command line exceeds protocol limit"])
        self.assertEqual(
            commands,
            [{"protocol": PROTOCOL_ID, "type": "hide", "payload": {}}],
        )

    def test_presenter_rejects_sensitive_paths_without_changing_state(self):
        window, events = self.make_window()
        original_live = dict(window._live)

        window.process_command(
            {
                "protocol": PROTOCOL_ID,
                "type": "configure",
                "payload": {
                    "live": {"opacity": 0.25},
                    "nested": {"config_dir": "C:/private/settings"},
                },
            }
        )

        self.assertEqual(window._live, original_live)
        error = json.loads(events[-1])
        self.assertEqual(error["protocol"], PROTOCOL_ID)
        self.assertEqual(error["type"], "error")
        self.assertIn("forbidden", error["payload"]["reason"])

    def test_presenter_accepts_only_normalized_bounded_snapshot_rows(self):
        window, events = self.make_window()
        rows = [
            [
                [f"Anonymous {index}", f"@tester{index}"],
                index + 0.5,
                10.0,
                0.0,
                2.0,
                1.0,
                0,
                0,
                index,
            ]
            for index in range(MAX_ROWS + 20)
        ]

        window.process_command(
            {
                "protocol": PROTOCOL_ID,
                "type": "snapshot",
                "payload": {
                    "sequence": 4,
                    "rows": rows,
                    "duration": 21.5,
                },
            }
        )

        self.assertEqual(len(window._model.rows), MAX_ROWS)
        self.assertEqual(window._duration, 21.5)
        self.assertEqual(events, [])
        self.assertTrue(all(len(row) == 9 for row in window._model.rows))

    def test_stale_snapshots_are_ignored_and_new_empty_snapshot_clears(self):
        window, _events = self.make_window()
        row = [["Anonymous", "@tester"], 10, 9, 8, 7, 6, 5, 4, 0]

        window.process_command(
            {
                "protocol": PROTOCOL_ID,
                "type": "snapshot",
                "payload": {"sequence": 8, "rows": [row], "duration": 12},
            }
        )
        window.process_command(
            {
                "protocol": PROTOCOL_ID,
                "type": "snapshot",
                "payload": {"sequence": 7, "rows": [], "duration": 1},
            }
        )
        self.assertEqual(len(window._model.rows), 1)
        self.assertEqual(window._duration, 12)

        window.process_command(
            {
                "protocol": PROTOCOL_ID,
                "type": "snapshot",
                "payload": {"sequence": 9, "rows": [], "duration": 14},
            }
        )
        self.assertEqual(window._model.rows, ())
        self.assertEqual(window._duration, 14)

    def test_wrong_protocol_and_unknown_commands_are_nonfatal_errors(self):
        window, events = self.make_window()

        window.process_command(
            {"protocol": "other.v1", "type": "hide", "payload": {}}
        )
        window.process_command(
            {"protocol": PROTOCOL_ID, "type": "read-log", "payload": {}}
        )

        decoded = [json.loads(event) for event in events]
        self.assertEqual([event["type"] for event in decoded], ["error", "error"])
        self.assertFalse(window.isVisible())

    def test_hiding_clears_in_progress_relative_pointer_drag(self):
        window, _events = self.make_window()
        window._dragging = True
        window._drag_fraction = [0.75, -0.5]

        window.process_command(
            {"protocol": PROTOCOL_ID, "type": "hide", "payload": {}}
        )

        self.assertFalse(window._dragging)
        self.assertEqual(window._drag_fraction, [0.0, 0.0])


class WaylandHostSupportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    @staticmethod
    def supported_probe(root):
        plugin = (
            root
            / "layershellqt"
            / "wayland-shell-integration"
            / "liblayer-shell.so"
        )
        plugin.parent.mkdir(parents=True)
        plugin.write_bytes(b"test plugin")
        interface = root / "libLayerShellQtInterface.so.6"
        interface.write_bytes(
            b"\0".join(
                symbol.encode("ascii")
                for symbol in waylandoverlay._REQUIRED_SYMBOLS
            )
        )
        environment = {
            "RE_OSCR_WAYLAND_TEST_OVERRIDE": "1",
            "RE_OSCR_LAYER_SHELL_QT_VERSION": waylandoverlay.qVersion(),
        }
        return detect_layer_shell_support(
            environ=environment,
            frozen_root=root,
        )

    def test_non_wayland_probe_is_unsupported_and_does_not_mutate_parent_env(self):
        supplied = {
            "XDG_SESSION_TYPE": "x11",
            "QT_QPA_PLATFORM": "offscreen",
        }
        supplied_before = dict(supplied)
        parent_before = dict(os.environ)
        with patch.object(waylandoverlay.sys, "platform", "linux"):
            support = detect_layer_shell_support(environ=supplied)

        self.assertFalse(support.supported)
        self.assertIn("not native Wayland", support.reason)
        self.assertEqual(supplied, supplied_before)
        self.assertEqual(dict(os.environ), parent_before)

    def test_gnome_mutter_uses_conservative_normal_popout_fallback(self):
        environment = {
            "WAYLAND_DISPLAY": "wayland-0",
            "XDG_SESSION_TYPE": "wayland",
            "XDG_CURRENT_DESKTOP": "GNOME",
        }
        with patch.object(waylandoverlay.sys, "platform", "linux"):
            support = detect_layer_shell_support(environ=environment)

        self.assertFalse(support.supported)
        self.assertIn("GNOME/Mutter", support.reason)

    def test_frozen_bundle_paths_and_required_symbols_enable_support(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            support = self.supported_probe(root)

            self.assertTrue(support.supported, support.reason)
            self.assertEqual(
                Path(support.plugin_path),
                (
                    root
                    / "layershellqt"
                    / "wayland-shell-integration"
                    / "liblayer-shell.so"
                ).resolve(),
            )
            self.assertEqual(
                Path(support.interface_library),
                (root / "libLayerShellQtInterface.so.6").resolve(),
            )

            with patch.dict(
                os.environ,
                {
                    "QT_PLUGIN_PATH": "existing-plugins",
                    "LD_LIBRARY_PATH": "existing-libraries",
                },
                clear=True,
            ):
                selected = prepare_environment(support)
                self.assertIs(selected, support)
                self.assertEqual(
                    os.environ["QT_WAYLAND_SHELL_INTEGRATION"],
                    "layer-shell",
                )
                self.assertEqual(
                    os.environ["RE_OSCR_LAYER_SHELL_INTERFACE"],
                    support.interface_library,
                )
                self.assertIn(
                    support.plugin_root,
                    os.environ["QT_PLUGIN_PATH"].split(os.pathsep),
                )
                runtime_plugins = waylandoverlay.QLibraryInfo.path(
                    waylandoverlay.QLibraryInfo.LibraryPath.PluginsPath)
                self.assertEqual(
                    os.environ["QT_PLUGIN_PATH"].split(os.pathsep)[0],
                    runtime_plugins,
                )
                self.assertEqual(
                    os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"],
                    str(Path(runtime_plugins) / "platforms"),
                )
                self.assertEqual(
                    os.environ["LD_LIBRARY_PATH"],
                    "existing-libraries",
                )

    def test_mismatched_system_qt_abi_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            plugin_root = root / "plugins"
            plugin = (
                plugin_root
                / "wayland-shell-integration"
                / "liblayer-shell.so"
            )
            plugin.parent.mkdir(parents=True)
            plugin.write_bytes(b"test plugin")
            interface = root / "libLayerShellQtInterface.so.6"
            interface.write_bytes(
                b"\0".join(
                    symbol.encode("ascii")
                    for symbol in waylandoverlay._REQUIRED_SYMBOLS
                )
            )
            support = detect_layer_shell_support(
                environ={
                    "RE_OSCR_WAYLAND_TEST_OVERRIDE": "1",
                    "RE_OSCR_LAYER_SHELL_PLUGIN_ROOT": str(plugin_root),
                    "RE_OSCR_LAYER_SHELL_INTERFACE": str(interface),
                    "RE_OSCR_LAYER_SHELL_QT_VERSION": "6.0.0",
                }
            )

        self.assertFalse(support.supported)
        self.assertIn("ABI", support.reason)

    def test_missing_native_support_does_not_create_a_child_controller(self):
        unsupported = LayerShellSupport(
            supported=False,
            reason="synthetic missing LayerShellQt",
            runtime_qt_version=waylandoverlay.qVersion(),
        )
        with patch.object(
            waylandoverlay,
            "detect_layer_shell_support",
            return_value=unsupported,
        ):
            controller = WaylandPresentationProcess.create_if_supported(
                str(REPOSITORY_ROOT)
            )

        self.assertIsNone(controller)

    def test_parent_row_sanitizer_preserves_player_identity_pair(self):
        rows = waylandoverlay._sanitize_rows(
            [
                [
                    ["Anonymous", "@tester"],
                    123.5,
                    15.0,
                    0.0,
                    3.0,
                    4.0,
                    2,
                    0,
                    1,
                ]
            ]
        )

        self.assertEqual(rows[0][0], ["Anonymous", "@tester"])
        self.assertEqual(rows[0][1:], [123.5, 15.0, 0.0, 3.0, 4.0, 2, 0, 1])

    def test_configuration_allowlist_strips_sensitive_and_browser_fields(self):
        support = LayerShellSupport(
            supported=True,
            reason="test",
            plugin_root="C:/layer/plugins",
            plugin_path="C:/layer/plugins/wayland-shell-integration/plugin.so",
            interface_library="C:/layer/libLayerShellQtInterface.so.6",
            runtime_qt_version=waylandoverlay.qVersion(),
        )
        controller = WaylandPresentationProcess(
            str(REPOSITORY_ROOT),
            support=support,
        )
        self.addCleanup(controller.deleteLater)

        controller.send_configuration(
            {
                "theme_id": "command-console",
                "log_path": "C:/private/CombatLog.log",
                "config_dir": "C:/private/settings",
                "browser_feed_token": "secret",
                "live": {
                    "opacity": 0.75,
                    "sto_log_path": "C:/private/CombatLog.log",
                    "feed_bind": "0.0.0.0",
                },
                "labels": {
                    "copy": "Copy Result",
                    "telemetry": "secret",
                },
            }
        )

        packet = controller._outbox[-1]
        payload = packet["payload"]
        self.assertEqual(
            payload,
            {
                "theme_id": "command-console",
                "live": {"opacity": 0.75},
                "labels": {"copy": "Copy Result"},
            },
        )
        serialized = json.dumps(packet)
        self.assertNotIn("CombatLog", serialized)
        self.assertNotIn("secret", serialized)

    def test_source_launch_argv_is_presentation_only_and_never_spawns_in_test(self):
        support = LayerShellSupport(
            supported=True,
            reason="test",
            plugin_root="C:/layer/plugins",
            plugin_path="C:/layer/plugins/wayland-shell-integration/plugin.so",
            interface_library="C:/layer/libLayerShellQtInterface.so.6",
            runtime_qt_version=waylandoverlay.qVersion(),
        )
        controller = WaylandPresentationProcess(
            str(REPOSITORY_ROOT),
            support=support,
        )
        self.addCleanup(controller.deleteLater)

        with patch.object(waylandoverlay, "QProcess", FakeProcess):
            self.assertTrue(controller._start())

        process = controller._process
        self.assertIsInstance(process, FakeProcess)
        self.assertIn("--wayland-live-presenter", process.arguments)
        self.assertIn("--app-dir", process.arguments)
        self.assertNotIn("--config_dir", process.arguments)
        self.assertNotIn("--config-dir", process.arguments)
        self.assertNotIn("--log-path", process.arguments)
        self.assertNotIn("--log-file", process.arguments)
        self.assertTrue(process.program)
        controller._startup_timer.stop()
        process._state = FakeProcess.ProcessState.NotRunning

    def test_quick_close_preserves_initial_show_handshake_before_hide(self):
        support = LayerShellSupport(
            supported=True,
            reason="test",
            plugin_root="C:/layer/plugins",
            plugin_path="C:/layer/plugins/wayland-shell-integration/plugin.so",
            interface_library="C:/layer/libLayerShellQtInterface.so.6",
            runtime_qt_version=waylandoverlay.qVersion(),
        )
        controller = WaylandPresentationProcess(
            str(REPOSITORY_ROOT),
            support=support,
        )
        self.addCleanup(controller.deleteLater)

        with patch.object(waylandoverlay, "QProcess", FakeProcess):
            self.assertTrue(
                controller.show_presentation({}, [], 0.0, False)
            )
            controller.hide_presentation()

        process = controller._process
        self.assertIsInstance(process, FakeProcess)
        packet_types = [
            json.loads(frame.decode("utf-8"))["type"]
            for frame in process.writes
        ]
        self.assertEqual(
            packet_types,
            ["configure", "snapshot", "parser-state", "show", "hide"],
        )
        controller._startup_timer.stop()
        process._state = FakeProcess.ProcessState.NotRunning

    def test_builder_requires_one_qtpaths_layer_shell_pair(self):
        script = (
            REPOSITORY_ROOT
            / "distribution"
            / "linux"
            / "build_retro_escalation.sh"
        ).read_text(encoding="utf-8")

        self.assertIn("qtpaths6 --plugin-dir", script)
        self.assertIn("qtpaths6 --query QT_INSTALL_LIBS", script)
        self.assertNotIn("/usr/lib/*-linux-gnu/qt6/plugins", script)
        self.assertNotIn(
            "/usr/lib/*-linux-gnu/libLayerShellQtInterface", script
        )


class WaylandPresenterEntrypointTests(unittest.TestCase):
    def test_internal_presenter_launch_does_not_resolve_user_config(self):
        app_dir = str(REPOSITORY_ROOT / "assets")
        argv = [
            "re-oscr",
            "--wayland-live-presenter",
            "--app-dir",
            app_dir,
        ]

        with (
            patch.object(sys, "argv", argv),
            patch(
                "retro_escalation.RetroEscalationLauncher.default_config_dir",
                side_effect=AssertionError("presenter must not resolve a config path"),
            ),
            patch(
                "re_oscr.waylandpresenter.run_presenter",
                return_value=17,
            ) as run_presenter,
        ):
            with self.assertRaisesRegex(SystemExit, "^17$"):
                RetroEscalationLauncher.launch()

        run_presenter.assert_called_once_with(app_dir)


class WaylandPackagingContractTests(unittest.TestCase):
    def test_pywayland_is_an_optional_extra_not_a_core_dependency(self):
        metadata = tomllib.loads(
            (REPOSITORY_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        )["project"]

        self.assertNotIn("pywayland", " ".join(metadata["dependencies"]).lower())
        self.assertTrue(
            any(
                dependency.lower().startswith("pywayland")
                for dependency in metadata["optional-dependencies"]["wayland"]
            )
        )


if __name__ == "__main__":
    unittest.main()
