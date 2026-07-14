"""Command Console Settings presentation using the inherited settings and callbacks."""

from collections.abc import Callable, Sequence
from pathlib import Path

from OSCR import HEAL_TREE_HEADER, LIVE_TABLE_HEADER, TABLE_HEADER, TREE_HEADER
from PySide6.QtCore import QRegularExpression, QSignalBlocker, Qt
from PySide6.QtGui import QColor, QIntValidator, QRegularExpressionValidator
from PySide6.QtWidgets import (
    QColorDialog, QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QSizePolicy, QTabWidget, QVBoxLayout, QWidget)

from ..appearance import (
    COMMAND_CONSOLE_BACKGROUND_NAMES, COMMAND_CONSOLE_PALETTE_NAMES,
    COMMAND_CONSOLE_PALETTES, normalize_hex_colour)
from ..iofunctions import browse_path
from ..themes import DEFAULT_THEME_ID, available_themes
from ..themes.command_console import command_console_accents
from ..translation import tr
from ..widgetbuilder import (
    create_annotated_slider, create_button, create_combo_box, create_entry, create_label)
from ..widgets import FlipButton


class CommandSettingsView:
    """Build a compact category-based settings dashboard for Command Console."""

    def __init__(
            self, theme, settings, config, widgets, tables, live_parser,
            browse_sto_logpath: Callable, set_sto_logpath_callback: Callable,
            appearance_changed: Callable[[str], None] | None = None):
        self.theme = theme
        self.settings = settings
        self.config = config
        self.widgets = widgets
        self.tables = tables
        self.live_parser = live_parser
        self.browse_sto_logpath = browse_sto_logpath
        self.set_sto_logpath_callback = set_sto_logpath_callback
        self.appearance_changed = appearance_changed
        self.accents = command_console_accents(theme)
        self._appearance_colour_entries: list[QLineEdit] = []
        self._appearance_colour_pickers: list[QPushButton] = []
        self._appearance_palette_selector: QComboBox | None = None
        self._appearance_background_selector: QComboBox | None = None

    def build(self, parent_frame: QFrame) -> None:
        layout = QVBoxLayout()
        margin = round(12 * self.theme.scale)
        layout.setContentsMargins(margin, margin, margin, margin)
        layout.setSpacing(round(9 * self.theme.scale))
        layout.addWidget(self._build_heading())

        tabber = QTabWidget()
        tabber.setObjectName('commandConsoleSettingsTabber')
        tabber.tabBar().hide()
        tabber.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        tabber.setStyleSheet(
            'QTabWidget#commandConsoleSettingsTabber::pane {'
            'background-color: transparent; border: none;}')
        tabber.addTab(self._build_appearance_page(), 'Appearance')
        tabber.addTab(self._build_core_page(), 'Core Systems')
        tabber.addTab(self._build_live_page(), 'Live Parser')
        tabber.addTab(self._build_damage_page(), 'Damage Columns')
        tabber.addTab(self._build_heal_live_page(), 'Heal and Live Columns')
        self.widgets.settings_tabber = tabber

        layout.addWidget(self._build_navigation(tabber))
        layout.addWidget(tabber, 1)
        parent_frame.setLayout(layout)

    def _build_heading(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName('commandConsoleSettingsHeading')
        frame.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        frame.setFixedHeight(round(72 * self.theme.scale))
        frame.setStyleSheet(
            'QFrame#commandConsoleSettingsHeading {'
            f'background-color: transparent; border: none; border-left: 5px solid {self.accents[3]};}}')
        layout = QHBoxLayout()
        layout.setContentsMargins(round(15 * self.theme.scale), 0, 0, 0)

        titles = QVBoxLayout()
        titles.setContentsMargins(0, 0, 0, 0)
        titles.setSpacing(round(3 * self.theme.scale))
        eyebrow = QLabel('SYSTEM CONFIGURATION // LOCAL FRONTEND PROFILE')
        eyebrow.setStyleSheet(self._eyebrow_style())
        titles.addWidget(eyebrow)
        title = QLabel('SETTINGS')
        title.setObjectName('commandConsoleSettingsTitle')
        title.setStyleSheet(
            'color: #f4efe6; background: transparent; border: none;'
            f'font-family: Overpass; font-size: {round(25 * self.theme.scale)}px; font-weight: 700;')
        titles.addWidget(title)
        layout.addLayout(titles, 1)

        readout = QLabel('PROFILE  LOCAL\nPARSER   UNCHANGED')
        readout.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        readout.setStyleSheet(
            'color: #85d997; background: transparent; border: none;'
            f'font-family: Roboto Mono; font-size: {round(9 * self.theme.scale)}px; font-weight: 600;')
        layout.addWidget(readout)
        frame.setLayout(layout)
        return frame

    def _build_navigation(self, tabber: QTabWidget) -> QFrame:
        frame = QFrame()
        frame.setObjectName('commandConsoleSettingsNavigation')
        frame.setStyleSheet(
            'QFrame#commandConsoleSettingsNavigation {'
            'background-color: #0b1116; border: 1px solid #293944; border-radius: 11px;}')
        layout = QHBoxLayout()
        spacing = round(7 * self.theme.scale)
        layout.setContentsMargins(spacing, spacing, spacing, spacing)
        layout.setSpacing(spacing)
        labels = (
            'C1  APPEARANCE', 'C2  CORE SYSTEMS', 'C3  LIVE PARSER',
            'C4  DAMAGE TABLE', 'C5  HEAL + LIVE')
        accents = (
            self.accents[3], self.accents[0], self.accents[1],
            self.accents[2], self.accents[4])
        buttons = []
        for index, (label, accent) in enumerate(zip(labels, accents)):
            button = QPushButton(label)
            button.setObjectName(f'commandSettingsNav{index + 1}')
            button.setCheckable(True)
            button.setAutoExclusive(True)
            button.setChecked(index == 0)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setMinimumHeight(round(36 * self.theme.scale))
            button.setStyleSheet(self._navigation_button_style(accent))
            button.clicked.connect(
                lambda checked=False, page=index: checked and tabber.setCurrentIndex(page))
            layout.addWidget(button, 1)
            buttons.append(button)
        frame.setLayout(layout)
        self.widgets.settings_menu_buttons = buttons
        return frame

    def _build_appearance_page(self) -> QScrollArea:
        content = self._page_content('commandConsoleSettingsAppearancePage')
        layout = QGridLayout()
        gap = round(10 * self.theme.scale)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(gap)
        layout.setVerticalSpacing(gap)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)

        profile_panel, profile = self._panel(
            'VISUAL PROFILE', self.accents[3], 'commandConsoleAppearanceProfilePanel')
        row = 1
        theme_selector = self._combo(())
        for definition in available_themes():
            theme_selector.addItem(tr(definition.display_name), definition.theme_id)
        theme_index = theme_selector.findData(self.settings.theme_id)
        if theme_index < 0:
            theme_index = theme_selector.findData(DEFAULT_THEME_ID)
        theme_selector.setCurrentIndex(theme_index)
        theme_selector.currentIndexChanged.connect(
            lambda index: self.settings.set('theme_id', theme_selector.itemData(index)))
        self._add_field(profile, row, 'Theme:', theme_selector)
        self.widgets.theme_selector = theme_selector
        row += 1

        palette_selector = self._combo(())
        for palette_id, display_name in COMMAND_CONSOLE_PALETTE_NAMES.items():
            palette_selector.addItem(display_name, palette_id)
        palette_index = palette_selector.findData(self.settings.command_console_palette_preset)
        palette_selector.setCurrentIndex(max(0, palette_index))
        palette_selector.currentIndexChanged.connect(
            lambda index: self._apply_palette_preset(palette_selector.itemData(index)))
        self._add_field(profile, row, 'Rail Preset:', palette_selector)
        self._appearance_palette_selector = palette_selector
        self.widgets.appearance_palette_selector = palette_selector
        row += 1

        background_selector = self._combo(())
        for background_id, display_name in COMMAND_CONSOLE_BACKGROUND_NAMES.items():
            background_selector.addItem(display_name, background_id)
        background_index = background_selector.findData(
            self.settings.command_console_background_mode)
        background_selector.setCurrentIndex(max(0, background_index))
        background_selector.currentIndexChanged.connect(
            lambda index: self._set_background_mode(background_selector.itemData(index)))
        self._add_field(profile, row, 'Background:', background_selector)
        self._appearance_background_selector = background_selector
        self.widgets.appearance_background_selector = background_selector
        row += 1

        profile.addWidget(self._field_label('Background Intensity:'), row, 0)
        profile.addLayout(create_annotated_slider(
            self.theme, round(self.settings.command_console_background_opacity * 100), 0, 50,
            callback=self._set_background_opacity), row, 1)
        row += 1

        path_layout = QHBoxLayout()
        path_layout.setContentsMargins(0, 0, 0, 0)
        path_layout.setSpacing(round(7 * self.theme.scale))
        path_entry = create_entry(
            self.theme, self.settings.command_console_background_path,
            style_override={'margin-top': 0})
        path_entry.setObjectName('commandConsoleBackgroundPath')
        self._expand_field(path_entry)
        path_entry.setPlaceholderText('Select a PNG, JPG, or WebP image')
        path_entry.editingFinished.connect(
            lambda: self._set_background_path(path_entry.text()))
        path_layout.addWidget(path_entry, 1)
        browse_button = QPushButton('BROWSE')
        browse_button.setObjectName('commandConsoleBackgroundBrowse')
        browse_button.setCursor(Qt.CursorShape.PointingHandCursor)
        browse_button.setMinimumHeight(round(30 * self.theme.scale))
        browse_button.setStyleSheet(self._compact_button_style(self.accents[3]))
        browse_button.clicked.connect(lambda: self._browse_background(path_entry))
        path_layout.addWidget(browse_button)
        profile.addWidget(self._field_label('Custom Image:'), row, 0)
        profile.addLayout(path_layout, row, 1)
        self.widgets.appearance_background_path_entry = path_entry
        row += 1

        restart = QLabel('SHELL + OVERVIEW APPLY LIVE // THEME SWITCH RELAUNCHES')
        restart.setObjectName('commandConsoleThemeRestartLabel')
        restart.setWordWrap(True)
        restart.setStyleSheet(self._small_status_style(self.accents[4]))
        profile.addWidget(restart, row, 0, 1, 2)
        self.widgets.theme_restart_label = restart

        palette_panel, palette = self._panel(
            'FIVE-RAIL PALETTE', self.accents[0], 'commandConsoleAppearancePalettePanel')
        roles = ('OVERVIEW', 'ANALYSIS', 'LEAGUE', 'SETTINGS', 'LIVE PARSER')
        for index, role in enumerate(roles):
            palette.addWidget(self._field_label(f'{index + 1:02d}  {role}'), index + 1, 0)
            rail_controls = QHBoxLayout()
            rail_controls.setContentsMargins(0, 0, 0, 0)
            rail_controls.setSpacing(round(5 * self.theme.scale))
            for preset_id, colours in COMMAND_CONSOLE_PALETTES.items():
                swatch = QPushButton()
                swatch.setObjectName(
                    f'commandConsoleColourSwatch{index + 1}{preset_id.title()}')
                swatch.setToolTip(COMMAND_CONSOLE_PALETTE_NAMES[preset_id])
                swatch.setCursor(Qt.CursorShape.PointingHandCursor)
                swatch.setFixedSize(
                    round(24 * self.theme.scale), round(24 * self.theme.scale))
                swatch.setStyleSheet(self._swatch_style(colours[index]))
                swatch.clicked.connect(
                    lambda _checked=False, role_index=index, colour=colours[index]:
                        self._set_custom_colour(role_index, colour))
                rail_controls.addWidget(swatch)
            picker = QPushButton('PICK')
            picker.setObjectName(f'commandConsoleColourPicker{index + 1}')
            picker.setCursor(Qt.CursorShape.PointingHandCursor)
            picker.setMinimumHeight(round(28 * self.theme.scale))
            picker.clicked.connect(
                lambda _checked=False, role_index=index: self._pick_custom_colour(role_index))
            rail_controls.addWidget(picker)
            entry = create_entry(
                self.theme, self.settings.command_console_accents[index],
                style_override={'margin-top': 0})
            entry.setValidator(QRegularExpressionValidator(
                QRegularExpression(r'^#[0-9A-Fa-f]{6}$'), entry))
            entry.setObjectName(f'commandConsoleColourCode{index + 1}')
            entry.setMaximumWidth(round(108 * self.theme.scale))
            entry.setMinimumHeight(round(28 * self.theme.scale))
            entry.editingFinished.connect(
                lambda role_index=index, colour_entry=entry:
                    self._set_custom_colour(role_index, colour_entry.text()))
            rail_controls.addWidget(entry)
            palette.addLayout(rail_controls, index + 1, 1)
            self._appearance_colour_entries.append(entry)
            self._appearance_colour_pickers.append(picker)

        self.widgets.appearance_color_entries = self._appearance_colour_entries
        self._refresh_colour_controls()
        layout.addWidget(profile_panel, 0, 0)
        layout.addWidget(palette_panel, 0, 1)
        content.setLayout(layout)
        return self._scroll_page(content, 'commandConsoleSettingsAppearanceScroll')

    def _build_core_page(self) -> QScrollArea:
        content = self._page_content('commandConsoleSettingsCorePage')
        layout = QGridLayout()
        gap = round(10 * self.theme.scale)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(gap)
        layout.setVerticalSpacing(gap)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)

        parsing_panel, parsing = self._panel(
            'PARSING & LOG ISOLATION', self.accents[0],
            'commandConsoleParsingSettingsPanel')
        row = 1
        self._add_field(parsing, row, 'Seconds Between Combats:', self._int_entry(
            self.settings.seconds_between_combats, 1,
            lambda value: self.settings.set('seconds_between_combats', value),
            'settingsSecondsBetweenCombats'))
        row += 1
        self._add_field(parsing, row, 'Number of combats to isolate:', self._int_entry(
            self.settings.combats_to_parse, 1,
            lambda value: self.settings.set('combats_to_parse', value),
            'settingsCombatsToParse'))
        row += 1
        self._add_field(parsing, row, 'Minimum lines per combat:', self._int_entry(
            self.settings.combat_min_lines, 1,
            lambda value: self.settings.set('combat_min_lines', value),
            'settingsCombatMinLines'))
        row += 1
        parsing.addWidget(self._field_label('Graph resolution:'), row, 0)
        parsing.addLayout(create_annotated_slider(
            self.theme, self.settings.graph_resolution * 10, 1, 20,
            callback=self.settings.set_graph_resolution), row, 1)
        row += 1
        self._add_field(parsing, row, 'Scan log automatically:', self._toggle(
            self.settings.auto_scan,
            lambda: self.settings.set('auto_scan', True),
            lambda: self.settings.set('auto_scan', False),
            self.accents[0], 'settingsAutoScan'))
        row += 1
        logfile_button = create_button(self.theme, tr('STO Logfile:'), style_override={
            'margin': 0, 'font': ('Overpass', 11, 'medium'), 'border-color': '@bc',
            'border-style': 'solid', 'border-width': '@bw', 'padding-bottom': 1})
        logfile_button.setObjectName('settingsBrowseLogfile')
        logfile_button.clicked.connect(self.browse_sto_logpath)
        parsing.addWidget(logfile_button, row, 0)
        logfile_entry = create_entry(
            self.theme, self.settings.sto_log_path, style_override={'margin-top': 0})
        logfile_entry.setObjectName('settingsStoLogPath')
        self._expand_field(logfile_entry)
        logfile_entry.editingFinished.connect(
            lambda: self.set_sto_logpath_callback(logfile_entry))
        parsing.addWidget(logfile_entry, row, 1)
        self.widgets.sto_log_path_entry = logfile_entry

        interface_panel, interface = self._panel(
            'INTERFACE & RESULTS', self.accents[3],
            'commandConsoleInterfaceSettingsPanel')
        row = 1
        overview_sort = self._combo(TABLE_HEADER, self.settings.overview_sort_column)
        overview_sort.currentIndexChanged.connect(
            lambda index: self.settings.set('overview_sort_column', index))
        self._add_field(interface, row, 'Sort Overview by:', overview_sort)
        row += 1
        sort_order = self._combo((tr('Descending'), tr('Ascending')))
        sort_order.setCurrentText(self.settings.overview_sort_order)
        sort_order.currentTextChanged.connect(
            lambda text: self.settings.set('overview_sort_order', text))
        self._add_field(interface, row, 'Overview sort order:', sort_order)
        row += 1
        overview_tab = self._combo((tr('DPS Bar'), tr('DPS Graph'), tr('Damage Graph')),
                                   self.settings.first_overview_tab)
        overview_tab.currentIndexChanged.connect(
            lambda index: self.settings.set('first_overview_tab', index))
        self._add_field(interface, row, 'Default Overview Tab:', overview_tab)
        row += 1
        interface.addWidget(self._field_label('UI Scale:'), row, 0)
        interface.addLayout(create_annotated_slider(
            self.theme, round(self.settings.ui_scale * 50, 0), 25, 75,
            callback=self.settings.set_ui_scale), row, 1)
        row += 1
        language = self._combo(('English',))
        language.setCurrentIndex(0)
        language.currentIndexChanged.connect(lambda _index: self.settings.set('language', 'en'))
        self._add_field(interface, row, 'Language:', language)
        row += 1
        self._add_field(interface, row, 'League rows to fetch:', self._int_entry(
            self.settings.league_table_rows, 1,
            lambda value: self.settings.set('league_table_rows', value),
            'settingsLeagueRows', maximum=150))

        layout.addWidget(parsing_panel, 0, 0)
        layout.addWidget(interface_panel, 0, 1)
        content.setLayout(layout)
        return self._scroll_page(content, 'commandConsoleSettingsCoreScroll')

    def _build_live_page(self) -> QScrollArea:
        content = self._page_content('commandConsoleSettingsLivePage')
        layout = QGridLayout()
        gap = round(10 * self.theme.scale)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(gap)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)

        display_panel, display = self._panel(
            'WINDOW & GRAPH', self.accents[1],
            'commandConsoleLiveDisplaySettingsPanel')
        row = 1
        display.addWidget(self._field_label('Window Opacity:'), row, 0)
        display.addLayout(create_annotated_slider(
            self.theme, round(self.settings.liveparser__window_opacity * 20, 0), 1, 20,
            callback=self.settings.set_liveparser_opacity,
            style_override_slider={'::sub-page:horizontal': {'background-color': '@bc'}}), row, 1)
        row += 1
        self._add_field(display, row, 'Graph:', self._toggle(
            self.settings.liveparser__graph_active,
            lambda: self.settings.set('liveparser__graph_active', True),
            lambda: self.settings.set('liveparser__graph_active', False),
            self.accents[1], 'settingsLiveGraph'))
        row += 1
        graph_field = self._combo(
            self.config.live_graph_fields, self.settings.liveparser__graph_field)
        graph_field.currentIndexChanged.connect(
            lambda index: self.settings.set('liveparser__graph_field', index))
        self._add_field(display, row, 'Graph Field:', graph_field)
        row += 1
        player_display = self._combo(('Name', 'Handle'))
        player_display.setCurrentText(self.settings.liveparser__player_display)
        player_display.currentTextChanged.connect(
            lambda text: self.settings.set('liveparser__player_display', text))
        self._add_field(display, row, 'Player Display:', player_display)
        row += 1
        display.addWidget(self._field_label('Window Scale:'), row, 0)
        display.addLayout(create_annotated_slider(
            self.theme, round(self.settings.liveparser__window_scale * 50, 0), 25, 75,
            callback=self.settings.set_liveparser_scale), row, 1)

        behavior_panel, behavior = self._panel(
            'STARTUP & COPY', self.accents[4],
            'commandConsoleLiveBehaviorSettingsPanel')
        row = 1
        self._add_field(behavior, row, 'Default state:', self._toggle(
            self.settings.liveparser__auto_enabled,
            lambda: self.settings.set('liveparser__auto_enabled', True),
            lambda: self.settings.set('liveparser__auto_enabled', False),
            self.accents[4], 'settingsLiveDefault'))
        row += 1
        copy_format = self._combo(('Compact', 'Verbose', 'CSV'))
        copy_format.setCurrentText(self.settings.copy_format)
        copy_format.currentTextChanged.connect(
            lambda text: self.settings.set('copy_format', text))
        self._add_field(behavior, row, 'Clipboard Format:', copy_format)
        row += 1
        self._add_field(behavior, row, 'Include kills in copy:', self._toggle(
            self.settings.liveparser__copy_kills,
            lambda: self.settings.set('liveparser__copy_kills', True),
            lambda: self.settings.set('liveparser__copy_kills', False),
            self.accents[4], 'settingsLiveCopyKills'))
        row += 1
        note = QLabel(
            'Live Parser changes use the existing OSCR runtime and are stored in the local '
            'RE-OSCR profile.')
        note.setWordWrap(True)
        note.setStyleSheet(
            'color: #8fa1aa; background: transparent; border: none;'
            f'font-family: Overpass; font-size: {round(10 * self.theme.scale)}px;')
        behavior.addWidget(note, row, 0, 1, 2)

        layout.addWidget(display_panel, 0, 0)
        layout.addWidget(behavior_panel, 0, 1)
        content.setLayout(layout)
        return self._scroll_page(content, 'commandConsoleSettingsLiveScroll')

    def _build_damage_page(self) -> QScrollArea:
        content = self._page_content('commandConsoleSettingsDamagePage')
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        panel, buttons = self._column_panel(
            'DAMAGE TABLE COLUMNS', self.accents[2], tr(TREE_HEADER)[1:],
            self.settings.dmg_columns,
            lambda index, state: self.settings.dmg_columns.__setitem__(index, state),
            self.tables.update_shown_damage_columns,
            'commandConsoleDamageColumnsPanel', 'commandConsoleDamageColumnToggle',
            'APPLY DAMAGE COLUMNS')
        self.widgets.settings_damage_column_buttons = buttons
        layout.addWidget(panel)
        layout.addStretch(1)
        content.setLayout(layout)
        return self._scroll_page(content, 'commandConsoleSettingsDamageScroll')

    def _build_heal_live_page(self) -> QScrollArea:
        content = self._page_content('commandConsoleSettingsHealLivePage')
        layout = QGridLayout()
        gap = round(10 * self.theme.scale)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(gap)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)
        heal_panel, heal_buttons = self._column_panel(
            'HEAL TABLE COLUMNS', self.accents[3], tr(HEAL_TREE_HEADER)[1:],
            self.settings.heal_columns,
            lambda index, state: self.settings.heal_columns.__setitem__(index, state),
            self.tables.update_shown_heal_columns,
            'commandConsoleHealColumnsPanel', 'commandConsoleHealColumnToggle',
            'APPLY HEAL COLUMNS', columns=2)
        live_panel, live_buttons = self._column_panel(
            'LIVE PARSER COLUMNS', self.accents[4], tr(LIVE_TABLE_HEADER),
            self.settings.liveparser__columns,
            lambda index, state: self.settings.liveparser__columns.__setitem__(index, state),
            self.live_parser.update_shown_columns,
            'commandConsoleLiveColumnsPanel', 'commandConsoleLiveColumnToggle',
            'APPLY LIVE COLUMNS', columns=2)
        self.widgets.settings_heal_column_buttons = heal_buttons
        self.widgets.settings_live_column_buttons = live_buttons
        layout.addWidget(heal_panel, 0, 0)
        layout.addWidget(live_panel, 0, 1)
        content.setLayout(layout)
        return self._scroll_page(content, 'commandConsoleSettingsHealLiveScroll')

    def _apply_palette_preset(self, preset_id: str) -> None:
        if preset_id not in COMMAND_CONSOLE_PALETTE_NAMES:
            return
        self.settings.command_console_palette_preset = preset_id
        if preset_id in COMMAND_CONSOLE_PALETTES:
            self.settings.command_console_accents = list(COMMAND_CONSOLE_PALETTES[preset_id])
        self._refresh_colour_controls()
        self._notify_appearance_changed('palette')

    def _set_custom_colour(self, role_index: int, colour: str) -> None:
        current = self.settings.command_console_accents[role_index]
        normalized = normalize_hex_colour(colour) or current
        self.settings.command_console_accents[role_index] = normalized
        self.settings.command_console_palette_preset = 'custom'
        if self._appearance_palette_selector is not None:
            blocker = QSignalBlocker(self._appearance_palette_selector)
            self._appearance_palette_selector.setCurrentIndex(
                self._appearance_palette_selector.findData('custom'))
            del blocker
        self._refresh_colour_controls()
        self._notify_appearance_changed('palette')

    def _pick_custom_colour(self, role_index: int) -> None:
        current = QColor(self.settings.command_console_accents[role_index])
        selected = QColorDialog.getColor(current, None, 'Select Rail Colour')
        if selected.isValid():
            self._set_custom_colour(role_index, selected.name().upper())

    def _refresh_colour_controls(self) -> None:
        for index, (entry, picker) in enumerate(zip(
                self._appearance_colour_entries, self._appearance_colour_pickers)):
            colour = self.settings.command_console_accents[index]
            entry.setText(colour)
            picker.setStyleSheet(self._colour_picker_style(colour))

    def _browse_background(self, entry: QLineEdit) -> None:
        current = Path(entry.text()).expanduser()
        start_path = current if current.is_file() else Path.home()
        selected = browse_path(
            start_path, 'Images (*.png *.jpg *.jpeg *.webp);;Any File (*.*)')
        if selected is None:
            return
        entry.setText(str(selected))
        self.settings.command_console_background_path = str(selected)
        self.settings.command_console_background_mode = 'custom'
        if self._appearance_background_selector is not None:
            blocker = QSignalBlocker(self._appearance_background_selector)
            self._appearance_background_selector.setCurrentIndex(
                self._appearance_background_selector.findData('custom'))
            del blocker
        self._notify_appearance_changed('background')

    def _set_background_mode(self, mode: str) -> None:
        self.settings.command_console_background_mode = mode
        self._notify_appearance_changed('background')

    def _set_background_opacity(self, value: int) -> str:
        label = self.settings.set_command_background_opacity(value)
        self._notify_appearance_changed('background')
        return label

    def _set_background_path(self, path: str) -> None:
        self.settings.command_console_background_path = path
        self._notify_appearance_changed('background')

    def _notify_appearance_changed(self, change: str) -> None:
        if self.appearance_changed is not None:
            self.appearance_changed(change)

    def _column_panel(
            self, title: str, accent: str, headers: Sequence[str], states: list[bool],
            state_callback: Callable, apply_callback: Callable, object_name: str,
            button_object_name: str, apply_text: str, columns: int = 3) -> tuple[QFrame, list]:
        panel, grid = self._panel(title, accent, object_name)
        for column in range(columns):
            grid.setColumnStretch(column, 1)
        buttons = []
        for index, header in enumerate(headers):
            button = create_button(
                self.theme, str(header), 'toggle_button', toggle=states[index])
            button.setObjectName(button_object_name)
            button.setMinimumHeight(round(32 * self.theme.scale))
            button.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            button.setStyleSheet(self._column_toggle_style(accent))
            button.clicked[bool].connect(
                lambda state, column_index=index: state_callback(column_index, state))
            grid.addWidget(button, 1 + index // columns, index % columns)
            buttons.append(button)
        apply_button = QPushButton(apply_text)
        apply_button.setObjectName(f'{object_name}Apply')
        apply_button.setCursor(Qt.CursorShape.PointingHandCursor)
        apply_button.setMinimumHeight(round(36 * self.theme.scale))
        apply_button.setStyleSheet(self._apply_button_style(accent))
        apply_button.clicked.connect(apply_callback)
        final_row = 2 + (len(headers) - 1) // columns
        grid.addWidget(apply_button, final_row, 0, 1, columns)
        return panel, buttons

    def _panel(self, title: str, accent: str, object_name: str) -> tuple[QFrame, QGridLayout]:
        panel = QFrame()
        panel.setObjectName(object_name)
        panel.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        panel.setStyleSheet(
            f'QFrame#{object_name} {{background-color: #0e161d; border: 1px solid {accent};'
            'border-radius: 12px;}')
        grid = QGridLayout()
        margin = round(12 * self.theme.scale)
        grid.setContentsMargins(margin, margin, margin, margin)
        grid.setHorizontalSpacing(round(10 * self.theme.scale))
        grid.setVerticalSpacing(round(8 * self.theme.scale))
        grid.setColumnStretch(1, 1)
        grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        heading = QLabel(title)
        heading.setStyleSheet(
            f'color: {accent}; background: transparent; border: none;'
            f'font-family: Roboto Mono; font-size: {round(11 * self.theme.scale)}px;'
            'font-weight: 600;')
        grid.addWidget(heading, 0, 0, 1, 3)
        panel.setLayout(grid)
        return panel, grid

    def _add_field(self, grid: QGridLayout, row: int, label: str, widget: QWidget) -> None:
        grid.addWidget(self._field_label(label), row, 0)
        grid.addWidget(widget, row, 1)

    def _field_label(self, text: str) -> QLabel:
        label = create_label(self.theme, tr(text), 'label_subhead')
        label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        label.setStyleSheet(
            'color: #b9c6cc; background: transparent; border: none;'
            f'font-family: Overpass; font-size: {round(10 * self.theme.scale)}px;')
        return label

    def _int_entry(
            self, value: int, minimum: int, callback: Callable[[int], None],
            object_name: str, maximum: int | None = None) -> QLineEdit:
        validator = QIntValidator()
        if maximum is None:
            validator.setBottom(minimum)
        else:
            validator.setRange(minimum, maximum)
        entry = create_entry(
            self.theme, str(value), validator, style_override={'margin-top': 0})
        entry.setObjectName(object_name)
        self._expand_field(entry)
        entry.editingFinished.connect(
            lambda: entry.text() and callback(int(entry.text())))
        return entry

    def _combo(self, items: Sequence[str], current_index: int | None = None) -> QComboBox:
        combo = create_combo_box(self.theme, style_override={'font': '@small_text'})
        combo.addItems([str(item) for item in items])
        if current_index is not None:
            combo.setCurrentIndex(current_index)
        self._expand_field(combo)
        return combo

    def _toggle(
            self, initial: bool, enable_callback: Callable, disable_callback: Callable,
            accent: str, object_name: str) -> FlipButton:
        button = FlipButton(tr('Disabled'), tr('Enabled'), checkable=True)
        button.setObjectName(object_name)
        button.r_function = enable_callback
        button.l_function = disable_callback
        button.setMinimumHeight(round(32 * self.theme.scale))
        button.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        button.setStyleSheet(self._column_toggle_style(accent))
        if initial:
            button.flip()
        return button

    def _expand_field(self, widget: QWidget) -> None:
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        widget.setMinimumHeight(round(30 * self.theme.scale))

    def _page_content(self, object_name: str) -> QFrame:
        frame = QFrame()
        frame.setObjectName(object_name)
        frame.setStyleSheet(f'QFrame#{object_name} {{background: transparent; border: none;}}')
        frame.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        return frame

    def _scroll_page(self, content: QFrame, object_name: str) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setObjectName(object_name)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(
            f'QScrollArea#{object_name} {{background: transparent; border: none;}}'
            f'QScrollArea#{object_name} > QWidget > QWidget {{background: transparent;}}')
        scroll.setWidget(content)
        return scroll

    def _eyebrow_style(self) -> str:
        return (
            'color: #77dbe2; background: transparent; border: none;'
            f'font-family: Roboto Mono; font-size: {round(9 * self.theme.scale)}px;')

    def _small_status_style(self, accent: str) -> str:
        return (
            f'color: {accent}; background: transparent; border: none;'
            f'font-family: Roboto Mono; font-size: {round(8 * self.theme.scale)}px;'
            'font-weight: 600;')

    def _navigation_button_style(self, accent: str) -> str:
        large = round(15 * self.theme.scale)
        small = round(3 * self.theme.scale)
        return (
            'QPushButton {'
            'background-color: #111b22; color: #aebdc4; border: 1px solid #354650;'
            f'border-bottom: 4px solid #141b20; border-top-left-radius: {large}px;'
            f'border-top-right-radius: {small}px; border-bottom-right-radius: {large}px;'
            f'border-bottom-left-radius: {small}px; padding: 6px 11px;'
            f'font-family: Overpass; font-size: {round(10 * self.theme.scale)}px;'
            'font-weight: 700;}'
            f'QPushButton:hover {{border-color: {accent}; color: #ffffff;}}'
            f'QPushButton:checked {{background-color: {accent}; color: #10161a;'
            'border: 1px solid #f4efe6; border-bottom: 4px solid #141b20;}')

    def _column_toggle_style(self, accent: str) -> str:
        large = round(11 * self.theme.scale)
        small = round(3 * self.theme.scale)
        return (
            'QPushButton {'
            'background-color: #111b22; color: #c8d3d8;'
            f'border: 1px solid {accent}; border-top-left-radius: {large}px;'
            f'border-top-right-radius: {small}px; border-bottom-right-radius: {large}px;'
            f'border-bottom-left-radius: {small}px; padding: 5px 8px;'
            f'font-family: Overpass; font-size: {round(9 * self.theme.scale)}px;}}'
            f'QPushButton:hover {{background-color: {accent}; color: #11171b;}}'
            f'QPushButton:checked {{background-color: {accent}; color: #11171b;'
            'font-weight: 700;}')

    def _apply_button_style(self, accent: str) -> str:
        large = round(15 * self.theme.scale)
        small = round(3 * self.theme.scale)
        return (
            'QPushButton {'
            f'background-color: {accent}; color: #11171b; border: 2px solid transparent;'
            f'border-bottom: 4px solid #141b20; border-top-left-radius: {large}px;'
            f'border-top-right-radius: {small}px; border-bottom-right-radius: {large}px;'
            f'border-bottom-left-radius: {small}px; padding: 6px 12px;'
            f'font-family: Overpass; font-size: {round(10 * self.theme.scale)}px;'
            'font-weight: 700;}'
            'QPushButton:hover {border-color: #f4efe6;}')

    def _compact_button_style(self, accent: str) -> str:
        large = round(11 * self.theme.scale)
        small = round(3 * self.theme.scale)
        return (
            'QPushButton {'
            'background-color: #111b22; color: #d7e2e6;'
            f'border: 1px solid {accent}; border-top-left-radius: {large}px;'
            f'border-top-right-radius: {small}px; border-bottom-right-radius: {large}px;'
            f'border-bottom-left-radius: {small}px; padding: 4px 10px;'
            f'font-family: Overpass; font-size: {round(9 * self.theme.scale)}px;'
            'font-weight: 700;}'
            f'QPushButton:hover {{background-color: {accent}; color: #11171b;}}')

    def _swatch_style(self, colour: str) -> str:
        return (
            'QPushButton {'
            f'background-color: {colour}; border: 1px solid #d8e1e5;'
            'border-top-left-radius: 8px; border-top-right-radius: 2px;'
            'border-bottom-right-radius: 8px; border-bottom-left-radius: 2px;}'
            'QPushButton:hover {border: 2px solid #ffffff;}')

    def _colour_picker_style(self, colour: str) -> str:
        text = '#0c1115' if QColor(colour).lightness() > 145 else '#f4efe6'
        return (
            'QPushButton {'
            f'background-color: {colour}; color: {text}; border: 1px solid #d8e1e5;'
            'border-top-left-radius: 10px; border-top-right-radius: 2px;'
            'border-bottom-right-radius: 10px; border-bottom-left-radius: 2px;'
            'padding: 4px 8px; font-family: Roboto Mono; font-weight: 700;}'
            'QPushButton:hover {border: 2px solid #ffffff;}')
