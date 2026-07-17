"""Theme-selectable application shells for RE-OSCR.

The inherited shell remains byte-for-byte equivalent in structure for Legacy. The
Command Console shell owns only presentation and navigation widgets; page models, parser callbacks,
and application state remain shared.
"""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout

from .iofunctions import get_asset_path
from .theme import AppTheme
from .themes import COMMAND_CONSOLE_THEME_ID
from .themes.command_console import command_console_accents
from .translation import tr
from .widgetbuilder import SMINMAX, SMINMIN, create_button_series, create_frame, create_icon_button
from .widgets import BannerLabel


def build_application_shell(
        theme: AppTheme, active_theme_id: str, widgets, live_parser, status_bar,
        app_dir: str, settings=None) -> tuple[QVBoxLayout, QFrame]:
    """Build the selected application chrome and return its content frame."""
    if active_theme_id == COMMAND_CONSOLE_THEME_ID:
        return _build_command_console_shell(
            theme, widgets, live_parser, status_bar, settings)
    return _build_default_shell(theme, widgets, live_parser, status_bar, app_dir)


def build_context_rail(theme: AppTheme, active_theme_id: str, widgets=None) -> tuple[QFrame, QFrame]:
    """Return the collapsible rail container and the frame that receives sidebar content."""
    if active_theme_id != COMMAND_CONSOLE_THEME_ID:
        frame = create_frame(theme)
        frame.setObjectName('defaultContextRail')
        frame.setSizePolicy(SMINMAX)
        return frame, frame

    from .console.tokens import px

    container = QFrame()
    container.setObjectName('commandConsoleContextRail')
    container.setSizePolicy(SMINMAX)
    layout = QHBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(px(6, theme.scale))

    accent_frame = QFrame()
    accent_frame.setObjectName('commandConsoleColourRail')
    accent_frame.setFixedWidth(px(44, theme.scale))
    accent_layout = QVBoxLayout()
    accent_layout.setContentsMargins(
        px(4, theme.scale), px(5, theme.scale), px(4, theme.scale), px(5, theme.scale))
    accent_layout.setSpacing(px(3, theme.scale))
    accents = command_console_accents(theme)
    rail_segments = []
    section_marks = ('OV', 'AN', 'LG', 'ST', 'LP')
    section_names = ('Overview', 'Analysis', 'League', 'Settings', 'Live Parser')
    for index, _colour in enumerate(accents):
        segment = QFrame()
        segment.setObjectName(f'commandConsoleRailSegment{index + 1}')
        segment.setProperty('consoleRole', 'spineSegment')
        segment.setProperty('accentIndex', str(index))
        segment.setProperty('active', index == 0)
        segment.setToolTip(section_names[index])
        segment_layout = QVBoxLayout()
        segment_layout.setContentsMargins(0, 0, 0, 0)
        mark = QLabel(section_marks[index])
        mark.setObjectName(f'commandConsoleRailMark{index + 1}')
        mark.setProperty('consoleRole', 'spineMark')
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        segment_layout.addWidget(mark)
        segment.setLayout(segment_layout)
        accent_layout.addWidget(segment, 1)
        rail_segments.append(segment)
    accent_frame.setLayout(accent_layout)
    layout.addWidget(accent_frame)

    sidebar_host = QFrame()
    sidebar_host.setObjectName('commandConsoleSidebarHost')
    sidebar_host.setSizePolicy(SMINMIN)
    drawer_layout = QVBoxLayout()
    drawer_layout.setContentsMargins(0, 0, 0, 0)
    drawer_layout.setSpacing(0)

    drawer_header = QFrame()
    drawer_header.setObjectName('commandConsoleDrawerHeader')
    drawer_header.setProperty('section', '0')
    header_layout = QHBoxLayout()
    header_layout.setContentsMargins(
        px(12, theme.scale), px(8, theme.scale), px(12, theme.scale), px(8, theme.scale))
    header_layout.setSpacing(px(9, theme.scale))
    section_label = QLabel('OV')
    section_label.setObjectName('commandConsoleDrawerSection')
    section_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    section_label.setMinimumWidth(px(26, theme.scale))
    header_layout.addWidget(section_label)
    title_label = QLabel('COMBAT LOG')
    title_label.setObjectName('commandConsoleDrawerTitle')
    header_layout.addWidget(title_label, 1)
    drawer_header.setLayout(header_layout)
    drawer_layout.addWidget(drawer_header)

    sidebar_content = QFrame()
    sidebar_content.setObjectName('commandConsoleSidebarContent')
    sidebar_content.setSizePolicy(SMINMIN)
    drawer_layout.addWidget(sidebar_content, 1)
    sidebar_host.setLayout(drawer_layout)
    layout.addWidget(sidebar_host, 1)
    container.setLayout(layout)
    if widgets is not None:
        widgets.context_rail = container
        widgets.context_colour_rail = accent_frame
        widgets.context_rail_segments = rail_segments
        widgets.sidebar_host = sidebar_host
        widgets.sidebar_content_host = sidebar_content
        widgets.drawer_header = drawer_header
        widgets.drawer_section_label = section_label
        widgets.drawer_title_label = title_label
        widgets.context_accents = list(accents)
    return container, sidebar_content


