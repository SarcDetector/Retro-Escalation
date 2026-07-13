"""Theme-selectable application shells for RE-OSCR.

The inherited shell remains byte-for-byte equivalent in structure for the Default theme. The
Command Console shell owns only presentation and navigation widgets; page models, parser callbacks,
and application state remain shared.
"""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

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

    container = create_frame(theme)
    container.setObjectName('commandConsoleContextRail')
    container.setSizePolicy(SMINMAX)
    container.setStyleSheet(
        'QFrame#commandConsoleContextRail {'
        'background-color: #0d1419; border: 1px solid #293944; border-radius: 10px;}')
    layout = QHBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)

    accent_frame = QFrame()
    accent_frame.setObjectName('commandConsoleColourRail')
    accent_frame.setFixedWidth(max(8, round(10 * theme.scale)))
    accent_layout = QVBoxLayout()
    accent_layout.setContentsMargins(0, 0, 0, 0)
    accent_layout.setSpacing(max(1, round(2 * theme.scale)))
    accents = command_console_accents(theme)
    rail_segments = []
    for index, colour in enumerate(accents):
        segment = QFrame()
        segment.setObjectName(f'commandConsoleRailSegment{index + 1}')
        segment.setStyleSheet(f'background-color: {colour}; border: none;')
        accent_layout.addWidget(segment, 1)
        rail_segments.append(segment)
    accent_frame.setLayout(accent_layout)
    layout.addWidget(accent_frame)

    sidebar_host = create_frame(theme, style='medium_frame', size_policy=SMINMIN)
    sidebar_host.setObjectName('commandConsoleSidebarHost')
    sidebar_host.setStyleSheet(
        sidebar_host.styleSheet()
        + 'QFrame#commandConsoleSidebarHost {background-color: #0d1419; border: none;}')
    layout.addWidget(sidebar_host, 1)
    container.setLayout(layout)
    if widgets is not None:
        widgets.context_rail = container
        widgets.context_colour_rail = accent_frame
        widgets.context_rail_segments = rail_segments
        widgets.sidebar_host = sidebar_host
        widgets.context_accents = list(accents)
        widgets.context_tints = [
            _blend_colour(colour, '#0d1419', 0.16) for colour in accents]
    return container, sidebar_host


def _blend_colour(foreground: str, background: str, foreground_ratio: float) -> str:
    """Blend a bright accent into a dark surface for readable contextual panels."""
    fg = QColor(foreground)
    bg = QColor(background)
    ratio = max(0.0, min(1.0, foreground_ratio))
    return QColor(
        round(fg.red() * ratio + bg.red() * (1 - ratio)),
        round(fg.green() * ratio + bg.green() * (1 - ratio)),
        round(fg.blue() * ratio + bg.blue() * (1 - ratio)),
    ).name()


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
        self._theme = theme
        self._mode = getattr(settings, 'command_console_background_mode', 'grid')
        self._opacity = max(
            0.0, min(0.5, getattr(settings, 'command_console_background_opacity', 0.28)))
        custom_path = Path(getattr(settings, 'command_console_background_path', ''))
        self._background = QPixmap(str(custom_path)) if (
            self._mode == 'custom' and custom_path.is_file()) else QPixmap()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor('#080d12'))
        if self._mode == 'custom' and not self._background.isNull():
            scaled = self._background.scaled(
                self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation)
            painter.setOpacity(self._opacity)
            painter.drawPixmap(
                round((self.width() - scaled.width()) / 2),
                round((self.height() - scaled.height()) / 2), scaled)
            painter.setOpacity(1.0)
            painter.fillRect(self.rect(), QColor(7, 11, 15, 120))
        if self._mode in ('custom', 'grid'):
            grid = QColor(command_console_accents(self._theme)[3])
            grid.setAlpha(20 if self._mode == 'grid' else 12)
            painter.setPen(QPen(grid, 1))
            spacing = max(44, round(72 * self._theme.scale))
            for x_position in range(0, self.width(), spacing):
                painter.drawLine(x_position, 0, x_position, self.height())
            for y_position in range(0, self.height(), spacing):
                painter.drawLine(0, y_position, self.width(), y_position)
        painter.end()


