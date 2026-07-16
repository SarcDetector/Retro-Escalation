"""Read-only browser overlay and global presentation controls for Command Console."""

from __future__ import annotations

from dataclasses import dataclass
import hmac
import ipaddress
import json
import math
from pathlib import Path
import secrets

from OSCR import LIVE_TABLE_HEADER
from PySide6.QtCore import QObject, QUrlQuery, Qt, Signal, Slot
from PySide6.QtNetwork import QAbstractSocket, QHostAddress, QNetworkInterface
from PySide6.QtWebSockets import QWebSocketProtocol, QWebSocketServer

from .console.tokens import BORDERS, STATES, SURFACES, TEXT, ConsoleTokens
from .globalhotkeys import GlobalHotkeyController


OVERLAY_SCHEMA_VERSION = 1
DEFAULT_OVERLAY_PORT = 47025
MAX_OVERLAY_CLIENTS = 8
MAX_OVERLAY_ROWS = 64
MAX_OVERLAY_STRING = 128
MAX_CUSTOM_CSS_BYTES = 256 * 1024
MAX_CLIENT_BACKLOG = 256 * 1024
PRIVATE_NETWORKS = tuple(map(ipaddress.ip_network, (
    '10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16')))


@dataclass(frozen=True)
class OverlayBindAddress:
    """One explicit network adapter address available to the feed."""

    label: str
    address: str


def is_rfc1918_address(value: str) -> bool:
    """Return True only for the three explicit RFC1918 IPv4 ranges."""
    try:
        address = ipaddress.ip_address(str(value))
    except ValueError:
        return False
    return address.version == 4 and any(address in network for network in PRIVATE_NETWORKS)


def available_private_bind_addresses() -> tuple[OverlayBindAddress, ...]:
    """List active RFC1918 adapter addresses without wildcard or fallback values."""
    results: list[OverlayBindAddress] = []
    flags = QNetworkInterface.InterfaceFlag
    ipv4 = QAbstractSocket.NetworkLayerProtocol.IPv4Protocol
    for interface in QNetworkInterface.allInterfaces():
        interface_flags = interface.flags()
        if not interface_flags & flags.IsUp or not interface_flags & flags.IsRunning:
            continue
        if interface_flags & flags.IsLoopBack:
            continue
        for entry in interface.addressEntries():
            address = entry.ip()
            value = address.toString()
            if address.protocol() != ipv4 or not is_rfc1918_address(value):
                continue
            label = interface.humanReadableName() or interface.name() or 'Local network'
            results.append(OverlayBindAddress(f'{label} — {value}', value))
    unique = {item.address: item for item in results}
    return tuple(unique[address] for address in sorted(unique))


def validate_overlay_bind(value: str, available: set[str] | None = None) -> tuple[bool, str]:
    """Validate an exact loopback or currently assigned private IPv4 address."""
    candidate = str(value).strip()
    if candidate == '127.0.0.1':
        return True, ''
    if not is_rfc1918_address(candidate):
        return False, 'Choose Local only or an explicit private IPv4 adapter address.'
    available_values = available
    if available_values is None:
        available_values = {item.address for item in available_private_bind_addresses()}
    if candidate not in available_values:
        return False, (
            f'{candidate} is not currently assigned to an active network adapter. '
            'The feed was not started and did not fall back to another interface.')
    return True, ''


def validate_overlay_port(value: int) -> tuple[bool, str]:
    """Reject privileged, invalid, and out-of-range websocket ports."""
    try:
        port = int(value)
    except (TypeError, ValueError):
        return False, 'The overlay port must be a number from 1024 to 65535.'
    if not 1024 <= port <= 65535:
        return False, 'The overlay port must be from 1024 to 65535.'
    return True, ''


def _safe_number(value) -> int | float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0
    if not math.isfinite(number):
        return 0
    if number.is_integer() and abs(number) <= 9_007_199_254_740_991:
        return int(number)
    return number


