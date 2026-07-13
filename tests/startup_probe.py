"""Build one real OSCR window in an isolated process for startup regression tests."""

import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QWidget  # noqa: E402

from re_oscr.app import REOSCRApplication  # noqa: E402
from re_oscr.config import OSCRSettings  # noqa: E402
from re_oscr.themes import COMMAND_CONSOLE_THEME_ID, DEFAULT_THEME_ID  # noqa: E402


def main() -> int:
    config_dir = sys.argv[1]
    expected_theme_id = sys.argv[2]
    select_theme_id = sys.argv[3]
    project_root = Path(__file__).resolve().parents[1]

    ui = REOSCRApplication(
        args=SimpleNamespace(config_dir=config_dir),
        app_dir_path=str(project_root),
        version="theme-startup-test",
    )
    ui.app.processEvents()

    assert ui.window.windowTitle() == "RE-OSCR — Retro Escalation"
    assert ui.window.isVisible()
    assert ui.widgets.main_tabber.count() == 4
    assert ui.active_theme_id == expected_theme_id
    assert ui.settings.theme_id == expected_theme_id
    assert ui.widgets.theme_selector.currentData() == expected_theme_id
    assert ui.widgets.theme_selector.count() == 2
    assert ui.widgets.ladder_table.objectName() == "leagueStandingsTable"
    assert ui.widgets.ladder_search.objectName() == "leagueSearchEntry"
    assert ui.widgets.league_search_button is not None
    assert ui.widgets.league_clear_button is not None
    assert ui.widgets.league_more_button is not None

    command_shell = ui.window.findChild(QWidget, "commandConsoleApplicationShell")
    default_shell = ui.window.findChild(QWidget, "defaultApplicationShell")
    if expected_theme_id == COMMAND_CONSOLE_THEME_ID:
        assert command_shell is not None
        assert default_shell is None
        assert ui.window.findChild(QWidget, "commandConsoleBrandMark").text() == "RE"
        assert ui.window.findChild(QWidget, "commandConsoleBrandTitle").text() == (
            "OPEN SOURCE COMBATLOG READER")
        assert ui.window.findChild(QWidget, "commandConsoleColourRail") is not None
        context_rail = ui.window.findChild(QWidget, "commandConsoleContextRail")
        sidebar_host = ui.window.findChild(QWidget, "commandConsoleSidebarHost")
        colour_rail = ui.window.findChild(QWidget, "commandConsoleColourRail")
        assert context_rail is not None
        assert sidebar_host is not None
        assert context_rail.property("activeAccent") == "#FF8A2A"
        assert sidebar_host.property("activeAccent") == "#FF8A2A"
        ui.widgets.sidebar_flip_button.click()
        ui.app.processEvents()
        assert sidebar_host.isHidden()
        assert not context_rail.isHidden()
        assert not colour_rail.isHidden()
        ui.widgets.sidebar_flip_button.click()
        ui.app.processEvents()
        assert not sidebar_host.isHidden()
        assert ui.window.findChild(QWidget, "commandConsoleOverviewGraphPanel") is not None
        assert ui.window.findChild(QWidget, "commandConsoleOverviewTablePanel") is not None
        assert ui.window.findChild(QWidget, "commandConsoleOverviewSummaryDeck") is not None
        assert ui.window.findChild(QWidget, "commandConsoleOverviewMetricBar") is not None
        assert ui.window.findChild(QWidget, "commandConsoleOverviewTitle").text() == (
            "AWAITING COMBAT DATA")
        assert len(ui.widgets.overview_stat_values) == 4
        assert [button.text() for button in ui.widgets.overview_metric_buttons] == [
            "T1  SUMMARY", "T2  DAMAGE OUT", "T3  DAMAGE IN", "T4  HEALING",
            "T5  ALL METRICS"]
        assert ui.widgets.overview_metric_buttons[0].isChecked()
        telemetry_row = [float(index + 1) for index in range(24)]
        ui.parser.overview_table_model.set_data(
            [telemetry_row], [f"Metric {index}" for index in range(24)], ["Test@handle"])
        ui.widgets.update_overview_telemetry(
            "Infected Space", "Elite", 38.6, 20.7, [telemetry_row])
        ui.app.processEvents()
        assert ui.window.findChild(QWidget, "commandConsoleOverviewTitle").text() == (
            "INFECTED SPACE [ELITE]")
        assert ui.widgets.overview_stat_values[0].text() == "1"
        assert not ui.widgets.overview_table.isColumnHidden(0)
        assert ui.widgets.overview_table.isColumnHidden(2)
        ui.widgets.switch_overview_metric_group(4)
        assert not any(ui.widgets.overview_table.isColumnHidden(index) for index in range(24))
        ui.widgets.switch_overview_metric_group(0)
        ui.parser.overview_table_model.clear()
        assert ui.window.findChild(QWidget, "commandConsoleAnalysisHeading") is not None
        assert ui.window.findChild(QWidget, "commandConsoleAnalysisTitle").text() == "ANALYSIS"
        assert ui.window.findChild(QWidget, "commandConsoleAnalysisGraphPanel") is not None
        assert ui.window.findChild(QWidget, "commandConsoleAnalysisTelemetryPanel") is not None
        assert ui.window.findChild(QWidget, "commandConsoleLeagueHeading") is not None
        assert ui.window.findChild(QWidget, "commandConsoleLeagueTitle").text() == (
            "LEAGUE STANDINGS")
        assert ui.window.findChild(QWidget, "commandConsoleLeagueTablePanel") is not None
        assert ui.window.findChild(QWidget, "commandConsoleLeagueControlDeck") is not None
        assert ui.window.findChild(QWidget, "commandConsoleSettingsHeading") is not None
        assert ui.window.findChild(QWidget, "commandConsoleSettingsTitle").text() == "SETTINGS"
        assert ui.window.findChild(QWidget, "commandConsoleSettingsNavigation") is not None
        assert ui.widgets.settings_tabber.count() == 5
        assert [button.text() for button in ui.widgets.settings_menu_buttons] == [
            "C1  APPEARANCE", "C2  CORE SYSTEMS", "C3  LIVE PARSER",
            "C4  DAMAGE TABLE", "C5  HEAL + LIVE"]
        assert ui.window.findChild(QWidget, "commandConsoleAppearanceProfilePanel") is not None
        assert ui.window.findChild(QWidget, "commandConsoleAppearancePalettePanel") is not None
        assert ui.widgets.appearance_palette_selector.count() == 5
        assert ui.widgets.appearance_background_selector.count() == 3
        assert len(ui.widgets.appearance_color_entries) == 5
        assert ui.widgets.appearance_color_entries[0].text() == "#FF8A2A"
        assert len(ui.widgets.settings_damage_column_buttons) == len(ui.settings.dmg_columns)
        assert len(ui.widgets.settings_heal_column_buttons) == len(ui.settings.heal_columns)
        assert len(ui.widgets.settings_live_column_buttons) == len(
            ui.settings.liveparser__columns)
        assert ui.widgets.league_search_button.text() == "SEARCH"
        assert ui.widgets.league_clear_button.text() == "RESET"
        assert ui.widgets.league_open_local_button.text() == "OPEN LOCAL"
        assert ui.widgets.league_open_parse_button.text() == "OPEN SELECTED"
        assert ui.widgets.league_save_parse_button.text() == "SAVE SELECTED"
        assert ui.widgets.league_more_button.text() == "LOAD MORE"
        assert len(ui.widgets.main_menu_buttons) == 4
        assert all(button.isCheckable() for button in ui.widgets.main_menu_buttons)
        assert ui.widgets.main_menu_buttons[0].isChecked()
        assert ui.widgets.overview_menu_buttons[0].text() == "A1  DPS BAR"
        assert [button.text() for button in ui.widgets.analysis_menu_buttons] == [
            "B1  DAMAGE OUT", "B2  DAMAGE TAKEN", "B3  HEALS OUT", "B4  HEALS IN"]
        assert len(ui.window.findChildren(QWidget, "analysisFreezeButton")) == 4
        assert len(ui.window.findChildren(QWidget, "analysisClearButton")) == 4

        ui.widgets.main_menu_buttons[1].click()
        ui.app.processEvents()
        assert ui.widgets.main_tabber.currentIndex() == 1
        assert ui.widgets.main_menu_buttons[1].isChecked()
        for index, button in enumerate(ui.widgets.analysis_menu_buttons):
            button.click()
            ui.app.processEvents()
            assert ui.widgets.analysis_graph_tabber.currentIndex() == index
            assert ui.widgets.analysis_tree_tabber.currentIndex() == index
            assert button.isChecked()
        ui.widgets.switch_analysis_tab(0)
        ui.widgets.collapse_analysis_graph()
        assert ui.widgets.analysis_graph_tabber.isHidden()
        assert not ui.settings.analysis_graph
        ui.widgets.expand_analysis_graph()
        assert not ui.widgets.analysis_graph_tabber.isHidden()
        assert ui.settings.analysis_graph
        ui.widgets.main_menu_buttons[0].click()
        ui.app.processEvents()
        assert ui.widgets.main_tabber.currentIndex() == 0
        assert ui.widgets.main_menu_buttons[0].isChecked()
        ui.widgets.switch_main_tab(2)
        ui.app.processEvents()
        assert ui.widgets.main_tabber.currentIndex() == 2
        assert ui.widgets.sidebar_tabber.currentIndex() == 1
        assert context_rail.property("activeAccent") == "#9A6BC4"
        ui.widgets.ladder_search.setText("tester")
        assert ui.league.current_filter_term == "tester"
        ui.widgets.ladder_search.clear()
        assert ui.league.current_filter_term == ""
        ui.widgets.switch_main_tab(3)
        ui.app.processEvents()
        assert ui.widgets.main_tabber.currentIndex() == 3
        assert ui.widgets.sidebar_tabber.currentIndex() == 2
        assert context_rail.property("activeAccent") == "#4FC3CC"
        for index, button in enumerate(ui.widgets.settings_menu_buttons):
            button.click()
            ui.app.processEvents()
            assert ui.widgets.settings_tabber.currentIndex() == index
            assert button.isChecked()
    else:
        assert default_shell is not None
        assert command_shell is None
        assert not any(button.isCheckable() for button in ui.widgets.main_menu_buttons)
        assert ui.widgets.overview_menu_buttons[0].text() == "DPS Bar"
        assert ui.window.findChild(QWidget, "defaultAnalysisGraph") is not None
        assert ui.window.findChild(QWidget, "defaultAnalysisTelemetry") is not None
        assert ui.window.findChild(QWidget, "commandConsoleAnalysisHeading") is None
        assert ui.window.findChild(QWidget, "commandConsoleOverviewSummaryDeck") is None
        assert ui.window.findChild(QWidget, "commandConsoleOverviewMetricBar") is None
        assert ui.widgets.overview_metric_buttons == []
        assert ui.window.findChild(QWidget, "commandConsoleLeagueHeading") is None
        assert ui.window.findChild(QWidget, "commandConsoleLeagueControlDeck") is None
        assert ui.window.findChild(QWidget, "commandConsoleSettingsHeading") is None
        assert ui.window.findChild(QWidget, "commandConsoleSettingsNavigation") is None
        assert [button.text() for button in ui.widgets.analysis_menu_buttons] == [
            "Damage Out", "Damage Taken", "Heals Out", "Heals In"]
        assert ui.widgets.league_search_button.text() == "Search"
        assert ui.widgets.league_clear_button.text() == "Clear"
        assert ui.widgets.league_open_local_button.text() == "Open Local Log..."
        assert ui.widgets.league_open_parse_button.text() == "Open Selected Parse"
        assert ui.widgets.league_save_parse_button.text() == "Save Selected Parse..."
        assert ui.widgets.league_more_button.text() == "More"

    assert ui.widgets.analysis_graph_tabber.count() == 4
    assert ui.widgets.analysis_tree_tabber.count() == 4
    assert ui.widgets.analysis_copy_combobox.count() == 5

    expected_stored_theme_id = expected_theme_id
    if select_theme_id != "-":
        assert select_theme_id in (DEFAULT_THEME_ID, COMMAND_CONSOLE_THEME_ID)
        next_theme_index = ui.widgets.theme_selector.findData(select_theme_id)
        ui.widgets.theme_selector.setCurrentIndex(next_theme_index)
        assert ui.settings.theme_id == select_theme_id
        assert ui.active_theme_id == expected_theme_id
        expected_stored_theme_id = select_theme_id

    ui.window.close()
    ui.app.processEvents()
    ui.app.quit()

    restored = OSCRSettings(Path(config_dir, "RE_OSCR_settings.ini"))
    assert restored.theme_id == expected_stored_theme_id
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
