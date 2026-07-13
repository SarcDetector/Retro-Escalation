from PySide6.QtWidgets import (
    QComboBox, QFrame, QLabel, QLineEdit, QListView, QListWidget, QPushButton, QSplitter,
    QTableView, QTabWidget)

from .widgets import FlipButton
from .config import OSCRSettings


class WidgetManager():
    """
    Class to store and manage widgets.
    """
    def __init__(self, global_settings: OSCRSettings):
        self.main_menu_buttons: list[QPushButton] = list()
        self.main_tabber: QTabWidget
        self.main_tab_frames: list[QFrame] = list()
        self.sidebar_tabber: QTabWidget
        self.sidebar_tab_frames: list[QFrame] = list()
        self.sidebar_host: QFrame | None = None
        self.sidebar_flip_button: FlipButton
        self.context_rail: QFrame | None = None
        self.context_colour_rail: QFrame | None = None
        self.context_rail_segments: list[QFrame] = list()
        self.context_accents: list[str] = list()
        self.context_tints: list[str] = list()
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

        self.analysis_splitter: QSplitter
        self.analysis_menu_buttons: list[QPushButton] = list()
        self.analysis_copy_combobox: QComboBox
        self.analysis_graph_tabber: QTabWidget
        self.analysis_tree_tabber: QTabWidget
        self.analysis_graph_button: FlipButton

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

        self.live_parser_button: QPushButton
        self.sto_log_path_entry: QLineEdit
        self.theme_selector: QComboBox
        self.theme_restart_label: QLabel
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
            if index == tab_index:
                button.setChecked(True)
            else:
                button.setChecked(False)

    def switch_overview_tab(self, tab_index: int):
        """
        Callback for tab switch buttons; switches tab and sets active button.

        Parameters:
        - :param tab_index: index of the tab to switch to
        """
        self.overview_tabber.setCurrentIndex(tab_index)
        for index, button in enumerate(self.overview_menu_buttons):
            if index == tab_index:
                button.setChecked(True)
            else:
                button.setChecked(False)

    def switch_main_tab(self, tab_index: int):
        """
        Callback for main tab switch buttons. Switches main and sidebar tabs.

        Parameters:
        - :param tab_index: index of the tab to switch to
        """
        SIDEBAR_TAB_CONVERSION = (0, 0, 1, 2)
        self.main_tabber.setCurrentIndex(tab_index)
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
        """Synchronize the persistent Command Console rail and sidebar surface to a page."""
        if not self.context_rail or not self.context_accents:
            return
        accent_index = max(0, min(tab_index, len(self.context_accents) - 1))
        accent = self.context_accents[accent_index]
        tint = self.context_tints[accent_index]
        self.context_rail.setProperty('activeAccent', accent)
        self.context_rail.setStyleSheet(
            'QFrame#commandConsoleContextRail {'
            f'background-color: #0d1419; border: 1px solid {accent}; border-radius: 10px;}}')
        if self.sidebar_host:
            self.sidebar_host.setProperty('activeAccent', accent)
            self.sidebar_host.setStyleSheet(
                'QFrame#commandConsoleSidebarHost {'
                f'background-color: {tint}; border: none; border-top: 5px solid {accent};}}')
        for index, segment in enumerate(self.context_rail_segments):
            colour = self.context_accents[index]
            selected_border = 'border-right: 3px solid #f4efe6;' if index == accent_index else ''
            segment.setStyleSheet(
                f'background-color: {colour}; border: none; {selected_border}')
        for frame in self.sidebar_tab_frames:
            name = frame.objectName()
            if name.startswith('commandConsoleSidebar'):
                frame.setStyleSheet(
                    f'QFrame#{name} {{background-color: {tint}; border: none;}}')

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
