"""Functional Overview presentation shared by both built-in themes."""

from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHeaderView, QHBoxLayout, QLabel, QSplitter, QTableView,
    QTabWidget, QVBoxLayout)

from ..datamodels import SortingProxy
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
            layout.addWidget(self._build_summary_deck())

        switch_layout = QGridLayout()
        switch_layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(switch_layout)
        splitter = QSplitter(OVERTICAL)
        splitter.setObjectName(
            'commandConsoleOverviewSplitter' if self.command_console else 'defaultOverviewSplitter')
        if not self.command_console:
            splitter.setStyleSheet(self.theme.get_style_class('QSplitter', 'splitter'))
        splitter.setChildrenCollapsible(False)
        self.widgets.overview_splitter = splitter
        layout.addWidget(splitter, 1)

        self.graphs.create_overview_plots(compact_labels=self.command_console)
        overview_tabber = QTabWidget(parent_frame)
        overview_tabber.setObjectName(
            'commandConsoleOverviewGraphPanel' if self.command_console else 'defaultOverviewGraph')
        if self.command_console:
            overview_tabber.setProperty('consoleRole', 'embeddedSurface')
        else:
            overview_tabber.setStyleSheet(self.theme.get_style_class('QTabWidget', 'tabber'))
        overview_tabber.tabBar().hide()
        overview_tabber.addTab(self.graphs.dps_bar_plot, 'BAR')
        overview_tabber.addTab(self.graphs.dps_graph_plot, 'DPS')
        overview_tabber.addTab(self.graphs.dmg_bar_plot, 'DMG')
        if self.command_console:
            overview_tabber.setMinimumHeight(round(120 * self.theme.scale))
        else:
            overview_tabber.setMinimumHeight(self.sidebar_width * 0.8)
        splitter.addWidget(overview_tabber)
        splitter.setStretchFactor(
            0, 3 if self.command_console else self.theme.opt.overview_graph_stretch)

        self._build_switcher(switch_layout)
        table_frame = self._build_table()
        splitter.addWidget(table_frame)
        if self.command_console:
            splitter.setStretchFactor(1, 2)
        self.tables.overview_table_frame = table_frame
        parent_frame.setLayout(layout)
        if self.settings.state__overview_splitter:
            splitter.restoreState(self.settings.state__overview_splitter)
        else:
            height = splitter.height()
            if self.command_console:
                splitter.setSizes((height * 0.58, height * 0.42))
            else:
                splitter.setSizes((height * 0.5, height * 0.5))
        self.widgets.overview_tabber = overview_tabber

    def _build_heading(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName('commandConsoleOverviewHeading')
        frame.setProperty('consoleRole', 'capLine')
        frame.setProperty('accentIndex', '0')
        layout = QHBoxLayout()
        layout.setContentsMargins(round(15 * self.theme.scale), 0, 0, 0)
        layout.setSpacing(round(14 * self.theme.scale))

        identity_layout = QVBoxLayout()
        identity_layout.setContentsMargins(0, 0, 0, 0)
        identity_layout.setSpacing(round(3 * self.theme.scale))
        eyebrow = QLabel('ACTIVE ENCOUNTER // TELEMETRY OVERVIEW')
        eyebrow.setObjectName('commandConsoleOverviewEyebrow')
        eyebrow.setProperty('consoleRole', 'eyebrow')
        identity_layout.addWidget(eyebrow)
        title = QLabel('AWAITING COMBAT DATA')
        title.setObjectName('commandConsoleOverviewTitle')
        title.setProperty('consoleRole', 'title')
        identity_layout.addWidget(title)
        meta = QLabel('SELECT OR ANALYZE A COMBAT LOG TO BEGIN')
        meta.setObjectName('commandConsoleOverviewMeta')
        meta.setProperty('consoleRole', 'muted')
        identity_layout.addWidget(meta)
        layout.addLayout(identity_layout, 1)

        context_layout = QHBoxLayout()
        context_layout.setContentsMargins(0, 0, 0, 0)
        context_layout.setSpacing(round(6 * self.theme.scale))
        context_values = list()
        for index, text in enumerate(('NO PARSE', '0 OPERATORS', '0.0S LOG')):
            from ..console.components import chip
            label = chip(text, f'commandConsoleOverviewContext{index}')
            label.setMinimumHeight(round(28 * self.theme.scale))
            context_layout.addWidget(label)
            context_values.append(label)
        layout.addLayout(context_layout)

        self.widgets.overview_encounter_title = title
        self.widgets.overview_encounter_meta = meta
        self.widgets.overview_context_values = context_values
        frame.setLayout(layout)
        return frame

    def _build_summary_deck(self) -> QFrame:
        from ..console.components import capped_panel

        deck = QFrame()
        deck.setObjectName('commandConsoleOverviewSummaryDeck')
        layout = QGridLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(round(8 * self.theme.scale))
        layout.setVerticalSpacing(round(8 * self.theme.scale))
        specifications = (
            ('TEAM DPS', 'COMBINED OUTPUT'),
            ('TOTAL DAMAGE', 'CUMULATIVE OUT'),
            ('PEAK HIT', 'LARGEST STRIKE'),
            ('TEAM HEALING', 'TOTAL RESTORED'),
        )
        value_labels = list()
        for index, (heading, detail) in enumerate(specifications):
            panel = capped_panel(
                self.theme.scale, f'commandConsoleOverviewStatCard{index}',
                f'SUMMARY // {index + 1:02d}', heading, index)
            value_label = QLabel('\u2014')
            value_label.setObjectName(f'commandConsoleOverviewStatValue{index}')
            value_label.setProperty('consoleRole', 'statValue')
            panel.body_layout.addWidget(value_label)
            detail_label = QLabel(detail)
            detail_label.setProperty('consoleRole', 'muted')
            panel.body_layout.addWidget(detail_label)
            layout.addWidget(panel.frame, 0, index)
            layout.setColumnStretch(index, 1)
            value_labels.append(value_label)
        deck.setLayout(layout)
        self.widgets.overview_stat_values = value_labels
        return deck

    def _build_switcher(self, switch_layout: QGridLayout) -> None:
        switch_layout.setColumnStretch(0, 1)
        if self.command_console:
            from ..console.components import mode_button
            switch_frame = QFrame()
            switch_frame.setObjectName('commandConsoleOverviewCommandBar')
            switch_frame.setProperty('consoleRole', 'capLine')
            switch_frame.setProperty('accentIndex', '0')
        else:
            switch_frame = create_frame(self.theme)
        switch_layout.addWidget(switch_frame, 0, 1, alignment=ACENTER)
        switch_layout.setColumnStretch(1, 2)

        if self.command_console:
            switcher = QHBoxLayout()
            switcher.setContentsMargins(round(5 * self.theme.scale), round(5 * self.theme.scale),
                                        round(5 * self.theme.scale), round(5 * self.theme.scale))
            switcher.setSpacing(round(5 * self.theme.scale))
            buttons = []
            for index, label in enumerate((tr('DPS Bar'), tr('DPS Graph'), tr('Damage Graph'))):
                button = mode_button(
                    self.theme.scale, f'A{index + 1}', label, 0,
                    f'commandConsoleOverviewGraphMode{index + 1}')
                button.clicked.connect(
                    lambda _checked=False, tab_index=index:
                    self.widgets.switch_overview_tab(tab_index))
                button.setChecked(index == 0)
                button.setMinimumHeight(round(38 * self.theme.scale))
                switcher.addWidget(button)
                buttons.append(button)
        else:
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
            switcher.setContentsMargins(0, self.theme['defaults']['margin'], 0, 0)
        switch_frame.setLayout(switcher)
        self.widgets.overview_menu_buttons = buttons

        icon_layout = QHBoxLayout()
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_layout.setSpacing(self.theme['defaults']['csp'])
        copy_button = create_icon_button(self.theme, 'copy', tr('Copy Result'))
        if self.command_console:
            copy_button.setStyleSheet('')
            copy_button.setProperty('consoleRole', 'actionButton')
            copy_button.setProperty('accentIndex', '0')
        copy_button.clicked.connect(self.parser.copy_summary_data)
        icon_layout.addWidget(copy_button)
        ladder_button = create_icon_button(self.theme, 'ladder', tr('Upload Result'))
        if self.command_console:
            ladder_button.setStyleSheet('')
            ladder_button.setProperty('consoleRole', 'actionButton')
            ladder_button.setProperty('accentIndex', '0')
        ladder_button.clicked.connect(self.league.upload_callback)
        icon_layout.addWidget(ladder_button)
        switch_layout.addLayout(icon_layout, 0, 2, alignment=ARIGHT | ABOTTOM)
        switch_layout.setColumnStretch(2, 1)

    def _build_table(self) -> QFrame:
        table_frame = QFrame() if self.command_console else create_frame(
            self.theme, size_policy=SMINMIN)
        table_frame.setSizePolicy(SMINMIN)
        table_frame.setObjectName(
            'commandConsoleOverviewTablePanel' if self.command_console else 'defaultOverviewTable')
        if self.command_console:
            table_frame.setProperty('consoleRole', 'embeddedSurface')
        if self.command_console:
            table_frame.setMinimumHeight(round(135 * self.theme.scale))
        else:
            table_frame.setMinimumHeight(self.sidebar_width * 0.4)
        table_layout = QVBoxLayout()
        panel_margin = round(7 * self.theme.scale) if self.command_console else 0
        table_layout.setContentsMargins(panel_margin, panel_margin, panel_margin, panel_margin)
        table_layout.setSpacing(round(5 * self.theme.scale) if self.command_console else 0)
        if self.command_console:
            table_layout.addWidget(self._build_table_controls())
        sorting_proxy = SortingProxy()
        self.parser.overview_table_model.init_fonts(
            self.theme.get_font('table_header'), self.theme.get_font('table'))
        sorting_proxy.setSourceModel(self.parser.overview_table_model)
        if self.command_console:
            from ..console.tables import OverviewDisplayProxy, OverviewTableView
            from ..console.tokens import ConsoleTokens

            table = OverviewTableView(ConsoleTokens.from_theme(self.theme))
            sorting_proxy.setParent(table)
            display_proxy = OverviewDisplayProxy(table)
            display_proxy.setSourceModel(sorting_proxy)
            table.setModel(display_proxy)
            self.widgets.overview_sorting_proxy = sorting_proxy
            self.widgets.overview_display_proxy = display_proxy
        else:
            table = QTableView()
            table.setObjectName('overviewTelemetryTable')
            table.horizontalHeader().setSectionResizeMode(
                QHeaderView.ResizeMode.ResizeToContents)
            table.setModel(sorting_proxy)
            self.tables.style_table(table)
        table_layout.addWidget(table)
        self.tables.overview_table = table
        self.widgets.overview_table = table
        table_frame.setLayout(table_layout)
        if self.command_console:
            self.widgets.switch_overview_metric_group(0)
        return table_frame

    def _build_table_controls(self) -> QFrame:
        from ..console.components import mode_button

        frame = QFrame()
        frame.setObjectName('commandConsoleOverviewMetricBar')
        frame.setProperty('consoleRole', 'capLine')
        frame.setProperty('accentIndex', '0')
        layout = QHBoxLayout()
        layout.setContentsMargins(
            round(7 * self.theme.scale), round(3 * self.theme.scale),
            round(7 * self.theme.scale), round(7 * self.theme.scale))
        layout.setSpacing(round(5 * self.theme.scale))

        identity_layout = QVBoxLayout()
        identity_layout.setContentsMargins(0, 0, 0, 0)
        identity_layout.setSpacing(0)
        eyebrow = QLabel('TELEMETRY MATRIX // COMPLETE DATASET')
        eyebrow.setProperty('consoleRole', 'eyebrow')
        identity_layout.addWidget(eyebrow)
        title = QLabel('CREW PERFORMANCE')
        title.setObjectName('commandConsoleOverviewTableTitle')
        title.setProperty('consoleRole', 'heading')
        identity_layout.addWidget(title)
        layout.addLayout(identity_layout, 1)

        buttons = list()
        names = ('SUMMARY', 'DAMAGE OUT', 'DAMAGE IN', 'HEALING', 'ALL METRICS')
        object_names = ('Summary', 'DamageOut', 'DamageIn', 'Healing', 'All')
        for index, (name, object_name) in enumerate(zip(names, object_names)):
            button = mode_button(
                self.theme.scale, f'T{index + 1}', name, 0,
                f'commandConsoleOverviewMetric{object_name}')
            button.clicked.connect(
                lambda _checked=False, tab_index=index:
                    self.widgets.switch_overview_metric_group(tab_index))
            layout.addWidget(button)
            buttons.append(button)
        self.widgets.overview_metric_buttons = buttons
        frame.setLayout(layout)
        return frame
