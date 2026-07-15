"""Build one real OSCR window in an isolated process for startup regression tests."""

import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QWidget  # noqa: E402

from re_oscr.app import REOSCRApplication  # noqa: E402
from re_oscr.config import OSCRSettings  # noqa: E402
from re_oscr.datamodels import SortingProxy  # noqa: E402
from re_oscr.themes import COMMAND_CONSOLE_THEME_ID, DEFAULT_THEME_ID  # noqa: E402


def main() -> int:
    config_dir = sys.argv[1]
    expected_theme_id = sys.argv[2]
    select_theme_id = sys.argv[3]
    expect_collapsed = len(sys.argv) > 4 and sys.argv[4] == "collapsed"
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
    analysis_credit = ui.window.findChild(QWidget, "analysisCreditAnotherNathan")
    cla_badge = ui.window.findChild(QWidget, "creditBadgeCLA")
    assert analysis_credit is not None
    assert "AnotherNathan" in analysis_credit.text()
    assert analysis_credit.toolTip() == ui.config.link_cla
    assert cla_badge is not None
    assert not cla_badge.icon().isNull()
    assert "AnotherNathan" in cla_badge.toolTip()
    assert ui.config.link_cla in cla_badge.toolTip()

    command_shell = ui.window.findChild(QWidget, "commandConsoleApplicationShell")
    default_shell = ui.window.findChild(QWidget, "defaultApplicationShell")
    if expected_theme_id == COMMAND_CONSOLE_THEME_ID:
        from re_oscr.console.tokens import SURFACES

        assert ui.workbench is not None
        assert command_shell is not None
        assert default_shell is None
        original_scale = ui.config.ui_scale
        ui.config.ui_scale = 1.5
        assert ui.sidebar_item_width == round(
            ui.theme.opt.sidebar_item_width * ui.window.width())
        ui.config.ui_scale = original_scale
        assert ui.window.findChild(QWidget, "commandConsoleBrandMark").text() == "RE"
        assert ui.window.findChild(QWidget, "commandConsoleBrandTitle").text() == (
            "OPEN SOURCE COMBATLOG READER")
        assert ui.window.findChild(QWidget, "commandConsoleSystemReadout") is None
        assert ui.window.findChild(QWidget, "commandConsoleColourRail") is not None
        context_rail = ui.window.findChild(QWidget, "commandConsoleContextRail")
        sidebar_host = ui.window.findChild(QWidget, "commandConsoleSidebarHost")
        colour_rail = ui.window.findChild(QWidget, "commandConsoleColourRail")
        assert context_rail is not None
        assert sidebar_host is not None
        assert colour_rail.width() == round(44 * ui.theme.scale)
        assert len(ui.widgets.context_rail_segments) == 5
        assert len(ui.window.findChildren(QWidget, "commandConsoleRailMark1")) == 1
        assert ui.widgets.context_rail_segments[0].property("active") is True
        assert all(segment.property("active") is False
                   for segment in ui.widgets.context_rail_segments[1:])
        assert ui.window.findChild(QWidget, "commandConsoleDrawerHeader") is not None
        assert ui.window.findChild(QWidget, "commandConsoleDrawerSection").text() == "OV"
        assert ui.window.findChild(QWidget, "commandConsoleDrawerTitle").text() == "COMBAT LOG"
        assert context_rail.property("activeAccent") == "#FF8A2A"
        assert sidebar_host.property("activeAccent") == "#FF8A2A"
        if expect_collapsed:
            assert sidebar_host.isHidden()
            ui.widgets.sidebar_flip_button.click()
            ui.app.processEvents()
            assert not sidebar_host.isHidden()
        ui.widgets.sidebar_flip_button.click()
        ui.app.processEvents()
        assert sidebar_host.isHidden()
        assert ui.settings.state__sidebar_collapsed is True
        assert not context_rail.isHidden()
        assert not colour_rail.isHidden()
        ui.widgets.sidebar_flip_button.click()
        ui.app.processEvents()
        assert not sidebar_host.isHidden()
        assert ui.settings.state__sidebar_collapsed is False
        assert ui.window.findChild(QWidget, "commandConsoleOverviewGraphPanel") is not None
        assert ui.window.findChild(QWidget, "commandConsoleOverviewTablePanel") is not None
        assert ui.window.findChild(QWidget, "commandConsoleMasthead").minimumHeight() == round(
            80 * ui.theme.scale)
        assert ui.widgets.overview_tabber.minimumHeight() == round(120 * ui.theme.scale)
        assert ui.widgets.overview_table.parentWidget().minimumHeight() == round(
            135 * ui.theme.scale)
        assert (
            ui.graphs.dps_bar_plot._plot.getAxis("left").style["tickFont"].pointSize()
            == ui.theme.get_font("live_plot_widget").pointSize()
        )
        for plot in (
                ui.graphs.dps_bar_plot, ui.graphs.dps_graph_plot,
                ui.graphs.dmg_bar_plot):
            assert plot._plot.backgroundBrush().color().name().upper() == SURFACES["raised"]
        assert ui.window.findChild(QWidget, "commandConsoleOverviewSummaryDeck") is not None
        assert ui.window.findChild(QWidget, "commandConsoleOverviewMetricBar") is not None
        assert ui.window.findChild(QWidget, "commandConsoleOverviewTitle").text() == (
            "AWAITING COMBAT DATA")
        assert len(ui.widgets.overview_stat_values) == 4
        assert [button.text() for button in ui.widgets.overview_metric_buttons] == [
            "T1  SUMMARY", "T2  DAMAGE OUT", "T3  DAMAGE IN", "T4  HEALING",
            "T5  ALL METRICS"]
        assert [button.property("accentIndex")
                for button in ui.widgets.overview_metric_buttons] == [
                    "0", "0", "0", "0", "0"]
        assert ui.widgets.overview_metric_buttons[0].isChecked()
        for mode_index in range(len(ui.widgets.overview_metric_buttons)):
            ui.widgets.switch_overview_metric_group(mode_index)
            assert [button.isChecked()
                    for button in ui.widgets.overview_metric_buttons] == [
                        index == mode_index
                        for index in range(len(ui.widgets.overview_metric_buttons))]
            assert [button.property("visualActive")
                    for button in ui.widgets.overview_metric_buttons] == [
                        index == mode_index
                        for index in range(len(ui.widgets.overview_metric_buttons))]
        ui.widgets.switch_overview_metric_group(0)
        for mode_index in range(len(ui.widgets.overview_menu_buttons)):
            ui.widgets.switch_overview_tab(mode_index)
            assert [button.property("visualActive")
                    for button in ui.widgets.overview_menu_buttons] == [
                        index == mode_index
                        for index in range(len(ui.widgets.overview_menu_buttons))]
        ui.widgets.switch_overview_tab(0)
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
        assert not ui.widgets.overview_table.isColumnHidden(1)
        assert ui.widgets.overview_table.isColumnHidden(3)
        display_proxy = ui.widgets.overview_table.model()
        assert display_proxy is ui.widgets.overview_display_proxy
        assert display_proxy.sourceModel() is ui.widgets.overview_sorting_proxy
        assert display_proxy.sourceModel().sourceModel() is ui.parser.overview_table_model
        assert ui.widgets.overview_table.frozen_view.model() is display_proxy
        assert (ui.widgets.overview_table.frozen_view.selectionModel()
                is ui.widgets.overview_table.selectionModel())
        ui.widgets.switch_overview_metric_group(4)
        assert not any(ui.widgets.overview_table.isColumnHidden(index) for index in range(25))
        ui.widgets.switch_overview_metric_group(0)
        ui.parser.overview_table_model.clear()
        assert ui.window.findChild(QWidget, "commandConsoleAnalysisHeading") is not None
        assert ui.window.findChild(QWidget, "commandConsoleAnalysisTitle").text() == "ANALYSIS"
        assert ui.window.findChild(QWidget, "commandConsoleAnalysisCommandDeck") is not None
        assert ui.window.findChild(QWidget, "commandConsoleAnalysisModifierBar") is not None
        assert ui.window.findChild(QWidget, "analysisWorkbenchFilter") is (
            ui.widgets.analysis_filter_entry)
        assert ui.window.findChild(QWidget, "analysisWorkbenchScope") is (
            ui.widgets.analysis_filter_scope)
        assert ui.window.findChild(QWidget, "analysisWorkbenchStart") is (
            ui.widgets.analysis_start_entry)
        assert ui.window.findChild(QWidget, "analysisWorkbenchEnd") is (
            ui.widgets.analysis_end_entry)
        assert ui.window.findChild(QWidget, "analysisParserTruthChip") is (
            ui.widgets.analysis_truth_chip)
        assert ui.window.findChild(QWidget, "analysisModifiedViewChip") is (
            ui.widgets.analysis_modified_chip)
        assert ui.window.findChild(QWidget, "analysisWorkbenchEventCount") is (
            ui.widgets.analysis_event_count_chip)
        assert ui.window.findChild(QWidget, "analysisWorkbenchReset") is (
            ui.widgets.analysis_reset_button)
        assert ui.widgets.analysis_filter_scope.currentData() == "ANY"
        assert ui.widgets.analysis_filter_entry.placeholderText() == "SEARCH COMBAT EVENTS"
        assert ui.widgets.analysis_start_entry.placeholderText() == "START"
        assert ui.widgets.analysis_end_entry.placeholderText() == "END"
        assert ui.widgets.analysis_truth_chip.isHidden()
        assert ui.widgets.analysis_modified_chip.isHidden()
        assert ui.widgets.analysis_event_count_chip.text() == "NO COMBAT"
        assert not ui.widgets.analysis_reset_button.isEnabled()
        analysis_graph_panel = ui.window.findChild(
            QWidget, "commandConsoleAnalysisGraphPanel")
        analysis_telemetry_panel = ui.window.findChild(
            QWidget, "commandConsoleAnalysisTelemetryPanel")
        assert analysis_graph_panel.property("consoleRole") == "surfaceTabs"
        assert analysis_telemetry_panel.property("consoleRole") == "embeddedSurface"
        assert ui.window.findChild(
            QWidget, "commandConsoleAnalysisTelemetryTabs") is ui.widgets.analysis_tree_tabber
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
        assert ui.widgets.appearance_background_selector.count() == 2
        assert len(ui.widgets.appearance_color_entries) == 5
        assert ui.widgets.appearance_color_entries[0].text() == "#FF8A2A"
        original_window = ui.window
        original_overview_table = ui.widgets.overview_table
        federation_index = ui.widgets.appearance_palette_selector.findData("federation")
        ui.widgets.appearance_palette_selector.setCurrentIndex(federation_index)
        ui.app.processEvents()
        assert ui.active_theme_id == COMMAND_CONSOLE_THEME_ID
        assert ui.window is original_window
        assert ui.widgets.overview_table is original_overview_table
        assert ui.widgets.context_accents[0] == "#4D8FD8"
        assert "#4D8FD8" in ui.app.styleSheet()
        command_index = ui.widgets.appearance_palette_selector.findData("command")
        ui.widgets.appearance_palette_selector.setCurrentIndex(command_index)
        ui.app.processEvents()
        assert ui.widgets.context_accents[0] == "#FF8A2A"
        assert ui.window.findChild(QWidget, "commandConsoleThemeRestartLabel").text() == (
            "SHELL + OVERVIEW APPLY LIVE // THEME SWITCH RELAUNCHES")
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
        assert all(button.property("consoleRole") == "modeControl"
                   for button in ui.widgets.analysis_menu_buttons)
        freeze_buttons = ui.window.findChildren(QWidget, "analysisFreezeButton")
        clear_buttons = ui.window.findChildren(QWidget, "analysisClearButton")
        assert len(freeze_buttons) == 4
        assert len(clear_buttons) == 4
        assert all(button.property("consoleRole") == "actionButton"
                   for button in freeze_buttons + clear_buttons)
        assert ui.window.findChild(
            QWidget, "analysisCopyButton").property("consoleRole") == "actionButton"
        assert ui.widgets.analysis_copy_combobox.property("consoleRole") == "compactCombo"
        assert all(table.property("consoleRole") == "analysisTree" for table in (
            ui.tables.damage_out_table, ui.tables.damage_in_table,
            ui.tables.heal_out_table, ui.tables.heal_in_table))

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
        assert ui.window.findChild(QWidget, "commandConsoleDrawerSection").text() == "LG"
        assert ui.window.findChild(QWidget, "commandConsoleDrawerTitle").text() == "LEAGUE ACCESS"
        ui.widgets.set_live_parser_active(True)
        assert ui.widgets.context_rail_segments[4].property("active") is True
        assert all(segment.property("active") is False
                   for segment in ui.widgets.context_rail_segments[:4])
        assert ui.widgets.navigation_buttons[4].property("visualActive") is True
        ui.widgets.set_live_parser_active(False)
        assert ui.widgets.context_rail_segments[2].property("active") is True
        assert ui.widgets.navigation_buttons[2].property("visualActive") is True
        ui.widgets.ladder_search.setText("tester")
        assert ui.league.current_filter_term == "tester"
        ui.widgets.ladder_search.clear()
        assert ui.league.current_filter_term == ""
        ui.widgets.switch_main_tab(3)
        ui.app.processEvents()
        assert ui.widgets.main_tabber.currentIndex() == 3
        assert ui.widgets.sidebar_tabber.currentIndex() == 2
        assert context_rail.property("activeAccent") == "#4FC3CC"
        assert ui.window.findChild(QWidget, "commandConsoleDrawerSection").text() == "ST"
        assert ui.window.findChild(QWidget, "commandConsoleDrawerTitle").text() == (
            "SYSTEM SETTINGS")
        for index, button in enumerate(ui.widgets.settings_menu_buttons):
            button.click()
            ui.app.processEvents()
            assert ui.widgets.settings_tabber.currentIndex() == index
            assert button.isChecked()
    else:
        assert ui.workbench is None
        assert "re_oscr.console" not in sys.modules
        assert default_shell is not None
        assert command_shell is None
        original_scale = ui.config.ui_scale
        ui.config.ui_scale = 1.5
        assert ui.sidebar_item_width == int(
            ui.theme.opt.sidebar_item_width * ui.window.width() * ui.config.ui_scale)
        ui.config.ui_scale = original_scale
        assert not any(button.isCheckable() for button in ui.widgets.main_menu_buttons)
        assert ui.widgets.overview_menu_buttons[0].text() == "DPS Bar"
        assert ui.window.findChild(QWidget, "defaultAnalysisGraph") is not None
        assert ui.window.findChild(QWidget, "defaultAnalysisTelemetry") is not None
        assert ui.window.findChild(QWidget, "commandConsoleAnalysisHeading") is None
        assert ui.window.findChild(QWidget, "analysisWorkbenchFilter") is None
        assert ui.window.findChild(QWidget, "analysisParserTruthChip") is None
        assert ui.window.findChild(QWidget, "analysisModifiedViewChip") is None
        assert ui.window.findChild(QWidget, "analysisWorkbenchEventCount") is None
        assert ui.window.findChild(QWidget, "analysisWorkbenchReset") is None
        assert ui.window.findChild(QWidget, "commandConsoleOverviewSummaryDeck") is None
        assert ui.window.findChild(QWidget, "commandConsoleOverviewMetricBar") is None
        assert (
            ui.graphs.dps_bar_plot._plot.getAxis("left").style["tickFont"].pointSize()
            == ui.theme.get_font("app").pointSize()
        )
        assert ui.widgets.overview_metric_buttons == []
        assert type(ui.widgets.overview_table.model()) is SortingProxy
        assert ui.widgets.overview_table.model().sourceModel() is ui.parser.overview_table_model
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
    assert len(ui.widgets.analysis_plots) == 4

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
