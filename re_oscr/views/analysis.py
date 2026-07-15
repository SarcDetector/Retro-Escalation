"""Functional Analysis presentation shared by both built-in themes."""

from PySide6.QtCore import Qt, QTimer

from PySide6.QtWidgets import (
    QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLayout, QLineEdit, QSplitter,
    QScrollArea, QSizePolicy, QTabWidget, QTreeView, QVBoxLayout)

from OSCR import HEAL_TREE_HEADER, TREE_HEADER

from ..datamodels import TreeModel, TreeSelectionModel
from ..translation import tr
from ..widgetbuilder import (
    ABOTTOM, ACENTER, AHCENTER, ARIGHT, ATOP, AVCENTER, OVERTICAL, SMAXMIN, SMINMAX,
    create_button_series, create_combo_box, create_frame, create_icon_button)
from ..widgets import AnalysisPlot


class AnalysisView:
    """Build Analysis without owning parser data or interaction behavior."""

    _MODE_LABELS = ('DAMAGE OUT', 'DAMAGE TAKEN', 'HEALS OUT', 'HEALS IN')
    _MODE_CODES = ('B1', 'B2', 'B3', 'B4')

    def __init__(
            self, theme, config, settings, widgets, parser, tables, copy_callback,
            command_console: bool, workbench_controller=None):
        self.theme = theme
        self.config = config
        self.settings = settings
        self.widgets = widgets
        self.parser = parser
        self.tables = tables
        self.copy_callback = copy_callback
        self.command_console = command_console
        self.workbench_controller = workbench_controller
        # Workspace modes belong to Analysis, so the active state uses the
        # Analysis rail colour instead of borrowing unrelated page accents.
        self.mode_accent_indices = (1, 1, 1, 1)
        self._command_heading_title: QLabel | None = None
        self._analysis_presentation_mode = 'simple'

    def build(self, parent_frame: QFrame) -> None:
        if self.command_console:
            self._build_command_console(parent_frame)
        else:
            self._build_legacy(parent_frame)

    def _build_command_console(self, parent_frame: QFrame) -> None:
        from ..console.components import embedded_panel
        from ..console.tokens import px

        layout = QVBoxLayout()
        layout.setContentsMargins(*([px(12, self.theme.scale)] * 4))
        layout.setSpacing(px(10, self.theme.scale))
        layout.addWidget(self._build_command_heading())
        self.parser.combat_displayed.connect(self._update_command_heading)
        layout.addWidget(self._build_command_switcher())

        splitter = QSplitter(OVERTICAL)
        splitter.setObjectName('commandConsoleAnalysisSplitter')
        splitter.setChildrenCollapsible(False)
        self.widgets.analysis_splitter = splitter
        layout.addWidget(splitter, 1)

        graph_surfaces = [
            embedded_panel(
                self.theme.scale, f'commandConsoleAnalysisGraphMode{index + 1}',
                f'PLOT // {self._MODE_CODES[index]} ACTIVE SELECTION', label, 1)
            for index, label in enumerate(self._MODE_LABELS)
        ]
        for surface in graph_surfaces:
            # At the supported 720px window the plot needs the vertical pixels more than a
            # second, redundant caption line.  Keep the mode title and action controls while
            # compacting only the graph panels; telemetry retains its two-line identity cap.
            surface.eyebrow.hide()
            surface.cap.layout().setContentsMargins(
                px(10, self.theme.scale), px(4, self.theme.scale),
                px(10, self.theme.scale), px(4, self.theme.scale))
            surface.body_layout.setContentsMargins(
                px(8, self.theme.scale), px(4, self.theme.scale),
                px(8, self.theme.scale), px(4, self.theme.scale))
        graph_tabber = self._build_command_tabber(
            parent_frame, [surface.frame for surface in graph_surfaces],
            'commandConsoleAnalysisGraphPanel')
        # Keep the chart useful at the supported 1280x720 minimum without reducing
        # the telemetry tree to a single visible row.
        graph_tabber.setMinimumHeight(px(150, self.theme.scale))
        self.widgets.analysis_graph_tabber = graph_tabber
        splitter.addWidget(graph_tabber)

        tree_frames = [self._create_command_page() for _ in range(4)]
        telemetry_surface = embedded_panel(
            self.theme.scale, 'commandConsoleAnalysisTelemetryPanel',
            'ACTORS → ABILITIES → EVENTS // EXPAND FOR DETAIL', 'COMBAT BREAKDOWN', 1)
        self._add_telemetry_lens_controls(telemetry_surface.cap.layout())
        self._add_copy_controls(telemetry_surface.cap.layout(), command_console=True)
        tree_tabber = self._build_command_tabber(
            telemetry_surface.body, tree_frames, 'commandConsoleAnalysisTelemetryTabs')
        telemetry_surface.body_layout.addWidget(tree_tabber)
        telemetry_surface.frame.setMinimumHeight(px(175, self.theme.scale))
        self.widgets.analysis_tree_tabber = tree_tabber
        splitter.addWidget(telemetry_surface.frame)
        # The graph stays persistently available, but the telemetry tree is the
        # primary work surface.  The splitter remains user-adjustable for an
        # investigation that needs a larger plot.
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)

        analysis_tables = []
        plots = []
        for index, (graph_surface, tree_frame, (model, is_heal)) in enumerate(zip(
                graph_surfaces, tree_frames, self._models())):
            tree, plot = self._create_command_analysis_tab(
                graph_surface, tree_frame, model, is_heal, index)
            analysis_tables.append(tree)
            plots.append(plot)
        self._store_analysis_tables(analysis_tables)
        self._select_telemetry_lens('CORE')
        self.widgets.analysis_plots = plots
        if self.workbench_controller is not None:
            self.workbench_controller.attach_controls()
        self._set_analysis_presentation_mode(
            getattr(self.settings, 'analysis_presentation_mode', 'simple'), persist=False)

        parent_frame.setLayout(layout)
        self._restore_splitter(splitter)
        if not self.settings.analysis_graph:
            self.widgets.analysis_graph_button.flip()

    def _build_legacy(self, parent_frame: QFrame) -> None:
        graph_frames = [create_frame(self.theme) for _ in range(4)]
        tree_frames = [create_frame(self.theme) for _ in range(4)]

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        switch_layout = QGridLayout()
        switch_layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(switch_layout)

        splitter = QSplitter(OVERTICAL)
        splitter.setObjectName('defaultAnalysisSplitter')
        splitter.setStyleSheet(self.theme.get_style_class('QSplitter', 'splitter'))
        splitter.setChildrenCollapsible(False)
        self.widgets.analysis_splitter = splitter
        layout.addWidget(splitter)

        graph_tabber = self._build_legacy_tabber(
            parent_frame, graph_frames, 'defaultAnalysisGraph')
        self.widgets.analysis_graph_tabber = graph_tabber
        splitter.addWidget(graph_tabber)

        tree_tabber = self._build_legacy_tabber(
            parent_frame, tree_frames, 'defaultAnalysisTelemetry')
        self.widgets.analysis_tree_tabber = tree_tabber
        splitter.addWidget(tree_tabber)

        self._build_legacy_switcher(switch_layout)
        analysis_tables = []
        plots = []
        for graph_frame, tree_frame, (model, is_heal) in zip(
                graph_frames, tree_frames, self._models()):
            tree, plot = self._create_legacy_analysis_tab(
                graph_frame, tree_frame, model, is_heal)
            analysis_tables.append(tree)
            plots.append(plot)
        self._store_analysis_tables(analysis_tables)
        self.widgets.analysis_plots = plots

        parent_frame.setLayout(layout)
        self._restore_splitter(splitter)
        if not self.settings.analysis_graph:
            self.widgets.analysis_graph_button.flip()

    def _models(self) -> tuple[tuple[TreeModel, bool], ...]:
        return (
            (self.parser.damage_out_model, False),
            (self.parser.damage_in_model, False),
            (self.parser.heal_out_model, True),
            (self.parser.heal_in_model, True),
        )

    def _store_analysis_tables(self, tables: list[QTreeView]) -> None:
        self.tables.damage_out_table = tables[0]
        self.tables.damage_in_table = tables[1]
        self.tables.heal_out_table = tables[2]
        self.tables.heal_in_table = tables[3]

    def _restore_splitter(self, splitter: QSplitter) -> None:
        if self.settings.state__analysis_splitter:
            splitter.restoreState(self.settings.state__analysis_splitter)
        elif self.command_console:
            # Construction happens before the window has its final height.  Apply the
            # chart-led default once the shown window has a real geometry.
            QTimer.singleShot(0, lambda: self._balance_command_splitter(splitter))
        else:
            height = splitter.height()
            splitter.setSizes((height * 0.5, height * 0.5))

    def _balance_command_splitter(self, splitter: QSplitter) -> None:
        from ..console.tokens import px

        available = max(2, splitter.height() - splitter.handleWidth())
        # Keep a readable live graph strip while giving the drill-down tree the
        # majority of the first-run workspace.
        compact = available < px(480, self.theme.scale)
        upper = round(available * (0.42 if compact else 0.38))
        splitter.setSizes((upper, available - upper))

    def _build_command_heading(self) -> QFrame:
        from ..console.components import cap_line

        panel = cap_line(
            self.theme.scale, 'commandConsoleAnalysisHeading',
            'SELECTED ENCOUNTER // EVENT AND SOURCE TELEMETRY',
            'AWAITING ENCOUNTER', 1)
        panel.eyebrow.setObjectName('commandConsoleAnalysisEyebrow')
        panel.title.setObjectName('commandConsoleAnalysisTitle')
        self._command_heading_title = panel.title
        return panel.frame

    def _update_command_heading(self, combat) -> None:
        """Show selected-combat identity without altering parser-owned data."""
        if self._command_heading_title is None:
            return
        map_name = str(getattr(combat, 'map', '') or '').strip()
        difficulty = str(getattr(combat, 'difficulty', '') or '').strip()
        if map_name:
            title = map_name.upper()
            if difficulty:
                title = f'{title} [{difficulty.upper()}]'
        else:
            title = 'UNIDENTIFIED ENCOUNTER'
        self._command_heading_title.setText(title)

    def _build_command_switcher(self) -> QFrame:
        from ..console.components import action_button, chip, mode_button
        from ..console.tokens import px

        deck = QFrame()
        deck.setObjectName('commandConsoleAnalysisCommandDeck')
        deck.setProperty('consoleRole', 'analysisCommandDeck')
        deck_layout = QVBoxLayout()
        deck_layout.setContentsMargins(0, 0, 0, 0)
        deck_layout.setSpacing(0)

        mode_row = QFrame()
        mode_row.setObjectName('commandConsoleAnalysisModeRow')
        mode_row.setProperty('consoleRole', 'analysisModeRow')
        mode_layout = QHBoxLayout()
        mode_layout.setContentsMargins(
            px(8, self.theme.scale), px(6, self.theme.scale),
            px(8, self.theme.scale), px(6, self.theme.scale))
        mode_layout.setSpacing(px(8, self.theme.scale))
        buttons = []
        for index, (code, label, accent_index) in enumerate(zip(
                self._MODE_CODES, self._MODE_LABELS, self.mode_accent_indices)):
            button = mode_button(
                self.theme.scale, code, label, accent_index,
                f'commandConsoleAnalysisMode{index + 1}')
            button.clicked.connect(
                lambda _checked=False, tab_index=index:
                self.widgets.switch_analysis_tab(tab_index))
            button.setChecked(index == 0)
            button.setProperty('visualActive', index == 0)
            button.setMinimumHeight(px(36, self.theme.scale))
            mode_layout.addWidget(button, 1)
            buttons.append(button)
        mode_row.setLayout(mode_layout)
        self.widgets.analysis_menu_buttons = buttons
        deck_layout.addWidget(mode_row)

        presentation_row = QFrame()
        presentation_row.setObjectName('commandConsoleAnalysisPresentationRow')
        presentation_row.setProperty('consoleRole', 'analysisPresentationRow')
        presentation_layout = QHBoxLayout()
        presentation_layout.setContentsMargins(
            px(10, self.theme.scale), px(3, self.theme.scale),
            px(10, self.theme.scale), px(3, self.theme.scale))
        presentation_layout.setSpacing(px(8, self.theme.scale))
        presentation_label = QLabel('ANALYSIS VIEW //')
        presentation_label.setProperty('consoleRole', 'eyebrow')
        presentation_layout.addWidget(presentation_label)

        simple_button = action_button('SIMPLE', 'analysisSimpleMode', 1, primary=True)
        advanced_button = action_button('ADVANCED', 'analysisAdvancedMode', 1)
        for button, mode in ((simple_button, 'simple'), (advanced_button, 'advanced')):
            button.setCheckable(True)
            button.clicked.connect(
                lambda _checked=False, selected=mode:
                self._set_analysis_presentation_mode(selected))
            presentation_layout.addWidget(button)
        presentation_layout.addStretch(1)

        truth_chip = chip('PARSER TRUTH', 'analysisParserTruthChip')
        truth_chip.setProperty('status', 'truth')
        presentation_layout.addWidget(truth_chip)
        self.widgets.analysis_truth_chip = truth_chip

        modified_chip = chip('MODIFIED VIEW', 'analysisModifiedViewChip')
        modified_chip.setProperty('status', 'modified')
        modified_chip.setProperty('accentIndex', '1')
        presentation_layout.addWidget(modified_chip)
        self.widgets.analysis_modified_chip = modified_chip

        count_chip = chip('NO COMBAT', 'analysisWorkbenchEventCount')
        presentation_layout.addWidget(count_chip)
        self.widgets.analysis_event_count_chip = count_chip

        reset_button = action_button('RESET', 'analysisWorkbenchReset', 1)
        reset_button.setToolTip('Reset all Analysis modifiers to parser truth')
        presentation_layout.addWidget(reset_button)
        self.widgets.analysis_reset_button = reset_button

        presentation_row.setLayout(presentation_layout)
        self.widgets.analysis_presentation_buttons = [simple_button, advanced_button]
        deck_layout.addWidget(presentation_row)

        modifier_bar = QFrame()
        modifier_bar.setObjectName('commandConsoleAnalysisModifierBar')
        modifier_bar.setProperty('consoleRole', 'modifierBar')
        modifier_layout = QVBoxLayout()
        modifier_layout.setContentsMargins(0, 0, 0, 0)
        modifier_layout.setSpacing(0)

        filter_row = QFrame()
        filter_row.setProperty('consoleRole', 'workbenchFilterRow')
        filter_layout = QHBoxLayout()
        filter_layout.setContentsMargins(
            px(10, self.theme.scale), px(3, self.theme.scale),
            px(10, self.theme.scale), px(3, self.theme.scale))
        filter_layout.setSpacing(px(8, self.theme.scale))
        modifier_label = QLabel('WORKBENCH // FILTER')
        modifier_label.setProperty('consoleRole', 'eyebrow')
        filter_layout.addWidget(modifier_label)

        filter_scope = QComboBox()
        filter_scope.setObjectName('analysisWorkbenchScope')
        filter_scope.setProperty('consoleRole', 'compactCombo')
        for label, key in (
                ('ANY FIELD', 'ANY'), ('OWNER', 'OWNER'), ('SOURCE', 'SOURCE'),
                ('TARGET', 'TARGET'), ('EVENT', 'EVENT'), ('TYPE', 'TYPE'),
                ('FLAG', 'FLAG'), ('MIN MAGNITUDE', 'MIN_MAGNITUDE'),
                ('MAX MAGNITUDE', 'MAX_MAGNITUDE')):
            filter_scope.addItem(label, key)
        filter_scope.setToolTip(
            'Choose a quick-search field or a structured filter to add')
        filter_scope.setMinimumWidth(px(112, self.theme.scale))
        self.widgets.analysis_filter_scope = filter_scope
        filter_layout.addWidget(filter_scope)

        filter_entry = QLineEdit()
        filter_entry.setObjectName('analysisWorkbenchFilter')
        filter_entry.setProperty('consoleRole', 'workbenchFilter')
        filter_entry.setPlaceholderText('SEARCH COMBAT EVENTS')
        filter_entry.setClearButtonEnabled(True)
        filter_entry.setMinimumWidth(px(210, self.theme.scale))
        filter_layout.addWidget(filter_entry, 1)
        self.widgets.analysis_filter_entry = filter_entry

        add_filter_button = action_button(
            'ADD FILTER', 'analysisWorkbenchAddFilter', 1, primary=True)
        add_filter_button.setToolTip(
            'Add the selected field and value as an active Analysis filter')
        add_filter_button.setMaximumWidth(px(104, self.theme.scale))
        filter_layout.addWidget(add_filter_button)
        self.widgets.analysis_filter_add_button = add_filter_button

        filter_row.setLayout(filter_layout)
        self.widgets.analysis_filter_row = filter_row
        modifier_layout.addWidget(filter_row)

        # Structured clauses are intentionally a second, normally absent line.
        # The controller owns clause creation/removal; the view only supplies a
        # compact scrollable surface that can accept an arbitrary number of chip
        # buttons without forcing the command deck wider than the 1280px target.
        clause_row = QFrame()
        clause_row.setObjectName('analysisWorkbenchClauseRow')
        clause_row.setProperty('consoleRole', 'workbenchClauseRow')
        clause_row_layout = QHBoxLayout()
        clause_row_layout.setContentsMargins(
            px(10, self.theme.scale), px(2, self.theme.scale),
            px(10, self.theme.scale), px(2, self.theme.scale))
        clause_row_layout.setSpacing(px(8, self.theme.scale))

        clause_label = QLabel('ACTIVE MODIFIERS //')
        clause_label.setObjectName('analysisWorkbenchClauseLabel')
        clause_label.setProperty('consoleRole', 'eyebrow')
        clause_row_layout.addWidget(clause_label)

        clause_scroll = QScrollArea()
        clause_scroll.setObjectName('analysisWorkbenchClauseScroll')
        clause_scroll.setProperty('consoleRole', 'workbenchClauseScroll')
        clause_scroll.setFrameShape(QFrame.Shape.NoFrame)
        clause_scroll.setWidgetResizable(True)
        clause_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        clause_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        clause_scroll.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        clause_scroll.setFixedHeight(px(34, self.theme.scale))

        clause_container = QFrame()
        clause_container.setObjectName('analysisWorkbenchClauseContainer')
        clause_container.setProperty('consoleRole', 'workbenchClauseContainer')
        clause_container.setSizePolicy(
            QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed)
        clause_layout = QHBoxLayout()
        clause_layout.setContentsMargins(0, 0, 0, 0)
        clause_layout.setSpacing(px(6, self.theme.scale))
        clause_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        clause_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinAndMaxSize)
        clause_container.setLayout(clause_layout)
        clause_scroll.setWidget(clause_container)
        clause_row_layout.addWidget(clause_scroll, 1)
        clause_row.setLayout(clause_row_layout)
        clause_row.hide()

        self.widgets.analysis_filter_clause_row = clause_row
        self.widgets.analysis_filter_clause_scroll = clause_scroll
        self.widgets.analysis_filter_clause_container = clause_container
        self.widgets.analysis_filter_clause_layout = clause_layout
        self.widgets.analysis_filter_clause_buttons = []
        self.widgets.analysis_rule_chip_buttons = []
        modifier_layout.addWidget(clause_row)

        time_row = QFrame()
        time_row.setObjectName('analysisWorkbenchTimeRuleRow')
        time_row.setProperty('consoleRole', 'workbenchTimeRow')
        time_layout = QHBoxLayout()
        time_layout.setContentsMargins(
            px(10, self.theme.scale), px(2, self.theme.scale),
            px(10, self.theme.scale), px(2, self.theme.scale))
        time_layout.setSpacing(px(8, self.theme.scale))
        time_label = QLabel('TIME CUT // SECONDS')
        time_label.setProperty('consoleRole', 'eyebrow')
        time_layout.addWidget(time_label)

        start_entry = self._build_time_entry(
            'analysisWorkbenchStart', 'START',
            'Inclusive seconds from the beginning of the combat')
        self.widgets.analysis_start_entry = start_entry
        time_layout.addWidget(start_entry)

        separator = QLabel('TO')
        separator.setProperty('consoleRole', 'muted')
        time_layout.addWidget(separator)

        end_entry = self._build_time_entry(
            'analysisWorkbenchEnd', 'END',
            'Inclusive seconds from the beginning of the combat')
        self.widgets.analysis_end_entry = end_entry
        time_layout.addWidget(end_entry)

        inclusive = QLabel('INCLUSIVE // BLANK = FULL RANGE')
        inclusive.setProperty('consoleRole', 'muted')
        time_layout.addWidget(inclusive)
        time_layout.addStretch(1)

        rule_set_label = QLabel('RULE SET')
        rule_set_label.setProperty('consoleRole', 'eyebrow')
        time_layout.addWidget(rule_set_label)

        rule_set_selector = QComboBox()
        rule_set_selector.setObjectName('analysisWorkbenchRuleSet')
        rule_set_selector.setProperty('consoleRole', 'compactCombo')
        rule_set_selector.setProperty('accentIndex', '1')
        rule_set_selector.setToolTip(
            'Choose ordered grouping, source-reversal, and exclusion rules. '
            'This selection is remembered; every rule starts OFF on a fresh combat.')
        rule_set_selector.setMinimumWidth(px(146, self.theme.scale))
        rule_set_selector.setMaximumWidth(px(210, self.theme.scale))
        # The controller supplies only validated bundled or user rule sets.  An
        # empty shell must not imply that an unnamed rule set is active.
        rule_set_selector.setEnabled(False)
        time_layout.addWidget(rule_set_selector)
        self.widgets.analysis_rule_set_selector = rule_set_selector

        rules_button = action_button(
            'RULES', 'analysisWorkbenchRules', 1)
        rules_button.setToolTip('Open the ordered Analysis rule-set editor')
        rules_button.setMaximumWidth(px(76, self.theme.scale))
        rules_button.setEnabled(False)
        time_layout.addWidget(rules_button)
        self.widgets.analysis_rules_button = rules_button

        time_row.setLayout(time_layout)
        self.widgets.analysis_time_rule_row = time_row
        modifier_layout.addWidget(time_row)

        modifier_bar.setLayout(modifier_layout)
        deck_layout.addWidget(modifier_bar)
        deck.setLayout(deck_layout)
        return deck

    def _build_time_entry(
            self, object_name: str, placeholder: str, tooltip: str) -> QLineEdit:
        from ..console.tokens import px

        entry = QLineEdit()
        entry.setObjectName(object_name)
        entry.setProperty('consoleRole', 'workbenchFilter')
        entry.setPlaceholderText(placeholder)
        entry.setToolTip(tooltip)
        entry.setClearButtonEnabled(True)
        entry.setMaximumWidth(px(96, self.theme.scale))
        return entry

    def _build_legacy_switcher(self, switch_layout: QGridLayout) -> None:
        switch_layout.setColumnStretch(0, 1)
        switch_frame = create_frame(self.theme)
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
        switcher.setContentsMargins(0, self.theme['defaults']['margin'], 0, 0)
        switch_frame.setLayout(switcher)
        self.widgets.analysis_menu_buttons = buttons

        copy_layout = QHBoxLayout()
        copy_layout.setContentsMargins(0, 0, 0, 0)
        copy_layout.setSpacing(self.theme['defaults']['csp'])
        self._add_copy_controls(copy_layout, command_console=False)
        switch_layout.addLayout(copy_layout, 0, 2, alignment=ARIGHT | ABOTTOM)
        switch_layout.setColumnStretch(2, 1)

    def _add_copy_controls(self, layout, command_console: bool) -> None:
        copy_combobox = create_combo_box(self.theme)
        copy_combobox.setObjectName('analysisCopyMode')
        copy_combobox.addItems((
            tr('Selection'), tr('Global Max One Hit'), tr('Max One Hit'), tr('Magnitude'),
            tr('Magnitude / s')))
        if command_console:
            copy_combobox.setStyleSheet('')
            copy_combobox.setProperty('consoleRole', 'compactCombo')
        layout.addWidget(copy_combobox)
        self.widgets.analysis_copy_combobox = copy_combobox

        if command_console:
            from ..console.components import action_button

            copy_button = action_button(
                tr('Copy Data').upper(), 'analysisCopyButton', 1, primary=True)
            copy_button.setToolTip(tr('Copy Data'))
        else:
            copy_button = create_icon_button(self.theme, 'copy', tr('Copy Data'))
            copy_button.setObjectName('analysisCopyButton')
        copy_button.clicked.connect(self.copy_callback)
        layout.addWidget(copy_button)

    def _add_telemetry_lens_controls(self, layout) -> None:
        """Add Command Console metric lenses without creating another data model."""
        from ..console.components import mode_button

        lenses = (
            ('CORE', 'CORE', 'Headline combat metrics'),
            ('EVENTS', 'EVENTS', 'Attacks, misses, criticals, flanks, and ticks'),
            ('DETAIL', 'DETAIL', 'Hull, shield, base, and channel detail'),
            ('ALL', 'ALL', 'Every metric enabled in Settings'),
        )
        buttons = []
        for index, (lens, label, tooltip) in enumerate(lenses, start=1):
            button = mode_button(
                self.theme.scale, f'T{index}', label, 1,
                f'commandConsoleAnalysisLens{index}')
            button.setToolTip(tooltip)
            button.clicked.connect(
                lambda _checked=False, selected=lens: self._select_telemetry_lens(selected))
            buttons.append(button)
            layout.addWidget(button)
        self.widgets.analysis_lens_buttons = buttons

    def _select_telemetry_lens(self, lens: str) -> None:
        """Synchronise the metric control with display-only table visibility."""
        self.tables.set_analysis_display_lens(lens)
        for button in self.widgets.analysis_lens_buttons:
            active = button.text().split(maxsplit=1)[-1] == lens
            button.setChecked(active)
            button.setProperty('visualActive', active)
            self._sync_toggle_visual(button, active)

    def _build_command_tabber(
            self, parent_frame: QFrame, frames: list[QFrame], object_name: str) -> QTabWidget:
        tabber = QTabWidget(parent_frame)
        tabber.setObjectName(object_name)
        tabber.setProperty('consoleRole', 'surfaceTabs')
        tabber.tabBar().hide()
        for frame, label in zip(frames, ('DOUT', 'DTAKEN', 'HOUT', 'HIN')):
            tabber.addTab(frame, label)
        return tabber

    def _build_legacy_tabber(
            self, parent_frame: QFrame, frames: list[QFrame], object_name: str) -> QTabWidget:
        tabber = QTabWidget(parent_frame)
        tabber.setObjectName(object_name)
        tabber.setStyleSheet(self.theme.get_style_class('QTabWidget', 'tabber'))
        tabber.tabBar().hide()
        for frame, label in zip(frames, ('DOUT', 'DTAKEN', 'HOUT', 'HIN')):
            tabber.addTab(frame, label)
        return tabber

    @staticmethod
    def _create_command_page() -> QFrame:
        frame = QFrame()
        frame.setProperty('consoleRole', 'surfacePage')
        return frame

    def _create_command_analysis_tab(
            self, graph_surface, tree_frame: QFrame, tree_model: TreeModel,
            is_heal_table: bool, mode_index: int) -> tuple[QTreeView, AnalysisPlot]:
        from ..console.components import action_button
        from ..console.tokens import SURFACES

        plot_widget, plot_bundle_frame = self._build_plot_bundle(instrument=True)
        plot_widget.set_viewport_background(SURFACES['raised'])
        graph_surface.body_layout.addWidget(plot_bundle_frame)

        freeze_button = action_button('LIVE PLOT', 'analysisFreezeButton', 1)
        freeze_button.setToolTip('Live plot: select rows to add their curves')
        freeze_button.setCheckable(True)
        freeze_button.setChecked(False)
        freeze_button.setProperty('toggleAction', True)
        freeze_button.setProperty('visualActive', False)
        freeze_button.clicked.connect(plot_widget.toggle_freeze)
        freeze_button.clicked.connect(
            lambda checked, button=freeze_button:
            self._sync_graph_freeze(button, checked))
        graph_surface.cap.layout().addWidget(freeze_button)

        style_button = action_button('BARS', 'analysisPlotStyleButton', 1)
        style_button.setToolTip('Switch to a detailed grouped-bar comparison')
        style_button.clicked.connect(
            lambda _checked=False, plot=plot_widget, button=style_button:
            self._toggle_plot_style(plot, button))
        graph_surface.cap.layout().addWidget(style_button)
        self.widgets.analysis_plot_style_buttons.append(style_button)

        clear_button = action_button(
            tr('Clear Graph').upper(), 'analysisClearButton', 1)
        clear_button.setToolTip(tr('Clear Graph'))
        clear_button.clicked.connect(plot_widget.clear)
        graph_surface.cap.layout().addWidget(clear_button)

        tree = self._build_tree(tree_model, is_heal_table, command_console=True)
        plot_selection = (
            lambda index, plot=plot_widget: plot.add_bar(index.internalPointer()))
        tree.clicked.connect(plot_selection)
        tree.frozen_view.clicked.connect(plot_selection)
        tree_layout = QVBoxLayout()
        tree_layout.setContentsMargins(0, 0, 0, 0)
        tree_layout.setSpacing(0)
        tree_layout.addWidget(tree)
        tree_frame.setLayout(tree_layout)
        return tree, plot_widget

    def _create_legacy_analysis_tab(
            self, graph_frame: QFrame, tree_frame: QFrame, tree_model: TreeModel,
            is_heal_table: bool) -> tuple[QTreeView, AnalysisPlot]:
        spacing = self.theme['defaults']['csp'] * self.config.ui_scale
        graph_layout = QHBoxLayout()
        graph_layout.setContentsMargins(spacing, spacing, spacing, 0)
        graph_layout.setSpacing(spacing)

        plot_widget, plot_bundle_frame = self._build_plot_bundle()
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

        tree = self._build_tree(tree_model, is_heal_table, command_console=False)
        tree.clicked.connect(lambda index, plot=plot_widget: plot.add_bar(index.internalPointer()))
        tree_layout = QVBoxLayout()
        tree_layout.setContentsMargins(0, 0, 0, 0)
        tree_layout.setSpacing(0)
        tree_layout.addWidget(tree)
        tree_frame.setLayout(tree_layout)
        return tree, plot_widget

    def _build_plot_bundle(self, instrument: bool = False) -> tuple[AnalysisPlot, QFrame]:
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
        plot_widget = AnalysisPlot(
            self.theme, self.theme['plot']['color_cycler'],
            presentation='instrument' if instrument else 'legacy')
        plot_widget.setObjectName('commandConsoleAnalysisPlot' if instrument else 'analysisPlot')
        plot_widget.setStyleSheet(self.theme.get_style('plot_widget_nullifier'))
        plot_widget.setSizePolicy(SMINMAX)
        plot_bundle_layout.addWidget(plot_widget)
        plot_bundle_layout.addWidget(plot_legend_frame, alignment=AHCENTER)
        plot_bundle_frame.setLayout(plot_bundle_layout)
        return plot_widget, plot_bundle_frame

    @staticmethod
    def _sync_graph_freeze(button, frozen: bool) -> None:
        button.setText('FROZEN' if frozen else 'LIVE PLOT')
        button.setToolTip(
            'Graph selection is frozen' if frozen else
            'Live plot: select rows to add their curves')
        AnalysisView._sync_toggle_visual(button, frozen)

    @staticmethod
    def _toggle_plot_style(plot: AnalysisPlot, button) -> None:
        if plot.display_mode == 'line':
            plot.set_display_mode('bar')
            button.setText('LINES')
            button.setToolTip('Return to the readable live line plot')
        else:
            plot.set_display_mode('line')
            button.setText('BARS')
            button.setToolTip('Switch to a detailed grouped-bar comparison')

    def _set_analysis_presentation_mode(self, mode: str, persist: bool = True) -> None:
        """Progressively disclose advanced controls without changing their state."""
        resolved = str(mode).strip().lower()
        if resolved not in ('simple', 'advanced'):
            resolved = 'simple'
        self._analysis_presentation_mode = resolved
        if persist:
            self.settings.analysis_presentation_mode = resolved
        advanced = resolved == 'advanced'

        for button in self.widgets.analysis_presentation_buttons:
            active = button.objectName() == (
                'analysisAdvancedMode' if advanced else 'analysisSimpleMode')
            button.setChecked(active)
            self._sync_toggle_visual(button, active)

        for row in (
                self.widgets.analysis_filter_row,
                self.widgets.analysis_time_rule_row):
            if row is not None:
                row.setVisible(advanced)

        for index, button in enumerate(self.widgets.analysis_lens_buttons):
            button.setVisible(advanced or index == 0)
        for button in self.widgets.analysis_plot_style_buttons:
            button.setVisible(advanced)

        if not advanced:
            self._select_telemetry_lens('CORE')

    def _build_tree(
            self, tree_model: TreeModel, is_heal_table: bool,
            command_console: bool) -> QTreeView:
        if command_console:
            from ..console.tables import AnalysisTreeView
            table = AnalysisTreeView()
        else:
            table = None
        tree = self.tables.create_analysis_table('tree_table', table)
        if command_console:
            from ..console.tokens import px

            tree.setStyleSheet('')
            tree.header().setStyleSheet('')
            tree.setProperty('consoleRole', 'analysisTree')
            tree.setAlternatingRowColors(True)
            tree.setIndentation(px(18, self.theme.scale))
            tree.header().setFixedHeight(px(32, self.theme.scale))
            tree.header().setSortIndicatorShown(True)
        if is_heal_table:
            tree_model.header_data = tr(HEAL_TREE_HEADER)
        else:
            tree_model.header_data = tr(TREE_HEADER)
        tree_model.init_fonts(
            self.theme.get_font('tree_table_header'), self.theme.get_font('tree_table'),
            self.theme.get_font('tree_table_cells'))
        tree.setModel(tree_model)
        tree.setSelectionModel(TreeSelectionModel(tree_model))
        return tree

    @staticmethod
    def _sync_toggle_visual(button, active: bool) -> None:
        button.setProperty('visualActive', bool(active))
        from ..console.tokens import refresh_style
        refresh_style(button, descendants=False)
