"""Command Console dedication plaque for RE-OSCR credits and lineage."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .console.components import action_button
from .console.tokens import ConsoleTokens, px


class DedicationPlaqueDialog(QDialog):
    """Show RE-OSCR's project credits using the active Command Console palette."""

    def __init__(self, theme, parent=None):
        super().__init__(parent)
        self._tokens = ConsoleTokens.from_theme(theme)
        self.setObjectName("commandConsoleDedicationPlaque")
        self.setProperty("consoleRole", "dedicationPlaqueDialog")
        self.setWindowTitle("RE-OSCR — Dedication Plaque")
        self.setModal(True)
        self.resize(px(680, theme.scale), px(630, theme.scale))

        outer = QVBoxLayout(self)
        outer.setContentsMargins(
            px(18, theme.scale), px(18, theme.scale),
            px(18, theme.scale), px(18, theme.scale))
        outer.setSpacing(px(12, theme.scale))

        plaque = QFrame(self)
        plaque.setProperty("consoleRole", "dedicationPlaquePanel")
        plaque_layout = QVBoxLayout(plaque)
        plaque_layout.setContentsMargins(0, 0, 0, px(22, theme.scale))
        plaque_layout.setSpacing(0)
        plaque_layout.addWidget(self._rail(plaque))
        plaque_layout.addSpacing(px(20, theme.scale))

        plaque_layout.addWidget(self._label(
            "SHIP'S DEDICATION PLAQUE // COMMAND CONSOLE", "eyebrow", plaque))
        title = self._label("RETRO ESCALATION", "plaqueTitle", plaque)
        plaque_layout.addWidget(title)
        plaque_layout.addWidget(self._label(
            "RE-OSCR • REGISTRY NX-2015 • RECOMMISSIONED 2026", "plaqueRegistry", plaque))
        plaque_layout.addSpacing(px(18, theme.scale))
        plaque_layout.addWidget(self._divider(plaque))
        plaque_layout.addSpacing(px(18, theme.scale))

        for accent, role, attribution in (
                (1, "PARSER", "OSCR PROJECT"),
                (2, "ANALYSIS DOCTRINE", "ANOTHERNATHAN / CLA"),
                (3, "LEGACY APPEARANCE", "UPSTREAM FRONTEND BASELINE"),
                (4, "LICENSE", "GPL-3.0 • SOURCE TRAVELS WITH THE SHIP")):
            plaque_layout.addWidget(self._role_line(accent, role, attribution, plaque))
            plaque_layout.addSpacing(px(5, theme.scale))

        plaque_layout.addSpacing(px(14, theme.scale))
        plaque_layout.addWidget(self._label("PRODUCED AND MAINTAINED BY", "plaqueRegistry", plaque))
        plaque_layout.addWidget(self._label("SARC", "plaqueProducer", plaque))
        handle = self._label(
            '<a href="https://www.youtube.com/@sarcasmdetector">@SarcasmDetector</a>',
            "plaqueLink", plaque)
        handle.setOpenExternalLinks(True)
        handle.setTextInteractionFlags(Qt.TextInteractionFlag.LinksAccessibleByMouse)
        plaque_layout.addWidget(handle)
        plaque_layout.addSpacing(px(12, theme.scale))
        lineage = self._label(
            "DESCENDED FROM CLR • SCM • OSCR • CLA", "plaqueRegistry", plaque)
        plaque_layout.addWidget(lineage)
        plaque_layout.addSpacing(px(16, theme.scale))
        plaque_layout.addWidget(self._divider(plaque))
        plaque_layout.addSpacing(px(12, theme.scale))
        plaque_layout.addWidget(self._label(
            "“We'll make it pretty later.”", "plaqueQuote", plaque))
        plaque_layout.addWidget(self._label(
            "— LATER, 2015–2026", "plaqueMotto", plaque))
        outer.addWidget(plaque)

        dismiss = action_button("DISMISS", "dedicationPlaqueDismiss", accent_index=0, primary=True)
        dismiss.setParent(self)
        dismiss.clicked.connect(self.accept)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(dismiss)
        buttons.addStretch(1)
        outer.addLayout(buttons)

    def _rail(self, parent: QWidget) -> QWidget:
        rail = QFrame(parent)
        rail.setProperty("consoleRole", "dedicationPlaqueRail")
        rail.setFixedHeight(px(8, self._tokens.scale))
        layout = QHBoxLayout(rail)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        for index in range(5):
            segment = QFrame(rail)
            segment.setProperty("consoleRole", "dedicationPlaqueRailSegment")
            segment.setProperty("accentIndex", str(index))
            layout.addWidget(segment, 1)
        return rail

    def _divider(self, parent: QWidget) -> QWidget:
        divider = QWidget(parent)
        layout = QHBoxLayout(divider)
        layout.setContentsMargins(px(42, self._tokens.scale), 0, px(42, self._tokens.scale), 0)
        layout.setSpacing(px(10, self._tokens.scale))
        for index in range(3):
            part = QFrame(divider)
            part.setProperty(
                "consoleRole",
                "dedicationPlaqueDividerMark" if index == 1 else "dedicationPlaqueDivider",
            )
            if index == 1:
                part.setFixedSize(px(30, self._tokens.scale), px(6, self._tokens.scale))
            else:
                part.setFixedHeight(px(2, self._tokens.scale))
            layout.addWidget(part, 0 if index == 1 else 1)
        return divider

    def _role_line(
            self, accent_index: int, role: str, attribution: str, parent: QWidget) -> QWidget:
        line = QWidget(parent)
        layout = QHBoxLayout(line)
        layout.setContentsMargins(px(18, self._tokens.scale), 0, px(18, self._tokens.scale), 0)
        layout.setSpacing(px(8, self._tokens.scale))
        layout.addStretch(1)
        label = self._label(role, "plaqueRole", line)
        label.setProperty("accentIndex", str(accent_index))
        layout.addWidget(label)
        layout.addWidget(self._label("—", "plaqueRegistry", line))
        layout.addWidget(self._label(attribution, "plaqueAttribution", line))
        layout.addStretch(1)
        return line

    @staticmethod
    def _label(text: str, role: str, parent: QWidget) -> QLabel:
        label = QLabel(text, parent)
        label.setProperty("consoleRole", role)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setWordWrap(True)
        return label


__all__ = ("DedicationPlaqueDialog",)
