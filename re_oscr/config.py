import os
from pathlib import Path

from PySide6.QtCore import QByteArray, QSettings

from .appearance import (
    DEFAULT_COMMAND_CONSOLE_BACKGROUND, DEFAULT_COMMAND_CONSOLE_PALETTE,
    normalize_background_mode, resolve_command_console_palette)


class OSCRConfig():
    def __init__(self):
        self.config_dir: Path = Path()
        self.default_icon_size: int = 24
        self.default_live_parser_scale: float = 1.0
        self.default_ui_scale: float = 1.0
        self.excluded_event_ids: list[str] = ['Autodesc.Combatevent.Falling']
        self.home_dir: Path = Path()
        self.icon_size: int = 24
        self.link_downloads: str = 'https://github.com/SarcDetector/Retro-Escalation/releases'
        self.link_github: str = 'https://github.com/SarcDetector/Retro-Escalation'
        self.link_cla: str = 'https://github.com/AnotherNathan/STO_CombatLogAnalyzer'
        self.link_stobuilds: str = 'https://discord.gg/stobuilds'
        self.link_stocd: str = 'https://github.com/STOCD'
        self.link_website: str = 'https://oscr.stobuilds.com'
        self.live_graph_fields: tuple[str] = ('DPS', 'Debuff', 'Attacks-in Share', 'HPS')
        self.live_parser_scale: float = 1.0
        self.minimum_window_width: int = 1280
        self.minimum_window_height: int = 720
        self.settings_file: str = 'RE_OSCR_settings.ini'
        self.legacy_settings_files: tuple[str, ...] = ('OSCR_UI_settings.ini',)
        self.templog_folder_name: str = '_temp'
        self.templog_folder_path: Path = Path()
        self.ui_scale: float = 1.0

    def __repr__(self):
        return f'<OSCR-Config ui_scale={self.ui_scale} icon_size={self.icon_size} ...>'


