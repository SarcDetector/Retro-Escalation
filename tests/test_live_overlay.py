import json
import math
import os
from pathlib import Path
import tempfile
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QUrl
from PySide6.QtNetwork import QHostAddress, QTcpServer
from PySide6.QtWebSockets import QWebSocket
from PySide6.QtWidgets import QApplication

from re_oscr.config import OSCRSettings
from re_oscr.liveoverlay import (
    MAX_CUSTOM_CSS_BYTES,
    LiveOverlayFeed,
    is_rfc1918_address,
    validate_overlay_bind,
    validate_overlay_port,
)
from re_oscr.themes.command_console import create_command_console_theme


class LiveOverlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.asset_dir = Path(__file__).resolve().parents[1] / "assets" / "overlay"

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.settings = OSCRSettings(self.root / "settings.ini")
        self.settings.overlay__feed_port = self._free_port()
        self.theme = create_command_console_theme(1.0)
        self.feed = LiveOverlayFeed(
            self.settings, self.root, self.asset_dir, self.theme)
        self.addCleanup(self.feed.shutdown)

    def _free_port(self):
        probe = QTcpServer()
        self.assertTrue(probe.listen(QHostAddress("127.0.0.1"), 0))
        port = probe.serverPort()
        probe.close()
        return port

    def _wait_for(self, predicate, timeout=2.0):
        deadline = time.monotonic() + timeout
        while not predicate() and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.005)
        self.app.processEvents()
        return predicate()

    def test_bind_and_port_validation_never_widens_the_listener(self):
        self.assertTrue(is_rfc1918_address("192.168.1.20"))
        self.assertTrue(is_rfc1918_address("172.16.0.1"))
        self.assertFalse(is_rfc1918_address("8.8.8.8"))
        self.assertFalse(is_rfc1918_address("127.0.0.1"))
        self.assertEqual(validate_overlay_bind("127.0.0.1"), (True, ""))
        for address in ("0.0.0.0", "::", "localhost", "8.8.8.8", "169.254.1.2"):
            with self.subTest(address=address):
                self.assertFalse(validate_overlay_bind(address)[0])
        self.assertTrue(validate_overlay_bind(
            "192.168.1.20", {"192.168.1.20"})[0])
        self.assertFalse(validate_overlay_bind("192.168.1.21", {"192.168.1.20"})[0])
        self.assertEqual(validate_overlay_port(1024), (True, ""))
        self.assertEqual(validate_overlay_port(65535), (True, ""))
        for port in (80, 65536, "invalid"):
            with self.subTest(port=port):
                self.assertFalse(validate_overlay_port(port)[0])

    def test_payload_is_versioned_sanitized_and_restored_after_hide(self):
        long_label = "R" * 180
        rows = [
            [(long_label, "@raman"), 500_000.5, 12.0, math.nan, math.inf, 0, 4, 0, 2],
        ]
        self.feed.publish_snapshot(rows, math.inf)
        payload = self.feed.last_payload

        self.assertEqual(payload["type"], "snapshot")
        self.assertEqual(payload["version"], 1)
        self.assertEqual(payload["duration"], 0)
        self.assertEqual(payload["rows"][0]["label"], "@raman")
        self.assertEqual(payload["rows"][0]["color"], self.theme["plot"]["color_cycler"][2])
        self.assertTrue(all(math.isfinite(value) for value in payload["rows"][0]["values"]))
        cached_headers = payload["headers"]

        self.feed.set_presentation_visible(False)
        hidden = self.feed.last_payload
        self.assertFalse(hidden["visible"])
        self.assertEqual(hidden["rows"], [])
        self.assertEqual(hidden["headers"], [])
        self.assertEqual(hidden["duration"], 0)
        self.assertFalse(hidden["parserActive"])

        self.feed.set_presentation_visible(True)
        self.assertEqual(self.feed.last_payload["headers"], cached_headers)
        self.assertEqual(self.feed.last_payload["rows"][0]["label"], "@raman")

    def test_start_generates_complete_obs_folder_and_masks_state_token(self):
        self.assertTrue(self.feed.start())

        output_dir = self.feed.output_path.parent
        self.assertEqual(
            {path.name for path in output_dir.iterdir()},
            {
                "README.txt", "overlay-config.js", "overlay-custom.css",
                "overlay.css", "overlay.html", "overlay.js",
            },
        )
        self.assertIn(
            'href="overlay-custom.css"',
            (output_dir / "overlay.html").read_text(encoding="utf-8"),
        )
        config = (output_dir / "overlay-config.js").read_text(encoding="utf-8")
        self.assertIn(self.feed.endpoint, config)
        self.assertNotIn(self.settings.overlay__feed_token, self.feed.display_endpoint)
        self.assertNotIn(self.settings.overlay__feed_token, self.feed.current_state()["endpoint"])

    def test_malformed_port_and_custom_css_fail_inline_without_stopping_parser_data(self):
        self.assertFalse(self.feed.start(port="not-a-port"))
        self.assertEqual(self.feed.current_state()["status"], "error")

        self.feed.set_custom_css("//server/share/overlay.css")
        self.assertIn("rejected", self.feed.current_state()["customCssWarning"].lower())
        oversized = self.root / "oversized.css"
        oversized.write_bytes(b"x" * (MAX_CUSTOM_CSS_BYTES + 1))
        self.feed.set_custom_css(str(oversized))
        self.assertIn("ignored", self.feed.current_state()["customCssWarning"].lower())

    def test_real_client_receives_snapshot_and_stop_disposes_it_once(self):
        self.feed.publish_snapshot(
            [[("Raman", "@raman"), 1000, 10, 20, 30, 40, 5, 0, 0]], 10.0)
        self.assertTrue(self.feed.start())
        client = QWebSocket()
        messages = []
        client.textMessageReceived.connect(messages.append)
        client.open(QUrl(self.feed.endpoint))
        self.addCleanup(client.deleteLater)

        self.assertTrue(self._wait_for(lambda: bool(messages)))
        payload = json.loads(messages[0])
        self.assertEqual(payload["version"], 1)
        self.assertEqual(payload["rows"][0]["label"], "@raman")
        self.assertEqual(self.feed.client_count, 1)

        self.feed.stop()
        self.assertTrue(self._wait_for(lambda: self.feed.client_count == 0))
        self.assertFalse(self.feed.active)

    def test_any_client_message_is_rejected_as_read_only(self):
        self.assertTrue(self.feed.start())
        client = QWebSocket()
        connected = []
        disconnected = []
        client.connected.connect(lambda: connected.append(True))
        client.disconnected.connect(lambda: disconnected.append(True))
        client.open(QUrl(self.feed.endpoint))
        self.addCleanup(client.deleteLater)
        self.assertTrue(self._wait_for(lambda: bool(connected)))

        client.sendTextMessage("mutate")
        self.assertTrue(self._wait_for(lambda: bool(disconnected)))

    def test_wrong_path_or_token_cannot_join_the_feed(self):
        self.assertTrue(self.feed.start())
        rejected_urls = (
            self.feed.endpoint.replace("/feed?", "/wrong?"),
            self.feed.endpoint.rsplit("=", 1)[0] + "=wrong-token",
        )
        for url in rejected_urls:
            with self.subTest(url=url.split("?", 1)[0]):
                client = QWebSocket()
                disconnected = []
                messages = []
                client.disconnected.connect(lambda: disconnected.append(True))
                client.textMessageReceived.connect(messages.append)
                client.open(QUrl(url))
                self.assertTrue(self._wait_for(lambda: bool(disconnected)))
                self.assertEqual(messages, [])
                self.assertEqual(self.feed.client_count, 0)
                client.deleteLater()


if __name__ == "__main__":
    unittest.main()