def _build_default_shell(theme, widgets, live_parser, status_bar, app_dir):
    layout = QVBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    bg_frame = create_frame(theme, style_override={'background-color': '@oscr'})
    bg_frame.setObjectName('defaultApplicationShell')
    bg_frame.setSizePolicy(SMINMIN)
    layout.addWidget(bg_frame)

    main_layout = QVBoxLayout()
    main_layout.setContentsMargins(0, 0, 0, 0)
    main_layout.setSpacing(0)
    label = BannerLabel(get_asset_path('oscrbanner-slim-dark-label.png', app_dir), bg_frame)
    label.setObjectName('legacyBanner')
    main_layout.addWidget(label)

    menu_frame = create_frame(theme, style_override={'background-color': '@oscr'})
    menu_frame.setSizePolicy(SMINMAX)
    menu_frame.setContentsMargins(0, 0, 0, 0)
    main_layout.addWidget(menu_frame)
    menu_layout = QGridLayout()
    menu_layout.setContentsMargins(0, 0, 0, 0)
    menu_layout.setSpacing(0)
    menu_layout.setColumnStretch(1, 1)
    menu_button_style = {
        tr('Overview'): {'style': {'margin-left': '@isp'}},
        tr('Analysis'): {},
        tr('League Standings'): {},
        tr('Settings'): {},
    }
    button_layout, buttons = create_button_series(
        theme, menu_button_style, style='menu_button', seperator='•', ret=True)
    menu_layout.addLayout(button_layout, 0, 0)
    widgets.main_menu_buttons = buttons

    size = [theme.opt.icon_size * 1.3] * 2
    live_parser_button = create_icon_button(
        theme, 'live-parser', tr('Live Parser'), 'live_icon_button', icon_size=size)
    live_parser_button.setCheckable(True)
    live_parser_button.clicked[bool].connect(live_parser.toggle_window)
    menu_layout.addWidget(live_parser_button, 0, 2)
    widgets.live_parser_button = live_parser_button
    menu_frame.setLayout(menu_layout)

    width = theme['app']['frame_thickness']
    main_frame = create_frame(theme, style_override={'margin': (0, width, 0, width)})
    main_frame.setObjectName('defaultWorkspace')
    main_frame.setSizePolicy(SMINMIN)
    main_layout.addWidget(main_frame)
    main_layout.addWidget(status_bar)
    bg_frame.setLayout(main_layout)
    return layout, main_frame


class CommandConsoleWorkspace(QFrame):
    """Paint the optional local background behind the shared page widgets."""

    def __init__(self, theme: AppTheme, settings):
        super().__init__()
        from .console.tokens import ConsoleTokens

        self._theme = theme
        self._tokens = ConsoleTokens.from_theme(theme)
        self._mode = 'none'
        self._opacity = 0.28
        self._background_path = Path()
        self._background = QPixmap()
        self.apply_appearance(settings)

    def apply_appearance(self, settings) -> None:
        """Refresh the optional local background without rebuilding the workspace."""
        self._mode = getattr(settings, 'command_console_background_mode', 'none')
        self._opacity = max(
            0.0, min(0.5, getattr(settings, 'command_console_background_opacity', 0.28)))
        custom_path = Path(getattr(settings, 'command_console_background_path', ''))
        if custom_path != self._background_path:
            self._background_path = custom_path
            self._background = QPixmap(str(custom_path)) if custom_path.is_file() else QPixmap()
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        from .console.tokens import SURFACES

        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(SURFACES['void']))
        if self._mode == 'custom' and not self._background.isNull():
            scaled = self._background.scaled(
                self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation)
            painter.setOpacity(self._opacity)
            painter.drawPixmap(
                round((self.width() - scaled.width()) / 2),
                round((self.height() - scaled.height()) / 2), scaled)
            painter.setOpacity(1.0)
            scrim = QColor(SURFACES['void'])
            scrim.setAlpha(185)
            painter.fillRect(self.rect(), scrim)
        painter.end()