class OSCRSettings():

    __slots__ = ('_settings', 'analysis_graph', 'auto_scan', 'combat_min_lines',
                 'command_console_accents', 'command_console_background_mode',
                 'command_console_background_opacity', 'command_console_background_path',
                 'command_console_palette_preset',
                 'combats_to_parse', 'copy_format', 'dmg_columns', 'favorite_ladders',
                 'first_overview_tab', 'graph_resolution', 'heal_columns', 'league_table_rows',
                 'language', 'log_path', 'overview_sort_column', 'overview_sort_order',
                 'seconds_between_combats', 'sto_log_path', 'ui_scale', 'state__analysis_splitter',
                 'state__geometry', 'state__live_geometry', 'state__live_splitter',
                 'state__overview_splitter', 'state__sidebar_collapsed',
                 'liveparser__auto_enabled', 'liveparser__columns',
                 'liveparser__copy_kills', 'liveparser__graph_active', 'liveparser__graph_field',
                 'liveparser__player_display', 'liveparser__window_scale',
                 'liveparser__window_opacity', 'theme_id',
                 'workbench_auto_enable_rules', 'workbench_auto_rules',
                 'workbench_auto_rule_set', 'workbench_rule_set')

    def __init__(self, settings_file_path: Path):
        self.analysis_graph: bool = True
        self.auto_scan: bool = False
        self.command_console_accents: list[str] = list(DEFAULT_COMMAND_CONSOLE_PALETTE)
        self.command_console_background_mode: str = DEFAULT_COMMAND_CONSOLE_BACKGROUND
        self.command_console_background_opacity: float = 0.28
        self.command_console_background_path: str = ''
        self.command_console_palette_preset: str = 'command'
        self.combat_min_lines: int = 20
        self.combats_to_parse: int = 10
        self.copy_format: str = 'Compact'
        self.dmg_columns: list[bool] = [True] * 21
        self.favorite_ladders: list[str] = list()
        self.first_overview_tab: int = 0
        self.graph_resolution: float = 0.2
        self.heal_columns: list[bool] = [True] * 13
        self.league_table_rows: int = 50
        self.language: str = 'en'
        self.log_path: str = ''
        self.overview_sort_column: int = 1
        self.overview_sort_order: str = 'Descending'
        self.seconds_between_combats: int = 45
        self.sto_log_path: str = ''
        self.theme_id: str = 'command_console'
        self.ui_scale: float = 1.0
        self.workbench_auto_enable_rules: bool = False
        self.workbench_auto_rules: str = '[]'
        self.workbench_auto_rule_set: str = ''
        self.workbench_rule_set: str = 'Community examples'

        self.state__analysis_splitter: QByteArray = QByteArray()
        self.state__geometry: QByteArray = QByteArray()
        self.state__live_geometry: QByteArray = QByteArray()
        self.state__live_splitter: QByteArray = QByteArray()
        self.state__overview_splitter: QByteArray = QByteArray()
        self.state__sidebar_collapsed: bool = False

        self.liveparser__auto_enabled: bool = False
        self.liveparser__columns: list[bool] = [True, False, True, False, False, False, False]
        self.liveparser__copy_kills: bool = False
        self.liveparser__graph_active: bool = False
        self.liveparser__graph_field: int = 0
        self.liveparser__player_display: str = 'Handle'
        self.liveparser__window_scale: float = 1.0
        self.liveparser__window_opacity: float = 0.85

        if os.name == 'nt':
            self._settings = QSettings(str(settings_file_path), QSettings.Format.IniFormat)
        else:
            self._settings = QSettings(str(settings_file_path), QSettings.Format.NativeFormat)

        self.load_settings()
        self.command_console_background_mode = normalize_background_mode(
            self.command_console_background_mode)
        if self.command_console_palette_preset not in (
                'command', 'federation', 'romulan', 'klingon', 'custom'):
            self.command_console_palette_preset = 'command'
        self.command_console_accents = list(resolve_command_console_palette(
            self.command_console_palette_preset, self.command_console_accents))

    def load_settings(self):
        """
        Loads settings from settings file given in constructor into attributes.
        """
        for setting in self.__slots__:
            if setting.startswith('_'):
                continue
            setting_id = setting.replace('__', '/')
            if self._settings.contains(setting_id):
                item_type = type(getattr(self, setting))
                if item_type is list:
                    settings_item: list = getattr(self, setting)
                    if len(settings_item) > 0:
                        list_element_type = type(settings_item[0])
                    else:
                        list_element_type = str
                    item_list = self._settings.value(setting_id, type=list)
                    if list_element_type is bool:
                        # Depending on platform and QSettings backend, list elements may come
                        # back as native bools, numeric values, or strings.  Comparing a native
                        # ``True`` only to the string ``'true'`` silently disabled every saved
                        # table column on the next launch.
                        items = []
                        for element in item_list:
                            if isinstance(element, bool):
                                items.append(element)
                            elif isinstance(element, (int, float)):
                                items.append(bool(element))
                            else:
                                items.append(
                                    str(element).strip().casefold()
                                    in ('true', '1', 'yes', 'on'))
                        setattr(self, setting, items)
                    else:
                        setattr(self, setting, [list_element_type(el) for el in item_list])
                else:
                    setattr(self, setting, self._settings.value(setting_id, type=item_type))

    def store_settings(self):
        """
        Stores settings from attributes to settings file given in constructor.
        """
        for setting in self.__slots__:
            if not setting.startswith('_'):
                setting_id = setting.replace('__', '/')
                self._settings.setValue(setting_id, getattr(self, setting))

    def set(self, setting_name: str, value):
        """
        Sets setting `setting_name` to `value`. Only use when direct assignment cannot be used
        (e.g. inside a lambda function).
        """
        setattr(self, setting_name, value)

    def set_graph_resolution(self, new_value: int) -> float:
        """
        Calculates `new_value` / 10 and stores it to `graph_resolution`. Returns the calculated
        value.

        Parameters:
        - :param new_value: data points per second
        """
        try:
            setting_value = round(new_value / 10, 1)
            self.graph_resolution = setting_value
            return setting_value
        except (ValueError, ZeroDivisionError):
            return

    def set_liveparser_opacity(self, new_value: int) -> str:
        """
        Calculates `new_value` / 10 and stores it to `liveparser__window_opacity`. Returns the
        calculated value.

        Parameters:
        - :param new_value: 20 times the opacity percentage
        """
        setting_value = round(new_value / 20, 2)
        self.liveparser__window_opacity = setting_value
        return f'{setting_value:.2f}'

    def set_ui_scale(self, new_value: int) -> str:
        """
        Calculates `new_value` / 50 and stores it to `ui_scale`. Returns the calculated value.

        Parameters:
        - :param new_value: 50 times the ui scale percentage
        """
        setting_value = round(new_value / 50, 2)
        self.ui_scale = setting_value
        return f'{setting_value:.2f}'

    def set_liveparser_scale(self, new_value: int):
        """
        Calculates new_value / 50 and stores it to `liveparser__window_scale`. Returns the
        calculated value.

        Parameters:
        - :param new_value: 50 times the live scale percentage
        """
        setting_value = round(new_value / 50, 2)
        self.liveparser__window_scale = setting_value
        return f'{setting_value:.2f}'

    def set_command_background_opacity(self, new_value: int) -> str:
        """Store Command Console background intensity from a zero-to-fifty slider."""
        setting_value = round(max(0, min(50, new_value)) / 100, 2)
        self.command_console_background_opacity = setting_value
        return f'{setting_value * 100:.0f}%'
