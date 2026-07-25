import logging
from pathlib import Path

from pyqtgraph import mkPen, PlotDataItem, PlotWidget
from PySide6.QtCore import QPoint, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QCloseEvent, QMouseEvent
from PySide6.QtWidgets import (
    QApplication, QGridLayout, QFrame, QHBoxLayout, QLabel, QSplitter, QTableView, QVBoxLayout)

from OSCR import LIVE_TABLE_HEADER, LiveParser

from .datamodels import LiveParserTableModel
from .dialogs import DialogsWrapper
from .config import OSCRSettings
from .theme import AppTheme
from .translation import tr
from .widgetbuilder import (
    create_frame, create_icon_button, create_label,
    ABOTTOM, ALEFT, ARIGHT, AVCENTER, SMAXMAX, SMINMIN, SMIXMAX, RFIXED)
from .widgetmanager import WidgetManager
from .widgets import CustomPlotAxis, FlipButton, SizeGrip


LIVE_GRAPH_FIELD_TO_COLUMN = {0: 0, 1: 2, 2: 3, 3: 4}
logger = logging.getLogger(__name__)


class LiveParserWindow(QFrame):
    """Manages LiveParser and its window"""
    update_table = Signal(object)
    update_graph = Signal(object)
    snapshot_updated = Signal(object, float)
    duration_updated = Signal(float)
    parser_active_changed = Signal(bool)
    popout_visible_changed = Signal(bool)

    def __init__(
            self, global_settings: OSCRSettings, theme: AppTheme, dialogs: DialogsWrapper,
            widgets: WidgetManager, command_console: bool = False,
            app_dir: str | Path | None = None):
        """
        Parameters:
        - :param global_settings: OSCRSettings
        - :param theme: reference to app theme
        - :param dialogs: reference to dialogs
        - :param widgets: reference to widget store
        """
        super().__init__()
        self._settings: OSCRSettings = global_settings
        self._theme: AppTheme = theme
        self._dialogs: DialogsWrapper = dialogs
        self._widgets: WidgetManager = widgets
        self._command_console = bool(command_console)
        self._app_dir = str(app_dir or Path(__file__).resolve().parents[1])
        self._liveparser: LiveParser = LiveParser(
            update_callback=self.update_live_display, settings=self.live_parser_settings)
        self._move_start_pos: QPoint
        self._window_scale: float
        self._splitter: QSplitter
        self._graph_curves: list[PlotDataItem]
        self._table: QTableView
        self._table_model: LiveParserTableModel
        self._activate_button: FlipButton
        self._duration_label: QLabel
        self._graph_active: bool = False
        self._graph_data_buffer: list[list[int | float]] = list()
        self._graph_column: int = 0
        self._parser_active: bool = False
        self._popout_visible: bool = False
        self._activate_button_transition: bool = False
        self._shutting_down: bool = False
        self._last_snapshot: list[list] = list()
        self._last_combat_time: float = 0.0
        self._wayland_presenter = None
        self._using_wayland_presentation: bool = False
        self.build_window()
        self.update_table.connect(self.update_live_table)
        self.update_graph.connect(self.update_live_graph)
        self.duration_updated.connect(self._update_duration_label)
        self.parser_active_changed.connect(self._sync_activate_button)
        if self._command_console:
            self.popout_visible_changed.connect(self._widgets.set_live_parser_active)
        self._initialize_wayland_presenter()

    @property
    def parser_active(self) -> bool:
        """Whether RE-OSCR has asked the inherited live parser to run."""
        return self._parser_active

    @property
    def popout_visible(self) -> bool:
        """Whether the local always-on-top meter is visible."""
        return self._popout_visible

    @property
    def last_snapshot(self) -> tuple[list[list], float]:
        """Return a presentation-only copy of the latest normalized live rows."""
        return [list(row) for row in self._last_snapshot], self._last_combat_time

    @property
    def live_parser_settings(self) -> dict:
        """
        Returns settings relevant to the LiveParser
        """
        return {'seconds_between_combats': self._settings.seconds_between_combats}

    def build_window(self):
        """
        Creates layout for window
        """
        self._window_scale = self._settings.liveparser__window_scale
        ui_scale_temp = self._theme.scale
        self._theme.scale = self._window_scale

        self.setStyleSheet(self._theme.get_style('live_parser'))
        self.setWindowTitle("Live Parser")
        self.setWindowIcon(self._theme.icons['oscr'])
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
            | Qt.WindowType.FramelessWindowHint)
        if QApplication.platformName().casefold().startswith('wayland'):
            self.mousePressEvent = self.live_parser_move_wayland
        else:
            self.mousePressEvent = self.live_parser_press_event
            self.mouseMoveEvent = self.live_parser_move_event
        self.setSizePolicy(SMAXMAX)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._splitter = QSplitter(Qt.Orientation.Vertical)
        self._splitter.setStyleSheet(self._theme.get_style_class(
            'QSplitter', 'splitter', {'border': 'none', 'margin': 0}))
        self._splitter.setChildrenCollapsible(False)
        graph_frame, self._graph_curves = self.create_live_graph()
        graph_frame.setMinimumHeight(self._window_scale * 50)
        self._splitter.addWidget(graph_frame)
        layout.addWidget(self._splitter, stretch=1)
        if not self._settings.liveparser__graph_active:
            self._splitter.widget(0).hide()

        table = QTableView()
        self._table = table
        table.setAlternatingRowColors(self._theme.opt.table_alternate)
        table.setShowGrid(self._theme.opt.table_gridline)
        table.setStyleSheet(self._theme.get_style_class('QTableView', 'live_table'))
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.horizontalHeader().setStyleSheet(
                self._theme.get_style_class('QHeaderView', 'live_table_header'))
        table.verticalHeader().setStyleSheet(
            self._theme.get_style_class('QHeaderView', 'live_table_index'))
        table.verticalHeader().setMinimumHeight(1)
        table.verticalHeader().setDefaultSectionSize(
            table.verticalHeader().fontMetrics().height() + 2)
        table.horizontalHeader().setMinimumWidth(1)
        table.horizontalHeader().setDefaultSectionSize(1)
        table.horizontalHeader().setSectionResizeMode(RFIXED)
        table.verticalHeader().setSectionResizeMode(RFIXED)
        table.setSizePolicy(SMINMIN)
        table.setSelectionMode(QTableView.SelectionMode.NoSelection)
        table.setMinimumWidth(self._window_scale * 150)
        table.setMinimumHeight(self._window_scale * 50)
        table.setSortingEnabled(True)
        graph_colors = (*self._theme['plot']['color_cycler'][:5], '#eeeeee')
        self._table_model = LiveParserTableModel(tr(LIVE_TABLE_HEADER), graph_colors)
        self._table_model.init_fonts(
            self._theme.get_font('live_table_header'), self._theme.get_font('live_table'))
        table.setModel(self._table_model)
        table.resizeRowsToContents()
        self._splitter.addWidget(table)
        if self._settings.liveparser__graph_active and self._settings.state__live_splitter:
            self._splitter.restoreState(self._settings.state__live_splitter)

        margin = self._theme.scale * 6
        bottom_layout = QGridLayout()
        bottom_layout.setContentsMargins(self._theme.scale * 4, 0, 0, 0)
        bottom_layout.setSpacing(margin)
        bottom_layout.setColumnStretch(4, 1)

        self._activate_button = FlipButton(tr('Activate'), tr('Deactivate'), checkable=True)
        self._activate_button.setStyleSheet(self._theme.get_style_class(
                'QPushButton', 'toggle_button', {'margin': (0, 0, 3, 0)}))
        self._activate_button.setFont(self._theme.get_font('app', '@subhead'))
        self._activate_button.r_function = self._start_from_activate_button
        self._activate_button.l_function = self._stop_from_activate_button
        bottom_layout.addWidget(self._activate_button, 0, 0, alignment=ALEFT | AVCENTER)
        icon_size = [self._theme.opt.default_icon_size * self._window_scale * 0.8] * 2
        copy_button = create_icon_button(
                self._theme, 'copy', tr('Copy Result'),
                style_override={'margin': (0, 0, 3, 0)}, icon_size=icon_size)
        copy_button.clicked.connect(self.copy_live_data_callback)
        bottom_layout.addWidget(copy_button, 0, 1, alignment=ALEFT | AVCENTER)
        close_button = create_icon_button(
                self._theme, 'close', tr('Close Live Parser'),
                style_override={'margin': (0, 0, 3, 0)}, icon_size=icon_size)
        close_button.clicked.connect(self._close_popout)
        bottom_layout.addWidget(close_button, 0, 2, alignment=ALEFT | AVCENTER)
        time_label = create_label(self._theme, 'Duration: 0s')
        bottom_layout.addWidget(time_label, 0, 3, alignment=ALEFT | AVCENTER)
        self._duration_label = time_label

        grip = SizeGrip(self)
        grip.setStyleSheet(self._theme.get_style('resize_handle'))
        bottom_layout.addWidget(grip, 0, 4, alignment=ARIGHT | ABOTTOM)

        layout.addLayout(bottom_layout)
        self.setLayout(layout)
        self.apply_runtime_settings()
        self._sync_activate_button(self._parser_active)
        self._theme.scale = ui_scale_temp

    def create_live_graph(self) -> tuple[QFrame, list[PlotDataItem]]:
        """
        Creates and styles live graph.

        :return: Frame containing the graph and list of curves that will be used to plot the data
        """
        plot_widget = PlotWidget()
        left_axis = CustomPlotAxis(
            'left', self._theme.get_font('live_plot_widget'), self._theme['defaults']['fg'],
            compressed=True)
        bottom_axis = CustomPlotAxis(
            'bottom', self._theme.get_font('plot_widget'), self._theme['defaults']['fg'], unit='s',
            no_labels=True)
        plot_widget.setAxisItems({'left': left_axis, 'bottom': bottom_axis})
        plot_widget.setStyleSheet(self._theme.get_style('plot_widget_nullifier'))
        plot_widget.setBackground(None)
        plot_widget.setMouseEnabled(False, False)
        plot_widget.setMenuEnabled(False)
        plot_widget.hideButtons()
        plot_widget.setDefaultPadding(padding=0)
        plot_widget.setXRange(-14, 0, padding=0)

        curves = list()
        for color_index in range(5):
            color = self._theme['plot']['color_cycler'][color_index]
            curves.append(plot_widget.plot([0], [0], pen=mkPen(color, width=1)))

        frame = create_frame(self._theme, 'plot_widget', size_policy=SMIXMAX, style_override={
                'margin': 4, 'padding': 2, 'border': 'none'})
        frame.setMinimumWidth(self._window_scale * 200)
        frame.setMinimumHeight(self._window_scale * 200)
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(plot_widget, stretch=1)
        frame.setLayout(layout)
        return frame, curves

    def update_shown_columns(self, publish: bool = True):
        """Shows/Hides appropriate table columns"""
        for index, state in enumerate(self._settings.liveparser__columns):
            if state:
                self._table.showColumn(index)
            else:
                self._table.hideColumn(index)
            # self._table.setColumnHidden(index, not state)
        self._table.resizeColumnsToContents()
        if publish:
            self._publish_wayland_configuration()

    def update_live_display(self, player_data: dict[tuple, dict], combat_time: float):
        """
        Updates display of live parser to show the new data.

        Parameters:
        - :param player_data: dictionary containing the new data
        - :param combat_time: duration of the entire combat
        """
        cells = list()
        curves = list()
        for player, values in player_data.items():
            cells.append([player, *values.values(), 5])
        if self._graph_active:
            if len(self._graph_data_buffer) == 0:
                self._graph_data_buffer.extend(([0] * 15, [0] * 15, [0] * 15, [0] * 15, [0] * 15))
            zipper = zip(self._graph_data_buffer, cells, self._graph_curves)
            for id, (buffer_item, player_data, curve) in enumerate(zipper):
                buffer_item.pop(0)
                buffer_item.append(player_data[1 + self._graph_column])
                player_data[8] = id
                curves.append((curve, buffer_item))
            if len(curves) > 0:
                self.update_graph.emit(curves)

        self._last_snapshot = [list(row) for row in cells]
        self._last_combat_time = float(combat_time)
        self.update_table.emit([list(row) for row in cells])
        self.duration_updated.emit(float(combat_time))
        self.snapshot_updated.emit([list(row) for row in cells], float(combat_time))

    def toggle_window(self, activate: bool):
        """
        Preserve the inherited Legacy one-button popout behavior.

        Parameters:
        - :param activate: True when parser should be shown; False when open parser should be
        closed.
        """
        if self._command_console:
            self.set_popout_visible(activate)
            return
        if activate:
            if not self._set_log_path(show_warning=True):
                self._widgets.live_parser_button.setChecked(False)
                return
            self.set_popout_visible(True)
        else:
            self.set_popout_visible(False, stop_parser=True)
            self._widgets.live_parser_button.setChecked(False)

    def start_parser(self) -> bool:
        """Start the inherited live parser without changing page or popout visibility."""
        if self._parser_active:
            return True
        if not self._set_log_path(show_warning=True):
            self.parser_active_changed.emit(False)
            QTimer.singleShot(0, lambda: self._sync_activate_button(False))
            return False
        self._liveparser.settings.update(self.live_parser_settings)
        self._liveparser.start()
        self._parser_active = True
        self.parser_active_changed.emit(True)
        return True

    def stop_parser(self) -> None:
        """Stop the inherited live parser without hiding either presentation."""
        if self._parser_active:
            self._liveparser.stop()
        self._parser_active = False
        self.parser_active_changed.emit(False)

    def set_popout_visible(self, visible: bool, stop_parser: bool = False) -> None:
        """Show or hide the local meter independently from the live parser session."""
        visible = bool(visible)
        if visible:
            self._prepare_popout()
            using_wayland = False
            if self._wayland_presenter is not None:
                try:
                    rows, duration = self.last_snapshot
                    using_wayland = bool(self._wayland_presenter.show_presentation(
                        self._wayland_configuration(), rows, duration, self._parser_active))
                except Exception as error:
                    self._handle_wayland_unavailable(str(error))
            self._using_wayland_presentation = using_wayland
            if using_wayland:
                if bool(getattr(
                        self._wayland_presenter, 'ready_received', False)):
                    self.hide()
                else:
                    # Keep the ordinary popout visible until the child confirms
                    # that LayerShellQt configured and showed a real surface.
                    self.show()
            else:
                self.show()
            self._popout_visible = True
            self.popout_visible_changed.emit(True)
            if self._settings.liveparser__auto_enabled and not self._parser_active:
                self.start_parser()
            return

        if self._using_wayland_presentation and self._wayland_presenter is not None:
            self._wayland_presenter.hide_presentation()
            if self.isVisible():
                self.store_window_state()
        elif self.isVisible() or self._popout_visible:
            self.store_window_state()
        self.hide()
        self._using_wayland_presentation = False
        self._popout_visible = False
        self.popout_visible_changed.emit(False)
        if stop_parser:
            self.stop_parser()

    def apply_runtime_settings(self) -> None:
        """Apply the existing liveparser settings to the popout without creating parser state."""
        self._liveparser.settings.update(self.live_parser_settings)
        graph_column = LIVE_GRAPH_FIELD_TO_COLUMN.get(
            self._settings.liveparser__graph_field, 0)
        if graph_column != self._graph_column:
            self._graph_data_buffer = list()
        self._graph_column = graph_column
        self._table_model.legend_column = graph_column
        self._graph_active = bool(self._settings.liveparser__graph_active)
        self._splitter.widget(0).setVisible(self._graph_active)
        if self._graph_active and self._settings.state__live_splitter:
            self._splitter.restoreState(self._settings.state__live_splitter)
        self._table_model.name_index = (
            1 if self._settings.liveparser__player_display == 'Handle' else 0)
        self.setWindowOpacity(self._settings.liveparser__window_opacity)
        self.update_shown_columns(publish=False)
        self._publish_wayland_configuration()

    def shutdown(self) -> None:
        """Persist the popout and stop background parser work during application exit."""
        if self._shutting_down:
            return
        self._shutting_down = True
        if self.isVisible() and not self._using_wayland_presentation:
            self.store_window_state()
        presenter = self._wayland_presenter
        self._wayland_presenter = None
        self._using_wayland_presentation = False
        if presenter is not None:
            presenter.shutdown()
        self.hide()
        self._popout_visible = False
        self.popout_visible_changed.emit(False)
        if self._parser_active:
            self._liveparser.stop()
        self._parser_active = False
        self.parser_active_changed.emit(False)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Keep direct window closes aligned with the public popout state contract."""
        if self._shutting_down:
            event.accept()
            return
        self.set_popout_visible(False, stop_parser=not self._command_console)
        if not self._command_console:
            self._widgets.live_parser_button.setChecked(False)
        event.ignore()

    def _initialize_wayland_presenter(self) -> None:
        """Create the isolated renderer only on a supported native Wayland session."""
        if not QApplication.platformName().casefold().startswith('wayland'):
            return
        try:
            from .waylandoverlay import WaylandPresentationProcess

            presenter = WaylandPresentationProcess.create_if_supported(
                self._app_dir, parent=self)
        except Exception as error:
            logger.warning("Wayland live presentation is unavailable: %s", error)
            return
        if presenter is None:
            return
        self._wayland_presenter = presenter
        presenter.ready.connect(self._handle_wayland_ready)
        presenter.close_requested.connect(self._handle_wayland_close_requested)
        presenter.parser_requested.connect(self._handle_wayland_parser_requested)
        presenter.geometry_changed.connect(self._handle_wayland_geometry_changed)
        presenter.unavailable.connect(self._handle_wayland_unavailable)
        self.snapshot_updated.connect(presenter.send_snapshot)
        self.parser_active_changed.connect(presenter.send_parser_state)

    def _wayland_configuration(self) -> dict:
        """Return display-only settings; never include a log or settings path."""
        return {
            'theme_id': self._settings.theme_id,
            'ui_scale': float(self._settings.ui_scale),
            'palette': list(self._theme['plot']['color_cycler'][:5]),
            'style': {
                'background': self._theme['defaults']['bg'],
                'raised': self._theme['defaults']['mbg'],
                'overlay': self._theme['defaults']['lbg'],
                'deep': self._theme['app']['bg'],
                'border': self._theme['defaults']['bc'],
                'text': self._theme['defaults']['fg'],
                'secondary': self._theme['defaults']['mfg'],
                'muted': self._theme['defaults']['mfg'],
            },
            'live': {
                'columns': [bool(value) for value in self._settings.liveparser__columns],
                'graph_active': bool(self._settings.liveparser__graph_active),
                'graph_field': int(self._settings.liveparser__graph_field),
                'player_display': str(self._settings.liveparser__player_display),
                'window_scale': float(self._settings.liveparser__window_scale),
                'opacity': float(self._settings.liveparser__window_opacity),
                'overlay_left': int(self._settings.liveparser__overlay_left),
                'overlay_top': int(self._settings.liveparser__overlay_top),
                'overlay_width': int(self._settings.liveparser__overlay_width),
                'overlay_height': int(self._settings.liveparser__overlay_height),
                'copy_kills': bool(self._settings.liveparser__copy_kills),
            },
            'labels': {
                'activate': tr('Activate'),
                'deactivate': tr('Deactivate'),
                'copy': tr('Copy Result'),
                'close': tr('Close Live Parser'),
                'duration': tr('Duration'),
            },
            'header': list(tr(LIVE_TABLE_HEADER)),
        }

    def _publish_wayland_configuration(self) -> None:
        presenter = getattr(self, '_wayland_presenter', None)
        if presenter is not None:
            presenter.send_configuration(self._wayland_configuration())

    @Slot()
    def _handle_wayland_ready(self) -> None:
        if self._popout_visible and self._using_wayland_presentation:
            self.hide()

    @Slot()
    def _handle_wayland_close_requested(self) -> None:
        if not self._using_wayland_presentation:
            return
        self.set_popout_visible(False, stop_parser=not self._command_console)
        if not self._command_console:
            self._widgets.live_parser_button.setChecked(False)

    @Slot(bool)
    def _handle_wayland_parser_requested(self, active: bool) -> None:
        if active:
            self.start_parser()
        else:
            self.stop_parser()

    @Slot(object)
    def _handle_wayland_geometry_changed(self, geometry: object) -> None:
        if not isinstance(geometry, dict):
            return
        bounds = {
            'left': ('liveparser__overlay_left', 0, 100_000),
            'top': ('liveparser__overlay_top', 0, 100_000),
            'width': ('liveparser__overlay_width', 0, 16_384),
            'height': ('liveparser__overlay_height', 0, 16_384),
        }
        for key, (setting, minimum, maximum) in bounds.items():
            try:
                value = int(geometry[key])
            except (KeyError, TypeError, ValueError, OverflowError):
                return
            setattr(self._settings, setting, max(minimum, min(maximum, value)))

    @Slot(str)
    def _handle_wayland_unavailable(self, reason: str) -> None:
        """Fall back to the ordinary window without touching parser or browser state."""
        if self._shutting_down:
            return
        logger.warning(
            "Wayland live presentation failed; using the normal popout: %s",
            reason or "unknown error")
        self._wayland_presenter = None
        was_presented = self._using_wayland_presentation
        self._using_wayland_presentation = False
        if self._popout_visible and was_presented:
            self._prepare_popout()
            self.show()

    def _prepare_popout(self) -> None:
        if self._window_scale != self._settings.liveparser__window_scale:
            QFrame().setLayout(self.layout())
            self.build_window()
        if self._settings.state__live_geometry:
            self.restoreGeometry(self._settings.state__live_geometry)
        self.apply_runtime_settings()

    def _set_log_path(self, show_warning: bool) -> bool:
        if self._liveparser.set_log_path(self._settings.sto_log_path):
            return True
        if show_warning:
            bad_logfile_message = tr(
                'Make sure to set the STO Logfile setting in the settings tab to a valid '
                'logfile before starting the live parser.')
            self._dialogs.show_message(
                tr('Invalid Logfile'), bad_logfile_message, 'warning')
        return False

    def _close_popout(self) -> None:
        self.set_popout_visible(False, stop_parser=not self._command_console)
        if not self._command_console:
            self._widgets.live_parser_button.setChecked(False)

    def _start_from_activate_button(self) -> bool:
        self._activate_button_transition = True
        try:
            return self.start_parser()
        finally:
            self._activate_button_transition = False

    def _stop_from_activate_button(self) -> None:
        self._activate_button_transition = True
        try:
            self.stop_parser()
        finally:
            self._activate_button_transition = False

    @Slot()
    def update_live_table(self, data: list):
        """
        Updates the table of the live parser with the supplied data

        Parameters:
        - :param data: list containing the index and cell values
        """
        self._table_model.replace_data(data)
        if data:
            self._table.sortByColumn(0, Qt.SortOrder.DescendingOrder)
        self._table.resizeColumnsToContents()
        self._table.resizeRowsToContents()
        self.update_shown_columns(publish=False)

    @Slot(float)
    def _update_duration_label(self, combat_time: float) -> None:
        self._duration_label.setText(f'Duration: {combat_time:.1f}s')

    @Slot(bool)
    def _sync_activate_button(self, active: bool) -> None:
        """Keep the inherited popout button aligned with page-driven parser state."""
        if (not hasattr(self, '_activate_button')
                or self._activate_button_transition):
            return
        blocked = self._activate_button.blockSignals(True)
        self._activate_button._r = not active
        self._activate_button.setChecked(active)
        self._activate_button.setText(tr('Deactivate') if active else tr('Activate'))
        self._activate_button.blockSignals(blocked)

    @Slot()
    def update_live_graph(self, curve_data: list[tuple[PlotDataItem, list[float]]]):
        """
        Updates the graph of the live parser with the supplied data

        Parameters:
        - :param curve_data: list containing pairs of curve items and data lists; curve items will
        be updated with the data
        """
        time_data = list(range(-14, 1))
        for curve, data_points in curve_data:
            curve.setData(time_data, data_points)

    def live_parser_press_event(self, event: QMouseEvent):
        """
        Used to start moving the parser window.
        """
        self._move_start_pos = event.globalPosition().toPoint()
        event.accept()

    def live_parser_move_event(self, event: QMouseEvent):
        """
        Used to move the parser window to new location.
        """
        pos_delta = QPoint(event.globalPosition().toPoint() - self._move_start_pos)
        self.move(self.x() + pos_delta.x(), self.y() + pos_delta.y())
        self._move_start_pos = event.globalPosition().toPoint()
        event.accept()

    def live_parser_move_wayland(self, event: QMouseEvent):
        """
        Used to move the parser window on wayland.
        """
        self.windowHandle().startSystemMove()
        event.accept()

    def store_window_state(self):
        """
        Stores state of window
        """
        self._settings.state__live_geometry = self.saveGeometry()
        if self._graph_active:
            self._settings.state__live_splitter = self._splitter.saveState()

    def copy_live_data_callback(self):
        """
        Copies the data from the live parser table.
        """
        output = list()
        name_index = 0 if self._settings.liveparser__player_display == 'Name' else 1
        if self._settings.liveparser__copy_kills:
            for row in self._table_model._data:
                output.append(f"{row[0][name_index]}: {row[1]:,.2f} ({row[6]:.0f})")
            output = '{ OSCR } DPS (Kills): ' + ' | '.join(output)
        else:
            for row in self._table_model._data:
                output.append(f"{row[0][name_index]}: {row[1]:,.2f}")
            output = '{ OSCR } DPS: ' + ' | '.join(output)
        QApplication.clipboard().setText(output)
