import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from re_oscr.theme import AppTheme
from re_oscr.themes import (
    COMMAND_CONSOLE_THEME_ID,
    DEFAULT_THEME_ID,
    ThemeDefinition,
    available_themes,
    resolve_theme,
)
from re_oscr.themes.registry import THEME_REGISTRY


class DefaultThemeTests(unittest.TestCase):
    def setUp(self):
        self.theme = AppTheme(1.0)

    def test_default_palette_matches_oscr_11_1(self):
        self.assertEqual(self.theme["app"]["bg"], "#1a1a1a")
        self.assertEqual(self.theme["app"]["fg"], "#eeeeee")
        self.assertEqual(self.theme["app"]["oscr"], "#c82934")
        self.assertEqual(self.theme["defaults"]["mbg"], "#242424")
        self.assertEqual(self.theme["defaults"]["lbg"], "#404040")

    def test_default_plot_palette_remains_readable_and_complete(self):
        self.assertEqual(
            self.theme["plot"]["color_cycler"],
            (
                "#8f54b4", "#B14D54", "#89B177", "#545DB4", "#C8B74E",
                "#B45492", "#A27534", "#54A9B4", "#E47B1C", "#BCBCBC",
            ),
        )

    def test_stylesheet_generation_resolves_shortcuts_and_scale(self):
        scaled_theme = AppTheme(1.5)

        stylesheet = scaled_theme.get_style("frame")
        button_stylesheet = scaled_theme.get_style_class("QPushButton", "button")

        self.assertIn("background-color:#1a1a1a", stylesheet)
        self.assertIn("QPushButton", button_stylesheet)
        self.assertIn("border-color:#c82934", button_stylesheet)
        self.assertIn("margin:4.5px 4.5px 4.5px 4.5px", button_stylesheet)


class ThemeRegistryTests(unittest.TestCase):
    def test_registry_has_stable_public_theme_order(self):
        self.assertEqual(
            tuple((definition.theme_id, definition.display_name)
                  for definition in available_themes()),
            ((DEFAULT_THEME_ID, "OSCR-UI Legacy"),
             (COMMAND_CONSOLE_THEME_ID, "Command Console")),
        )

    def test_command_console_overrides_default_without_mutating_it(self):
        project_root = Path(__file__).resolve().parents[1]
        default = resolve_theme(DEFAULT_THEME_ID, 1.0, project_root)
        command = resolve_theme(COMMAND_CONSOLE_THEME_ID, 1.0, project_root)

        self.assertFalse(default.fallback_used)
        self.assertFalse(command.fallback_used)
        self.assertEqual(default.theme["defaults"]["oscr"], "#c82934")
        self.assertEqual(command.theme["defaults"]["oscr"], "#FF8A2A")
        self.assertEqual(
            command.theme["plot"]["color_cycler"][:5],
            ("#FF8A2A", "#D4AD3F", "#9A6BC4", "#4FC3CC", "#D94B55"),
        )
        self.assertNotIn("overview_bar_colours", default.theme["plot"])
        self.assertTrue(command.theme["plot"]["overview_bar_colours"])

    def test_command_console_accepts_a_validated_custom_palette(self):
        project_root = Path(__file__).resolve().parents[1]
        custom = ("#123456", "abcdef", "invalid", "#AABBCC", "#010203")

        resolution = resolve_theme(
            COMMAND_CONSOLE_THEME_ID, 1.0, project_root,
            command_console_palette=custom)

        self.assertEqual(
            resolution.theme["plot"]["color_cycler"][:5],
            ("#123456", "#ABCDEF", "#9A6BC4", "#AABBCC", "#010203"),
        )
        self.assertEqual(resolution.theme["defaults"]["oscr"], "#123456")

    def test_unknown_theme_falls_back_to_default(self):
        with self.assertLogs("re_oscr.themes.registry", level="WARNING"):
            resolution = resolve_theme("missing-theme", 1.0)

        self.assertTrue(resolution.fallback_used)
        self.assertEqual(resolution.definition.theme_id, DEFAULT_THEME_ID)
        self.assertEqual(resolution.theme["defaults"]["oscr"], "#c82934")

    def test_factory_failure_falls_back_to_default(self):
        def broken_factory(_scale):
            raise RuntimeError("deliberate test failure")

        broken = ThemeDefinition("broken", "Broken", broken_factory)
        with patch.dict(THEME_REGISTRY, {"broken": broken}):
            with self.assertLogs("re_oscr.themes.registry", level="ERROR"):
                resolution = resolve_theme("broken", 1.0)

        self.assertTrue(resolution.fallback_used)
        self.assertEqual(resolution.definition.theme_id, DEFAULT_THEME_ID)

    def test_missing_theme_asset_directory_falls_back_to_default(self):
        with TemporaryDirectory() as temp_dir:
            with self.assertLogs("re_oscr.themes.registry", level="ERROR"):
                resolution = resolve_theme(
                    COMMAND_CONSOLE_THEME_ID, 1.0, Path(temp_dir))

        self.assertTrue(resolution.fallback_used)
        self.assertEqual(resolution.definition.theme_id, DEFAULT_THEME_ID)


if __name__ == "__main__":
    unittest.main()