def _build_command_console_shell(
        theme, widgets, live_parser, status_bar, settings):
    layout = QVBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    bg_frame = QFrame()
    bg_frame.setObjectName('commandConsoleApplicationShell')
    bg_frame.setStyleSheet(
        'QFrame#commandConsoleApplicationShell {'
        'background-color: #070b0f; border: none;}')
    bg_frame.setSizePolicy(SMINMIN)
    layout.addWidget(bg_frame)

    root = QVBoxLayout()
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(0)
    root.addWidget(_build_masthead(theme))
    root.addWidget(_build_command_navigation(theme, widgets, live_parser))

    main_frame = CommandConsoleWorkspace(theme, settings)
    main_frame.setObjectName('commandConsoleWorkspace')
    main_frame.setStyleSheet(
        'QFrame#commandConsoleWorkspace {'
        'background: transparent; border: none;}')
    main_frame.setSizePolicy(SMINMIN)
    root.addWidget(main_frame, 1)
    root.addWidget(status_bar)
    bg_frame.setLayout(root)
    return layout, main_frame


def _build_masthead(theme: AppTheme) -> QFrame:
    accents = command_console_accents(theme)
    masthead = QFrame()
    masthead.setObjectName('commandConsoleMasthead')
    masthead.setMinimumHeight(round(92 * theme.scale))
    masthead.setStyleSheet(
        'QFrame#commandConsoleMasthead {'
        f'background-color: #0b1116; border: none; border-top: 5px solid {accents[3]};}}')
    layout = QHBoxLayout()
    horizontal_margin = round(32 * theme.scale)
    layout.setContentsMargins(horizontal_margin, round(13 * theme.scale), horizontal_margin,
                              round(13 * theme.scale))
    layout.setSpacing(round(18 * theme.scale))

    badge = QLabel('RE')
    badge.setObjectName('commandConsoleBrandMark')
    badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
    badge.setFixedSize(round(58 * theme.scale), round(54 * theme.scale))
    badge.setStyleSheet(
        'QLabel#commandConsoleBrandMark {'
        f'color: {_contrast_text(accents[0])}; background-color: {accents[0]}; border: none;'
        f'border-top-left-radius: {round(18 * theme.scale)}px;'
        f'border-top-right-radius: {round(5 * theme.scale)}px;'
        f'border-bottom-right-radius: {round(18 * theme.scale)}px;'
        f'border-bottom-left-radius: {round(5 * theme.scale)}px;'
        f'font-family: Overpass; font-size: {round(22 * theme.scale)}px; font-weight: 700;}}')
    layout.addWidget(badge)

    title_layout = QVBoxLayout()
    title_layout.setContentsMargins(0, 0, 0, 0)
    title_layout.setSpacing(round(3 * theme.scale))
    eyebrow = QLabel('RETRO ESCALATION')
    eyebrow.setObjectName('commandConsoleBrandEyebrow')
    eyebrow.setStyleSheet(
        'color: #77dbe2; background: transparent; border: none;'
        f'font-family: Roboto Mono; font-size: {round(10 * theme.scale)}px; font-weight: 600;')
    title_layout.addWidget(eyebrow)
    title = QLabel('OPEN SOURCE COMBATLOG READER')
    title.setObjectName('commandConsoleBrandTitle')
    title.setStyleSheet(
        'color: #f4efe6; background: transparent; border: none;'
        f'font-family: Overpass; font-size: {round(28 * theme.scale)}px; font-weight: 700;')
    title_layout.addWidget(title)
    layout.addLayout(title_layout, 1)

    readout = QLabel('SESSION  RE-04\nCORE     READY')
    readout.setObjectName('commandConsoleSystemReadout')
    readout.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    readout.setStyleSheet(
        'color: #85d997; background: transparent; border: none;'
        f'font-family: Roboto Mono; font-size: {round(10 * theme.scale)}px; font-weight: 600;')
    layout.addWidget(readout)
    masthead.setLayout(layout)
    return masthead


