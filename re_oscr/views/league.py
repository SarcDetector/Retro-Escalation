"""Functional League Standings presentation shared by both built-in themes."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QSizePolicy, QTableView, QVBoxLayout,
)

from ..translation import tr
from ..widgetbuilder import AVCENTER, create_button_series, create_entry


class LeagueView:
    """Build the ladder browser while leaving all league behavior in its connector."""

    def __init__(
            self, theme, widgets, league, tables, sidebar, clear_filter_callback,
            command_console: bool):
        self.theme = theme
        self.widgets = widgets
        self.league = league
        self.tables = tables
        self.sidebar = sidebar
        self.clear_filter_callback = clear_filter_callback
        self.command_console = command_console
        self._command_status: QLabel | None = None

    def build(self, parent_frame: QFrame) -> None:
        layout = QVBoxLayout()
        if self.command_console:
            from ..console.tokens import px

            layout.setContentsMargins(*([px(12, self.theme.scale)] * 4))
            layout.setSpacing(px(10, self.theme.scale))
            layout.addWidget(self._build_command_heading())
            layout.addWidget(self._build_command_controls())
            ladder_table = self._build_table()
            layout.addWidget(self._build_table_panel(ladder_table), 1)
        else:
            spacing = self.theme['defaults']['csp']
            layout.setContentsMargins(0, spacing, 0, spacing)
            layout.setSpacing(spacing)
            ladder_table = self._build_table()
            layout.addWidget(ladder_table, stretch=1)
            layout.addLayout(self._build_default_controls())
        parent_frame.setLayout(layout)

    def _build_command_heading(self) -> QFrame:
        from ..console.components import cap_line, chip

        heading = cap_line(
            self.theme.scale, 'commandConsoleLeagueHeading',
            'PUBLIC LEAGUE // COMMUNITY COMBAT RECORDS', 'LEAGUE STANDINGS', 2)
        heading.eyebrow.setObjectName('commandConsoleLeagueEyebrow')
        heading.title.setObjectName('commandConsoleLeagueTitle')
        status = chip('AWAITING SEASON', 'commandConsoleLeagueStatus')
        status.setProperty('consoleRole', 'leagueStatus')
        status.setToolTip('Select a season to retrieve its available ladders')
        heading.body_layout.addWidget(status)
        self._command_status = status
        self.widgets.league_status = status
        return heading.frame

    def _build_table(self) -> QTableView:
        if self.command_console:
            from ..console.tables import LeagueStandingsTableView
            from ..console.tokens import ConsoleTokens

            ladder_table = LeagueStandingsTableView(ConsoleTokens.from_theme(self.theme))
        else:
            ladder_table = QTableView()
            ladder_table.setObjectName('leagueStandingsTable')
            table_style = {
                'border-style': 'solid', 'border-width': '@bw', 'border-color': '@bc'}
            self.tables.style_table(ladder_table, table_style, single_row_selection=True)
        if self.command_console:
            ladder_table.setMeterMode(True)
        ladder_table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.league.ladder_table_model.init_fonts(
            self.theme.get_font('table_header'), self.theme.get_font('table'))
        ladder_table.setModel(self.league.ladder_table_sort)
        ladder_table.doubleClicked.connect(lambda _index: self.league.download_and_view_combat())
        self.widgets.ladder_table = ladder_table
        return ladder_table

    def _build_table_panel(self, ladder_table: QTableView) -> QFrame:
        if not self.command_console:
            return ladder_table
        from ..console.components import action_button, embedded_panel

        panel = embedded_panel(
            self.theme.scale, 'commandConsoleLeagueTablePanel',
            'RANKED RECORDS // NAME, HANDLE, DPS', 'LADDER STANDINGS', 2)
        meters = action_button('METERS', 'leagueMetersButton', 2)
        meters.setCheckable(True)
        meters.setChecked(True)
        meters.setProperty('toggleAction', True)
        meters.setProperty('visualActive', True)
        meters.clicked.connect(
            lambda checked: self._set_league_meters(ladder_table, meters, checked))
        open_selected = action_button('OPEN SELECTED', 'leagueOpenSelectedButton', 2, primary=True)
        open_selected.clicked.connect(self.league.download_and_view_combat)
        save_selected = action_button('SAVE SELECTED', 'leagueSaveSelectedButton', 2)
        save_selected.clicked.connect(self.league.download_and_save_combat)
        load_more = action_button('LOAD MORE', 'leagueLoadMoreButton', 2)
        load_more.clicked.connect(self.league.extend_ladder)
        for action in (meters, open_selected, save_selected, load_more):
            panel.cap.layout().addWidget(action)
        self.widgets.league_open_parse_button = open_selected
        self.widgets.league_save_parse_button = save_selected
        self.widgets.league_more_button = load_more
        panel.body_layout.addWidget(ladder_table)
        return panel.frame

    def _build_command_controls(self) -> QFrame:
        from ..console.components import action_button, capped_panel
        from ..console.tokens import px

        panel = capped_panel(
            self.theme.scale, 'commandConsoleLeagueControlDeck',
            'LADDER COMMAND // SEASON, MAP, FILTER', 'SELECT PUBLIC RECORDS', 2)
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(px(10, self.theme.scale))
        grid.setVerticalSpacing(px(5, self.theme.scale))
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)

        grid.addWidget(self._command_label('SEASON'), 0, 0)
        season = QComboBox()
        season.setObjectName('commandConsoleLeagueSeason')
        season.setProperty('consoleRole', 'compactCombo')
        season.setProperty('accentIndex', '2')
        season.setMinimumWidth(px(160, self.theme.scale))
        season.currentTextChanged.connect(self.league.update_seasonal_records)
        season.currentTextChanged.connect(self._season_selected)
        grid.addWidget(season, 1, 0)
        self.widgets.variant_combo = season

        grid.addWidget(self._command_label('FILTER HANDLE'), 0, 1)
        search = QLineEdit()
        search.setObjectName('leagueSearchEntry')
        search.setProperty('consoleRole', 'leagueSearch')
        search.setPlaceholderText(tr('name@handle'))
        search.setClearButtonEnabled(True)
        search.textChanged.connect(
            lambda text: setattr(self.league, 'current_filter_term', text))
        grid.addWidget(search, 1, 1)
        self.widgets.ladder_search = search

        search_actions = QHBoxLayout()
        search_actions.setContentsMargins(0, 0, 0, 0)
        search_actions.setSpacing(px(6, self.theme.scale))
        search_button = action_button('SEARCH', 'leagueSearchButton', 2, primary=True)
        search_button.clicked.connect(self.league.search_league_table)
        clear_button = action_button('RESET', 'leagueClearButton', 2)
        clear_button.clicked.connect(self.clear_filter_callback)
        open_local = action_button('OPEN LOCAL', 'leagueOpenLocalButton', 2)
        open_local.clicked.connect(self.sidebar.browse_and_analyze_log)
        search_actions.addWidget(search_button)
        search_actions.addWidget(clear_button)
        search_actions.addWidget(open_local)
        grid.addLayout(search_actions, 1, 2)
        self.widgets.league_search_button = search_button
        self.widgets.league_clear_button = clear_button
        self.widgets.league_open_local_button = open_local

        grid.addWidget(self._command_label('AVAILABLE LADDERS'), 2, 0, 1, 3)
        ladders = QListWidget()
        ladders.setObjectName('commandConsoleLeagueLadders')
        ladders.setProperty('consoleRole', 'leagueSelector')
        ladders.setCursor(Qt.CursorShape.PointingHandCursor)
        ladders.setMinimumHeight(px(70, self.theme.scale))
        ladders.setMaximumHeight(px(100, self.theme.scale))
        ladders.itemClicked.connect(self.league.show_ladder)
        ladders.itemClicked.connect(self._ladder_selected)
        grid.addWidget(ladders, 3, 0, 1, 3)
        self.widgets.ladder_selector = ladders

        panel.body_layout.addLayout(grid)
        return panel.frame

    def _command_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setProperty('consoleRole', 'eyebrow')
        return label

    def _season_selected(self, season: str) -> None:
        if not season:
            self._set_command_status('AWAITING SEASON')
            return
        self._set_command_status(f'SEASON // {season.upper()}')

    def _ladder_selected(self, ladder) -> None:
        difficulty = getattr(ladder, 'difficulty', None)
        suffix = f' // {difficulty.upper()}' if difficulty else ''
        self._set_command_status(f'LADDER // {ladder.text().upper()}{suffix}')

    def _set_command_status(self, text: str) -> None:
        if self._command_status is None:
            return
        self._command_status.setText(text)
        self._command_status.setToolTip(text.replace(' // ', ': '))

    @staticmethod
    def _set_league_meters(table, button, enabled: bool) -> None:
        table.setMeterMode(enabled)
        button.setProperty('visualActive', bool(enabled))
        from ..console.tokens import refresh_style
        refresh_style(button, descendants=False)

    def _create_search_bar(self):
        search_bar = create_entry(
            self.theme, placeholder=tr('name@handle'), style_override={'margin-top': 0})
        search_bar.setObjectName('leagueSearchEntry')
        search_bar.textChanged.connect(
            lambda text: setattr(self.league, 'current_filter_term', text))
        self.widgets.ladder_search = search_bar
        return search_bar

    def _create_search_buttons(self, separator: str = '•'):
        search_style = {
            tr('Search'): {'callback': self.league.search_league_table},
            tr('Clear'): {
                'callback': self.clear_filter_callback,
                'style': {'margin-right': 0},
            },
        }
        layout, buttons = create_button_series(
            self.theme, search_style, 'button', seperator=separator, ret=True)
        self.widgets.league_search_button = buttons[0]
        self.widgets.league_clear_button = buttons[1]
        return layout, buttons

    def _create_action_buttons(self, separator: str = '•'):
        action_style = {
            tr('Open Local Log...'): {'callback': self.sidebar.browse_and_analyze_log},
            tr('Open Selected Parse'): {'callback': self.league.download_and_view_combat},
            tr('Save Selected Parse...'): {'callback': self.league.download_and_save_combat},
            tr('More'): {
                'callback': self.league.extend_ladder,
                'style': {'margin-right': 0},
            },
        }
        layout, buttons = create_button_series(
            self.theme, action_style, 'button', seperator=separator, ret=True)
        self.widgets.league_open_local_button = buttons[0]
        self.widgets.league_open_parse_button = buttons[1]
        self.widgets.league_save_parse_button = buttons[2]
        self.widgets.league_more_button = buttons[3]
        return layout, buttons

    def _build_default_controls(self) -> QGridLayout:
        controls = QGridLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(0)
        controls.setColumnStretch(2, 1)
        controls.addWidget(self._create_search_bar(), 0, 0, alignment=AVCENTER)
        search_layout, _ = self._create_search_buttons()
        controls.addLayout(search_layout, 0, 1, alignment=AVCENTER)
        action_layout, _ = self._create_action_buttons()
        controls.addLayout(action_layout, 0, 3, alignment=AVCENTER)
        return controls
