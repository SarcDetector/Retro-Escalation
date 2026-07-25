"""Presentation-only Wayland live meter.

This module is the deliberately small half of RE-OSCR's Wayland popout.  The
main process remains the only process that reads the combat log or owns an OSCR
parser.  This child receives already-normalized display rows over a private
stdin pipe and emits UI requests over stdout.

No settings, configuration, combat-log, parser, or application module is
imported here.  In particular, this process never opens a user-controlled path.
``app_dir`` is retained only as opaque launch metadata for protocol parity.
"""

from __future__ import annotations

import json
import math
import os
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from pyqtgraph import PlotWidget, mkPen
from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QObject,
    QPoint,
    QSize,
    QSocketNotifier,
    Qt,
    QTimer,
    Signal,
    Slot,
)
from PySide6.QtGui import QColor, QCloseEvent, QMouseEvent, QResizeEvent
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizeGrip,
    QSplitter,
    QTableView,
    QVBoxLayout,
)


PROTOCOL_ID = "re-oscr.wayland-live.v1"
PROTOCOL_VERSION = 1
MAX_LINE_BYTES = 1_048_576
MAX_BUFFER_BYTES = 2_097_152
MAX_READ_BYTES = 65_536
MAX_MESSAGES_PER_TURN = 128
MAX_ROWS = 100
MAX_COLUMNS = 16
MAX_STRING_LENGTH = 512

DEFAULT_HEADER = (
    "DPS",
    "Combat Time",
    "Debuff",
    "Attacks-in",
    "HPS",
    "Kills",
    "Deaths",
)
DEFAULT_LABELS = {
    "activate": "Activate",
    "deactivate": "Deactivate",
    "copy": "Copy Result",
    "close": "Close Live Parser",
    "duration": "Duration",
}
DEFAULT_ACCENTS = (
    "#FF8A2A",
    "#71A7FF",
    "#B787F5",
    "#63D7C1",
    "#F06D85",
)
GRAPH_FIELD_TO_COLUMN = {0: 0, 1: 2, 2: 3, 3: 4}

_SURFACE_VOID = "#070B0F"
_SURFACE_BASE = "#0B1116"
_SURFACE_RAISED = "#0E161D"
_SURFACE_OVERLAY = "#121D25"
_SURFACE_DEEP = "#05080B"
_BORDER = "#30424E"
_TEXT = "#F4EFE6"
_TEXT_SECONDARY = "#AEBDC5"
_TEXT_MUTED = "#667B87"
DEFAULT_STYLE = {
    "background": _SURFACE_BASE,
    "raised": _SURFACE_RAISED,
    "overlay": _SURFACE_OVERLAY,
    "deep": _SURFACE_DEEP,
    "border": _BORDER,
    "text": _TEXT,
    "secondary": _TEXT_SECONDARY,
    "muted": _TEXT_MUTED,
}

_FORBIDDEN_KEYS = {
    "combat_log",
    "combatlog",
    "config",
    "config_dir",
    "log",
    "log_file",
    "log_path",
    "logfile",
    "oscr",
    "parser",
    "qsettings",
    "settings",
    "sto_log_path",
    "telemetry",
}


def _json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant {value!r}")


def _bounded_text(value: Any, fallback: str = "") -> str:
    if not isinstance(value, str):
        return fallback
    return value[:MAX_STRING_LENGTH]


def _finite_number(
        value: Any,
        fallback: float = 0.0,
        *,
        minimum: float | None = None,
        maximum: float | None = None,
) -> float:
    if not isinstance(value, (bool, int, float)):
        return fallback
    try:
        number = float(value)
    except (OverflowError, TypeError, ValueError):
        return fallback
    if not math.isfinite(number):
        return fallback
    if minimum is not None:
        number = max(minimum, number)
    if maximum is not None:
        number = min(maximum, number)
    return number


def _integer(
        value: Any,
        fallback: int = 0,
        *,
        minimum: int | None = None,
        maximum: int | None = None,
) -> int:
    number = _finite_number(value, float(fallback))
    result = int(number)
    if minimum is not None:
        result = max(minimum, result)
    if maximum is not None:
        result = min(maximum, result)
    return result


def _valid_colour(value: Any, fallback: str) -> str:
    if isinstance(value, str):
        colour = QColor(value)
        if colour.isValid():
            return colour.name().upper()
    return fallback


