import os
import re
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QWidget

from re_oscr.console.components import (
    action_button,
    cap_line,
    capped_panel,
    chip,
    embedded_surface,
    list_row,
    mode_button,
    primary_navigation_button,
)
from re_oscr.console.tokens import (
    BORDERS,
    STATES,
    SURFACES,
    TEXT,
    ConsoleTokens,
    contrast_text,
    px,
)


DEFAULT_ACCENTS = ("#FF8A2A", "#D4AD3F", "#9A6BC4", "#4FC3CC", "#D94B55")


class _ThemeFixture:
    def __init__(self, scale=1.0, accents=DEFAULT_ACCENTS):
        self.scale = scale
        self._plot = {"color_cycler": tuple(accents)}

    def __getitem__(self, key):
        if key == "plot":
            return self._plot
        raise KeyError(key)


class ConsoleTokenTests(unittest.TestCase):
    def test_canonical_colour_tokens_match_the_design(self):
        self.assertEqual(
            SURFACES,
            {
                "void": "#070B0F",
                "base": "#0B1116",
                "raised": "#0E161D",
                "overlay": "#121D25",
                "deep": "#05080B",
            },
        )
        self.assertEqual(
            BORDERS,
            {
                "hairline": "#293944",
                "control": "#30424E",
                "focus": "#F4EFE6",
            },
        )
        self.assertEqual(
            TEXT,
            {
                "primary": "#F4EFE6",
                "secondary": "#AEBDC5",
                "muted": "#667B87",
                "eyebrow": "#77DBE2",
                "inverse": "#10161B",
            },
        )
        self.assertEqual(STATES, {"success": "#85D997", "warning": "#E8C96A"})

    def test_theme_resolution_keeps_exactly_five_normalised_accents(self):
        tokens = ConsoleTokens.from_theme(
            _ThemeFixture(
                accents=(
                    "#ff8a2a", "#d4ad3f", "#9a6bc4", "#4fc3cc", "#d94b55", "red"
                )
            )
        )

        self.assertEqual(tokens.accents, DEFAULT_ACCENTS)
        self.assertEqual(len(tokens.accents), 5)

        with self.assertRaises(ValueError):
            ConsoleTokens.from_theme(_ThemeFixture(accents=DEFAULT_ACCENTS[:4]))
        with self.assertRaises(ValueError):
            ConsoleTokens.from_theme(
                _ThemeFixture(accents=(*DEFAULT_ACCENTS[:4], "not-a-colour"))
            )

    def test_default_accent_derivations_are_stable(self):
        tokens = ConsoleTokens(1.0, DEFAULT_ACCENTS)

        self.assertEqual(
            tuple(tokens.accent_dim(index) for index in range(5)),
            ("#693C17", "#584A20", "#413055", "#235358", "#5A2329"),
        )
        self.assertEqual(
            tuple(tokens.accent_edge(index) for index in range(5)),
            ("#784419", "#645423", "#4A3660", "#275E64", "#67272D"),
        )
        self.assertEqual(
            tuple(tokens.accent_tint(index) for index in range(5)),
            ("#35291F", "#2E2E22", "#242438", "#183239", "#2E1E26"),
        )

        stylesheet = tokens.stylesheet()
        for index, accent in enumerate(DEFAULT_ACCENTS):
            self.assertIn(accent, stylesheet)
            self.assertIn(tokens.accent_dim(index), stylesheet)
            self.assertIn(tokens.accent_edge(index), stylesheet)
            self.assertIn(tokens.accent_tint(index), stylesheet)

    def test_contrast_text_uses_the_documented_light_and_dark_roles(self):
        self.assertEqual(
            tuple(contrast_text(accent) for accent in DEFAULT_ACCENTS),
            (TEXT["inverse"], TEXT["inverse"], TEXT["inverse"], TEXT["inverse"], TEXT["primary"]),
        )
        self.assertEqual(contrast_text("#FFFFFF"), TEXT["inverse"])
        self.assertEqual(contrast_text("#000000"), TEXT["primary"])
        self.assertEqual(contrast_text("#777777"), TEXT["inverse"])
        self.assertEqual(contrast_text("#757575"), TEXT["primary"])

    def test_geometry_and_type_scale_at_supported_values(self):
        expected_minimum_type = {0.5: 6, 1.0: 11, 1.5: 16}
        expected_brand_type = {0.5: 14, 1.0: 28, 1.5: 42}

        for scale in (0.5, 1.0, 1.5):
            with self.subTest(scale=scale):
                self.assertEqual(px(4, scale), round(4 * scale))
                self.assertGreaterEqual(px(1, scale), 1)
                stylesheet = ConsoleTokens(scale, DEFAULT_ACCENTS).stylesheet()
                font_sizes = [int(value) for value in re.findall(r"font-size:(\d+)px", stylesheet)]
                self.assertTrue(font_sizes)
                self.assertEqual(min(font_sizes), expected_minimum_type[scale])
                self.assertIn(
                    f"font-size:{expected_brand_type[scale]}px;font-weight:700",
                    stylesheet,
                )

    def test_global_stylesheet_defines_interaction_state_selectors(self):
        stylesheet = ConsoleTokens(1.0, DEFAULT_ACCENTS).stylesheet()

        required_selectors = (
            "QPushButton[consoleRole='primaryNav']:pressed",
            "QPushButton[consoleRole='primaryNav']:disabled",
            "QPushButton[consoleRole='primaryNav'][accentIndex='0']:hover",
            "QPushButton[consoleRole='primaryNav'][accentIndex='0'][visualActive='true']",
            "QFrame[consoleRole='spineSegment'][accentIndex='0'][active='true']",
            "QPushButton[consoleRole='modeControl'][accentIndex='0']:hover",
            "QPushButton[consoleRole='modeControl'][accentIndex='0']:checked",
            "QPushButton[consoleRole='actionButton']:hover",
            "QPushButton[consoleRole='actionButton']:focus",
            "QPushButton[consoleRole='actionButton']:disabled",
            "QFrame[consoleRole='workbenchClauseRow']",
            "QScrollArea[consoleRole='workbenchClauseScroll'] QScrollBar:horizontal",
            "QPushButton[consoleRole='filterClauseChip']",
            "QPushButton[consoleRole='filterClauseChip']:hover",
            "QSplitter#commandConsoleAnalysisSplitter::handle:hover",
            "QTreeView[consoleRole='analysisTree'] QScrollBar::handle:horizontal:hover",
            "QTreeView[consoleRole='analysisTree'] QScrollBar::handle:vertical:hover",
            "AnalysisTreeView",
        )
        for selector in required_selectors:
            with self.subTest(selector=selector):
                self.assertIn(selector, stylesheet)


class ConsoleComponentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def assert_style_free(self, widget):
        self.assertEqual(widget.styleSheet(), "", widget.objectName())
        for child in widget.findChildren(QWidget):
            self.assertEqual(child.styleSheet(), "", child.objectName())

    def test_component_builders_assign_roles_without_local_styles(self):
        navigation = primary_navigation_button(
            1.0, 1, "Overview", 0, "testPrimaryNavigation"
        )
        mode = mode_button(1.0, "T1", "Summary", 0, "testMode")
        action = action_button("Copy", "testAction", 0, primary=True)
        status_chip = chip("READY", "testChip")
        capped = capped_panel(1.0, "testCappedPanel", "TELEMETRY", "SUMMARY", 0)
        embedded = embedded_surface(1.0, "testEmbeddedSurface")
        cap = cap_line(1.0, "testCapLine", "ACTIVE", "OVERVIEW", 0)
        row = list_row("testListRow")

        self.assertEqual(navigation.property("consoleRole"), "primaryNav")
        self.assertEqual(navigation.property("accentIndex"), "0")
        self.assertEqual(navigation.text(), "01   OVERVIEW")
        self.assertEqual(mode.property("consoleRole"), "modeControl")
        self.assertTrue(mode.isCheckable())
        self.assertEqual(action.property("consoleRole"), "actionButton")
        self.assertTrue(action.property("primary"))
        self.assertEqual(status_chip.property("consoleRole"), "chip")
        self.assertEqual(capped.frame.property("consoleRole"), "cappedPanel")
        self.assertEqual(capped.cap.property("consoleRole"), "panelCap")
        self.assertEqual(embedded.frame.property("consoleRole"), "embeddedSurface")
        self.assertEqual(cap.frame.property("consoleRole"), "capLine")
        self.assertEqual(row.property("consoleRole"), "listRow")

        for widget in (
            navigation,
            mode,
            action,
            status_chip,
            capped.frame,
            embedded.frame,
            cap.frame,
            row,
        ):
            with self.subTest(widget=widget.objectName()):
                self.assert_style_free(widget)


if __name__ == "__main__":
    unittest.main()
