from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QListView, QListWidget, QPushButton,
    QScrollArea, QSplitter, QTableView, QTabWidget)

from .widgets import FlipButton
from .config import OSCRSettings


class WidgetManager():
    """
    Class to store and manage widgets.
    """
    OVERVIEW_METRIC_COLUMN_GROUPS = (
        {0, 1, 3, 7, 8, 9, 10, 11, 14},
        {0, 1, 2, 3, 4, 7, 8, 9, 17, 18, 22, 23},
        {1, 5, 6, 10, 14, 15, 16, 19},
        {1, 10, 11, 12, 13, 20, 21},
        set(range(24)),
    )

    def __init__(self, global_settings: OSCRSettings):
        self.main_menu_buttons: list[QPushButton] = list()
        self.navigation_buttons: list[QPushButton] = list()
        self.main_tabber: QTabWidget
        self.main_tab_frames: list[QFrame] = list()
        self.sidebar_tabber: QTabWidget
        self.sidebar_tab_frames: list[QFrame] = list()
        self.sidebar_host: QFrame | None = None
        self.sidebar_content_host: QFrame | None = None
        self.sidebar_flip_button: FlipButton
        self.context_rail: QFrame | None = None
        self.context_colour_rail: QFrame | None = None
        self.context_rail_segments: list[QFrame] = list()
        self.context_accents: list[str] = list()
        self.context_tints: list[str] = list()
        self.command_console_workspace: QFrame | None = None
        self.drawer_header: QFrame | None = None
        self.drawer_section_label: QLabel | None = None
        self.drawer_title_label: QLabel | None = None
        self.active_main_tab: int = 0
        self.live_parser_active: bool = False
        self.map_tabber: QTabWidget
        self.map_tab_frames: list[QFrame] = list()
        self.map_menu_buttons: list[QPushButton] = list()

        self.combats_list: QListView
        self.log_duration_value: QLabel
        self.player_duration_value: QLabel

        self.overview_menu_buttons: list[QPushButton] = list()
        self.overview_tabber: QTabWidget
        self.overview_tab_frames: list[QFrame] = list()
        self.overview_table_button: FlipButton
        self.overview_splitter: QSplitter
        self.overview_table: QTableView | None = None
        self.overview_sorting_proxy = None
        self.overview_display_proxy = None
        self.overview_encounter_title: QLabel | None = None
        self.overview_encounter_meta: QLabel | None = None
        self.overview_context_values: list[QLabel] = list()
        self.overview_stat_values: list[QLabel] = list()
        self.overview_metric_buttons: list[QPushButton] = list()
        self.overview_metric_mode: int = 0

        self.analysis_splitter: QSplitter
        self.analysis_menu_buttons: list[QPushButton] = list()
        self.analysis_copy_combobox: QComboBox
        self.analysis_graph_tabber: QTabWidget
        self.analysis_tree_tabber: QTabWidget
        self.analysis_graph_button: FlipButton
        self.analysis_lens_buttons: list[QPushButton] = list()
        self.analysis_plots: list = list()
        self.analysis_filter_scope: QComboBox | None = None
        self.analysis_filter_entry: QLineEdit | None = None
        self.analysis_filter_add_button: QPushButton | None = None
        self.analysis_filter_clause_row: QFrame | None = None
        self.analysis_filter_clause_scroll: QScrollArea | None = None
        self.analysis_filter_clause_container: QFrame | None = None
        self.analysis_filter_clause_layout: QHBoxLayout | None = None
        self.analysis_filter_clause_buttons: list[QPushButton] = list()
        self.analysis_rule_set_selector: QComboBox | None = None
        self.analysis_rules_button: QPushButton | None = None
        self.analysis_rule_chip_buttons: list[QPushButton] = list()
        self.analysis_start_entry: QLineEdit | None = None
        self.analysis_end_entry: QLineEdit | None = None
        self.analysis_truth_chip: QLabel | None = None
        self.analysis_modified_chip: QLabel | None = None
        self.analysis_event_count_chip: QLabel | None = None
        self.analysis_reset_button: QPushButton | None = None

        self.ladder_selector: QListWidget
        self.favorite_ladder_selector: QListWidget
        self.variant_combo: QComboBox
        self.ladder_table: QTableView
        self.ladder_search: QLineEdit
        self.league_search_button: QPushButton
        self.league_clear_button: QPushButton
        self.league_open_local_button: QPushButton
        self.league_open_parse_button: QPushButton
        self.league_save_parse_button: QPushButton
        self.league_more_button: QPushButton
        self.league_status: QLabel | None = None

        self.live_parser_button: QPushButton
        self.sto_log_path_entry: QLineEdit
        self.theme_selector: QComboBox
        self.theme_restart_label: QLabel
        self.appearance_palette_selector: QComboBox
        self.appearance_background_selector: QComboBox
        self.appearance_background_path_entry: QLineEdit
        self.appearance_color_entries: list[QLineEdit] = list()
        self.settings_tabber: QTabWidget
        self.settings_menu_buttons: list[QPushButton] = list()
        self.settings_damage_column_buttons: list[QPushButton] = list()
        self.settings_heal_column_buttons: list[QPushButton] = list()
        self.settings_live_column_buttons: list[QPushButton] = list()

        self._global_settings: OSCRSettings = global_settings

    def switch_analysis_tab(self, tab_index: int):
        """
        Callback for tab switch buttons; switches tab and sets active button.

        Parameters:
        - :param tab_index: index of the tab to switch to
        """
        self.analysis_graph_tabber.setCurrentIndex(tab_index)
        self.analysis_tree_tabber.setCurrentIndex(tab_index)
        for index, button in enumerate(self.analysis_menu_buttons):
            active = index == tab_index
            button.setChecked(active)
            if button.property('consoleRole') == 'modeControl':
                button.setProperty('visualActive', active)
                # Dynamic properties are not automatically re-polished by Qt.  Keep the
                # console import inside this branch so the Legacy startup path stays isolated.
                from .console.tokens import refresh_style
                refresh_style(button, descendants=False)

    def switch_overview_tab(self, tab_index: int):
        """
        Callback for tab switch buttons; switches tab and sets active button.

        Parameters:
        - :param tab_index: index of the tab to switch to
        """
        self.overview_tabber.setCurrentIndex(tab_index)
        for index, button in enumerate(self.overview_menu_buttons):
            active = index == tab_index
            button.setChecked(active)
            if button.property('consoleRole') == 'modeControl':
                button.setProperty('visualActive', active)
                from .console.tokens import refresh_style
                refresh_style(button, descendants=False)

    def switch_overview_metric_group(self, group_index: int):
        """Show a readable Overview metric group while keeping the complete dataset available."""
        safe_index = max(0, min(group_index, len(self.OVERVIEW_METRIC_COLUMN_GROUPS) - 1))
        self.overview_metric_mode = safe_index
        visible_columns = self.OVERVIEW_METRIC_COLUMN_GROUPS[safe_index]
        if self.overview_table is not None and self.overview_table.model() is not None:
            if hasattr(self.overview_table, 'set_visible_source_columns'):
                self.overview_table.set_visible_source_columns(visible_columns)
                self.overview_table.set_meter_mode(safe_index == 0)
                self.overview_table.set_compact_magnitudes(
                    safe_index < len(self.OVERVIEW_METRIC_COLUMN_GROUPS) - 1)
            else:
                for column in range(self.overview_table.model().columnCount()):
                    self.overview_table.setColumnHidden(column, column not in visible_columns)
                self.overview_table.resizeColumnsToContents()
        for index, button in enumerate(self.overview_metric_buttons):
            active = index == safe_index
            button.setChecked(active)
            if button.property('consoleRole') == 'modeControl':
                button.setProperty('visualActive', active)
                from .console.tokens import refresh_style
                refresh_style(button, descendants=False)

    def update_overview_telemetry(
            self, map_name: str, difficulty: str, log_duration: float,
            player_duration: float, rows: list[list]):
        """Update Command Console encounter identity and summary displays from Overview rows."""
        if self.overview_encounter_title is None:
            return
        difficulty_label = difficulty.strip().upper() if difficulty else 'UNCLASSIFIED'
        self.overview_encounter_title.setText(f'{map_name.upper()} [{difficulty_label}]')
        if self.overview_encounter_meta is not None:
            self.overview_encounter_meta.setText(
                f'PARSE READY // ACTIVE PLAYER WINDOW {player_duration:.1f}S')
        context = (
            difficulty_label,
            f'{len(rows)} OPERATOR{"S" if len(rows) != 1 else ""}',
            f'{log_duration:.1f}S LOG',
        )
        for label, text in zip(self.overview_context_values, context):
            label.setText(text)

        values = (
            sum(float(row[0]) for row in rows if len(row) > 0),
            sum(float(row[3]) for row in rows if len(row) > 3),
            max((float(row[8]) for row in rows if len(row) > 8), default=0),
            sum(float(row[11]) for row in rows if len(row) > 11),
        )
        for label, value in zip(self.overview_stat_values, values):
            label.setText(self._format_telemetry_value(value))
        self.switch_overview_metric_group(self.overview_metric_mode)

    @staticmethod
    def _format_telemetry_value(value: float) -> str:
        """Format a telemetry magnitude for compact summary cards."""
        absolute = abs(value)
        if absolute >= 1_000_000_000:
            return f'{value / 1_000_000_000:.2f}B'
        if absolute >= 1_000_000:
            return f'{value / 1_000_000:.2f}M'
        if absolute >= 1_000:
            return f'{value / 1_000:.1f}K'
        return f'{value:,.0f}'

    def switch_main_tab(self, tab_index: int):
        """
        Callback for main tab switch buttons. Switches main and sidebar tabs.

        Parameters:
        - :param tab_index: index of the tab to switch to
        """
        SIDEBAR_TAB_CONVERSION = (0, 0, 1, 2)
        self.main_tabber.setCurrentIndex(tab_index)
        self.active_main_tab = tab_index
        self.sidebar_tabber.setCurrentIndex(SIDEBAR_TAB_CONVERSION[tab_index])
        for index, button in enumerate(self.main_menu_buttons):
            if button.isCheckable():
                button.setChecked(index == tab_index)
        self.apply_context_accent(tab_index)
        if tab_index == 0:
            self.overview_table_button.show()
        else:
            self.overview_table_button.hide()
        if tab_index == 1:
            self.analysis_graph_button.show()
        else:
            self.analysis_graph_button.hide()

    def apply_context_accent(self, tab_index: int):
        """Synchronize Command Console navigation, spine and neutral drawer state."""
        if not self.context_rail or not self.context_accents:
            return
        from .console.tokens import refresh_style

        accent_index = max(0, min(tab_index, len(self.context_accents) - 1))
        accent = self.context_accents[accent_index]
        self.context_rail.setProperty('activeAccent', accent)
        self.context_rail.setProperty('section', str(accent_index))
        if self.sidebar_host:
            self.sidebar_host.setProperty('activeAccent', accent)
            self.sidebar_host.setProperty('section', str(accent_index))
        if self.drawer_header:
            self.drawer_header.setProperty('section', str(accent_index))
            refresh_style(self.drawer_header)
        drawer_labels = (
            ('OV', 'COMBAT LOG'),
            ('AN', 'COMBAT LOG'),
            ('LG', 'LEAGUE ACCESS'),
            ('ST', 'SYSTEM SETTINGS'),
        )
        if accent_index < len(drawer_labels):
            section, title = drawer_labels[accent_index]
            if self.drawer_section_label:
                self.drawer_section_label.setText(section)
            if self.drawer_title_label:
                self.drawer_title_label.setText(title)

        visual_index = 4 if self.live_parser_active else accent_index
        for index, segment in enumerate(self.context_rail_segments):
            segment.setProperty('active', index == visual_index)
            refresh_style(segment)
        for index, button in enumerate(self.navigation_buttons):
            button.setProperty('visualActive', index == visual_index)
            refresh_style(button, descendants=False)

    def set_live_parser_active(self, active: bool):
        """Make Live Parser the visual fifth context while its window is open."""
        self.live_parser_active = bool(active)
        self.apply_context_accent(self.active_main_tab)

    def expand_analysis_graph(self):
        """
        Shows the analysis graph
        """
        self.analysis_graph_tabber.show()
        self._global_settings.analysis_graph = True

    def collapse_analysis_graph(self):
        """
        Hides the analysis graph
        """
        self.analysis_graph_tabber.hide()
        self._global_settings.analysis_graph = False