def _contains_forbidden_key(value: Any) -> bool:
    """Reject attempts to turn the child into a data/configuration consumer."""
    stack = [value]
    visited = 0
    while stack:
        current = stack.pop()
        visited += 1
        if visited > 10_000:
            # A presentation command never needs a deeply elaborate payload.
            return True
        if isinstance(current, Mapping):
            for key, child in current.items():
                normalized = str(key).strip().casefold().replace("-", "_")
                if (
                    normalized in _FORBIDDEN_KEYS
                    or normalized.startswith("log_")
                    or normalized.endswith("_log")
                    or "telemetry" in normalized
                ):
                    return True
                stack.append(child)
        elif isinstance(current, (list, tuple)):
            stack.extend(current)
    return False


def encode_event(event: str, **payload: Any) -> bytes:
    """Encode one child event as the canonical newline-delimited envelope."""
    envelope = {
        "protocol": PROTOCOL_ID,
        "type": _bounded_text(event),
        "payload": payload,
    }
    return (
        json.dumps(
            envelope,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _write_stdout(message: bytes) -> None:
    """Write one complete event without ever using stdout for diagnostics."""
    view = memoryview(message)
    while view:
        written = os.write(1, view)
        if written <= 0:
            raise BrokenPipeError("presenter event pipe is closed")
        view = view[written:]


class StdinCommandReader(QObject):
    """Bounded, non-blocking NDJSON reader integrated with the Qt event loop."""

    command_received = Signal(object)
    protocol_error = Signal(str)
    eof = Signal()

    def __init__(
        self,
        fd: int = 0,
        parent: QObject | None = None,
        *,
        start_notifier: bool = True,
    ):
        super().__init__(parent)
        self._fd = int(fd)
        self._buffer = bytearray()
        self._discarding_line = False
        self._closed = False
        self._notifier: QSocketNotifier | None = None
        if start_notifier:
            try:
                os.set_blocking(self._fd, False)
            except (AttributeError, OSError):
                pass
            self._notifier = QSocketNotifier(
                self._fd, QSocketNotifier.Type.Read, self)
            self._notifier.activated.connect(self._read_ready)

    def _read_ready(self, *_args: Any) -> None:
        if self._closed:
            return
        try:
            chunk = os.read(self._fd, MAX_READ_BYTES)
        except BlockingIOError:
            return
        except OSError:
            self._finish()
            return
        if not chunk:
            self._finish()
            return
        self.feed_bytes(chunk)

    def feed_bytes(self, chunk: bytes | bytearray | memoryview) -> None:
        """Feed bytes directly; kept public for deterministic protocol tests."""
        if self._closed or not chunk:
            return
        incoming = bytes(chunk)
        if self._discarding_line:
            newline = incoming.find(b"\n")
            if newline < 0:
                return
            self._discarding_line = False
            incoming = incoming[newline + 1:]
        if not incoming:
            return

        if len(self._buffer) + len(incoming) > MAX_BUFFER_BYTES:
            combined = bytes(self._buffer) + incoming
            newline = combined.find(b"\n", MAX_LINE_BYTES)
            self._buffer.clear()
            self.protocol_error.emit("command line exceeds protocol limit")
            if newline < 0:
                self._discarding_line = True
                return
            incoming = combined[newline + 1:]

        self._buffer.extend(incoming)
        self._drain_lines()

        if len(self._buffer) > MAX_LINE_BYTES:
            self._buffer.clear()
            self._discarding_line = True
            self.protocol_error.emit("command line exceeds protocol limit")

    @Slot()
    def _drain_lines(self) -> None:
        processed = 0
        while processed < MAX_MESSAGES_PER_TURN:
            newline = self._buffer.find(b"\n")
            if newline < 0:
                break
            line = bytes(self._buffer[:newline])
            del self._buffer[:newline + 1]
            processed += 1
            if not line.strip():
                continue
            if len(line) > MAX_LINE_BYTES:
                self.protocol_error.emit("command line exceeds protocol limit")
                continue
            try:
                decoded = line.decode("utf-8")
                command = json.loads(decoded, parse_constant=_json_constant)
            except (UnicodeDecodeError, ValueError, json.JSONDecodeError, RecursionError):
                self.protocol_error.emit("invalid protocol JSON")
                continue
            if not isinstance(command, dict):
                self.protocol_error.emit("command envelope must be an object")
                continue
            self.command_received.emit(command)
        if b"\n" in self._buffer:
            QTimer.singleShot(0, self._drain_lines)

    def finish(self) -> None:
        """Signal EOF when manually driven by a test or alternate pipe owner."""
        self._finish()

    def _finish(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._notifier is not None:
            self._notifier.setEnabled(False)
        self._buffer.clear()
        self.eof.emit()


class PresenterTableModel(QAbstractTableModel):
    """Local display model for normalized rows; it has no parser dependency."""

    def __init__(
        self,
        header: Sequence[str] = DEFAULT_HEADER,
        colours: Sequence[str] = DEFAULT_ACCENTS,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self._header = tuple(str(item) for item in header[:MAX_COLUMNS])
        self._colours = tuple(QColor(item) for item in colours)
        self._rows: list[list[Any]] = []
        self.name_index = 1
        self.legend_column = 0

    @property
    def rows(self) -> tuple[list[Any], ...]:
        return tuple(list(row) for row in self._rows)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._header)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        row = self._rows[index.row()]
        column = index.column()
        if not 0 <= column < len(self._header) or 1 + column >= len(row):
            return None
        value = row[1 + column]
        if role == Qt.ItemDataRole.DisplayRole:
            if column in (0, 4):
                return f"{_finite_number(value):,.2f}"
            if column == 1:
                return f"{_finite_number(value):.1f}s"
            if column == 2:
                number = _finite_number(value)
                return "---.--%" if number == 0 else f"{number:,.2f}%"
            if column == 3:
                return f"{_finite_number(value):,.2f}%"
            if column in (5, 6):
                return str(_integer(value))
            return str(value)
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight
        if (
            role == Qt.ItemDataRole.ForegroundRole
            and column == self.legend_column
            and self._colours
        ):
            colour_index = _integer(
                row[8] if len(row) > 8 else index.row(),
                index.row(),
                minimum=0,
            )
            return self._colours[colour_index % len(self._colours)]
        return None

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                if 0 <= section < len(self._header):
                    return self._header[section]
                return None
            if 0 <= section < len(self._rows):
                player = self._rows[section][0]
                if isinstance(player, (list, tuple)) and player:
                    index = min(self.name_index, len(player) - 1)
                    return _bounded_text(player[index], _bounded_text(player[0]))
                return _bounded_text(player)
        if role == Qt.ItemDataRole.TextAlignmentRole:
            if orientation == Qt.Orientation.Horizontal:
                return Qt.AlignmentFlag.AlignCenter
            return Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight
        return None

    def replace_rows(self, rows: Sequence[list[Any]]) -> None:
        self.beginResetModel()
        self._rows = [list(row) for row in rows]
        self._rows.sort(
            key=lambda row: _finite_number(row[1] if len(row) > 1 else 0),
            reverse=True,
        )
        self.endResetModel()

    def set_header(self, header: Sequence[str]) -> None:
        clean = tuple(
            _bounded_text(item) for item in header[:MAX_COLUMNS]
            if isinstance(item, str)
        )
        if not clean:
            clean = DEFAULT_HEADER
        self.beginResetModel()
        self._header = clean
        self.endResetModel()

    def set_colours(self, colours: Sequence[str]) -> None:
        resolved = tuple(QColor(item) for item in colours if QColor(item).isValid())
        self._colours = resolved or tuple(QColor(item) for item in DEFAULT_ACCENTS)
        if self._rows:
            self.dataChanged.emit(
                self.index(0, 0),
                self.index(len(self._rows) - 1, max(0, len(self._header) - 1)),
                [Qt.ItemDataRole.ForegroundRole],
            )

    def sort(
        self,
        column: int,
        order: Qt.SortOrder = Qt.SortOrder.AscendingOrder,
    ) -> None:
        if not 0 <= column < len(self._header):
            return
        self.layoutAboutToBeChanged.emit()
        reverse = order == Qt.SortOrder.DescendingOrder
        self._rows.sort(
            key=lambda row: _finite_number(
                row[1 + column] if 1 + column < len(row) else 0),
            reverse=reverse,
        )
        self.layoutChanged.emit()


class ManualSizeGrip(QSizeGrip):
    """Resize a layer surface directly; compositor resize is unavailable."""

    def __init__(self, target: "WaylandPresenterWindow"):
        super().__init__(target)
        self._target = target
        self._start_position = QPoint()
        self._start_size = QSize()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._start_position = event.globalPosition().toPoint()
            self._start_size = self._target.size()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self._start_position
            minimum = self._target.minimumSizeHint().expandedTo(
                self._target.minimumSize())
            width = max(minimum.width(), self._start_size.width() + delta.x())
            height = max(minimum.height(), self._start_size.height() + delta.y())
            self._target.resize(width, height)
            self._target.schedule_geometry_event()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._target.schedule_geometry_event(immediate=True)
            event.accept()
            return
        super().mouseReleaseEvent(event)


class WaylandPresenterWindow(QFrame):
    """Layer-shell live meter driven entirely by presentation commands."""

    def __init__(
        self,
        app_dir: str = "",
        *,
        event_writer: Callable[[bytes], None] | None = None,
    ):
        super().__init__(None)
        self._app_dir = _bounded_text(app_dir)
        self._theme_id = "command_console"
        self._ui_scale = 1.0
        self._event_writer = event_writer or _write_stdout
        self._labels = dict(DEFAULT_LABELS)
        self._header = list(DEFAULT_HEADER)
        self._accents = list(DEFAULT_ACCENTS)
        self._style = dict(DEFAULT_STYLE)
        self._live: dict[str, Any] = {
            "columns": [True] * len(DEFAULT_HEADER),
            "graph_active": False,
            "graph_field": 0,
            "player_display": "Handle",
            "window_scale": 1.0,
            "opacity": 1.0,
            "overlay_left": 0,
            "overlay_top": 0,
            "overlay_width": 0,
            "overlay_height": 0,
            "copy_kills": False,
        }
        self._parser_active = False
        self._duration = 0.0
        self._sequence = -1
        self._ready_sent = False
        self._layer_window: Any = None
        self._layer_configured = False
        self._relative_pointer: Any = None
        self._dragging = False
        self._drag_fraction = [0.0, 0.0]
        self._shutting_down = False
        self._graph_column = 0
        self._graph_buffers: dict[tuple[str, str], list[float]] = {}
        self._graph_keys: list[tuple[str, str]] = []

        self.setObjectName("waylandLivePresenter")
        self.setWindowTitle("RE-OSCR Live Parser")
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)
        self._build_ui()

        self._geometry_timer = QTimer(self)
        self._geometry_timer.setSingleShot(True)
        self._geometry_timer.setInterval(300)
        self._geometry_timer.timeout.connect(self._send_geometry)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._splitter = QSplitter(Qt.Orientation.Vertical, self)
        self._splitter.setChildrenCollapsible(False)

        self._plot = PlotWidget(self._splitter)
        self._plot.setBackground(None)
        self._plot.setMouseEnabled(False, False)
        self._plot.setMenuEnabled(False)
        self._plot.hideButtons()
        self._plot.setDefaultPadding(0)
        self._plot.setXRange(-14, 0, padding=0)
        self._plot.getAxis("bottom").setTicks([])
        self._curves = [
            self._plot.plot(
                list(range(-14, 1)),
                [0.0] * 15,
                pen=mkPen(colour, width=2),
            )
            for colour in self._accents
        ]
        self._splitter.addWidget(self._plot)

        self._table = QTableView(self._splitter)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.setSelectionMode(QTableView.SelectionMode.NoSelection)
        self._table.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._table.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents)
        self._table.verticalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents)
        self._model = PresenterTableModel(self._header, self._accents, self)
        self._table.setModel(self._model)
        self._table.setSortingEnabled(True)
        self._table.sortByColumn(0, Qt.SortOrder.DescendingOrder)
        self._splitter.addWidget(self._table)
        layout.addWidget(self._splitter, 1)

        footer = QGridLayout()
        footer.setContentsMargins(6, 3, 2, 2)
        footer.setHorizontalSpacing(6)

        self._activate_button = QPushButton(self._labels["activate"], self)
        self._activate_button.setCheckable(True)
        self._activate_button.clicked.connect(self._request_parser_state)
        footer.addWidget(self._activate_button, 0, 0)

        self._copy_button = QPushButton(self._labels["copy"], self)
        self._copy_button.clicked.connect(self.copy_live_data)
        footer.addWidget(self._copy_button, 0, 1)

        self._close_button = QPushButton(self._labels["close"], self)
        self._close_button.clicked.connect(self._user_close)
        footer.addWidget(self._close_button, 0, 2)

        self._duration_label = QLabel(
            f"{self._labels['duration']}: 0.0s", self)
        footer.addWidget(self._duration_label, 0, 3)
        footer.setColumnStretch(4, 1)

        self._size_grip = ManualSizeGrip(self)
        footer.addWidget(
            self._size_grip,
            0,
            5,
            alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom,
        )
        layout.addLayout(footer)

        self._apply_style()
        self._apply_live_settings()

    def send_event(self, event: str, **payload: Any) -> None:
        try:
            self._event_writer(encode_event(event, **payload))
        except (BrokenPipeError, OSError):
            app = QApplication.instance()
            if app is not None:
                app.quit()

    def send_ready(self) -> None:
        if not self._ready_sent:
            self._ready_sent = True
            self.send_event("ready")

    def send_error(self, message: str) -> None:
        safe = _bounded_text(message, "presenter protocol error")
        self.send_event("error", message=safe, reason=safe)

    @Slot(object)
    def process_command(self, envelope: object) -> None:
        """Validate and apply one canonical parent command."""
        if not isinstance(envelope, dict):
            self.send_error("command envelope must be an object")
            return
        if envelope.get("protocol") != PROTOCOL_ID:
            self.send_error("unsupported presenter protocol")
            return
        command_type = envelope.get("type")
        payload = envelope.get("payload", {})
        if not isinstance(command_type, str) or not isinstance(payload, dict):
            self.send_error("invalid command envelope")
            return
        if _contains_forbidden_key(payload):
            self.send_error("data and settings inputs are forbidden in presenter process")
            return

        handlers: dict[str, Callable[[dict[str, Any]], None]] = {
            "configure": self._configure,
            "snapshot": self._snapshot,
            "show": self._show_command,
            "hide": self._hide_command,
            "parser-state": self._parser_state,
            "shutdown": self._shutdown_command,
        }
        handler = handlers.get(command_type)
        if handler is None:
            self.send_error("unknown presenter command")
            return
        try:
            handler(payload)
        except Exception:
            # Protocol output intentionally does not include exception details or
            # parent-supplied values.
            self.send_error("presenter command failed")

    def _configure(self, payload: dict[str, Any]) -> None:
        app_dir = payload.get("app_dir")
        if isinstance(app_dir, str):
            self._app_dir = _bounded_text(app_dir)
        theme_id = payload.get("theme_id")
        if isinstance(theme_id, str):
            self._theme_id = _bounded_text(theme_id, "command_console")
        self._ui_scale = _finite_number(
            payload.get("ui_scale", self._ui_scale),
            self._ui_scale,
            minimum=0.5,
            maximum=3.0,
        )

        labels = payload.get("labels")
        if isinstance(labels, dict):
            for key in DEFAULT_LABELS:
                if isinstance(labels.get(key), str):
                    self._labels[key] = _bounded_text(
                        labels[key], DEFAULT_LABELS[key])

        header = payload.get("header")
        if isinstance(header, (list, tuple)):
            clean_header = [
                _bounded_text(item) for item in header[:MAX_COLUMNS]
                if isinstance(item, str)
            ]
            if clean_header:
                self._header = clean_header
                self._model.set_header(clean_header)

        palette = payload.get("palette")
        if isinstance(palette, (list, tuple)):
            clean_palette = []
            for index, item in enumerate(palette[:10]):
                fallback = DEFAULT_ACCENTS[index % len(DEFAULT_ACCENTS)]
                colour = _valid_colour(item, fallback)
                if QColor(colour).isValid():
                    clean_palette.append(colour)
            if clean_palette:
                self._accents = clean_palette
                self._model.set_colours(clean_palette)
                for index, curve in enumerate(self._curves):
                    curve.setPen(mkPen(
                        clean_palette[index % len(clean_palette)], width=2))

        style = payload.get("style")
        if isinstance(style, dict):
            for key, fallback in DEFAULT_STYLE.items():
                if key in style:
                    self._style[key] = _valid_colour(
                        style[key], self._style.get(key, fallback))

        live = payload.get("live")
        if isinstance(live, dict):
            columns = live.get("columns")
            if isinstance(columns, (list, tuple)):
                self._live["columns"] = [
                    bool(item) for item in columns[:MAX_COLUMNS]]
            self._live["graph_active"] = bool(
                live.get("graph_active", self._live["graph_active"]))
            self._live["graph_field"] = _integer(
                live.get("graph_field", self._live["graph_field"]),
                self._live["graph_field"],
                minimum=0,
                maximum=3,
            )
            display = live.get("player_display")
            if isinstance(display, str) and display.casefold() in ("name", "handle"):
                self._live["player_display"] = display.title()
            self._live["window_scale"] = _finite_number(
                live.get("window_scale", self._live["window_scale"]),
                self._live["window_scale"],
                minimum=0.5,
                maximum=3.0,
            )
            self._live["opacity"] = _finite_number(
                live.get("opacity", self._live["opacity"]),
                self._live["opacity"],
                minimum=0.05,
                maximum=1.0,
            )
            for key in ("overlay_left", "overlay_top"):
                self._live[key] = _integer(
                    live.get(key, self._live[key]),
                    self._live[key],
                    minimum=0,
                    maximum=100_000,
                )
            for key in ("overlay_width", "overlay_height"):
                self._live[key] = _integer(
                    live.get(key, self._live[key]),
                    self._live[key],
                    minimum=0,
                    maximum=16_384,
                )
            self._live["copy_kills"] = bool(
                live.get("copy_kills", self._live["copy_kills"]))

        graph_column = GRAPH_FIELD_TO_COLUMN.get(
            int(self._live["graph_field"]), 0)
        if graph_column != self._graph_column:
            self._graph_column = graph_column
            self._graph_buffers.clear()
            self._graph_keys.clear()
            self._clear_curves()

        self._activate_button.setText(
            self._labels["deactivate"]
            if self._parser_active else self._labels["activate"])
        self._copy_button.setText(self._labels["copy"])
        self._copy_button.setToolTip(self._labels["copy"])
        self._close_button.setText(self._labels["close"])
        self._close_button.setToolTip(self._labels["close"])
        self._update_duration_label()
        self._apply_style()
        self._apply_live_settings()

        if self._layer_window is not None:
            self._set_overlay_margins()

    def _snapshot(self, payload: dict[str, Any]) -> None:
        sequence = _integer(
            payload.get("sequence", self._sequence + 1),
            self._sequence + 1,
            minimum=0,
        )
        if sequence <= self._sequence:
            return
        self._sequence = sequence
        rows_value = payload.get("rows", [])
        rows = self._normalize_rows(rows_value)
        self._duration = _finite_number(
            payload.get("duration", 0.0), 0.0, minimum=0.0)
        self._update_graph(rows)
        self._model.replace_rows(rows)
        self._table.resizeColumnsToContents()
        self._table.resizeRowsToContents()
        self._apply_columns()
        self._update_duration_label()

    def _show_command(self, _payload: dict[str, Any]) -> None:
        if not self._ensure_layer_shell():
            return
        width = int(self._live["overlay_width"])
        height = int(self._live["overlay_height"])
        if width > 0 and height > 0:
            self.resize(width, height)
        self.show()
        self.raise_()
        self.schedule_geometry_event()
        # Readiness means the native layer surface was configured and shown,
        # not merely that the child Python process reached its event loop.
        self.send_ready()

    def _hide_command(self, _payload: dict[str, Any]) -> None:
        self._dragging = False
        self._drag_fraction = [0.0, 0.0]
        self.hide()

    def _parser_state(self, payload: dict[str, Any]) -> None:
        self._set_parser_active(bool(payload.get("active", False)))

    def _shutdown_command(self, _payload: dict[str, Any]) -> None:
        self._shutting_down = True
        self._dragging = False
        self._drag_fraction = [0.0, 0.0]
        self.hide()
        app = QApplication.instance()
        if app is not None:
            app.quit()

    def _normalize_rows(self, value: Any) -> list[list[Any]]:
        if not isinstance(value, (list, tuple)):
            return []
        clean: list[list[Any]] = []
        for row_index, source in enumerate(value[:MAX_ROWS]):
            if not isinstance(source, (list, tuple)) or len(source) < 8:
                continue
            player = source[0]
            if isinstance(player, (list, tuple)):
                name = _bounded_text(player[0]) if player else ""
                handle = _bounded_text(player[1]) if len(player) > 1 else name
            else:
                name = _bounded_text(player)
                handle = name
            metrics = [
                _finite_number(source[index], 0.0)
                for index in range(1, 8)
            ]
            colour_index = _integer(
                source[8] if len(source) > 8 else row_index,
                row_index,
                minimum=0,
            )
            clean.append([[name, handle], *metrics, colour_index])
        return clean

    def _update_graph(self, rows: Sequence[list[Any]]) -> None:
        if not self._live["graph_active"]:
            return
        active_keys: list[tuple[str, str]] = []
        value_index = 1 + self._graph_column
        for row in rows[:len(self._curves)]:
            player = row[0]
            key = (
                _bounded_text(player[0]) if player else "",
                _bounded_text(player[1]) if len(player) > 1 else "",
            )
            active_keys.append(key)
            buffer = self._graph_buffers.setdefault(key, [0.0] * 15)
            buffer.pop(0)
            buffer.append(_finite_number(
                row[value_index] if value_index < len(row) else 0.0))
        self._graph_keys = active_keys
        time_values = list(range(-14, 1))
        for index, curve in enumerate(self._curves):
            data = (
                self._graph_buffers[active_keys[index]]
                if index < len(active_keys) else [0.0] * 15
            )
            curve.setData(time_values, data)

    def _clear_curves(self) -> None:
        time_values = list(range(-14, 1))
        for curve in self._curves:
            curve.setData(time_values, [0.0] * 15)

    def _apply_live_settings(self) -> None:
        self._plot.setVisible(bool(self._live["graph_active"]))
        self._model.name_index = (
            0 if self._live["player_display"] == "Name" else 1)
        self._model.legend_column = self._graph_column
        self.setWindowOpacity(float(self._live["opacity"]))
        # The inherited popout deliberately replaces the application scale
        # with its independent Live Parser scale while building this surface.
        scale = float(self._live["window_scale"])
        self.setMinimumSize(round(240 * scale), round(90 * scale))
        font = self.font()
        font.setPointSizeF(max(7.0, 9.0 * scale))
        self.setFont(font)
        self._apply_columns()

    def _apply_columns(self) -> None:
        columns = self._live["columns"]
        for index in range(self._model.columnCount()):
            visible = bool(columns[index]) if index < len(columns) else True
            self._table.setColumnHidden(index, not visible)

    def _apply_style(self) -> None:
        accent = self._accents[0] if self._accents else DEFAULT_ACCENTS[0]
        background = self._style["background"]
        raised = self._style["raised"]
        overlay = self._style["overlay"]
        deep = self._style["deep"]
        border = self._style["border"]
        text = self._style["text"]
        secondary = self._style["secondary"]
        self.setStyleSheet(
            f"""
            QFrame#waylandLivePresenter {{
                background:{background};
                color:{text};
                border:1px solid {border};
            }}
            QSplitter::handle {{
                background:{border};
                height:1px;
            }}
            QTableView {{
                background:{background};
                alternate-background-color:{raised};
                color:{text};
                border:0;
                gridline-color:{border};
            }}
            QHeaderView::section {{
                background:{deep};
                color:{secondary};
                border:0;
                border-right:1px solid {border};
                border-bottom:1px solid {border};
                padding:3px 5px;
            }}
            QLabel {{
                color:{secondary};
                background:transparent;
            }}
            QPushButton {{
                color:{text};
                background:{overlay};
                border:1px solid {border};
                border-radius:3px;
                padding:3px 7px;
            }}
            QPushButton:hover {{
                border-color:{accent};
            }}
            QPushButton:checked {{
                color:{background};
                background:{accent};
                border-color:{accent};
            }}
            """
        )

    def _update_duration_label(self) -> None:
        self._duration_label.setText(
            f"{self._labels['duration']}: {self._duration:.1f}s")

    def _set_parser_active(self, active: bool) -> None:
        self._parser_active = bool(active)
        blocked = self._activate_button.blockSignals(True)
        self._activate_button.setChecked(self._parser_active)
        self._activate_button.setText(
            self._labels["deactivate"]
            if self._parser_active else self._labels["activate"])
        self._activate_button.blockSignals(blocked)

    @Slot(bool)
    def _request_parser_state(self, checked: bool) -> None:
        self._set_parser_active(bool(checked))
        self.send_event("parser", active=self._parser_active)

    @Slot()
    def copy_live_data(self) -> None:
        output: list[str] = []
        name_index = 0 if self._live["player_display"] == "Name" else 1
        for row in self._model.rows:
            player = row[0]
            name = (
                _bounded_text(player[min(name_index, len(player) - 1)])
                if player else ""
            )
            dps = _finite_number(row[1] if len(row) > 1 else 0.0)
            if self._live["copy_kills"]:
                kills = _integer(row[6] if len(row) > 6 else 0)
                output.append(f"{name}: {dps:,.2f} ({kills})")
            else:
                output.append(f"{name}: {dps:,.2f}")
        prefix = "{ OSCR } DPS (Kills): " if self._live["copy_kills"] else "{ OSCR } DPS: "
        QApplication.clipboard().setText(prefix + " | ".join(output))

    @Slot()
    def _user_close(self) -> None:
        self.hide()
        self.send_event("close")

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._shutting_down:
            event.accept()
            return
        self._user_close()
        event.ignore()

    def _ensure_layer_shell(self) -> bool:
        if self._layer_configured:
            return True
        try:
            from . import waylandoverlay

            self.create()
            anchors = (
                waylandoverlay.ANCHOR_TOP | waylandoverlay.ANCHOR_LEFT)
            self._layer_window = waylandoverlay.configure_as_overlay(
                self.windowHandle(),
                anchors=anchors,
                margins=(
                    int(self._live["overlay_left"]),
                    int(self._live["overlay_top"]),
                    0,
                    0,
                ),
            )
            self._relative_pointer = waylandoverlay.create_relative_pointer(
                self._relative_motion)
        except Exception:
            self.send_error("Wayland layer-shell presentation is unavailable")
            return False
        self._layer_configured = True
        return True

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self._relative_pointer is not None
        ):
            self._dragging = True
            self._drag_fraction = [0.0, 0.0]
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._dragging:
            self._dragging = False
            self.schedule_geometry_event(immediate=True)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _relative_motion(self, dx: float, dy: float) -> None:
        if not self._dragging or self._layer_window is None:
            return
        self._drag_fraction[0] += _finite_number(dx)
        self._drag_fraction[1] += _finite_number(dy)
        step_x = int(self._drag_fraction[0])
        step_y = int(self._drag_fraction[1])
        if step_x == 0 and step_y == 0:
            return
        self._drag_fraction[0] -= step_x
        self._drag_fraction[1] -= step_y

        screen = self.windowHandle().screen()
        geometry = screen.availableGeometry() if screen is not None else None
        max_left = (
            max(0, geometry.width() - self.width()) if geometry is not None
            else 100_000
        )
        max_top = (
            max(0, geometry.height() - self.height()) if geometry is not None
            else 100_000
        )
        self._live["overlay_left"] = min(
            max(0, int(self._live["overlay_left"]) + step_x), max_left)
        self._live["overlay_top"] = min(
            max(0, int(self._live["overlay_top"]) + step_y), max_top)
        self._set_overlay_margins()
        self.schedule_geometry_event()

    def _set_overlay_margins(self) -> None:
        if self._layer_window is None:
            return
        from . import waylandoverlay

        waylandoverlay.set_margins(
            self._layer_window,
            int(self._live["overlay_left"]),
            int(self._live["overlay_top"]),
            0,
            0,
        )
        handle = self.windowHandle()
        if handle is not None:
            handle.requestUpdate()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if hasattr(self, "_geometry_timer"):
            self.schedule_geometry_event()

    def schedule_geometry_event(self, *, immediate: bool = False) -> None:
        if not hasattr(self, "_geometry_timer"):
            return
        self._geometry_timer.start(0 if immediate else 300)

    @Slot()
    def _send_geometry(self) -> None:
        self._live["overlay_width"] = self.width()
        self._live["overlay_height"] = self.height()
        self.send_event(
            "geometry",
            left=int(self._live["overlay_left"]),
            top=int(self._live["overlay_top"]),
            width=self.width(),
            height=self.height(),
        )


def run_presenter(app_dir: str = "") -> int:
    """Run the dedicated Wayland presentation process and return its Qt code."""
    # Shell integration selection is process-global and must precede QApplication.
    from . import waylandoverlay

    waylandoverlay.prepare_environment()
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("RE-OSCR Wayland Live Presenter")
    app.setQuitOnLastWindowClosed(False)

    window = WaylandPresenterWindow(app_dir)
    reader = StdinCommandReader(parent=window)
    reader.command_received.connect(window.process_command)
    reader.protocol_error.connect(window.send_error)
    reader.eof.connect(app.quit)
    return app.exec()


__all__ = [
    "MAX_BUFFER_BYTES",
    "MAX_LINE_BYTES",
    "MAX_ROWS",
    "PROTOCOL_ID",
    "PROTOCOL_VERSION",
    "PresenterTableModel",
    "StdinCommandReader",
    "WaylandPresenterWindow",
    "encode_event",
    "run_presenter",
]
