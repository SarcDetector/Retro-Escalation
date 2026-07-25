"""Command Console control centre for the inherited OSCR live parser."""

from pathlib import Path

from pyqtgraph import PlotWidget, mkPen
from PySide6.QtCore import QEvent, QObject, QSignalBlocker, Qt, QUrl, Slot
from PySide6.QtGui import QDesktopServices, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFrame, QGridLayout, QHeaderView, QHBoxLayout, QLabel,
    QKeySequenceEdit, QLineEdit, QScrollArea, QSizePolicy, QSpinBox, QSplitter,
    QTableView, QVBoxLayout, QWidget,
)
from OSCR import LIVE_TABLE_HEADER

from ..console.components import action_button, capped_panel, cap_line, chip, embedded_panel
from ..console.tokens import SURFACES, refresh_style
from ..datamodels import LiveParserTableModel
from ..iofunctions import browse_path
from ..liveoverlay import available_private_bind_addresses
from ..liveparser import LIVE_GRAPH_FIELD_TO_COLUMN
from ..translation import tr
from ..widgetbuilder import create_annotated_slider


class LiveView(QObject):
    """Present parser controls, popout controls, preview, and existing live settings."""

    def __init__(
            self, theme, settings, config, widgets, live_parser,
            overlay_controller=None):
        super().__init__()
        self.theme = theme
        self.settings = settings
        self.config = config
        self.widgets = widgets
        self.live_parser = live_parser
        self.overlay = overlay_controller
        self._preview_model: LiveParserTableModel | None = None
        self._preview_table: QTableView | None = None
        self._preview_graph: PlotWidget | None = None
        self._preview_curves = []
        self._preview_buffers: list[list[float]] = []
        self._latest_rows: list[list] = []
        self._parser_button = None
        self._popout_button = None
        self._parser_chip = None
        self._popout_chip = None
        self._feed_chip = None
        self._clients_chip = None
        self._preview_status = None
        self._preview_duration = None
        self._preview_title = None
        self._preview_idle = None
        self._source_label = None
        self._graph_toggle = None
        self._graph_field = None
        self._feed_button = None
        self._feed_detail = None
        self._feed_endpoint = None
        self._feed_output = None
        self._feed_bind = None
        self._feed_port = None
        self._feed_lan_warning = None
        self._feed_copy_button = None
        self._feed_open_button = None
        self._custom_css_entry = None
        self._hotkey_edit = None
        self._hotkey_chip = None
        self._hotkey_detail = None
        self._hotkey_mode = None
        self._hotkey_mode_warning = None
        self._hotkey_capture_open = False
        self._lan_confirmation_pending = False

    def build(self, parent_frame: QFrame) -> None:
        layout = QVBoxLayout()
        margin = round(12 * self.theme.scale)
        layout.setContentsMargins(margin, margin, margin, margin)
        layout.setSpacing(round(10 * self.theme.scale))
        layout.addWidget(self._build_heading())
        layout.addWidget(self._build_master_controls())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setObjectName('commandConsoleLiveSplitter')
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_preview())
        splitter.addWidget(self._build_settings())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([600, 400])
        layout.addWidget(splitter, 1)
        parent_frame.setLayout(layout)

        self.live_parser.snapshot_updated.connect(self.update_preview)
        self.live_parser.parser_active_changed.connect(self._sync_parser_state)
        self.live_parser.popout_visible_changed.connect(self._sync_popout_state)
        if self.overlay is not None:
            self.overlay.feed.state_changed.connect(self._sync_feed_state)
            self.overlay.feed.clients_changed.connect(self._sync_feed_clients)
            self.overlay.hotkey.status_changed.connect(self._sync_hotkey_state)
        self._sync_parser_state(self.live_parser.parser_active)
        self._sync_popout_state(self.live_parser.popout_visible)
        if self.overlay is not None:
            self._sync_feed_state(self.overlay.feed.current_state())
            self._sync_feed_clients(self.overlay.feed.client_count)
            self._sync_hotkey_state(
                self.overlay.hotkey.state, self.overlay.hotkey.detail)
        rows, combat_time = self.live_parser.last_snapshot
        self.update_preview(rows, combat_time)

    def _build_heading(self) -> QFrame:
        heading = cap_line(
            self.theme.scale, 'commandConsoleLiveHeading',
            'LIVE SESSION // LOCAL TELEMETRY', 'LIVE CONTROL CENTER', 4)
        status_layout = QHBoxLayout()
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(round(6 * self.theme.scale))
        self._parser_chip = chip('PARSER STOPPED', 'commandConsoleLiveParserStatus')
        self._popout_chip = chip('POPOUT HIDDEN', 'commandConsoleLivePopoutStatus')
        status_labels = [self._parser_chip, self._popout_chip]
        if self.overlay is not None:
            self._feed_chip = chip('FEED STOPPED', 'commandConsoleLiveFeedStatus')
            self._clients_chip = chip('0 CLIENTS', 'commandConsoleLiveClientStatus')
            status_labels.extend((self._feed_chip, self._clients_chip))
        for label in status_labels:
            label.setProperty('accentIndex', '4')
            label.setMinimumHeight(round(28 * self.theme.scale))
            status_layout.addWidget(label)
        heading.body_layout.addLayout(status_layout)
        self.widgets.live_parser_status_chip = self._parser_chip
        self.widgets.live_parser_popout_chip = self._popout_chip
        if self.overlay is not None:
            self.widgets.live_overlay_status_chip = self._feed_chip
            self.widgets.live_overlay_clients_chip = self._clients_chip
        return heading.frame

    def _build_master_controls(self) -> QFrame:
        panel = capped_panel(
            self.theme.scale, 'commandConsoleLiveMasterPanel',
            'SESSION CONTROL // INDEPENDENT STATES', 'PARSER + LOCAL POPOUT', 4)
        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(round(7 * self.theme.scale))

        self._parser_button = action_button(
            'START PARSING', 'commandConsoleLiveParserToggle', 4, primary=True)
        self._parser_button.setCheckable(True)
        self._parser_button.setProperty('toggleAction', True)
        self._parser_button.clicked.connect(self._toggle_parser)
        controls.addWidget(self._parser_button)

        self._popout_button = action_button(
            'SHOW POPOUT', 'commandConsoleLivePopoutToggle', 4)
        self._popout_button.setCheckable(True)
        self._popout_button.setProperty('toggleAction', True)
        self._popout_button.clicked.connect(self._toggle_popout)
        controls.addWidget(self._popout_button)

        if self.overlay is not None:
            self._feed_button = action_button(
                'START BROWSER FEED', 'commandConsoleLiveFeedToggle', 4)
            self._feed_button.setCheckable(True)
            self._feed_button.setProperty('toggleAction', True)
            self._feed_button.clicked.connect(self._toggle_feed)
            controls.addWidget(self._feed_button)

        copy_button = action_button('COPY RESULT', 'commandConsoleLiveCopy', 4)
        copy_button.clicked.connect(self.live_parser.copy_live_data_callback)
        controls.addWidget(copy_button)
        log_settings_button = action_button(
            'LOG SETTINGS', 'commandConsoleLiveLogSettings', 4)
        log_settings_button.clicked.connect(self._open_log_settings)
        controls.addWidget(log_settings_button)
        controls.addStretch(1)
        panel.body_layout.addLayout(controls)

        self._source_label = QLabel()
        self._source_label.setObjectName('commandConsoleLiveSource')
        self._source_label.setProperty('consoleRole', 'muted')
        self._source_label.setWordWrap(True)
        self.refresh_source()
        panel.body_layout.addWidget(self._source_label)
        self.widgets.live_parser_start_button = self._parser_button
        self.widgets.live_parser_popout_button = self._popout_button
        self.widgets.live_parser_copy_button = copy_button
        if self.overlay is not None:
            self.widgets.live_overlay_feed_button = self._feed_button
        return panel.frame

    def _build_preview(self) -> QFrame:
        panel = embedded_panel(
            self.theme.scale, 'commandConsoleLivePreviewPanel',
            'LIVE PREVIEW // POPULATES FROM THE ACTIVE SESSION', 'WAITING FOR COMBAT', 4)
        self._preview_title = panel.title
        meta = QHBoxLayout()
        meta.setContentsMargins(0, 0, 0, 0)
        meta.setSpacing(round(7 * self.theme.scale))
        self._preview_status = chip('NO TELEMETRY', 'commandConsoleLivePreviewStatus')
        self._preview_duration = chip('0.0S', 'commandConsoleLivePreviewDuration')
        meta.addWidget(self._preview_status)
        meta.addWidget(self._preview_duration)
        meta.addStretch(1)
        panel.body_layout.addLayout(meta)

        self._preview_idle = QLabel(
            'START PARSING TO RECEIVE LIVE COMBAT TELEMETRY')
        self._preview_idle.setObjectName('commandConsoleLivePreviewIdle')
        self._preview_idle.setProperty('consoleRole', 'muted')
        self._preview_idle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_idle.setWordWrap(True)
        self._preview_idle.setMinimumHeight(round(46 * self.theme.scale))
        panel.body_layout.addWidget(self._preview_idle)

        graph = PlotWidget()
        graph.setObjectName('commandConsoleLivePreviewGraph')
        graph.setBackground(SURFACES['base'])
        graph.setMouseEnabled(False, False)
        graph.setMenuEnabled(False)
        graph.hideButtons()
        graph.setDefaultPadding(0.02)
        graph.setXRange(-14, 0, padding=0)
        graph.showGrid(x=True, y=True, alpha=0.12)
        graph.setMinimumHeight(round(130 * self.theme.scale))
        for colour in self.theme['plot']['color_cycler'][:5]:
            self._preview_curves.append(
                graph.plot([0], [0], pen=mkPen(colour, width=2.4)))
        self._preview_graph = graph
        panel.body_layout.addWidget(graph, 2)

        table = QTableView()
        table.setObjectName('commandConsoleLivePreviewTable')
        table.setProperty('consoleRole', 'telemetryTable')
        table.setAlternatingRowColors(False)
        table.setShowGrid(False)
        table.setSelectionMode(QTableView.SelectionMode.NoSelection)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.setSortingEnabled(True)
        colours = (*self.theme['plot']['color_cycler'][:5], self.theme['defaults']['fg'])
        model = LiveParserTableModel(tr(LIVE_TABLE_HEADER), colours)
        model.init_fonts(
            self.theme.get_font('live_table_header'), self.theme.get_font('live_table'))
        table.setModel(model)
        self._preview_model = model
        self._preview_table = table
        panel.body_layout.addWidget(table, 3)

        self.widgets.live_parser_preview_status = self._preview_status
        self.widgets.live_parser_preview_duration = self._preview_duration
        self.widgets.live_parser_preview_table = table
        self.widgets.live_parser_preview_model = model
        return panel.frame

    def _build_settings(self) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setObjectName('commandConsoleLiveSettingsScroll')
        scroll.setProperty('consoleRole', 'surfaceScroll')
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setMinimumWidth(round(350 * self.theme.scale))
        content = QFrame()
        content.setObjectName('commandConsoleLiveSettingsPage')
        content.setProperty('consoleRole', 'surfacePage')
        content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(round(9 * self.theme.scale))
        if self.overlay is not None:
            layout.addWidget(self._build_browser_output_settings())
            layout.addWidget(self._build_hotkey_settings())
        layout.addWidget(self._build_display_settings())
        layout.addWidget(self._build_behavior_settings())
        layout.addWidget(self._build_column_settings())
        layout.addStretch(1)
        content.setLayout(layout)
        scroll.setWidget(content)
        return scroll

    def _build_browser_output_settings(self) -> QFrame:
        panel = capped_panel(
            self.theme.scale, 'commandConsoleLiveBrowserPanel',
            'BROWSER OUTPUT', 'OBS + READ-ONLY FEED', 4)
        grid = self._settings_grid()
        row = 0

        bind = QComboBox()
        bind.setObjectName('settingsLiveOverlayBind')
        bind.setProperty('consoleRole', 'compactCombo')
        bind.addItem('LOCAL ONLY - 127.0.0.1', '127.0.0.1')
        known_addresses = {'127.0.0.1'}
        for item in available_private_bind_addresses():
            bind.addItem(item.label.upper(), item.address)
            known_addresses.add(item.address)
        configured_bind = str(self.settings.overlay__feed_bind)
        if configured_bind not in known_addresses:
            bind.addItem(f'UNAVAILABLE ADAPTER - {configured_bind}', configured_bind)
        configured_index = bind.findData(configured_bind)
        bind.setCurrentIndex(max(0, configured_index))
        bind.setMinimumHeight(round(30 * self.theme.scale))
        bind.currentIndexChanged.connect(self._set_feed_bind)
        self._feed_bind = bind
        self._add_field(grid, row, 'Network', bind)
        row += 1

        port = QSpinBox()
        port.setObjectName('settingsLiveOverlayPort')
        port.setProperty('consoleRole', 'compactEntry')
        port.setRange(1024, 65535)
        port.setValue(int(self.settings.overlay__feed_port))
        port.setMinimumHeight(round(30 * self.theme.scale))
        port.valueChanged.connect(self._set_feed_port)
        self._feed_port = port
        self._add_field(grid, row, 'Port', port)
        row += 1

        endpoint = QLineEdit()
        endpoint.setObjectName('settingsLiveOverlayEndpoint')
        endpoint.setReadOnly(True)
        endpoint.setProperty('consoleRole', 'compactEntry')
        copy_endpoint = action_button(
            'COPY FEED URL', 'settingsLiveOverlayCopyEndpoint', 4)
        copy_endpoint.clicked.connect(self._copy_feed_endpoint)
        self._feed_copy_button = copy_endpoint
        endpoint_row = self._inline_controls(endpoint, copy_endpoint)
        self._feed_endpoint = endpoint
        self._add_field(grid, row, 'Feed URL', endpoint_row)
        row += 1

        output = QLineEdit()
        output.setObjectName('settingsLiveOverlayOutput')
        output.setReadOnly(True)
        output.setProperty('consoleRole', 'compactEntry')
        open_folder = action_button(
            'OPEN FOLDER', 'settingsLiveOverlayOpenFolder', 4)
        open_folder.clicked.connect(self._open_overlay_folder)
        self._feed_open_button = open_folder
        output_row = self._inline_controls(output, open_folder)
        self._feed_output = output
        self._add_field(grid, row, 'OBS file', output_row)
        row += 1

        custom_css = QLineEdit(str(self.settings.overlay__custom_css_path))
        custom_css.setObjectName('settingsLiveOverlayCustomCss')
        custom_css.setPlaceholderText('OPTIONAL LOCAL .CSS FILE')
        custom_css.setProperty('consoleRole', 'compactEntry')
        custom_css.editingFinished.connect(self._apply_custom_css)
        choose_css = action_button('CHOOSE', 'settingsLiveOverlayChooseCss', 4)
        choose_css.clicked.connect(self._browse_custom_css)
        clear_css = action_button('CLEAR', 'settingsLiveOverlayClearCss', 4)
        clear_css.clicked.connect(self._clear_custom_css)
        css_row = self._inline_controls(custom_css, choose_css, clear_css)
        self._custom_css_entry = custom_css
        self._add_field(grid, row, 'Custom CSS', css_row)
        row += 1

        self._feed_lan_warning = QLabel()
        self._feed_lan_warning.setObjectName('settingsLiveOverlayLanWarning')
        self._feed_lan_warning.setProperty('consoleRole', 'muted')
        self._feed_lan_warning.setProperty('status', 'warning')
        self._feed_lan_warning.setWordWrap(True)
        grid.addWidget(self._feed_lan_warning, row, 0, 1, 2)
        row += 1

        self._feed_detail = QLabel('BROWSER OVERLAY FEED IS STOPPED')
        self._feed_detail.setObjectName('settingsLiveOverlayDetail')
        self._feed_detail.setProperty('consoleRole', 'muted')
        self._feed_detail.setWordWrap(True)
        grid.addWidget(self._feed_detail, row, 0, 1, 2)
        row += 1

        note = QLabel(
            'OBS // ADD A BROWSER SOURCE, ENABLE LOCAL FILE, THEN SELECT OVERLAY.HTML. '
            'THE FEED URL CONTAINS A PRIVATE SESSION TOKEN; SHARE IT ONLY WITH THE DISPLAY '
            'YOU INTEND TO USE. REFRESH THE OBS BROWSER SOURCE AFTER CHANGING CUSTOM CSS.')
        note.setProperty('consoleRole', 'muted')
        note.setWordWrap(True)
        grid.addWidget(note, row, 0, 1, 2)
        panel.body_layout.addLayout(grid)

        self.widgets.live_overlay_bind = bind
        self.widgets.live_overlay_port = port
        self.widgets.live_overlay_endpoint = endpoint
        self.widgets.live_overlay_output = output
        self.widgets.live_overlay_custom_css = custom_css
        return panel.frame

    def _build_hotkey_settings(self) -> QFrame:
        panel = capped_panel(
            self.theme.scale, 'commandConsoleLiveHotkeyPanel',
            'GLOBAL VISIBILITY', 'WINDOWS HOTKEY', 4)
        grid = self._settings_grid()

        hotkey = QKeySequenceEdit()
        hotkey.setObjectName('settingsLiveOverlayHotkey')
        hotkey.setProperty('consoleRole', 'compactEntry')
        hotkey.setMaximumSequenceLength(1)
        hotkey.setKeySequence(QKeySequence.fromString(
            str(self.settings.overlay__hotkey_visibility),
            QKeySequence.SequenceFormat.PortableText))
        hotkey.installEventFilter(self)
        hotkey.editingFinished.connect(self._commit_hotkey)
        clear_button = action_button('CLEAR', 'settingsLiveOverlayHotkeyClear', 4)
        clear_button.clicked.connect(self._clear_hotkey)
        hotkey_row = self._inline_controls(hotkey, clear_button)
        self._hotkey_edit = hotkey
        self._add_field(grid, 0, 'Show / hide', hotkey_row)

        mode = QComboBox()
        mode.setObjectName('settingsLiveOverlayHideMode')
        mode.setProperty('consoleRole', 'compactCombo')
        mode.addItem('POPOUT + BROWSER METER', 'all')
        mode.addItem('POPOUT ONLY', 'popout')
        mode.setCurrentIndex(max(0, mode.findData(
            str(self.settings.overlay__hotkey_hide_mode))))
        mode.currentIndexChanged.connect(self._set_hotkey_mode)
        self._hotkey_mode = mode
        self._add_field(grid, 1, 'Hotkey hides', mode)

        status_row = QHBoxLayout()
        status_row.setContentsMargins(0, 0, 0, 0)
        self._hotkey_chip = chip('NOT ASSIGNED', 'settingsLiveOverlayHotkeyStatus')
        self._hotkey_chip.setProperty('accentIndex', '4')
        status_row.addWidget(self._hotkey_chip)
        status_row.addStretch(1)
        grid.addLayout(status_row, 2, 0, 1, 2)

        self._hotkey_detail = QLabel('NO GLOBAL HOTKEY IS ASSIGNED')
        self._hotkey_detail.setObjectName('settingsLiveOverlayHotkeyDetail')
        self._hotkey_detail.setProperty('consoleRole', 'muted')
        self._hotkey_detail.setWordWrap(True)
        grid.addWidget(self._hotkey_detail, 3, 0, 1, 2)

        self._hotkey_mode_warning = QLabel()
        self._hotkey_mode_warning.setObjectName('settingsLiveOverlayHotkeyModeNote')
        self._hotkey_mode_warning.setProperty('consoleRole', 'muted')
        self._hotkey_mode_warning.setWordWrap(True)
        grid.addWidget(self._hotkey_mode_warning, 4, 0, 1, 2)
        self._refresh_hotkey_mode_note()
        panel.body_layout.addLayout(grid)

        if not self.overlay.hotkey.supported:
            hotkey.setEnabled(False)
            clear_button.setEnabled(False)
        self.widgets.live_overlay_hotkey = hotkey
        self.widgets.live_overlay_hotkey_mode = mode
        self.widgets.live_overlay_hotkey_status = self._hotkey_chip
        return panel.frame

    def _build_display_settings(self) -> QFrame:
        panel = capped_panel(
            self.theme.scale, 'commandConsoleLiveDisplaySettingsPanel',
            'PRESENTATION', 'WINDOW + GRAPH', 4)
        grid = self._settings_grid()
        row = 0
        grid.addWidget(self._field_label('Window opacity'), row, 0)
        opacity_controls = create_annotated_slider(
            self.theme, round(self.settings.liveparser__window_opacity * 20), 1, 20,
            callback=self._set_opacity)
        opacity_controls.itemAt(1).widget().setObjectName('settingsLiveOpacity')
        grid.addLayout(opacity_controls, row, 1)
        row += 1

        self._graph_toggle = self._toggle_button(
            self.settings.liveparser__graph_active, 'settingsLiveGraph',
            self._set_graph_active, 'GRAPH ON', 'GRAPH OFF')
        self._add_field(grid, row, 'Graph', self._graph_toggle)
        row += 1

        self._graph_field = self._combo(
            self.config.live_graph_fields, self.settings.liveparser__graph_field,
            'settingsLiveGraphField')
        self._graph_field.setEnabled(self.settings.liveparser__graph_active)
        self._graph_field.currentIndexChanged.connect(self._set_graph_field)
        self._add_field(grid, row, 'Graph field', self._graph_field)
        row += 1

        player_display = self._combo(
            ('Name', 'Handle'), object_name='settingsLivePlayerDisplay')
        player_display.setCurrentText(self.settings.liveparser__player_display)
        player_display.currentTextChanged.connect(self._set_player_display)
        self._add_field(grid, row, 'Player display', player_display)
        row += 1

        grid.addWidget(self._field_label('Window scale'), row, 0)
        scale_controls = create_annotated_slider(
            self.theme, round(self.settings.liveparser__window_scale * 50), 25, 75,
            callback=self._set_scale)
        scale_controls.itemAt(1).widget().setObjectName('settingsLiveScale')
        grid.addLayout(scale_controls, row, 1)
        row += 1
        note = QLabel('WINDOW SCALE APPLIES THE NEXT TIME THE POPOUT OPENS')
        note.setProperty('consoleRole', 'muted')
        note.setWordWrap(True)
        grid.addWidget(note, row, 0, 1, 2)
        panel.body_layout.addLayout(grid)
        self.widgets.live_parser_graph_toggle = self._graph_toggle
        self.widgets.live_parser_graph_field = self._graph_field
        self.widgets.live_parser_player_display = player_display
        return panel.frame

    def _build_behavior_settings(self) -> QFrame:
        panel = capped_panel(
            self.theme.scale, 'commandConsoleLiveBehaviorSettingsPanel',
            'SESSION DEFAULTS', 'STARTUP + COPY', 4)
        grid = self._settings_grid()
        auto = self._toggle_button(
            self.settings.liveparser__auto_enabled, 'settingsLiveDefault',
            lambda state: self.settings.set('liveparser__auto_enabled', state),
            'AUTO START', 'MANUAL START')
        self._add_field(grid, 0, 'When popout opens', auto)
        kills = self._toggle_button(
            self.settings.liveparser__copy_kills, 'settingsLiveCopyKills',
            self._set_copy_kills,
            'KILLS INCLUDED', 'DPS ONLY')
        self._add_field(grid, 1, 'Copy result', kills)
        note = QLabel(
            'The parser, this page, and the popout are independent. Hiding the popout does not '
            'stop an active session.')
        note.setProperty('consoleRole', 'muted')
        note.setWordWrap(True)
        grid.addWidget(note, 2, 0, 1, 2)
        panel.body_layout.addLayout(grid)
        return panel.frame

    def _build_column_settings(self) -> QFrame:
        panel = capped_panel(
            self.theme.scale, 'commandConsoleLiveColumnsPanel',
            'VISIBLE METRICS', 'LIVE TABLE COLUMNS', 4)
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(round(6 * self.theme.scale))
        grid.setVerticalSpacing(round(6 * self.theme.scale))
        buttons = []
        for index, header in enumerate(tr(LIVE_TABLE_HEADER)):
            button = action_button(str(header).upper(), 'commandConsoleLiveColumnToggle', 4)
            button.setCheckable(True)
            button.setChecked(self.settings.liveparser__columns[index])
            button.setProperty('toggleAction', True)
            button.clicked[bool].connect(
                lambda state, column=index: self._set_column(column, state))
            grid.addWidget(button, index // 2, index % 2)
            buttons.append(button)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        panel.body_layout.addLayout(grid)
        self.widgets.live_parser_column_buttons = buttons
        self.widgets.settings_live_column_buttons = buttons
        return panel.frame

    @Slot(object, float)
    def update_preview(self, rows: list, combat_time: float) -> None:
        copied_rows = [list(row) for row in rows]
        for index, row in enumerate(copied_rows):
            row[8] = index if index < 5 else 5
        self._latest_rows = [list(row) for row in copied_rows]
        if self._preview_model is None or self._preview_table is None:
            return
        self._preview_model.replace_data(copied_rows)
        if copied_rows:
            self._preview_table.sortByColumn(0, Qt.SortOrder.DescendingOrder)
        self._preview_table.resizeColumnsToContents()
        self._preview_table.resizeRowsToContents()
        self._preview_status.setText(
            f'{len(copied_rows)} OPERATOR{"S" if len(copied_rows) != 1 else ""}'
            if copied_rows else 'NO TELEMETRY')
        self._preview_status.setProperty('status', 'truth' if copied_rows else '')
        refresh_style(self._preview_status, descendants=False)
        self._preview_duration.setText(f'{combat_time:.1f}S')
        if self._preview_idle is not None:
            self._preview_idle.setVisible(not copied_rows)
        if self._preview_title is not None:
            self._preview_title.setText(
                'LIVE COMBAT TELEMETRY' if copied_rows else 'WAITING FOR COMBAT')
        self._sync_preview_settings(reset_graph=False)
        self._update_preview_graph(copied_rows)

    def _toggle_parser(self) -> None:
        if self.live_parser.parser_active:
            self.live_parser.stop_parser()
        else:
            self.live_parser.start_parser()

    def refresh_source(self) -> None:
        """Refresh the real combat-log path shown beside the session controls."""
        if self._source_label is not None:
            self._source_label.setText(
                f'COMBAT LOG // {self.settings.sto_log_path or "NOT CONFIGURED"}')

    def _toggle_popout(self) -> None:
        self.live_parser.set_popout_visible(not self.live_parser.popout_visible)

    def _toggle_feed(self) -> None:
        if self.overlay is None:
            return
        if self.overlay.feed.active:
            self._lan_confirmation_pending = False
            self.overlay.set_feed_enabled(False)
            return
        is_lan = str(self.settings.overlay__feed_bind) != '127.0.0.1'
        confirmed = is_lan and self._lan_confirmation_pending
        accepted = self.overlay.set_feed_enabled(True, lan_confirmed=confirmed)
        if is_lan and not accepted and not confirmed:
            self._lan_confirmation_pending = True
        else:
            self._lan_confirmation_pending = False
        self._sync_feed_state(self.overlay.feed.current_state())

    def _set_feed_bind(self, index: int) -> None:
        if self.overlay is None or self._feed_bind is None:
            return
        address = self._feed_bind.itemData(index)
        if not address:
            return
        self._lan_confirmation_pending = False
        self.overlay.set_bind(str(address))

    def _set_feed_port(self, port: int) -> None:
        if self.overlay is not None:
            self._lan_confirmation_pending = False
            self.overlay.set_port(int(port))

    def _copy_feed_endpoint(self) -> None:
        if self.overlay is None:
            return
        if not self.overlay.feed.active:
            self.overlay.feed.report_state(
                'warning', 'Start the browser feed before copying its private URL.')
            return
        QApplication.clipboard().setText(self.overlay.feed.endpoint)
        self.overlay.feed.report_state(
            'active', 'Private feed URL copied. Share it only with the intended display.')

    def _open_overlay_folder(self) -> None:
        if self.overlay is None:
            return
        directory = self.overlay.feed.output_path.parent
        if not directory.is_dir():
            self.overlay.feed.report_state(
                'warning', 'Start the browser feed once to create the OBS overlay folder.')
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(directory))):
            self.overlay.feed.report_state(
                'warning', f'Could not open the overlay folder: {directory}')

    def _browse_custom_css(self) -> None:
        configured = str(self.settings.overlay__custom_css_path).strip()
        start = Path(configured).parent if configured else Path(self.config.config_dir)
        path = browse_path(start, 'CSS File (*.css);;Any File (*.*)')
        if path is None or self._custom_css_entry is None:
            return
        self._custom_css_entry.setText(str(path))
        self._apply_custom_css()

    def _clear_custom_css(self) -> None:
        if self._custom_css_entry is None:
            return
        self._custom_css_entry.clear()
        self._apply_custom_css()

    def _apply_custom_css(self) -> None:
        if self.overlay is not None and self._custom_css_entry is not None:
            self.overlay.set_custom_css(self._custom_css_entry.text().strip())

    def eventFilter(self, watched, event) -> bool:
        if (watched is self._hotkey_edit
                and event.type() == QEvent.Type.FocusIn
                and self.overlay is not None
                and self.overlay.hotkey.supported
                and not self._hotkey_capture_open):
            self._hotkey_capture_open = True
            self.overlay.begin_hotkey_capture()
        return super().eventFilter(watched, event)

    def _commit_hotkey(self) -> None:
        if self.overlay is None or self._hotkey_edit is None:
            return
        binding = self._hotkey_edit.keySequence().toString(
            QKeySequence.SequenceFormat.PortableText)
        if self._hotkey_capture_open:
            self._hotkey_capture_open = False
            accepted = self.overlay.commit_hotkey_capture(binding)
        else:
            accepted = self.overlay.apply_hotkey(binding)
        if not accepted:
            blocker = QSignalBlocker(self._hotkey_edit)
            self._hotkey_edit.setKeySequence(QKeySequence.fromString(
                self.overlay.hotkey.binding,
                QKeySequence.SequenceFormat.PortableText))
            del blocker

    def _clear_hotkey(self) -> None:
        if self.overlay is None or self._hotkey_edit is None:
            return
        self._hotkey_capture_open = False
        self.overlay.apply_hotkey('')
        blocker = QSignalBlocker(self._hotkey_edit)
        self._hotkey_edit.clear()
        del blocker

    def _set_hotkey_mode(self, index: int) -> None:
        if self.overlay is None or self._hotkey_mode is None:
            return
        self.overlay.set_hide_mode(str(self._hotkey_mode.itemData(index)))
        self._refresh_hotkey_mode_note()

    def _refresh_hotkey_mode_note(self) -> None:
        if self._hotkey_mode_warning is None:
            return
        if str(self.settings.overlay__hotkey_hide_mode) == 'popout':
            text = (
                'THE HOTKEY HIDES ONLY THE LOCAL POPOUT. THE BROWSER METER STAYS VISIBLE. '
                'THE PARSER KEEPS RUNNING.')
        else:
            text = (
                'THE HOTKEY HIDES THE LOCAL POPOUT AND BROWSER METER TOGETHER. '
                'THE PARSER KEEPS RUNNING.')
        self._hotkey_mode_warning.setText(text)

    def _open_log_settings(self) -> None:
        self.widgets.switch_main_tab(3)
        if len(self.widgets.settings_menu_buttons) > 1:
            self.widgets.settings_menu_buttons[1].click()

    @Slot(bool)
    def _sync_parser_state(self, active: bool) -> None:
        self._sync_action_state(
            self._parser_button, active, 'STOP PARSING', 'START PARSING')
        if self._parser_chip is not None:
            self._parser_chip.setText('PARSER RUNNING' if active else 'PARSER STOPPED')
            self._parser_chip.setProperty('status', 'truth' if active else '')
            refresh_style(self._parser_chip, descendants=False)

    @Slot(bool)
    def _sync_popout_state(self, visible: bool) -> None:
        self._sync_action_state(
            self._popout_button, visible, 'HIDE POPOUT', 'SHOW POPOUT')
        if self._popout_chip is not None:
            self._popout_chip.setText('POPOUT VISIBLE' if visible else 'POPOUT HIDDEN')
            self._popout_chip.setProperty('status', 'truth' if visible else '')
            refresh_style(self._popout_chip, descendants=False)

    @Slot(object)
    def _sync_feed_state(self, state: dict) -> None:
        if self.overlay is None:
            return
        active = bool(state.get('active'))
        status = str(state.get('status', 'stopped'))
        visible = bool(state.get('visible', True))
        if active:
            self._lan_confirmation_pending = False
        self._sync_action_state(
            self._feed_button, active, 'STOP BROWSER FEED', 'START BROWSER FEED')
        if self._lan_confirmation_pending and self._feed_button is not None:
            self._feed_button.setText('CONFIRM LAN START')
            self._feed_button.setChecked(False)
            self._feed_button.setProperty('visualActive', False)
            refresh_style(self._feed_button, descendants=False)

        if self._feed_chip is not None:
            if active and visible:
                label, chip_status = 'FEED LIVE', 'truth'
            elif active:
                label, chip_status = 'FEED HIDDEN', 'warning'
            elif status == 'error':
                label, chip_status = 'FEED ERROR', 'error'
            elif status == 'warning':
                label, chip_status = 'FEED ATTENTION', 'warning'
            else:
                label, chip_status = 'FEED STOPPED', ''
            self._feed_chip.setText(label)
            self._feed_chip.setProperty('status', chip_status)
            refresh_style(self._feed_chip, descendants=False)

        if self._feed_detail is not None:
            detail = str(state.get('detail', ''))
            css_warning = str(state.get('customCssWarning', ''))
            self._feed_detail.setText(
                f'{detail} {css_warning}'.strip().upper())
            self._feed_detail.setProperty(
                'status', 'error' if status == 'error'
                else 'warning' if status == 'warning' or css_warning else '')
            refresh_style(self._feed_detail, descendants=False)
        if self._feed_endpoint is not None:
            self._feed_endpoint.setText(str(state.get('endpoint', '')))
            self._feed_endpoint.setCursorPosition(0)
        if self._feed_output is not None:
            self._feed_output.setText(str(state.get('outputPath', '')))
            self._feed_output.setCursorPosition(0)
        if self._feed_bind is not None:
            self._feed_bind.setEnabled(not active)
        if self._feed_port is not None:
            self._feed_port.setEnabled(not active)
        lan = str(self.settings.overlay__feed_bind) != '127.0.0.1'
        if self._feed_lan_warning is not None:
            self._feed_lan_warning.setVisible(lan)
            self._feed_lan_warning.setText(
                'LAN MODE // THIS IS AN UNENCRYPTED WS:// FEED. LIVE CHARACTER AND COMBAT '
                'TELEMETRY IS AVAILABLE TO CLIENTS ON THIS PRIVATE NETWORK. STARTING IT '
                'REQUIRES A ONE-TIME CONFIRMATION.'
                if lan else '')

    @Slot(int)
    def _sync_feed_clients(self, count: int) -> None:
        if self._clients_chip is None:
            return
        self._clients_chip.setText(
            f'{count} CLIENT' if count == 1 else f'{count} CLIENTS')
        self._clients_chip.setProperty('status', 'truth' if count else '')
        refresh_style(self._clients_chip, descendants=False)

    @Slot(str, str)
    def _sync_hotkey_state(self, state: str, detail: str) -> None:
        if self._hotkey_chip is None:
            return
        labels = {
            'registered': ('REGISTERED', 'truth'),
            'capturing': ('LISTENING', 'warning'),
            'conflict': ('CONFLICT', 'error'),
            'invalid': ('INVALID', 'error'),
            'unsupported': ('WINDOWS ONLY', ''),
            'unbound': ('NOT ASSIGNED', ''),
        }
        label, status = labels.get(state, (str(state).upper(), ''))
        self._hotkey_chip.setText(label)
        self._hotkey_chip.setProperty('status', status)
        refresh_style(self._hotkey_chip, descendants=False)
        if self._hotkey_detail is not None:
            self._hotkey_detail.setText(str(detail).upper())
            self._hotkey_detail.setProperty(
                'status', 'error' if state in ('conflict', 'invalid')
                else 'warning' if state == 'capturing' else '')
            refresh_style(self._hotkey_detail, descendants=False)

    def _set_opacity(self, value: int) -> str:
        label = self.settings.set_liveparser_opacity(value)
        self.live_parser.apply_runtime_settings()
        return label

    def _set_scale(self, value: int) -> str:
        label = self.settings.set_liveparser_scale(value)
        self.live_parser.apply_runtime_settings()
        return label

    def _set_copy_kills(self, state: bool) -> None:
        self.settings.set('liveparser__copy_kills', bool(state))
        self.live_parser.apply_runtime_settings()

    def _set_graph_active(self, state: bool) -> None:
        self.settings.set('liveparser__graph_active', bool(state))
        if self._graph_field is not None:
            self._graph_field.setEnabled(bool(state))
        self.live_parser.apply_runtime_settings()
        self._sync_preview_settings(reset_graph=True)

    def _set_graph_field(self, index: int) -> None:
        self.settings.set('liveparser__graph_field', index)
        self.live_parser.apply_runtime_settings()
        self._sync_preview_settings(reset_graph=True)

    def _set_player_display(self, text: str) -> None:
        self.settings.set('liveparser__player_display', text)
        self.live_parser.apply_runtime_settings()
        self._sync_preview_settings(reset_graph=False)
        if self.overlay is not None:
            self.overlay.refresh_presentation_settings()

    def _set_column(self, index: int, state: bool) -> None:
        self.settings.liveparser__columns[index] = bool(state)
        self.live_parser.update_shown_columns()
        self._update_preview_columns()
        if self.overlay is not None:
            self.overlay.refresh_presentation_settings()

    def _sync_preview_settings(self, reset_graph: bool) -> None:
        if self._preview_model is None:
            return
        self._preview_model.legend_column = LIVE_GRAPH_FIELD_TO_COLUMN.get(
            self.settings.liveparser__graph_field, 0)
        self._preview_model.name_index = (
            1 if self.settings.liveparser__player_display == 'Handle' else 0)
        if self._preview_graph is not None:
            self._preview_graph.setVisible(self.settings.liveparser__graph_active)
        if reset_graph:
            self._preview_buffers = []
            self._update_preview_graph(self._latest_rows)
        self._update_preview_columns()
        if self._preview_table is not None:
            self._preview_table.verticalHeader().viewport().update()

    def _update_preview_columns(self) -> None:
        if self._preview_table is None:
            return
        for index, state in enumerate(self.settings.liveparser__columns):
            self._preview_table.setColumnHidden(index, not state)

    def _update_preview_graph(self, rows: list[list]) -> None:
        if not self._preview_curves:
            return
        if not self._preview_buffers:
            self._preview_buffers = [[0.0] * 15 for _ in range(5)]
        graph_column = LIVE_GRAPH_FIELD_TO_COLUMN.get(
            self.settings.liveparser__graph_field, 0)
        values_by_colour = [0.0] * 5
        for row in rows:
            colour_index = int(row[8])
            if 0 <= colour_index < len(values_by_colour):
                values_by_colour[colour_index] = float(row[1 + graph_column])
        time_data = list(range(-14, 1))
        for index, (curve, buffer) in enumerate(zip(
                self._preview_curves, self._preview_buffers)):
            buffer.pop(0)
            buffer.append(values_by_colour[index])
            curve.setData(time_data, buffer)

    def _toggle_button(
            self, initial: bool, object_name: str, callback,
            active_text: str, inactive_text: str):
        button = action_button('', object_name, 4)
        button.setCheckable(True)
        button.setProperty('toggleAction', True)
        button.setChecked(bool(initial))
        button.setText(active_text if initial else inactive_text)
        button.clicked[bool].connect(callback)
        button.clicked[bool].connect(
            lambda state, control=button: control.setText(
                active_text if state else inactive_text))
        return button

    def _combo(
            self, items, current_index: int | None = None,
            object_name: str = '') -> QComboBox:
        combo = QComboBox()
        combo.setProperty('consoleRole', 'compactCombo')
        if object_name:
            combo.setObjectName(object_name)
        combo.addItems([str(item) for item in items])
        if current_index is not None:
            combo.setCurrentIndex(current_index)
        combo.setMinimumHeight(round(30 * self.theme.scale))
        combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        return combo

    def _field_label(self, text: str) -> QLabel:
        label = QLabel(text.upper())
        label.setProperty('consoleRole', 'muted')
        label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return label

    def _add_field(self, grid: QGridLayout, row: int, label: str, widget: QWidget) -> None:
        grid.addWidget(self._field_label(label), row, 0)
        grid.addWidget(widget, row, 1)

    def _inline_controls(self, *controls: QWidget) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(round(6 * self.theme.scale))
        for index, control in enumerate(controls):
            layout.addWidget(control, 1 if index == 0 else 0)
        return container

    def _settings_grid(self) -> QGridLayout:
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(round(8 * self.theme.scale))
        grid.setVerticalSpacing(round(7 * self.theme.scale))
        grid.setColumnStretch(1, 1)
        return grid

    @staticmethod
    def _sync_action_state(button, active: bool, active_text: str, inactive_text: str) -> None:
        if button is None:
            return
        blocked = button.blockSignals(True)
        button.setChecked(bool(active))
        button.setProperty('visualActive', bool(active))
        button.setText(active_text if active else inactive_text)
        button.blockSignals(blocked)
        refresh_style(button, descendants=False)
