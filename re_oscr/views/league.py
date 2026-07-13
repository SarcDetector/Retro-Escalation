"""Functional League Standings presentation shared by both built-in themes."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QSizePolicy, QTableView, QVBoxLayout)

from ..themes.command_console import command_console_accents
from ..translation import tr
from ..widgetbuilder import (
    AVCENTER, create_button_series, create_entry, create_frame)


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
        self.accents = command_console_accents(theme)

    def build(self, parent_frame: QFrame) -> None:
        layout = QVBoxLayout()
        if self.command_console:
            margin = round(12 * self.theme.scale)
            layout.setContentsMargins(margin, margin, margin, margin)
            layout.setSpacing(round(10 * self.theme.scale))
            layout.addWidget(self._build_heading())
        else:
            spacing = self.theme['defaults']['csp']
            layout.setContentsMargins(0, spacing, 0, spacing)
            layout.setSpacing(spacing)

        ladder_table = self._build_table()
        if self.command_console:
            layout.addWidget(self._build_table_panel(ladder_table), 1)
            layout.addWidget(self._build_command_controls())
        else:
            layout.addWidget(ladder_table, stretch=1)
            layout.addLayout(self._build_default_controls())
        parent_frame.setLayout(layout)

    def _build_heading(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName('commandConsoleLeagueHeading')
        frame.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        frame.setFixedHeight(round(76 * self.theme.scale))
        frame.setStyleSheet(
            'QFrame#commandConsoleLeagueHeading {'
            f'background-color: transparent; border: none; border-left: 5px solid {self.accents[2]};}}')
        layout = QHBoxLayout()
        layout.setContentsMargins(round(15 * self.theme.scale), 0, 0, 0)
        layout.setSpacing(round(12 * self.theme.scale))

        title_layout = QVBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(round(3 * self.theme.scale))
        eyebrow = QLabel('PUBLIC LEAGUE // VERIFIED COMBAT RECORDS')
        eyebrow.setObjectName('commandConsoleLeagueEyebrow')
        eyebrow.setStyleSheet(
            'color: #77dbe2; background: transparent; border: none;'
            f'font-family: Roboto Mono; font-size: {round(9 * self.theme.scale)}px;')
        title_layout.addWidget(eyebrow)
        title = QLabel('LEAGUE STANDINGS')
        title.setObjectName('commandConsoleLeagueTitle')
        title.setStyleSheet(
            'color: #f4efe6; background: transparent; border: none;'
            f'font-family: Overpass; font-size: {round(25 * self.theme.scale)}px; font-weight: 700;')
        title_layout.addWidget(title)
        layout.addLayout(title_layout, 1)

        readout = QLabel('NETWORK  LEAGUE API\nSOURCE   COMMUNITY RECORDS')
        readout.setObjectName('commandConsoleLeagueReadout')
        readout.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        readout.setStyleSheet(
            'color: #85d997; background: transparent; border: none;'
            f'font-family: Roboto Mono; font-size: {round(9 * self.theme.scale)}px; font-weight: 600;')
        layout.addWidget(readout)
        frame.setLayout(layout)
        return frame

    def _build_table(self) -> QTableView:
        ladder_table = QTableView()
        ladder_table.setObjectName('leagueStandingsTable')
        table_style = {'border-style': 'solid', 'border-width': '@bw', 'border-color': '@bc'}
        self.tables.style_table(ladder_table, table_style, single_row_selection=True)
        ladder_table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.league.ladder_table_model.init_fonts(
            self.theme.get_font('table_header'), self.theme.get_font('table'))
        ladder_table.setModel(self.league.ladder_table_sort)
        ladder_table.doubleClicked.connect(lambda _index: self.league.download_and_view_combat())
        self.widgets.ladder_table = ladder_table
        return ladder_table

    def _build_table_panel(self, ladder_table: QTableView) -> QFrame:
        panel = create_frame(self.theme)
        panel.setObjectName('commandConsoleLeagueTablePanel')
        panel.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        panel.setStyleSheet(
            'QFrame#commandConsoleLeagueTablePanel {'
            'background-color: #0e161d; border: 1px solid #293944; border-radius: 12px;}')
        layout = QVBoxLayout()
        margin = round(7 * self.theme.scale)
        layout.setContentsMargins(margin, margin, margin, margin)
        layout.addWidget(ladder_table)
        panel.setLayout(layout)
        return panel

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

    def _build_command_controls(self) -> QFrame:
        deck = QFrame()
        deck.setObjectName('commandConsoleLeagueControlDeck')
        deck.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        deck.setMinimumHeight(round(120 * self.theme.scale))
        deck.setStyleSheet(
            'QFrame#commandConsoleLeagueControlDeck {'
            'background-color: #0b1116; border: 1px solid #293944; border-radius: 12px;}')
        layout = QGridLayout()
        margin = round(9 * self.theme.scale)
        layout.setContentsMargins(margin, margin, margin, margin)
        layout.setHorizontalSpacing(round(9 * self.theme.scale))
        layout.setVerticalSpacing(round(7 * self.theme.scale))
        layout.setColumnStretch(1, 1)

        filter_label = self._build_control_label('FILTER RECORDS', self.accents[0])
        layout.addWidget(filter_label, 0, 0)
        search_bar = self._create_search_bar()
        search_bar.setMinimumWidth(round(250 * self.theme.scale))
        layout.addWidget(search_bar, 0, 1)
        search_layout, search_buttons = self._create_search_buttons(separator='')
        search_layout.setSpacing(round(7 * self.theme.scale))
        search_buttons[0].setText('SEARCH')
        search_buttons[1].setText('RESET')
        for button, accent in zip(search_buttons, self.accents[:2]):
            button.setMinimumHeight(round(34 * self.theme.scale))
            button.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            button.setStyleSheet(self._command_button_style(accent))
        layout.addLayout(search_layout, 0, 2)

        action_label = self._build_control_label('PARSE OPERATIONS', self.accents[2])
        layout.addWidget(action_label, 1, 0)
        action_layout, action_buttons = self._create_action_buttons(separator='')
        action_layout.setSpacing(round(7 * self.theme.scale))
        labels = ('OPEN LOCAL', 'OPEN SELECTED', 'SAVE SELECTED', 'LOAD MORE')
        accents = (
            self.accents[3], self.accents[0], self.accents[2], self.accents[4])
        for button, label, accent in zip(action_buttons, labels, accents):
            button.setText(label)
            button.setMinimumHeight(round(34 * self.theme.scale))
            button.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            button.setStyleSheet(self._command_button_style(accent))
        layout.addLayout(action_layout, 1, 1, 1, 2)

        deck.setLayout(layout)
        return deck

    def _build_control_label(self, text: str, accent: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(
            f'color: {accent}; background: transparent; border: none;'
            f'font-family: Roboto Mono; font-size: {round(10 * self.theme.scale)}px;'
            'font-weight: 600;')
        return label

    def _command_button_style(self, accent: str) -> str:
        large = round(14 * self.theme.scale)
        small = round(3 * self.theme.scale)
        font_size = round(10 * self.theme.scale)
        return (
            'QPushButton {'
            'background-color: #111b22; color: #dce6ea;'
            f'border: 1px solid {accent}; border-bottom: 4px solid #141b20;'
            f'border-top-left-radius: {large}px; border-top-right-radius: {small}px;'
            f'border-bottom-right-radius: {large}px; border-bottom-left-radius: {small}px;'
            'padding: 6px 12px;'
            f'font-family: Overpass; font-size: {font_size}px; font-weight: 700;}}'
            f'QPushButton:hover {{background-color: {accent}; color: #11171b;'
            'border-bottom-color: #273039;}'
            f'QPushButton:pressed {{background-color: {accent}; color: #ffffff;}}'
            'QPushButton:disabled {color: #60727c; border-color: #35444d;}')
