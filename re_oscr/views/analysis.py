"""Functional Analysis presentation shared by both built-in themes."""

from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QLayout, QSplitter, QTabWidget, QTreeView,
    QVBoxLayout)

from OSCR import HEAL_TREE_HEADER, TREE_HEADER

from ..datamodels import TreeModel, TreeSelectionModel
from ..themes.command_console import command_console_accents
from ..translation import tr
from ..widgetbuilder import (
    ABOTTOM, ACENTER, AHCENTER, ARIGHT, ATOP, AVCENTER, OVERTICAL, SMAXMIN, SMINMAX,
    create_button_series, create_combo_box, create_frame, create_icon_button)
from ..widgets import AnalysisPlot


class AnalysisView:
    """Build Analysis without owning parser data or interaction behavior."""

    def __init__(
            self, theme, config, settings, widgets, parser, tables, copy_callback,
            command_console: bool):
        self.theme = theme
        self.config = config
        self.settings = settings
        self.widgets = widgets
        self.parser = parser
        self.tables = tables
        self.copy_callback = copy_callback
        self.command_console = command_console
        self.accents = command_console_accents(theme)
        self.mode_accents = (
            self.accents[0], self.accents[4], self.accents[3], self.accents[2])

    def build(self, parent_frame: QFrame) -> None:
        graph_frames = [self._create_content_frame(f'analysisGraphMode{index + 1}')
                        for index in range(4)]
        tree_frames = [self._create_content_frame(f'analysisTreeMode{index + 1}')
                       for index in range(4)]

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
            'commandConsoleAnalysisSplitter' if self.command_console else 'defaultAnalysisSplitter')
        splitter.setStyleSheet(self.theme.get_style_class('QSplitter', 'splitter'))
        if self.command_console:
            splitter.setStyleSheet(
                splitter.styleSheet()
                + 'QSplitter#commandConsoleAnalysisSplitter::handle {'
                  'background-color: #263944; min-height: 7px; margin: 3px 18px;}')
        splitter.setChildrenCollapsible(False)
        self.widgets.analysis_splitter = splitter
        if self.command_console:
            layout.addWidget(splitter, 1)
        else:
            layout.addWidget(splitter)

        graph_tabber = self._build_tabber(
            parent_frame, graph_frames, 'commandConsoleAnalysisGraphPanel', 'defaultAnalysisGraph')
        self.widgets.analysis_graph_tabber = graph_tabber
        splitter.addWidget(graph_tabber)
        if not self.settings.analysis_graph:
            self.widgets.analysis_graph_button.flip()

        tree_tabber = self._build_tabber(
            parent_frame, tree_frames, 'commandConsoleAnalysisTelemetryPanel',
            'defaultAnalysisTelemetry')
        self.widgets.analysis_tree_tabber = tree_tabber
        splitter.addWidget(tree_tabber)

        self._build_switcher(switch_layout)
        models = (
            (self.parser.damage_out_model, False),
            (self.parser.damage_in_model, False),
            (self.parser.heal_out_model, True),
            (self.parser.heal_in_model, True),
        )
        analysis_tables = [
            self._create_analysis_tab(graph_frame, tree_frame, model, is_heal)
            for graph_frame, tree_frame, (model, is_heal)
            in zip(graph_frames, tree_frames, models)
        ]
        self.tables.damage_out_table = analysis_tables[0][0]
        self.tables.damage_in_table = analysis_tables[1][0]
        self.tables.heal_out_table = analysis_tables[2][0]
        self.tables.heal_in_table = analysis_tables[3][0]

        parent_frame.setLayout(layout)
        if self.settings.state__analysis_splitter:
            splitter.restoreState(self.settings.state__analysis_splitter)
        else:
            height = splitter.height()
            splitter.setSizes((height * 0.5, height * 0.5))

    def _create_content_frame(self, object_name: str) -> QFrame:
        frame = create_frame(self.theme)
        if self.command_console:
            frame.setObjectName(object_name)
            frame.setStyleSheet(
                f'QFrame#{object_name} {{background-color: #0e161d; border: none;}}')
        return frame

    def _build_heading(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName('commandConsoleAnalysisHeading')
        frame.setStyleSheet(
            'QFrame#commandConsoleAnalysisHeading {'
            f'background-color: transparent; border: none; border-left: 5px solid {self.accents[1]};}}')
        layout = QVBoxLayout()
        layout.setContentsMargins(round(15 * self.theme.scale), 0, 0, 0)
        layout.setSpacing(round(3 * self.theme.scale))
        eyebrow = QLabel('SELECTED ENCOUNTER // EVENT AND SOURCE TELEMETRY')
        eyebrow.setObjectName('commandConsoleAnalysisEyebrow')
        eyebrow.setStyleSheet(
            'color: #77dbe2; background: transparent; border: none;'
            f'font-family: Roboto Mono; font-size: {round(9 * self.theme.scale)}px;')
        layout.addWidget(eyebrow)
        title = QLabel('ANALYSIS')
        title.setObjectName('commandConsoleAnalysisTitle')
        title.setStyleSheet(
            'color: #f4efe6; background: transparent; border: none;'
            f'font-family: Overpass; font-size: {round(25 * self.theme.scale)}px; font-weight: 700;')
        layout.addWidget(title)
        frame.setLayout(layout)
        return frame

    def _build_tabber(
            self, parent_frame: QFrame, frames: list[QFrame], command_name: str,
            default_name: str) -> QTabWidget:
        tabber = QTabWidget(parent_frame)
        tabber.setObjectName(command_name if self.command_console else default_name)
        tabber.setStyleSheet(self.theme.get_style_class('QTabWidget', 'tabber'))
        if self.command_console:
            tabber.setStyleSheet(
                tabber.styleSheet()
                + f'QTabWidget#{command_name} {{background-color: #0e161d;'
                  'border: 1px solid #293944; border-radius: 12px;}')
        tabber.tabBar().hide()
        for frame, label in zip(frames, ('DOUT', 'DTAKEN', 'HOUT', 'HIN')):
            tabber.addTab(frame, label)
        return tabber

    def _build_switcher(self, switch_layout: QGridLayout) -> None:
        switch_layout.setColumnStretch(0, 1)
        switch_frame = create_frame(self.theme)
        if self.command_console:
            switch_frame.setObjectName('commandConsoleAnalysisCommandBar')
            switch_frame.setStyleSheet(
                'QFrame#commandConsoleAnalysisCommandBar {'
                'background-color: #0b1116; border: 1px solid #293944; border-radius: 12px;}')
        switch_layout.addWidget(switch_frame, 0, 1, alignment=ACENTER)
        switch_layout.setColumnStretch(1, 2)

        switch_style = {
            'default': {'margin-left': '@margin', 'margin-right': '@margin'},
            tr('Damage Out'): {
                'callback': lambda _: self.widgets.switch_analysis_tab(0),
                'align': ACENTER, 'toggle': True},
            tr('Damage Taken'): {
                'callback': lambda _: self.widgets.switch_analysis_tab(1),
                'align': ACENTER, 'toggle': False},
            tr('Heals Out'): {
                'callback': lambda _: self.widgets.switch_analysis_tab(2),
                'align': ACENTER, 'toggle': False},
            tr('Heals In'): {
                'callback': lambda _: self.widgets.switch_analysis_tab(3),
                'align': ACENTER, 'toggle': False},
        }
        switcher, buttons = create_button_series(
            self.theme, switch_style, 'tab_button', ret=True)
        if self.command_console:
            switcher.setContentsMargins(round(5 * self.theme.scale), round(5 * self.theme.scale),
                                        round(5 * self.theme.scale), round(5 * self.theme.scale))
            for index, (button, accent) in enumerate(zip(buttons, self.mode_accents)):
                button.setObjectName(f'commandConsoleAnalysisMode{index + 1}')
                button.setText(f'B{index + 1}  {button.text().upper()}')
                button.setMinimumHeight(round(38 * self.theme.scale))
                button.setStyleSheet(self._mode_button_style(accent))
        else:
            switcher.setContentsMargins(0, self.theme['defaults']['margin'], 0, 0)
        switch_frame.setLayout(switcher)
        self.widgets.analysis_menu_buttons = buttons

        copy_layout = QHBoxLayout()
        copy_layout.setContentsMargins(0, 0, 0, 0)
        copy_layout.setSpacing(self.theme['defaults']['csp'])
        copy_combobox = create_combo_box(self.theme)
        copy_combobox.setObjectName('analysisCopyMode')
        copy_combobox.addItems((
            tr('Selection'), tr('Global Max One Hit'), tr('Max One Hit'), tr('Magnitude'),
            tr('Magnitude / s')))
        copy_layout.addWidget(copy_combobox)
        self.widgets.analysis_copy_combobox = copy_combobox
        copy_button = create_icon_button(self.theme, 'copy', tr('Copy Data'))
        copy_button.setObjectName('analysisCopyButton')
        copy_button.clicked.connect(self.copy_callback)
        copy_layout.addWidget(copy_button)
        switch_layout.addLayout(copy_layout, 0, 2, alignment=ARIGHT | ABOTTOM)
        switch_layout.setColumnStretch(2, 1)

    def _create_analysis_tab(
            self, graph_frame: QFrame, tree_frame: QFrame, tree_model: TreeModel,
            is_heal_table: bool) -> tuple[QTreeView, AnalysisPlot]:
        spacing = self.theme['defaults']['csp'] * self.config.ui_scale
        graph_layout = QHBoxLayout()
        graph_layout.setContentsMargins(spacing, spacing, spacing, 0)
        graph_layout.setSpacing(spacing)

        plot_bundle_frame = create_frame(self.theme, size_policy=SMINMAX)
        plot_bundle_layout = QVBoxLayout()
        plot_bundle_layout.setContentsMargins(0, 0, 0, 0)
        plot_bundle_layout.setSpacing(0)
        plot_bundle_layout.setSizeConstraint(QLayout.SizeConstraint.SetMaximumSize)
        plot_legend_frame = create_frame(self.theme)
        plot_legend_layout = QHBoxLayout()
        plot_legend_layout.setContentsMargins(0, 0, 0, 0)
        plot_legend_layout.setSpacing(2 * self.theme['defaults']['margin'])
        plot_legend_frame.setLayout(plot_legend_layout)
        plot_widget = AnalysisPlot(self.theme, self.theme['plot']['color_cycler'])
        plot_widget.setStyleSheet(self.theme.get_style('plot_widget_nullifier'))
        plot_widget.setSizePolicy(SMINMAX)
        plot_bundle_layout.addWidget(plot_widget)
        plot_bundle_layout.addWidget(plot_legend_frame, alignment=AHCENTER)
        plot_bundle_frame.setLayout(plot_bundle_layout)
        graph_layout.addWidget(plot_bundle_frame, stretch=1)

        plot_button_frame = create_frame(self.theme, size_policy=SMAXMIN)
        plot_button_layout = QVBoxLayout()
        plot_button_layout.setContentsMargins(0, 0, 0, 0)
        plot_button_layout.setSpacing(0)
        plot_button_layout.setAlignment(AVCENTER)
        freeze_button = create_icon_button(self.theme, 'freeze', tr('Freeze Graph'))
        freeze_button.setObjectName('analysisFreezeButton')
        freeze_button.setCheckable(True)
        freeze_button.setChecked(True)
        freeze_button.clicked.connect(plot_widget.toggle_freeze)
        plot_button_layout.addWidget(freeze_button, alignment=ABOTTOM)
        clear_button = create_icon_button(self.theme, 'clear-plot', tr('Clear Graph'))
        clear_button.setObjectName('analysisClearButton')
        clear_button.clicked.connect(plot_widget.clear)
        plot_button_layout.addWidget(clear_button, alignment=ATOP)
        plot_button_frame.setLayout(plot_button_layout)
        graph_layout.addWidget(plot_button_frame, stretch=0)
        graph_frame.setLayout(graph_layout)

        tree_layout = QVBoxLayout()
        tree_layout.setContentsMargins(0, 0, 0, 0)
        tree_layout.setSpacing(0)
        tree = self.tables.create_analysis_table('tree_table')
        if is_heal_table:
            tree_model.header_data = tr(HEAL_TREE_HEADER)
        else:
            tree_model.header_data = tr(TREE_HEADER)
        tree_model.init_fonts(
            self.theme.get_font('tree_table_header'), self.theme.get_font('tree_table'),
            self.theme.get_font('tree_table_cells'))
        tree.setModel(tree_model)
        tree.setSelectionModel(TreeSelectionModel(tree_model))
        tree.clicked.connect(lambda index, plot=plot_widget: plot.add_bar(index.internalPointer()))
        tree_layout.addWidget(tree)
        tree_frame.setLayout(tree_layout)
        return tree, plot_widget

    def _mode_button_style(self, accent: str) -> str:
        large = round(17 * self.theme.scale)
        small = round(4 * self.theme.scale)
        font_size = round(12 * self.theme.scale)
        return (
            'QPushButton {'
            'background-color: transparent; color: #aebdc5; border: 1px solid transparent;'
            f'border-top-left-radius: {large}px; border-top-right-radius: {small}px;'
            f'border-bottom-right-radius: {large}px; border-bottom-left-radius: {small}px;'
            'padding: 6px 14px;'
            f'font-family: Overpass; font-size: {font_size}px; font-weight: 600;}}'
            f'QPushButton:hover {{color: #f4efe6; border-color: {accent};}}'
            f'QPushButton:checked {{color: #11171b; background-color: {accent};'
            f'border: 1px solid {accent}; border-bottom: 4px solid #141b20;}}')