def _build_command_console_shell(
        theme, widgets, live_parser, status_bar, settings):
    layout = QVBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    bg_frame = QFrame()
    bg_frame.setObjectName('commandConsoleApplicationShell')
    bg_frame.setSizePolicy(SMINMIN)
    layout.addWidget(bg_frame)

    root = QVBoxLayout()
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(0)
    root.addWidget(_build_masthead(theme))
    root.addWidget(_build_command_navigation(theme, widgets, live_parser))

    main_frame = CommandConsoleWorkspace(theme, settings)
    main_frame.setObjectName('commandConsoleWorkspace')
    main_frame.setSizePolicy(SMINMIN)
    widgets.command_console_workspace = main_frame
    root.addWidget(main_frame, 1)
    root.addWidget(status_bar)
    bg_frame.setLayout(root)
    return layout, main_frame


def _build_masthead(theme: AppTheme) -> QFrame:
    masthead = QFrame()
    masthead.setObjectName('commandConsoleMasthead')
    masthead.setMinimumHeight(round(80 * theme.scale))
    layout = QHBoxLayout()
    horizontal_margin = round(32 * theme.scale)
    layout.setContentsMargins(horizontal_margin, round(10 * theme.scale), horizontal_margin,
                              round(10 * theme.scale))
    layout.setSpacing(round(18 * theme.scale))

    badge = QLabel('RE')
    badge.setObjectName('commandConsoleBrandMark')
    badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
    badge.setFixedSize(round(58 * theme.scale), round(54 * theme.scale))
    layout.addWidget(badge)

    title_layout = QVBoxLayout()
    title_layout.setContentsMargins(0, 0, 0, 0)
    title_layout.setSpacing(round(3 * theme.scale))
    eyebrow = QLabel('RETRO ESCALATION')
    eyebrow.setObjectName('commandConsoleBrandEyebrow')
    title_layout.addWidget(eyebrow)
    title = QLabel('OPEN SOURCE COMBATLOG READER')
    title.setObjectName('commandConsoleBrandTitle')
    title_layout.addWidget(title)
    layout.addLayout(title_layout, 1)

    masthead.setLayout(layout)
    return masthead


def _build_command_navigation(theme: AppTheme, widgets, live_parser) -> QFrame:
    from .console.components import primary_navigation_button

    nav = QFrame()
    nav.setObjectName('commandConsolePrimaryNavigation')
    layout = QHBoxLayout()
    margin = round(8 * theme.scale)
    layout.setContentsMargins(round(28 * theme.scale), margin, round(28 * theme.scale), margin)
    layout.setSpacing(round(7 * theme.scale))

    page_names = (
        tr('Overview'), tr('Analysis'), tr('League'), tr('Settings'), tr('Live Parser'))
    buttons = []
    object_names = ('Overview', 'Analysis', 'League', 'Settings', 'LiveParser')
    for index, (name, object_name) in enumerate(zip(page_names, object_names)):
        button = primary_navigation_button(
            theme.scale, index + 1, name, index, f'commandNav{object_name}',
            mirrored=index == 4)
        button.setCheckable(True)
        button.setAutoExclusive(True)
        button.setChecked(index == 0)
        button.setProperty('visualActive', index == 0)
        layout.addWidget(button, 1)
        buttons.append(button)
    widgets.main_menu_buttons = buttons
    widgets.live_parser_button = buttons[4]
    widgets.navigation_buttons = buttons
    nav.setLayout(layout)
    return nav
