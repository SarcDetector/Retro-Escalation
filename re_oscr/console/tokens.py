"""Palette-aware design tokens and the shared Command Console stylesheet."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget


SURFACES = {
    "void": "#070B0F",
    "base": "#0B1116",
    "raised": "#0E161D",
    "overlay": "#121D25",
    "deep": "#05080B",
}

BORDERS = {
    "hairline": "#293944",
    "control": "#30424E",
    "focus": "#F4EFE6",
}

TEXT = {
    "primary": "#F4EFE6",
    "secondary": "#AEBDC5",
    "muted": "#667B87",
    "eyebrow": "#77DBE2",
    "inverse": "#10161B",
}

STATES = {
    "success": "#85D997",
    "warning": "#E8C96A",
}


def _normalise_palette(values: Iterable[str]) -> tuple[str, ...]:
    candidates = tuple(values)
    if len(candidates) < 5 or any(not QColor(value).isValid() for value in candidates[:5]):
        raise ValueError("Command Console requires five valid accent colours")
    return tuple(QColor(value).name().upper() for value in candidates[:5])


def blend(foreground: str, background: str, foreground_ratio: float) -> str:
    """Blend two colours, returning an uppercase six-digit colour."""
    fg = QColor(foreground)
    bg = QColor(background)
    ratio = max(0.0, min(1.0, foreground_ratio))
    return QColor(
        round(fg.red() * ratio + bg.red() * (1.0 - ratio)),
        round(fg.green() * ratio + bg.green() * (1.0 - ratio)),
        round(fg.blue() * ratio + bg.blue() * (1.0 - ratio)),
    ).name().upper()


def contrast_text(colour: str) -> str:
    """Choose readable text for a user-configurable accent fill."""
    value = QColor(colour)
    luminance = 0.2126 * value.red() + 0.7152 * value.green() + 0.0722 * value.blue()
    return TEXT["inverse"] if luminance >= 118 else TEXT["primary"]


def px(value: float, scale: float, minimum: int = 1) -> int:
    """Scale a geometry token while keeping visible dimensions non-zero."""
    return max(minimum, round(value * scale))


@dataclass(frozen=True)
class ConsoleTokens:
    """Resolved Command Console token set for one scale and palette."""

    scale: float
    accents: tuple[str, ...]

    @classmethod
    def from_theme(cls, theme) -> "ConsoleTokens":
        return cls(
            scale=float(theme.scale),
            accents=_normalise_palette(theme["plot"]["color_cycler"][:5]),
        )

    def accent_dim(self, index: int) -> str:
        # 60% of the path from the accent toward the deep surface.
        return blend(self.accents[index], SURFACES["deep"], 0.40)

    def accent_edge(self, index: int) -> str:
        # 54% of the path from the accent toward the deep surface.
        return blend(self.accents[index], SURFACES["deep"], 0.46)

    def accent_tint(self, index: int) -> str:
        return blend(self.accents[index], SURFACES["raised"], 0.16)

    def stylesheet(self) -> str:
        """Generate all palette-dependent Command Console application QSS."""
        s = self.scale
        radius_control_large = px(16, s)
        radius_control_small = px(5, s)
        radius_chip_large = px(12, s)
        radius_chip_small = px(3, s)
        radius_panel = px(12, s)
        nav_edge = px(6, s)
        focus_width = px(2, s)
        drawer_cap = px(4, s)

        rules = [
            f"QFrame#commandConsoleApplicationShell {{background-color:{SURFACES['void']};border:none;}}",
            "QFrame#commandConsoleWorkspace {background:transparent;border:none;}",
            (
                "QFrame#commandConsoleMasthead {"
                f"background-color:{SURFACES['base']};border:none;"
                f"border-top:{px(5, s)}px solid {self.accents[3]};}}"
            ),
            (
                "QLabel#commandConsoleBrandMark {"
                f"color:{contrast_text(self.accents[0])};background-color:{self.accents[0]};"
                "border:none;"
                f"border-top-left-radius:{px(18, s)}px;"
                f"border-top-right-radius:{px(5, s)}px;"
                f"border-bottom-right-radius:{px(18, s)}px;"
                f"border-bottom-left-radius:{px(5, s)}px;"
                f"font-family:'Overpass';font-size:{px(22, s)}px;font-weight:700;}}"
            ),
            (
                "QLabel#commandConsoleBrandEyebrow {"
                f"color:{TEXT['eyebrow']};background:transparent;border:none;"
                f"font-family:'Roboto Mono';font-size:{px(11, s)}px;font-weight:600;}}"
            ),
            (
                "QLabel#commandConsoleBrandTitle {"
                f"color:{TEXT['primary']};background:transparent;border:none;"
                f"font-family:'Overpass';font-size:{px(28, s)}px;font-weight:700;}}"
            ),
            (
                "QFrame#commandConsolePrimaryNavigation {"
                f"background-color:{SURFACES['deep']};border:none;"
                f"border-bottom:1px solid {BORDERS['hairline']};}}"
            ),
            (
                "QPushButton[consoleRole='primaryNav'] {"
                f"color:{TEXT['primary']};border:{focus_width}px solid transparent;"
                f"border-bottom-width:{nav_edge}px;"
                f"border-top-left-radius:{radius_control_large}px;"
                f"border-top-right-radius:{radius_control_small}px;"
                f"border-bottom-right-radius:{radius_control_large}px;"
                f"border-bottom-left-radius:{radius_control_small}px;"
                f"padding:{px(7, s)}px {px(14, s)}px;text-align:left;"
                f"font-family:'Overpass';font-size:{px(15, s)}px;font-weight:700;}}"
            ),
            (
                "QPushButton[consoleRole='primaryNav'][mirrored='true'] {"
                f"border-top-left-radius:{radius_control_small}px;"
                f"border-top-right-radius:{radius_control_large}px;"
                f"border-bottom-right-radius:{radius_control_small}px;"
                f"border-bottom-left-radius:{radius_control_large}px;}}"
            ),
            (
                "QPushButton[consoleRole='primaryNav']:pressed {"
                f"padding-top:{px(9, s)}px;padding-bottom:{px(5, s)}px;}}"
            ),
            (
                "QPushButton[consoleRole='primaryNav']:disabled {"
                f"color:{TEXT['muted']};background-color:{SURFACES['overlay']};"
                f"border-color:{BORDERS['control']};}}"
            ),
            (
                "QFrame#commandConsoleContextRail {"
                "background:transparent;border:none;}"
            ),
            (
                "QFrame#commandConsoleColourRail {"
                f"background-color:{SURFACES['base']};border:none;"
                f"border-radius:{radius_panel}px;}}"
            ),
            (
                "QFrame[consoleRole='spineSegment'] {"
                "border:none;"
                f"border-radius:{px(8, s)}px;}}"
            ),
            (
                "QLabel[consoleRole='spineMark'] {"
                f"color:{TEXT['primary']};background:transparent;border:none;"
                f"font-family:'Roboto Mono';font-size:{px(11, s)}px;font-weight:600;}}"
            ),
            (
                "QFrame#commandConsoleSidebarHost {"
                f"background-color:{SURFACES['raised']};border:none;"
                f"border-radius:{radius_panel}px;}}"
            ),
            (
                "QFrame#commandConsoleSidebarContent,"
                "QFrame#commandConsoleSidebarLog,"
                "QFrame#commandConsoleSidebarLeague,"
                "QFrame#commandConsoleSidebarAbout {"
                f"background-color:{SURFACES['raised']};border:none;}}"
            ),
            (
                "QTabWidget#commandConsoleSidebarTabber::pane {"
                f"background-color:{SURFACES['raised']};border:none;}}"
            ),
            (
                "QTabWidget#commandConsoleMainTabber::pane {"
                f"background-color:{SURFACES['base']};border:none;}}"
            ),
            (
                "QFrame#commandConsoleDrawerHeader {"
                f"background-color:{SURFACES['overlay']};border:none;"
                f"border-top:{drawer_cap}px solid {self.accents[0]};}}"
            ),
            (
                "QLabel#commandConsoleDrawerSection {"
                f"color:{TEXT['eyebrow']};background:transparent;border:none;"
                f"font-family:'Roboto Mono';font-size:{px(11, s)}px;font-weight:600;}}"
            ),
            (
                "QLabel#commandConsoleDrawerTitle {"
                f"color:{TEXT['primary']};background:transparent;border:none;"
                f"font-family:'Overpass';font-size:{px(16, s)}px;font-weight:700;}}"
            ),
            (
                "QLabel[consoleRole='eyebrow'] {"
                f"color:{TEXT['eyebrow']};background:transparent;border:none;"
                f"font-family:'Roboto Mono';font-size:{px(11, s)}px;font-weight:600;}}"
            ),
            (
                "QLabel[consoleRole='title'] {"
                f"color:{TEXT['primary']};background:transparent;border:none;"
                f"font-family:'Overpass';font-size:{px(22, s)}px;font-weight:700;}}"
            ),
            (
                "QLabel[consoleRole='heading'] {"
                f"color:{TEXT['primary']};background:transparent;border:none;"
                f"font-family:'Overpass';font-size:{px(16, s)}px;font-weight:700;}}"
            ),
            (
                "QLabel[consoleRole='muted'] {"
                f"color:{TEXT['muted']};background:transparent;border:none;"
                f"font-family:'Roboto Mono';font-size:{px(11, s)}px;}}"
            ),
            (
                "QLabel[consoleRole='statValue'] {"
                f"color:{TEXT['primary']};background:transparent;border:none;"
                f"font-family:'Roboto Mono';font-size:{px(24, s)}px;font-weight:700;}}"
            ),
            (
                "QLabel[consoleRole='chip'] {"
                f"color:{TEXT['secondary']};background-color:{SURFACES['overlay']};"
                f"border:1px solid {BORDERS['control']};"
                f"border-radius:{radius_chip_large}px;padding:{px(2, s)}px {px(9, s)}px;"
                f"font-family:'Roboto Mono';font-size:{px(11, s)}px;}}"
            ),
            (
                "QFrame[consoleRole='cappedPanel'] {"
                f"background-color:{SURFACES['raised']};border:none;"
                f"border-radius:{radius_panel}px;}}"
            ),
            (
                "QFrame[consoleRole='panelCap'] {"
                f"background-color:{SURFACES['overlay']};border:none;"
                f"border-bottom:1px solid {BORDERS['hairline']};}}"
            ),
            (
                "QFrame[consoleRole='embeddedSurface'] {"
                f"background-color:{SURFACES['raised']};border:none;"
                f"border-radius:{radius_panel}px;}}"
            ),
            (
                "QFrame[consoleRole='surfacePage'] {"
                f"background-color:{SURFACES['raised']};border:none;}}"
            ),
            (
                "QFrame[consoleRole='analysisCommandDeck'] {"
                "background:transparent;border:none;}"
            ),
            (
                "QFrame[consoleRole='analysisModeRow'] {"
                f"background-color:{SURFACES['base']};"
                f"border:1px solid {BORDERS['hairline']};"
                f"border-radius:{radius_panel}px;}}"
            ),
            (
                "QFrame[consoleRole='modifierBar'] {"
                f"background-color:{SURFACES['base']};"
                f"border:1px solid {BORDERS['hairline']};"
                f"border-radius:{radius_panel}px;}}"
            ),
            (
                "QFrame[consoleRole='workbenchFilterRow'] {"
                "background:transparent;border:none;}"
            ),
            (
                "QFrame[consoleRole='workbenchTimeRow'] {"
                "background:transparent;border:none;"
                f"border-top:1px solid {BORDERS['hairline']};}}"
            ),
            (
                "QLineEdit[consoleRole='workbenchFilter'] {"
                f"background-color:{SURFACES['overlay']};color:{TEXT['primary']};"
                f"border:1px solid {BORDERS['control']};"
                f"border-radius:{radius_chip_small}px;"
                f"padding:{px(5, s)}px {px(9, s)}px;"
                f"font-family:'Roboto Mono';font-size:{px(11, s)}px;}}"
            ),
            (
                "QLineEdit[consoleRole='workbenchFilter']:hover,"
                "QLineEdit[consoleRole='workbenchFilter']:focus {"
                f"border-color:{BORDERS['focus']};}}"
            ),
            (
                "QLabel[consoleRole='chip'][status='truth'] {"
                f"color:{STATES['success']};border-color:{STATES['success']};}}"
            ),
            (
                "QTabWidget[consoleRole='surfaceTabs']::pane {"
                "background:transparent;border:none;}"
            ),
            (
                "QTabWidget#commandConsoleOverviewGraphPanel::pane {"
                f"background-color:{SURFACES['raised']};border:none;"
                f"border-radius:{radius_panel}px;}}"
            ),
            (
                "QSplitter#commandConsoleOverviewSplitter::handle {"
                f"background-color:{BORDERS['hairline']};min-height:{px(7, s)}px;"
                f"margin:{px(3, s)}px {px(18, s)}px;}}"
            ),
            (
                "QSplitter#commandConsoleAnalysisSplitter::handle {"
                f"background-color:{BORDERS['hairline']};min-height:{px(7, s)}px;"
                f"margin:{px(3, s)}px {px(18, s)}px;}}"
            ),
            (
                "QTableView[consoleRole='telemetryTable'],"
                "QTableView[consoleRole='frozenIdentityTable'] {"
                f"background-color:{SURFACES['raised']};color:{TEXT['secondary']};"
                "border:none;gridline-color:transparent;"
                "selection-background-color:transparent;"
                f"selection-color:{TEXT['primary']};}}"
            ),
            (
                "QTableView[consoleRole='telemetryTable'] QHeaderView,"
                "QTableView[consoleRole='frozenIdentityTable'] QHeaderView,"
                "QTableView[consoleRole='telemetryTable'] QTableCornerButton::section,"
                "QTableView[consoleRole='frozenIdentityTable'] QTableCornerButton::section {"
                f"background-color:{SURFACES['base']};border:none;}}"
            ),
            (
                "QTableView[consoleRole='telemetryTable'] QHeaderView::section,"
                "QTableView[consoleRole='frozenIdentityTable'] QHeaderView::section {"
                f"background-color:{SURFACES['base']};color:{TEXT['eyebrow']};"
                "border:none;"
                f"border-bottom:1px solid {BORDERS['hairline']};"
                f"padding:{px(7, s)}px {px(8, s)}px;"
                f"font-family:'Roboto Mono';font-size:{px(11, s)}px;font-weight:600;}}"
            ),
            (
                "QTreeView[consoleRole='analysisTree'] {"
                f"background-color:{SURFACES['raised']};"
                f"alternate-background-color:{SURFACES['base']};"
                f"color:{TEXT['secondary']};border:none;"
                "selection-background-color:transparent;"
                f"selection-color:{TEXT['primary']};outline:none;}}"
            ),
            (
                "QTreeView[consoleRole='analysisTree']::item {"
                f"border:none;padding:{px(3, s)}px {px(6, s)}px;}}"
            ),
            (
                "QTreeView[consoleRole='analysisTree']::item:selected {"
                f"background-color:{blend(self.accents[1], SURFACES['raised'], 0.18)};"
                f"color:{TEXT['primary']};}}"
            ),
            (
                "QTreeView[consoleRole='analysisTree'] QHeaderView::section {"
                f"background-color:{SURFACES['base']};color:{TEXT['eyebrow']};"
                "border:none;"
                f"border-bottom:1px solid {BORDERS['hairline']};"
                f"padding:{px(7, s)}px {px(8, s)}px;"
                f"font-family:'Roboto Mono';font-size:{px(11, s)}px;font-weight:600;}}"
            ),
            (
                "QComboBox[consoleRole='compactCombo'] {"
                f"background-color:{SURFACES['overlay']};color:{TEXT['secondary']};"
                f"border:1px solid {BORDERS['control']};"
                f"border-radius:{radius_chip_small}px;"
                f"padding:{px(5, s)}px {px(9, s)}px;"
                f"font-family:'Overpass';font-size:{px(11, s)}px;}}"
            ),
            (
                "QComboBox[consoleRole='compactCombo']:hover,"
                "QComboBox[consoleRole='compactCombo']:focus {"
                f"color:{TEXT['primary']};border-color:{BORDERS['focus']};}}"
            ),
            (
                "QComboBox[consoleRole='compactCombo'] QAbstractItemView {"
                f"background-color:{SURFACES['overlay']};color:{TEXT['secondary']};"
                f"border:1px solid {BORDERS['control']};"
                "selection-background-color:"
                f"{blend(self.accents[1], SURFACES['overlay'], 0.24)};"
                f"selection-color:{TEXT['primary']};}}"
            ),
            (
                "QFrame[consoleRole='capLine'] {"
                f"background-color:{SURFACES['base']};border:none;"
                f"border-bottom:1px solid {BORDERS['hairline']};}}"
            ),
            (
                "QPushButton[consoleRole='modeControl'] {"
                f"background:transparent;color:{TEXT['secondary']};"
                "border:1px solid transparent;"
                f"border-top-left-radius:{radius_chip_large}px;"
                f"border-top-right-radius:{radius_chip_small}px;"
                f"border-bottom-right-radius:{radius_chip_large}px;"
                f"border-bottom-left-radius:{radius_chip_small}px;"
                f"padding:{px(5, s)}px {px(10, s)}px;"
                f"font-family:'Overpass';font-size:{px(11, s)}px;font-weight:600;}}"
            ),
            (
                "QPushButton[consoleRole='modeControl']:pressed {"
                f"padding-top:{px(7, s)}px;padding-bottom:{px(3, s)}px;}}"
            ),
            (
                "QPushButton[consoleRole='modeControl']:disabled {"
                f"color:{TEXT['muted']};background-color:{SURFACES['overlay']};"
                f"border-color:{BORDERS['hairline']};}}"
            ),
            (
                "QPushButton[consoleRole='actionButton'] {"
                f"background-color:{SURFACES['overlay']};color:{TEXT['secondary']};"
                f"border:1px solid {BORDERS['control']};"
                f"border-radius:{radius_chip_small}px;padding:{px(5, s)}px {px(10, s)}px;"
                f"font-family:'Overpass';font-size:{px(11, s)}px;font-weight:600;}}"
            ),
            (
                "QPushButton[consoleRole='actionButton']:hover:enabled,"
                "QPushButton[consoleRole='actionButton']:focus:enabled {"
                f"color:{TEXT['primary']};border-color:{BORDERS['focus']};}}"
            ),
            (
                "QPushButton[consoleRole='actionButton']:pressed {"
                f"padding-top:{px(7, s)}px;padding-bottom:{px(3, s)}px;}}"
            ),
            (
                "QPushButton[consoleRole='actionButton']:disabled {"
                f"color:{TEXT['muted']};border-color:{BORDERS['hairline']};}}"
            ),
            (
                "QFrame[consoleRole='listRow'] {"
                f"background-color:{SURFACES['raised']};border:none;"
                f"border-bottom:1px solid {BORDERS['hairline']};}}"
            ),
        ]

        for index, accent in enumerate(self.accents):
            dim = self.accent_dim(index)
            edge = self.accent_edge(index)
            tint = self.accent_tint(index)
            inverse = contrast_text(accent)
            selector = f"[accentIndex='{index}']"
            rules.extend((
                (
                    f"QPushButton[consoleRole='primaryNav']{selector}:enabled {{"
                    f"background-color:{dim};border-color:{edge};"
                    f"border-bottom-color:{edge};}}"
                ),
                (
                    f"QPushButton[consoleRole='primaryNav']{selector}:hover,"
                    f"QPushButton[consoleRole='primaryNav']{selector}[visualActive='true']:enabled {{"
                    f"background-color:{accent};color:{inverse};}}"
                ),
                (
                    f"QPushButton[consoleRole='primaryNav']{selector}[visualActive='true']:enabled {{"
                    f"border-color:{BORDERS['focus']};border-bottom-color:{edge};}}"
                ),
                (
                    f"QFrame[consoleRole='spineSegment']{selector} {{"
                    f"background-color:{dim};}}"
                ),
                (
                    f"QFrame[consoleRole='spineSegment']{selector}[active='true'] {{"
                    f"background-color:{accent};border-right:{drawer_cap}px solid {BORDERS['focus']};}}"
                ),
                (
                    f"QFrame[consoleRole='spineSegment']{selector}[active='true'] "
                    f"QLabel[consoleRole='spineMark'] {{color:{inverse};}}"
                ),
                (
                    f"QFrame#commandConsoleDrawerHeader[section='{index}'] {{"
                    f"border-top:{drawer_cap}px solid {accent};background-color:{tint};}}"
                ),
                (
                    f"QFrame[consoleRole='panelCap']{selector} {{"
                    f"border-left:{drawer_cap}px solid {accent};}}"
                ),
                (
                    f"QFrame[consoleRole='capLine']{selector} {{"
                    f"border-left:{drawer_cap}px solid {accent};}}"
                ),
                (
                    f"QPushButton[consoleRole='modeControl']{selector}:hover:enabled {{"
                    f"color:{TEXT['primary']};border-color:{accent};}}"
                ),
                (
                    f"QPushButton[consoleRole='modeControl']{selector}:checked:enabled {{"
                    f"color:{inverse};background-color:{accent};border-color:{accent};"
                    f"border-bottom:{px(3, s)}px solid {edge};}}"
                ),
                (
                    f"QPushButton[consoleRole='modeControl']{selector}"
                    "[visualActive='true']:enabled {"
                    f"color:{inverse};background-color:{accent};border-color:{accent};"
                    f"border-bottom:{px(3, s)}px solid {edge};}}"
                ),
                (
                    f"QPushButton[consoleRole='actionButton']{selector}[primary='true']:enabled {{"
                    f"color:{inverse};background-color:{accent};border-color:{accent};}}"
                ),
                (
                    f"QPushButton[consoleRole='actionButton']{selector}"
                    "[toggleAction='true']:checked:enabled {"
                    f"color:{inverse};background-color:{accent};border-color:{accent};}}"
                ),
                (
                    f"QPushButton[consoleRole='actionButton']{selector}"
                    "[toggleAction='true'][visualActive='true']:enabled {"
                    f"color:{inverse};background-color:{accent};border-color:{accent};}}"
                ),
                (
                    f"QLabel[consoleRole='chip']{selector}[status='modified'] {{"
                    f"color:{accent};border-color:{accent};}}"
                ),
            ))

        # Qt's Windows style can let the inherited generic ``QPushButton:checked`` rule win
        # over a dynamic-property + pseudo-state selector on nested controls.  These stable
        # Analysis object names provide an equally palette-aware, deterministic active state.
        # Keep the mapping beside the token palette instead of introducing view-local colours.
        for mode_number, accent_index in enumerate((0, 4, 3, 2), start=1):
            accent = self.accents[accent_index]
            edge = self.accent_edge(accent_index)
            inverse = contrast_text(accent)
            rules.append(
                f"QPushButton#commandConsoleAnalysisMode{mode_number}:checked,"
                f"QPushButton#commandConsoleAnalysisMode{mode_number}[visualActive='true'] {{"
                f"color:{inverse};background-color:{accent};border-color:{accent};"
                f"border-bottom:{px(3, s)}px solid {edge};}}"
            )
        analysis_accent = self.accents[1]
        rules.append(
            "QPushButton#analysisFreezeButton:checked,"
            "QPushButton#analysisFreezeButton[visualActive='true'] {"
            f"color:{contrast_text(analysis_accent)};"
            f"background-color:{analysis_accent};border-color:{analysis_accent};}}"
        )
        return "\n".join(rules)


def build_console_stylesheet(theme) -> str:
    """Convenience entry point used during Command Console startup."""
    return ConsoleTokens.from_theme(theme).stylesheet()


def refresh_style(widget: QWidget, descendants: bool = True) -> None:
    """Re-evaluate QSS selectors after a dynamic property changes."""
    targets = (widget, *widget.findChildren(QWidget)) if descendants else (widget,)
    for target in targets:
        style = target.style()
        style.unpolish(target)
        style.polish(target)
        target.update()