class LiveOverlayFeed(QObject):
    """Qt-main-thread websocket service publishing presentation-only snapshots."""

    state_changed = Signal(object)
    clients_changed = Signal(int)
    presentation_visible_changed = Signal(bool)

    def __init__(self, settings, config_dir: Path, asset_dir: Path, theme, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._config_dir = Path(config_dir)
        self._asset_dir = Path(asset_dir)
        self._output_dir = self._config_dir / 'overlay'
        self._theme = theme
        self._server: QWebSocketServer | None = None
        self._clients: set = set()
        self._active = False
        self._visible = True
        self._parser_active = False
        self._bind = str(settings.overlay__feed_bind)
        self._port = int(settings.overlay__feed_port)
        self._token = ''
        self._last_rows: list[list] = []
        self._last_duration = 0.0
        self._last_serialized = ''
        self._detail = 'Browser overlay feed is stopped.'
        self._status = 'stopped'
        self._custom_css_warning = ''
        self._refresh_serialized()

    @property
    def active(self) -> bool:
        return self._active

    @property
    def presentation_visible(self) -> bool:
        return self._visible

    @property
    def client_count(self) -> int:
        return len(self._clients)

    @property
    def output_path(self) -> Path:
        return self._output_dir / 'overlay.html'

    @property
    def endpoint(self) -> str:
        token = self._ensure_token()
        return f'ws://{self._bind}:{self._port}/feed?token={token}'

    @property
    def display_endpoint(self) -> str:
        return f'ws://{self._bind}:{self._port}/feed?token=••••'

    @property
    def last_payload(self) -> dict:
        return json.loads(self._last_serialized)

    def current_state(self) -> dict:
        return {
            'active': self._active,
            'status': self._status,
            'detail': self._detail,
            'clients': len(self._clients),
            'endpoint': self.display_endpoint,
            'outputPath': str(self.output_path),
            'bind': self._bind,
            'port': self._port,
            'lan': self._bind != '127.0.0.1',
            'visible': self._visible,
            'customCssWarning': self._custom_css_warning,
        }

    def report_state(self, status: str, detail: str) -> None:
        """Expose a retryable inline state without touching parser or popout."""
        self._status = status
        self._detail = detail
        self.state_changed.emit(self.current_state())

    def configure(self, bind: str, port: int) -> None:
        """Stage an endpoint while stopped so the page can preview the exact choice."""
        if self._active:
            return
        self._bind = str(bind)
        self._port = int(port)
        self._refresh_serialized()
        self.state_changed.emit(self.current_state())

    def start(self, bind: str | None = None, port: int | None = None) -> bool:
        candidate_bind = str(
            bind if bind is not None else self._settings.overlay__feed_bind).strip()
        candidate_port_value = (
            port if port is not None else self._settings.overlay__feed_port)
        valid, detail = validate_overlay_bind(candidate_bind)
        if not valid:
            self.report_state('error', detail)
            return False
        valid, detail = validate_overlay_port(candidate_port_value)
        if not valid:
            self.report_state('error', detail)
            return False
        candidate_port = int(candidate_port_value)
        if self._active and candidate_bind == self._bind and candidate_port == self._port:
            self.report_state('active', f'Feed listening at {self.display_endpoint}.')
            return True
        if self._active:
            self.stop()

        server = QWebSocketServer(
            'RE-OSCR Live Overlay', QWebSocketServer.SslMode.NonSecureMode, self)
        server.setMaxPendingConnections(MAX_OVERLAY_CLIENTS)
        server.setHandshakeTimeout(5000)
        server.newConnection.connect(self._accept_connections)
        server.acceptError.connect(
            lambda _error: self.report_state('error', server.errorString()))
        server.serverError.connect(
            lambda _error: self.report_state('error', server.errorString()))
        address = QHostAddress(candidate_bind)
        if not server.listen(address, candidate_port):
            detail = server.errorString() or (
                f'Could not listen on {candidate_bind}:{candidate_port}.')
            server.deleteLater()
            self.report_state('error', detail)
            return False

        self._server = server
        self._bind = candidate_bind
        self._port = candidate_port
        self._active = True
        self._visible = True
        try:
            self._write_overlay_assets()
        except OSError as error:
            self.stop()
            self.report_state('error', f'Could not prepare the browser overlay: {error}')
            return False
        self._refresh_serialized()
        self.report_state('active', f'Feed listening at {self.display_endpoint}.')
        return True

    def stop(self) -> None:
        for client in tuple(self._clients):
            self._clients.discard(client)
            try:
                client.blockSignals(True)
                client.close(
                    QWebSocketProtocol.CloseCode.CloseCodeGoingAway,
                    'RE-OSCR overlay feed stopped')
            except RuntimeError:
                pass
            try:
                client.deleteLater()
            except RuntimeError:
                pass
        self._clients.clear()
        if self._server is not None:
            self._server.close()
            self._server.deleteLater()
            self._server = None
        self._active = False
        self._status = 'stopped'
        self._detail = 'Browser overlay feed is stopped.'
        self.clients_changed.emit(0)
        self.state_changed.emit(self.current_state())

    @Slot(object, float)
    def publish_snapshot(self, rows: list, duration: float) -> None:
        self._last_rows = [list(row) for row in list(rows)[:MAX_OVERLAY_ROWS]]
        self._last_duration = float(_safe_number(duration))
        self._refresh_serialized()
        if self._active:
            self._broadcast()

    @Slot(bool)
    def set_parser_active(self, active: bool) -> None:
        self._parser_active = bool(active)
        self._refresh_serialized()
        if self._active:
            self._broadcast()

    def set_presentation_visible(self, visible: bool) -> None:
        visible = bool(visible)
        if visible == self._visible:
            return
        self._visible = visible
        self._refresh_serialized()
        if self._active:
            self._broadcast()
        self.presentation_visible_changed.emit(visible)
        self.state_changed.emit(self.current_state())

    def refresh_presentation_settings(self) -> None:
        self._refresh_serialized()
        if self._active:
            try:
                self._write_overlay_assets()
            except OSError as error:
                self.report_state(
                    'warning', f'Telemetry remains live, but overlay files could not be '
                    f'updated: {error}')
                return
            self._broadcast()

    def set_theme(self, theme) -> None:
        self._theme = theme
        self._refresh_serialized()
        if self._active:
            self._broadcast()

    def set_custom_css(self, path: str) -> None:
        self._settings.overlay__custom_css_path = str(path)
        _content, self._custom_css_warning = self._load_custom_css()
        if self._active:
            try:
                self._write_overlay_assets()
            except OSError as error:
                self.report_state(
                    'warning', f'Telemetry remains live, but custom CSS could not be '
                    f'updated: {error}')
                return
        self.state_changed.emit(self.current_state())

    def shutdown(self) -> None:
        self.stop()

    def _ensure_token(self) -> str:
        candidate = str(self._settings.overlay__feed_token).strip()
        if (24 <= len(candidate) <= 128
                and all(character.isalnum() or character in '_-' for character in candidate)):
            self._token = candidate
            return candidate
        self._token = secrets.token_urlsafe(32)
        self._settings.overlay__feed_token = self._token
        return self._token

    def _accept_connections(self) -> None:
        if self._server is None:
            return
        while self._server.hasPendingConnections():
            client = self._server.nextPendingConnection()
            if client is None:
                continue
            request_url = client.requestUrl()
            token_values = [
                value for key, value in QUrlQuery(request_url).queryItems()
                if key == 'token']
            supplied_token = token_values[0] if len(token_values) == 1 else ''
            origin = client.origin().strip().lower()
            allowed_origin = (
                not origin or origin == 'null' or origin.startswith('file:'))
            if (len(self._clients) >= MAX_OVERLAY_CLIENTS
                    or request_url.path() != '/feed'
                    or not hmac.compare_digest(supplied_token, self._ensure_token())
                    or not allowed_origin):
                client.close(
                    QWebSocketProtocol.CloseCode.CloseCodePolicyViolated,
                    'Overlay feed access rejected')
                client.deleteLater()
                continue
            client.setMaxAllowedIncomingFrameSize(1024)
            client.setMaxAllowedIncomingMessageSize(1024)
            client.textMessageReceived.connect(
                lambda _message, socket=client: self._reject_incoming(socket))
            client.binaryMessageReceived.connect(
                lambda _message, socket=client: self._reject_incoming(socket))
            client.disconnected.connect(
                lambda socket=client: self._remove_client(socket))
            self._clients.add(client)
            client.sendTextMessage(self._last_serialized)
        self.clients_changed.emit(len(self._clients))
        self.state_changed.emit(self.current_state())

    def _reject_incoming(self, client) -> None:
        try:
            client.close(
                QWebSocketProtocol.CloseCode.CloseCodePolicyViolated,
                'RE-OSCR overlay is read-only')
        except RuntimeError:
            pass

    def _remove_client(self, client) -> None:
        self._clients.discard(client)
        try:
            client.deleteLater()
        except RuntimeError:
            pass
        self.clients_changed.emit(len(self._clients))
        self.state_changed.emit(self.current_state())

    def _broadcast(self) -> None:
        connected = QAbstractSocket.SocketState.ConnectedState
        for client in tuple(self._clients):
            try:
                if client.state() != connected:
                    self._remove_client(client)
                elif client.bytesToWrite() > MAX_CLIENT_BACKLOG:
                    client.close(
                        QWebSocketProtocol.CloseCode.CloseCodeTooMuchData,
                        'Overlay client is not keeping up')
                else:
                    client.sendTextMessage(self._last_serialized)
            except RuntimeError:
                self._remove_client(client)

    def _refresh_serialized(self) -> None:
        headers = list(LIVE_TABLE_HEADER)
        selected = [
            index for index, visible in enumerate(self._settings.liveparser__columns)
            if visible and index < len(headers)]
        colours = ConsoleTokens.from_theme(self._theme).accents
        display_index = 1 if self._settings.liveparser__player_display == 'Handle' else 0
        payload_rows = []
        if self._visible:
            for row_index, row in enumerate(self._last_rows[:MAX_OVERLAY_ROWS]):
                if len(row) < 8:
                    continue
                player = row[0] if isinstance(row[0], (tuple, list)) else (str(row[0]), '')
                if not player:
                    label = ''
                elif len(player) > display_index:
                    label = str(player[display_index])
                else:
                    label = str(player[0])
                try:
                    colour_index = int(row[8])
                except (IndexError, TypeError, ValueError):
                    colour_index = row_index
                if not 0 <= colour_index < len(colours):
                    colour_index = row_index
                payload_rows.append({
                    'label': label[:MAX_OVERLAY_STRING],
                    'values': [_safe_number(row[1 + index]) for index in selected],
                    'color': (
                        colours[colour_index]
                        if colour_index < len(colours) else TEXT['secondary']),
                })
        payload = {
            'type': 'snapshot',
            'version': OVERLAY_SCHEMA_VERSION,
            'visible': self._visible,
            'parserActive': self._parser_active if self._visible else False,
            'duration': _safe_number(self._last_duration) if self._visible else 0,
            'headers': (
                [str(headers[index])[:MAX_OVERLAY_STRING] for index in selected]
                if self._visible else []),
            'rows': payload_rows,
            'theme': self._theme_variables(),
        }
        self._last_serialized = json.dumps(
            payload, ensure_ascii=False, allow_nan=False, separators=(',', ':'))

    def _theme_variables(self) -> dict[str, str]:
        tokens = ConsoleTokens.from_theme(self._theme)
        accent = tokens.accents[4]
        return {
            '--re-surface-void': SURFACES['void'],
            '--re-surface-base': SURFACES['base'],
            '--re-surface-raised': SURFACES['raised'],
            '--re-surface-overlay': SURFACES['overlay'],
            '--re-surface-deep': SURFACES['deep'],
            '--re-border-hairline': BORDERS['hairline'],
            '--re-border-control': BORDERS['control'],
            '--re-text-primary': TEXT['primary'],
            '--re-text-secondary': TEXT['secondary'],
            '--re-text-muted': TEXT['muted'],
            '--re-text-eyebrow': TEXT['eyebrow'],
            '--re-text-inverse': TEXT['inverse'],
            '--re-accent': accent,
            '--re-accent-dim': tokens.accent_dim(4),
            '--re-accent-edge': tokens.accent_edge(4),
            '--re-accent-tint': tokens.accent_tint(4),
            '--re-accent-track': SURFACES['deep'],
            '--re-success': STATES['success'],
            '--re-warning': STATES['warning'],
            '--re-danger': accent,
        }

    def _write_overlay_assets(self) -> None:
        required = ('overlay.html', 'overlay.css', 'overlay.js')
        missing = [name for name in required if not (self._asset_dir / name).is_file()]
        if missing:
            raise OSError(f'Missing bundled overlay asset: {", ".join(missing)}')
        self._output_dir.mkdir(parents=True, exist_ok=True)
        for name in required:
            (self._output_dir / name).write_bytes((self._asset_dir / name).read_bytes())
        config = (
            'window.RE_OSCR_OVERLAY_CONFIG = Object.freeze('
            + json.dumps({'endpoint': self.endpoint}, ensure_ascii=False)
            + ');\n')
        (self._output_dir / 'overlay-config.js').write_text(config, encoding='utf-8')
        custom_css, warning = self._load_custom_css()
        self._custom_css_warning = warning
        (self._output_dir / 'overlay-custom.css').write_text(custom_css, encoding='utf-8')
        instructions = (
            'RE-OSCR browser overlay\n\n'
            'OBS: add a Browser source, enable Local file, and select overlay.html.\n'
            'Keep every file in this folder together. RE-OSCR updates overlay-config.js when '
            'the feed starts. Refresh the OBS Browser source after changing custom CSS.\n')
        (self._output_dir / 'README.txt').write_text(instructions, encoding='utf-8')

    def _load_custom_css(self) -> tuple[str, str]:
        value = str(self._settings.overlay__custom_css_path).strip()
        if not value:
            return '/* No custom overlay stylesheet configured. */\n', ''
        if value.startswith(('\\\\', '//')):
            return '/* Custom stylesheet rejected. */\n', (
                'Custom CSS must be a regular local file; network and device paths are rejected.')
        path = Path(value)
        try:
            if path.suffix.casefold() != '.css' or not path.is_file():
                raise OSError('not a regular .css file')
            if path.stat().st_size > MAX_CUSTOM_CSS_BYTES:
                raise OSError('file exceeds 256 KiB')
            content = path.read_text(encoding='utf-8')
        except (OSError, UnicodeError) as error:
            return '/* Custom stylesheet could not be loaded. */\n', (
                f'Custom CSS was ignored ({error}); the bundled style remains active.')
        return content, (
            'Custom CSS contains url(); external resources are blocked by the overlay policy.'
            if 'url(' in content.casefold() else '')


class LiveOverlayController(QObject):
    """App-owned coordinator for the feed, hotkey, and presentation visibility."""

    def __init__(
            self, app, settings, config_dir: Path, asset_dir: Path, theme,
            live_parser, parent=None, hotkey_backend_factory=None):
        super().__init__(parent)
        self.settings = settings
        self.live_parser = live_parser
        self.feed = LiveOverlayFeed(settings, config_dir, asset_dir, theme, self)
        hotkey_kwargs = {}
        if hotkey_backend_factory is not None:
            hotkey_kwargs['backend_factory'] = hotkey_backend_factory
        self.hotkey = GlobalHotkeyController(app, self, **hotkey_kwargs)
        self.hotkey.activated.connect(self.toggle_global_visibility)
        self.live_parser.snapshot_updated.connect(
            self.feed.publish_snapshot, Qt.ConnectionType.QueuedConnection)
        self.live_parser.parser_active_changed.connect(
            self.feed.set_parser_active, Qt.ConnectionType.QueuedConnection)
        self._started = False
        self._shutting_down = False
        self._lan_confirmed = False

    def start_services(self) -> None:
        if self._shutting_down or self._started:
            return
        self._started = True
        self.hotkey.start(self.settings.overlay__hotkey_visibility)
        if not self.settings.overlay__feed_enabled:
            return
        if self.settings.overlay__feed_bind != '127.0.0.1':
            self.settings.overlay__feed_enabled = False
            self.feed.report_state(
                'warning', 'LAN feeds require confirmation once per application session. '
                'Start the unencrypted feed from this page to expose live character and '
                'combat telemetry.')
            return
        if not self.feed.start():
            self.settings.overlay__feed_enabled = False

    def set_feed_enabled(self, enabled: bool, lan_confirmed: bool = False) -> bool:
        if self._shutting_down:
            return False
        if enabled:
            if self.settings.overlay__feed_bind != '127.0.0.1':
                if not (self._lan_confirmed or lan_confirmed):
                    self.feed.report_state(
                        'warning', 'Confirm LAN start to expose live character and combat '
                        'telemetry over unencrypted ws:// to devices on this private network.')
                    return False
                self._lan_confirmed = True
            accepted = self.feed.start(
                self.settings.overlay__feed_bind, self.settings.overlay__feed_port)
            self.settings.overlay__feed_enabled = accepted
            return accepted
        self.feed.stop()
        self.settings.overlay__feed_enabled = False
        return True

    def apply_hotkey(self, binding: str) -> bool:
        if self._shutting_down:
            return False
        accepted = self.hotkey.bind(binding)
        if accepted:
            self.settings.overlay__hotkey_visibility = self.hotkey.binding
        return accepted

    def begin_hotkey_capture(self) -> None:
        if not self._shutting_down:
            self.hotkey.begin_capture()

    def commit_hotkey_capture(self, binding: str) -> bool:
        if self._shutting_down:
            return False
        accepted = self.hotkey.commit_capture(binding)
        self.settings.overlay__hotkey_visibility = self.hotkey.binding
        return accepted

    def set_hide_mode(self, mode: str) -> None:
        if self._shutting_down:
            return
        self.settings.overlay__hotkey_hide_mode = mode if mode in ('all', 'popout') else 'all'

    def set_bind(self, address: str) -> None:
        if self._shutting_down:
            return
        self.settings.overlay__feed_bind = str(address)
        self.feed.configure(
            self.settings.overlay__feed_bind, self.settings.overlay__feed_port)

    def set_port(self, port: int) -> None:
        if self._shutting_down:
            return
        self.settings.overlay__feed_port = int(port)
        self.feed.configure(
            self.settings.overlay__feed_bind, self.settings.overlay__feed_port)

    def set_custom_css(self, path: str) -> None:
        if not self._shutting_down:
            self.feed.set_custom_css(path)

    def refresh_presentation_settings(self) -> None:
        if not self._shutting_down:
            self.feed.refresh_presentation_settings()

    def set_theme(self, theme) -> None:
        if not self._shutting_down:
            self.feed.set_theme(theme)

    @Slot()
    def toggle_global_visibility(self) -> None:
        if self._shutting_down:
            return
        mode = self.settings.overlay__hotkey_hide_mode
        if mode == 'popout':
            self.live_parser.set_popout_visible(not self.live_parser.popout_visible)
            return
        currently_visible = (
            self.live_parser.popout_visible
            or (self.feed.active and self.feed.presentation_visible))
        target_visible = not currently_visible
        self.live_parser.set_popout_visible(target_visible)
        if self.feed.active:
            self.feed.set_presentation_visible(target_visible)

    def shutdown(self) -> None:
        if self._shutting_down:
            return
        self._shutting_down = True
        self.hotkey.shutdown()
        try:
            self.live_parser.snapshot_updated.disconnect(self.feed.publish_snapshot)
            self.live_parser.parser_active_changed.disconnect(self.feed.set_parser_active)
        except (RuntimeError, TypeError):
            pass
        self.feed.shutdown()
