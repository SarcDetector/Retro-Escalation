import tempfile
import unittest
from pathlib import Path

from re_oscr.config import OSCRConfig, OSCRSettings


class OSCRSettingsTests(unittest.TestCase):
    def test_frontend_settings_use_re_oscr_name_with_legacy_migration_source(self):
        config = OSCRConfig()

        self.assertEqual(config.settings_file, "RE_OSCR_settings.ini")
        self.assertEqual(config.legacy_settings_files, ("OSCR_UI_settings.ini",))
        self.assertEqual(
            config.link_cla,
            "https://github.com/AnotherNathan/STO_CombatLogAnalyzer",
        )

    def test_fresh_settings_keep_parser_defaults_and_use_command_console(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = OSCRSettings(Path(temp_dir, "settings.ini"))

            self.assertFalse(settings.auto_scan)
            self.assertEqual(settings.analysis_presentation_mode, "simple")
            self.assertEqual(settings.combat_min_lines, 20)
            self.assertEqual(settings.combats_to_parse, 10)
            self.assertEqual(settings.graph_resolution, 0.2)
            self.assertEqual(settings.language, "en")
            self.assertEqual(settings.theme_id, "command_console")
            self.assertEqual(settings.ui_scale, 1.0)
            self.assertEqual(settings.dmg_columns, [True] * 21)
            self.assertEqual(settings.heal_columns, [True] * 13)
            self.assertFalse(settings.liveparser__auto_enabled)
            self.assertEqual(
                settings.liveparser__columns,
                [True, False, True, False, False, False, False],
            )
            self.assertFalse(settings.liveparser__copy_kills)
            self.assertFalse(settings.liveparser__graph_active)
            self.assertEqual(settings.liveparser__graph_field, 0)
            self.assertEqual(settings.liveparser__player_display, "Handle")
            self.assertEqual(settings.liveparser__window_scale, 1.0)
            self.assertEqual(settings.liveparser__window_opacity, 0.85)
            self.assertEqual(settings.overlay__custom_css_path, "")
            self.assertEqual(settings.overlay__feed_bind, "127.0.0.1")
            self.assertFalse(settings.overlay__feed_enabled)
            self.assertEqual(settings.overlay__feed_port, 47025)
            self.assertEqual(settings.overlay__feed_token, "")
            self.assertEqual(settings.overlay__hotkey_hide_mode, "all")
            self.assertEqual(settings.overlay__hotkey_visibility, "")
            self.assertEqual(settings.command_console_palette_preset, "command")
            self.assertEqual(
                settings.command_console_accents,
                ["#FF8A2A", "#D4AD3F", "#9A6BC4", "#4FC3CC", "#D94B55"],
            )
            self.assertEqual(settings.command_console_background_mode, "none")
            self.assertEqual(settings.command_console_background_opacity, 0.28)
            self.assertEqual(settings.command_console_background_path, "")
            self.assertFalse(settings.workbench_auto_enable_rules)
            self.assertEqual(settings.workbench_auto_rules, "[]")
            self.assertEqual(settings.workbench_auto_rule_set, "")
            self.assertEqual(settings.workbench_rule_set, "Community examples")

    def test_settings_round_trip_without_losing_types(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings_path = Path(temp_dir, "settings.ini")
            settings = OSCRSettings(settings_path)
            settings.auto_scan = True
            settings.analysis_presentation_mode = "advanced"
            settings.combats_to_parse = 7
            settings.graph_resolution = 0.5
            settings.language = "de"
            settings.theme_id = "command_console"
            settings.ui_scale = 1.2
            settings.dmg_columns[3] = False
            settings.dmg_columns[7] = False
            settings.heal_columns[2] = False
            settings.liveparser__columns = [True, False, True, True, False, False, True]
            settings.overlay__custom_css_path = "C:/Styles/re-oscr.css"
            settings.overlay__feed_bind = "192.168.1.25"
            settings.overlay__feed_enabled = True
            settings.overlay__feed_port = 49152
            settings.overlay__feed_token = "portable_test_token_123456789"
            settings.overlay__hotkey_hide_mode = "popout"
            settings.overlay__hotkey_visibility = "Ctrl+Shift+L"
            settings.favorite_ladders = ["alpha", "beta"]
            settings.command_console_palette_preset = "custom"
            settings.command_console_accents = [
                "#102030", "#203040", "#304050", "#405060", "#506070"]
            settings.command_console_background_mode = "custom"
            settings.command_console_background_opacity = 0.42
            settings.command_console_background_path = "C:/Images/bridge.webp"
            settings.workbench_rule_set = "My ISE rules"
            settings.workbench_auto_enable_rules = True
            settings.workbench_auto_rules = '["group-a","exclude-b"]'
            settings.workbench_auto_rule_set = "My ISE rules"
            settings.state__sidebar_collapsed = True
            settings.store_settings()
            settings._settings.sync()

            restored = OSCRSettings(settings_path)

            self.assertIs(restored.auto_scan, True)
            self.assertEqual(restored.analysis_presentation_mode, "advanced")
            self.assertEqual(restored.combats_to_parse, 7)
            self.assertEqual(restored.graph_resolution, 0.5)
            self.assertEqual(restored.language, "de")
            self.assertEqual(restored.theme_id, "command_console")
            self.assertEqual(restored.ui_scale, 1.2)
            expected_damage_columns = [True] * 21
            expected_damage_columns[3] = False
            expected_damage_columns[7] = False
            self.assertEqual(restored.dmg_columns, expected_damage_columns)
            expected_heal_columns = [True] * 13
            expected_heal_columns[2] = False
            self.assertEqual(restored.heal_columns, expected_heal_columns)
            self.assertEqual(
                restored.liveparser__columns,
                [True, False, True, True, False, False, True],
            )
            self.assertEqual(restored.overlay__custom_css_path, "C:/Styles/re-oscr.css")
            self.assertEqual(restored.overlay__feed_bind, "192.168.1.25")
            self.assertTrue(restored.overlay__feed_enabled)
            self.assertEqual(restored.overlay__feed_port, 49152)
            self.assertEqual(
                restored.overlay__feed_token, "portable_test_token_123456789")
            self.assertEqual(restored.overlay__hotkey_hide_mode, "popout")
            self.assertEqual(restored.overlay__hotkey_visibility, "Ctrl+Shift+L")
            self.assertEqual(restored.favorite_ladders, ["alpha", "beta"])
            self.assertEqual(restored.command_console_palette_preset, "custom")
            self.assertEqual(
                restored.command_console_accents,
                ["#102030", "#203040", "#304050", "#405060", "#506070"],
            )
            self.assertEqual(restored.command_console_background_mode, "custom")
            self.assertEqual(restored.workbench_rule_set, "My ISE rules")
            self.assertTrue(restored.workbench_auto_enable_rules)
            self.assertEqual(
                restored.workbench_auto_rules, '["group-a","exclude-b"]')
            self.assertEqual(restored.workbench_auto_rule_set, "My ISE rules")
            self.assertEqual(restored.command_console_background_opacity, 0.42)
            self.assertEqual(
                restored.command_console_background_path, "C:/Images/bridge.webp")
            self.assertIs(restored.state__sidebar_collapsed, True)

    def test_settings_file_without_theme_value_uses_command_console(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings_path = Path(temp_dir, "legacy-settings.ini")
            legacy = OSCRSettings(settings_path)
            legacy._settings.setValue("ui_scale", 1.25)
            legacy._settings.sync()

            migrated = OSCRSettings(settings_path)

            self.assertEqual(migrated.ui_scale, 1.25)
            self.assertEqual(migrated.theme_id, "command_console")

    def test_removed_background_modes_migrate_to_flat_workspace(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings_path = Path(temp_dir, "settings.ini")
            legacy = OSCRSettings(settings_path)
            legacy._settings.setValue("command_console_background_mode", "cosmic")
            legacy._settings.sync()

            migrated = OSCRSettings(settings_path)

            self.assertEqual(migrated.command_console_background_mode, "none")

    def test_explicit_legacy_theme_round_trips(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings_path = Path(temp_dir, "settings.ini")
            settings = OSCRSettings(settings_path)
            settings.theme_id = "default"
            settings.store_settings()
            settings._settings.sync()

            self.assertEqual(OSCRSettings(settings_path).theme_id, "default")

    def test_unknown_palette_preset_uses_complete_command_default(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings_path = Path(temp_dir, "settings.ini")
            settings = OSCRSettings(settings_path)
            settings._settings.setValue("command_console_palette_preset", "missing")
            settings._settings.setValue(
                "command_console_accents",
                ["#010101", "#020202", "#030303", "#040404", "#050505"])
            settings._settings.sync()

            restored = OSCRSettings(settings_path)
            self.assertEqual(restored.command_console_palette_preset, "command")
            self.assertEqual(
                restored.command_console_accents,
                ["#FF8A2A", "#D4AD3F", "#9A6BC4", "#4FC3CC", "#D94B55"])

    def test_unknown_analysis_presentation_mode_returns_to_simple(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings_path = Path(temp_dir, "settings.ini")
            settings = OSCRSettings(settings_path)
            settings._settings.setValue("analysis_presentation_mode", "dense")
            settings._settings.sync()

            self.assertEqual(OSCRSettings(settings_path).analysis_presentation_mode, "simple")

    def test_invalid_overlay_controls_return_to_safe_defaults(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings_path = Path(temp_dir, "settings.ini")
            settings = OSCRSettings(settings_path)
            settings._settings.setValue("overlay__feed_port", 80)
            settings._settings.setValue("overlay__hotkey_hide_mode", "everything")
            settings._settings.sync()

            restored = OSCRSettings(settings_path)
            self.assertEqual(restored.overlay__feed_port, 47025)
            self.assertEqual(restored.overlay__hotkey_hide_mode, "all")


if __name__ == "__main__":
    unittest.main()
