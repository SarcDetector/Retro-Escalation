"""Functional Overview presentation shared by both built-in themes."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHeaderView, QHBoxLayout, QLabel, QSplitter, QTableView, QTabWidget,
    QVBoxLayout)

from ..datamodels import SortingProxy
from ..themes.command_console import COMMAND_CONSOLE_ACCENTS
from ..translation import tr
from ..widgetbuilder import (
    ABOTTOM, ACENTER, ARIGHT, OVERTICAL, SMINMIN, create_button_series, create_frame,
    create_icon_button)


class OverviewView:
    """Build the Overview layout without owning parser or model behavior."""

    def __init__(
            self, theme, settings, widgets, graphs, parser, league, tables, sidebar_width: int,
            command_console: bool):
        self.theme = theme
        self.settings = settings
        self.widgets = widgets
        self.graphs = graphs
        self.parser = parser
        self.league = league
        self.tables = tables
        self.sidebar_width = sidebar_width
        self.command_console = command_console

    def build(self, parent_frame: QFrame) -> None:
        layout = QVBoxLayout()
        margin = round(12 * self.theme.scale) if self.command_console else 0
        layout.setContentsMargins(margin, margin, margin, margin)
        layout.setSpacing(round(10 * self.theme.scale) if self.command_console else 0)
        if self.command_console:
            layout.addWidget(self._build_heading())

        switch_layout = QGridLayout()
        switch_layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(switch_layout)
        splitter = QSplitter(OVERTICAL)
        splitter.setObjectName(
            'commandConsoleOverviewSplitter' if self.command_console else 'defaultOverviewSplitter')
        splitter.setStyleSheet(self.theme.get_style_class('QSplitter', 'splitter'))
        if self.command_console:
            splitter.setStyleSheet(
                splitter.styleSheet()
                + 'QSplitter#commandConsoleOverviewSplitter::handle {'
                  'background-color: #263944; min-height: 7px; margin: 3px 18px;}')
        splitter.setChildrenCollapsible(False)
        self.widgets.overview_splitter = splitter
        layout.addWidget(splitter)

        self.graphs.create_overview_plots()
        overview_tabber = QTabWidget(parent_frame)
        overview_tabber.setObjectName(
            'commandConsoleOverviewGraphPanel' if self.command_console else 'defaultOverviewGraph')
        overview_tabber.setStyleSheet(self.theme.get_style_class('QTabWidget', 'tabber'))
        if self.command_console:
            overview_tabber.setStyleSheet(
                overview_tabber.styleSheet()
                + 'QTabWidget#commandConsoleOverviewGraphPanel {'
                  'background-color: #0e161d; border: 1px solid #293944; border-radius: 12px;}')
        overview_tabber.tabBar().hide()
        overview_tabber.addTab(self.graphs.dps_bar_plot, 'BAR')
        overview_tabber.addTab(self.graphs.dps_graph_plot, 'DPS')
        overview_tabber.addTab(self.graphs.dmg_bar_plot, 'DMG')
        overview_tabber.setMinimumHeight(self.sidebar_width * 0.8)
        splitter.addWidget(overview_tabber)
        splitter.setStretchFactor(0, self.theme.opt.overview_graph_stretch)

        self._build_switcher(switch_layout)
        table_frame = self._build_table()
        splitter.addWidget(table_frame)
        self.tables.overview_table_frame = table_frame
        parent_frame.setLayout(layout)
        if self.settings.state__overview_splitter:
            splitter.restoreState(self.settings.state__overview_splitter)
        else:
            height = splitter.height()
            splitter.setSizes((height * 0.5, height * 0.5))
        self.widgets.overview_tabber = overview_tabber

    def _build_heading(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName('commandConsoleOverviewHeading')
        frame.setStyleSheet(
            'QFrame#commandConsoleOverviewHeading {'
            'background-color: transparent; border: none; border-left: 5px solid #ff8a2a;}')
        layout = QVBoxLayout()
        layout.setContentsMargins(round(15 * self.theme.scale), 0, 0, 0)
        layout.setSpacing(round(3 * self.theme.scale))
        eyebrow = QLabel('ACTIVE ENCOUNTER // TELEMETRY OVERVIEW')
        eyebrow.setObjectName('commandConsoleOverviewEyebrow')
        eyebrow.setStyleSheet(
            'color: #77dbe2; background: transparent; border: none;'
            f'font-family: Roboto Mono; font-size: {round(9 * self.theme.scale)}px;')
        layout.addWidget(eyebrow)
        title = QLabel('OVERVIEW')
        title.setObjectName('commandConsoleOverviewTitle')
        title.setStyleSheet(
            'color: #f4efe6; background: transparent; border: none;'
            f'font-family: Overpass; font-size: {round(25 * self.theme.scale)}px; font-weight: 700;')
        layout.addWidget(title)
        frame.setLayout(layout)
        return frame

    def _build_switcher(self, switch_layout: QGridLayout) -> None:
        switch_layout.setColumnStretch(0, 1)
        switch_frame = create_frame(self.theme)
        if self.command_console:
            switch_frame.setObjectName('commandConsoleOverviewCommandBar')
            switch_frame.setStyleSheet(
                'QFrame#commandConsoleOverviewCommandBar {'
                'background-color: #0b1116; border: 1px solid #293944; border-radius: 12px;}')
        switch_layout.addWidget(switch_frame, 0, 1, alignment=ACENTER)
        switch_layout.setColumnStretch(1, 2)

        switch_style = {
            'default': {'margin-left': '@margin', 'margin-right': '@margin'},
            tr('DPS Bar'): {
                'callback': lambda: self.widgets.switch_overview_tab(0),
                'align': ACENTER, 'toggle': True},
            tr('DPS Graph'): {
                'callback': lambda: self.widgets.switch_overview_tab(1),
                'align': ACENTER, 'toggle': False},
            tr('Damage Graph'): {
                'callback': lambda: self.widgets.switch_overview_tab(2),
                'align': ACENTER, 'toggle': False},
        }
        switcher, buttons = create_button_series(
            self.theme, switch_style, 'tab_button', ret=True)
        if self.command_console:
            switcher.setContentsMargins(round(5 * self.theme.scale), round(5 * self.theme.scale),
                                        round(5 * self.theme.scale), round(5 * self.theme.scale))
            for index, button in enumerate(buttons):
                button.setText(f'A{index + 1}  {button.text().upper()}')
                button.setMinimumHeight(round(38 * self.theme.scale))
                button.setStyleSheet(self._mode_button_style(COMMAND_CONSOLE_ACCENTS[index]))
        else:
            switcher.setContentsMargins(0, self.theme['defaults']['margin'], 0, 0)
        switch_frame.setLayout(switcher)
        self.widgets.overview_menu_buttons = buttons

        icon_layout = QHBoxLayout()
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_layout.setSpacing(self.theme['defaults']['csp'])
        copy_button = create_icon_button(self.theme, 'copy', tr('Copy Result'))
        copy_button.clicked.connect(self.parser.copy_summary_data)
        icon_layout.addWidget(copy_button)
        ladder_button = create_icon_button(self.theme, 'ladder', tr('Upload Result'))
        ladder_button.clicked.connect(self.league.upload_callback)
        icon_layout.addWidget(ladder_button)
        switch_layout.addLayout(icon_layout, 0, 2, alignment=ARIGHT | ABOTTOM)
        switch_layout.setColumnStretch(2, 1)

    def _build_table(self) -> QFrame:
        table_frame = create_frame(self.theme, size_policy=SMINMIN)
        table_frame.setObjectName(
            'commandConsoleOverviewTablePanel' if self.command_console else 'defaultOverviewTable')
        if self.command_console:
            table_frame.setStyleSheet(
                'QFrame#commandConsoleOverviewTablePanel {'
                'background-color: #0e161d; border: 1px solid #293944; border-radius: 12px;}')
        table_frame.setMinimumHeight(self.sidebar_width * 0.4)
        table_layout = QVBoxLayout()
        panel_margin = round(7 * self.theme.scale) if self.command_console else 0
        table_layout.setContentsMargins(panel_margin, panel_margin, panel_margin, panel_margin)
        sorting_proxy = SortingProxy()
        self.parser.overview_table_model.init_fonts(
            self.theme.get_font('table_header'), self.theme.get_font('table'))
        sorting_proxy.setSourceModel(self.parser.overview_table_model)
        table = QTableView()
        table.setObjectName('overviewTelemetryTable')
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.setModel(sorting_proxy)
        self.tables.style_table(table)
        table_layout.addWidget(table)
        self.tables.overview_table = table
        table_frame.setLayout(table_layout)
        return table_frame

    def _mode_button_style(self, accent: str) -> str:
        radius = round(9 * self.theme.scale)
        font_size = round(12 * self.theme.scale)
        return (
            'QPushButton {'
            'background-color: transparent; color: #aebdc5; border: 1px solid transparent;'
            f'border-radius: {radius}px; padding: 6px 12px;'
            f'font-family: Overpass; font-size: {font_size}px; font-weight: 600;}}'
            f'QPushButton:hover {{color: #f4efe6; border-color: {accent};}}'
            f'QPushButton:checked {{color: #11171b; background-color: {accent};'
            f'border-color: {accent};}}')
