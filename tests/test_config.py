import tempfile
import unittest
from pathlib import Path

from re_oscr.config import OSCRConfig, OSCRSettings


class OSCRSettingsTests(unittest.TestCase):
    def test_frontend_settings_use_re_oscr_name_with_legacy_migration_source(self):
        config = OSCRConfig()

        self.assertEqual(config.settings_file, "RE_OSCR_settings.ini")
        self.assertEqual(config.legacy_settings_files, ("OSCR_UI_settings.ini",))

    def test_fresh_settings_match_oscr_11_1_defaults(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = OSCRSettings(Path(temp_dir, "settings.ini"))

            self.assertFalse(settings.auto_scan)
            self.assertEqual(settings.combat_min_lines, 20)
            self.assertEqual(settings.combats_to_parse, 10)
            self.assertEqual(settings.graph_resolution, 0.2)
            self.assertEqual(settings.language, "en")
            self.assertEqual(settings.theme_id, "default")
            self.assertEqual(settings.ui_scale, 1.0)
            self.assertEqual(settings.dmg_columns, [True] * 21)
            self.assertEqual(settings.heal_columns, [True] * 13)
            self.assertEqual(settings.command_console_palette_preset, "command")
            self.assertEqual(
                settings.command_console_accents,
                ["#FF8A2A", "#D4AD3F", "#9A6BC4", "#4FC3CC", "#D94B55"],
            )
            self.assertEqual(settings.command_console_background_mode, "cosmic")
            self.assertEqual(settings.command_console_background_opacity, 0.28)
            self.assertEqual(settings.command_console_background_path, "")

    def test_settings_round_trip_without_losing_types(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings_path = Path(temp_dir, "settings.ini")
            settings = OSCRSettings(settings_path)
            settings.auto_scan = True
            settings.combats_to_parse = 7
            settings.graph_resolution = 0.5
            settings.language = "de"
            settings.theme_id = "command_console"
            settings.ui_scale = 1.2
            settings.dmg_columns[3] = False
            settings.favorite_ladders = ["alpha", "beta"]
            settings.command_console_palette_preset = "custom"
            settings.command_console_accents = [
                "#102030", "#203040", "#304050", "#405060", "#506070"]
            settings.command_console_background_mode = "custom"
            settings.command_console_background_opacity = 0.42
            settings.command_console_background_path = "C:/Images/bridge.webp"
            settings.store_settings()
            settings._settings.sync()

            restored = OSCRSettings(settings_path)

            self.assertIs(restored.auto_scan, True)
            self.assertEqual(restored.combats_to_parse, 7)
            self.assertEqual(restored.graph_resolution, 0.5)
            self.assertEqual(restored.language, "de")
            self.assertEqual(restored.theme_id, "command_console")
            self.assertEqual(restored.ui_scale, 1.2)
            self.assertFalse(restored.dmg_columns[3])
            self.assertEqual(restored.favorite_ladders, ["alpha", "beta"])
            self.assertEqual(restored.command_console_palette_preset, "custom")
            self.assertEqual(
                restored.command_console_accents,
                ["#102030", "#203040", "#304050", "#405060", "#506070"],
            )
            self.assertEqual(restored.command_console_background_mode, "custom")
            self.assertEqual(restored.command_console_background_opacity, 0.42)
            self.assertEqual(
                restored.command_console_background_path, "C:/Images/bridge.webp")

    def test_settings_file_without_theme_value_migrates_to_default(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings_path = Path(temp_dir, "legacy-settings.ini")
            legacy = OSCRSettings(settings_path)
            legacy._settings.setValue("ui_scale", 1.25)
            legacy._settings.sync()

            migrated = OSCRSettings(settings_path)

            self.assertEqual(migrated.ui_scale, 1.25)
            self.assertEqual(migrated.theme_id, "default")


if __name__ == "__main__":
    unittest.main()