def _build_command_navigation(theme: AppTheme, widgets, live_parser) -> QFrame:
    accents = command_console_accents(theme)
    nav = QFrame()
    nav.setObjectName('commandConsolePrimaryNavigation')
    nav.setStyleSheet(
        'QFrame#commandConsolePrimaryNavigation {'
        'background-color: #05080b; border: none; border-bottom: 1px solid #26343d;}')
    layout = QHBoxLayout()
    margin = round(12 * theme.scale)
    layout.setContentsMargins(round(28 * theme.scale), margin, round(28 * theme.scale), margin)
    layout.setSpacing(round(7 * theme.scale))

    page_names = (tr('Overview'), tr('Analysis'), tr('League'), tr('Settings'))
    buttons = []
    for index, (name, accent) in enumerate(zip(page_names, accents[:4])):
        button = _create_navigation_button(theme, index + 1, name, accent)
        button.setCheckable(True)
        button.setAutoExclusive(True)
        button.setChecked(index == 0)
        layout.addWidget(button, 1)
        buttons.append(button)
    widgets.main_menu_buttons = buttons

    live_parser_button = _create_navigation_button(
        theme, 5, tr('Live Parser'), accents[4], inverse=True)
    live_parser_button.setObjectName('commandNavLiveParser')
    live_parser_button.setCheckable(True)
    live_parser_button.clicked[bool].connect(live_parser.toggle_window)
    layout.addWidget(live_parser_button, 1)
    widgets.live_parser_button = live_parser_button
    nav.setLayout(layout)
    return nav


def _create_navigation_button(
        theme: AppTheme, index: int, name: str, accent: str,
        inverse: bool = False) -> QPushButton:
    button = QPushButton(f'{index:02d}   {name.upper()}')
    button.setObjectName(f'commandNav{name.replace(" ", "")}')
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setMinimumHeight(round(50 * theme.scale))
    large_radius = round(21 * theme.scale)
    small_radius = round(6 * theme.scale)
    font_size = round(15 * theme.scale)
    if inverse:
        corners = (
            f'border-top-left-radius: {small_radius}px;'
            f'border-top-right-radius: {large_radius}px;'
            f'border-bottom-right-radius: {small_radius}px;'
            f'border-bottom-left-radius: {large_radius}px;')
    else:
        corners = (
            f'border-top-left-radius: {large_radius}px;'
            f'border-top-right-radius: {small_radius}px;'
            f'border-bottom-right-radius: {large_radius}px;'
            f'border-bottom-left-radius: {small_radius}px;')
    dark_edge = _blend_colour(accent, '#05080b', 0.54)
    text_colour = _contrast_text(accent)
    button.setStyleSheet(
        'QPushButton {'
        f'background-color: {accent}; color: {text_colour}; border: 2px solid {dark_edge};'
        f'border-bottom-width: {round(7 * theme.scale)}px; {corners}'
        'padding: 7px 14px; text-align: left;'
        f'font-family: Overpass; font-size: {font_size}px; font-weight: 700;}}'
        'QPushButton:hover {border-color: #f4efe6;}'
        f'QPushButton:checked {{color: {text_colour}; border-color: #f4efe6;'
        f'border-bottom-color: {dark_edge};}}'
        'QPushButton:pressed {padding-top: 9px; padding-bottom: 5px;}')
    return button


def _contrast_text(colour: str) -> str:
    """Choose readable text for user-selectable rail colours."""
    value = QColor(colour)
    luminance = 0.2126 * value.red() + 0.7152 * value.green() + 0.0722 * value.blue()
    return '#10161b' if luminance >= 118 else '#f4efe6'
