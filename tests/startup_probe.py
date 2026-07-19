"""Build one real OSCR window in an isolated process for startup regression tests."""

import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QPushButton, QWidget  # noqa: E402

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
    assert ui.widgets.main_tabber.count() == (
        5 if expected_theme_id == COMMAND_CONSOLE_THEME_ID else 4)
    assert ui.active_theme_id == expected_theme_id
    assert ui.settings.theme_id == expected_theme_id
    assert ui.widgets.theme_selector.currentData() == expected_theme_id
    assert ui.widgets.theme_selector.count() == 2
    assert [ui.widgets.theme_selector.itemText(index) for index in range(2)] == [
        "Legacy", "Command Console"]
    assert ui.widgets.ladder_table.objectName() == "leagueStandingsTable"
    assert ui.widgets.ladder_search.objectName() == "leagueSearchEntry"
    assert ui.widgets.league_search_button is not None
    assert ui.widgets.league_clear_button is not None
    assert ui.widgets.league_more_button is not None
    about_description = ui.window.findChild(QWidget, "aboutProductDescription")
    analysis_credit = ui.window.findChild(QWidget, "analysisCreditAnotherNathan")
    cla_badge = ui.window.findChild(QWidget, "creditBadgeCLA")
    assert about_description is not None
    assert about_description.text() == (
        "RE-OSCR (Retro Escalation) is an independent frontend for the OSCR parser. OSCR is "
        "developed by the STO Community Developers. Not affiliated with STO"
        "CD or the STO "
        "Builds Discord.")
    assert analysis_credit is not None
    assert "AnotherNathan" in analysis_credit.text()
    assert analysis_credit.toolTip() == ui.config.link_cla
    assert cla_badge is not None
    assert not cla_badge.icon().isNull()
    assert "AnotherNathan" in cla_badge.toolTip()
    assert ui.config.link_cla in cla_badge.toolTip()
    assert ui.window.findChild(QWidget, "creditBadge" + "STO" + "CD") is None
    assert ui.window.findChild(QWidget, "creditBadge" + "STO" + "Builds") is None
    button_texts = {button.text() for button in ui.window.findChildren(QPushButton)}
    assert "Website" not in button_texts
    assert {"Github", "Downloads"}.issubset(button_texts)

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
        assert ui.window.findChild(
            QWidget, "commandConsoleAnalysisTitle").text() == "AWAITING ENCOUNTER"
        assert ui.window.findChild(QWidget, "commandConsoleAnalysisCommandDeck") is not None
        assert ui.window.findChild(QWidget, "commandConsoleAnalysisModifierBar") is not None
        assert ui.window.findChild(QWidget, "analysisWorkbenchFilter") is (
            ui.widgets.analysis_filter_entry)
        assert ui.window.findChild(QWidget, "analysisWorkbenchScope") is (
            ui.widgets.analysis_filter_scope)
        assert ui.window.findChild(QWidget, "analysisWorkbenchAddFilter") is (
            ui.widgets.analysis_filter_add_button)
        assert ui.window.findChild(QWidget, "analysisWorkbenchClauseRow") is (
            ui.widgets.analysis_filter_clause_row)
        assert ui.window.findChild(QWidget, "analysisWorkbenchClauseScroll") is (
            ui.widgets.analysis_filter_clause_scroll)
        assert ui.window.findChild(QWidget, "analysisWorkbenchClauseContainer") is (
            ui.widgets.analysis_filter_clause_container)
        assert ui.window.findChild(QWidget, "analysisWorkbenchStart") is (
            ui.widgets.analysis_start_entry)
        assert ui.window.findChild(QWidget, "analysisWorkbenchEnd") is (
            ui.widgets.analysis_end_entry)
        assert ui.window.findChild(QWidget, "analysisWorkbenchRuleSet") is (
            ui.widgets.analysis_rule_set_selector)
        assert ui.window.findChild(QWidget, "analysisWorkbenchRules") is (
            ui.widgets.analysis_rules_button)
        assert ui.window.findChild(QWidget, "analysisParserTruthChip") is (
            ui.widgets.analysis_truth_chip)
        assert ui.window.findChild(QWidget, "analysisModifiedViewChip") is (
            ui.widgets.analysis_modified_chip)
        assert ui.window.findChild(QWidget, "analysisWorkbenchEventCount") is (
            ui.widgets.analysis_event_count_chip)
        assert ui.window.findChild(QWidget, "analysisWorkbenchReset") is (
            ui.widgets.analysis_reset_button)
        assert ui.window.findChild(QWidget, "analysisClaDamageOutPreview") is (
            ui.widgets.analysis_cla_preview_button)
        assert ui.widgets.analysis_filter_scope.currentData() == "ANY"
        assert tuple(
            ui.widgets.analysis_filter_scope.itemData(index)
            for index in range(ui.widgets.analysis_filter_scope.count())
        ) == (
            "ANY", "OWNER", "SOURCE", "TARGET", "EVENT", "TYPE", "FLAG",
            "MIN_MAGNITUDE", "MAX_MAGNITUDE",
        )
        assert ui.widgets.analysis_filter_entry.placeholderText() == "SEARCH COMBAT EVENTS"
        assert ui.widgets.analysis_filter_add_button.text() == "ADD FILTER"
        assert ui.widgets.analysis_filter_clause_row.isHidden()
        assert ui.widgets.analysis_filter_clause_layout.count() == 0
        assert ui.widgets.analysis_filter_clause_buttons == []
        assert ui.widgets.analysis_rule_chip_buttons == []
        assert ui.window.findChild(
            QWidget, "analysisWorkbenchClauseLabel").text() == "ACTIVE MODIFIERS //"
        assert (
            ui.widgets.analysis_filter_clause_scroll.horizontalScrollBarPolicy()
            == Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        assert (
            ui.widgets.analysis_filter_clause_scroll.verticalScrollBarPolicy()
            == Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        assert ui.widgets.analysis_start_entry.placeholderText() == "START"
        assert ui.widgets.analysis_end_entry.placeholderText() == "END"
        assert ui.widgets.analysis_rule_set_selector.count() >= 1
        assert ui.widgets.analysis_rules_button.text() == "RULES"
        assert ui.widgets.analysis_rules_button.property("accentIndex") == "1"
        assert ui.widgets.analysis_truth_chip.isHidden()
        assert ui.widgets.analysis_modified_chip.isHidden()
        assert ui.widgets.analysis_event_count_chip.text() == "NO COMBAT"
        assert not ui.widgets.analysis_reset_button.isEnabled()
        assert ui.widgets.analysis_cla_preview_button.text() == "CLA v1.4 PREVIEW"
        assert not ui.widgets.analysis_cla_preview_button.isEnabled()
        analysis_graph_panel = ui.window.findChild(
            QWidget, "commandConsoleAnalysisGraphPanel")
        analysis_telemetry_panel = ui.window.findChild(
            QWidget, "commandConsoleAnalysisTelemetryPanel")
        assert analysis_graph_panel.property("consoleRole") == "surfaceTabs"
        assert analysis_telemetry_panel.property("consoleRole") == "embeddedSurface"
        assert ui.window.findChild(
            QWidget, "commandConsoleAnalysisTelemetryPanelCap") is not None
        assert ui.window.findChild(
            QWidget, "commandConsoleAnalysisTelemetryTabs") is ui.widgets.analysis_tree_tabber
        assert ui.window.findChild(QWidget, "commandConsoleLeagueHeading") is not None
        assert ui.window.findChild(QWidget, "commandConsoleLeagueTitle").text() == (
            "LEAGUE STANDINGS")
        assert ui.window.findChild(QWidget, "commandConsoleLeagueTablePanel") is not None
        league_control_deck = ui.window.findChild(
            QWidget, "commandConsoleLeagueControlDeck")
        assert league_control_deck is not None
        assert league_control_deck.minimumSizeHint().width() <= league_control_deck.width()
        assert ui.widgets.variant_combo.objectName() == "commandConsoleLeagueSeason"
        assert ui.widgets.ladder_selector.objectName() == "commandConsoleLeagueLadders"
        assert ui.widgets.ladder_search.property("consoleRole") == "leagueSearch"
        assert ui.widgets.league_status.text() == "AWAITING SEASON"
        assert ui.widgets.ladder_table.property("consoleRole") == "leagueTable"
        assert ui.widgets.ladder_table.frozen_view.model() is ui.widgets.ladder_table.model()
        assert ui.widgets.ladder_table.frozen_view.selectionModel() is (
            ui.widgets.ladder_table.selectionModel())
        assert ui.window.findChild(QWidget, "commandConsoleSettingsHeading") is not None
        assert ui.window.findChild(QWidget, "commandConsoleSettingsTitle").text() == "SETTINGS"
        assert ui.window.findChild(QWidget, "commandConsoleSettingsNavigation") is not None
        assert ui.widgets.settings_tabber.count() == 4
        assert [button.text() for button in ui.widgets.settings_menu_buttons] == [
            "C1  APPEARANCE", "C2  CORE + RESULTS", "C3  LIVE PARSER",
            "C4  TABLE COLUMNS"]
        assert ui.window.findChild(QWidget, "commandConsoleAppearanceProfilePanel") is not None
        appearance_palette = ui.window.findChild(
            QWidget, "commandConsoleAppearancePalettePanel")
        assert appearance_palette is not None
        assert appearance_palette.isHidden()
        assert ui.window.findChild(QWidget, "commandConsoleColourSwatch1Command") is None
        background_options = ui.window.findChild(
            QWidget, "commandConsoleBackgroundCustomControls")
        assert background_options is not None
        assert background_options.isHidden()
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
        custom_index = ui.widgets.appearance_palette_selector.findData("custom")
        ui.widgets.appearance_palette_selector.setCurrentIndex(custom_index)
        ui.app.processEvents()
        assert not appearance_palette.isHidden()
        command_index = ui.widgets.appearance_palette_selector.findData("command")
        ui.widgets.appearance_palette_selector.setCurrentIndex(command_index)
        ui.app.processEvents()
        assert ui.widgets.context_accents[0] == "#FF8A2A"
        assert appearance_palette.isHidden()
        custom_background_index = ui.widgets.appearance_background_selector.findData("custom")
        ui.widgets.appearance_background_selector.setCurrentIndex(custom_background_index)
        ui.app.processEvents()
        assert not background_options.isHidden()
        no_background_index = ui.widgets.appearance_background_selector.findData("none")
        ui.widgets.appearance_background_selector.setCurrentIndex(no_background_index)
        ui.app.processEvents()
        assert background_options.isHidden()
        assert ui.window.findChild(QWidget, "commandConsoleThemeRestartLabel").text() == (
            "THEME + UI SCALE APPLY ON NEXT LAUNCH")
        assert ui.window.findChild(QWidget, "settingsUiScaleRestartNote").text() == (
            "UI SCALE APPLIES ON NEXT LAUNCH")
        assert ui.window.findChild(QWidget, "settingsClipboardFormat") is not None
        live_graph = ui.window.findChild(QWidget, "settingsLiveGraph")
        live_graph_field = ui.window.findChild(QWidget, "settingsLiveGraphField")
        live_page = ui.window.findChild(QWidget, "commandConsoleMainPage5")
        assert live_page is not None
        assert ui.live_overlay is not None
        assert "re_oscr.liveoverlay" in sys.modules
        assert "re_oscr.globalhotkeys" in sys.modules
        assert "PySide6.QtWebSockets" in sys.modules
        assert not ui.live_overlay.feed.active
        assert not ui.settings.overlay__feed_enabled
        assert ui.window.findChild(QWidget, "commandConsoleLiveFeedToggle") is (
            ui.widgets.live_overlay_feed_button)
        assert ui.window.findChild(QWidget, "settingsLiveOverlayBind") is (
            ui.widgets.live_overlay_bind)
        assert ui.window.findChild(QWidget, "settingsLiveOverlayPort") is (
            ui.widgets.live_overlay_port)
        assert ui.window.findChild(QWidget, "settingsLiveOverlayHotkey") is (
            ui.widgets.live_overlay_hotkey)
        assert ui.window.findChild(QWidget, "settingsLiveOverlayHideMode") is (
            ui.widgets.live_overlay_hotkey_mode)
        assert live_page.isAncestorOf(live_graph)
        assert len(ui.window.findChildren(QWidget, "settingsLiveGraph")) == 1
        assert ui.window.findChild(
            QWidget, "commandConsoleLiveSettingsPointerPanel") is not None
        open_live = ui.window.findChild(QWidget, "settingsOpenLiveControlCenter")
        assert open_live is not None
        open_live.click()
        ui.app.processEvents()
        assert ui.widgets.main_tabber.currentIndex() == 4
        ui.widgets.switch_main_tab(0)
        assert not live_graph_field.isEnabled()
        live_graph.click()
        ui.app.processEvents()
        assert live_graph_field.isEnabled()
        live_graph.click()
        ui.app.processEvents()
        assert not live_graph_field.isEnabled()
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
        assert all(button.property("consoleRole") == "actionButton" for button in (
            ui.widgets.league_search_button, ui.widgets.league_clear_button,
            ui.widgets.league_open_local_button, ui.widgets.league_open_parse_button,
            ui.widgets.league_save_parse_button, ui.widgets.league_more_button))
        league_meters = ui.window.findChild(QWidget, "leagueMetersButton")
        assert league_meters is not None
        assert league_meters.isChecked()
        assert ui.widgets.ladder_table.meter_mode()
        league_meters.click()
        ui.app.processEvents()
        assert not ui.widgets.ladder_table.meter_mode()
        league_meters.click()
        ui.app.processEvents()
        assert ui.widgets.ladder_table.meter_mode()
        assert len(ui.widgets.main_menu_buttons) == 5
        assert all(button.isCheckable() for button in ui.widgets.main_menu_buttons)
        assert ui.widgets.main_menu_buttons[0].isChecked()
        assert ui.widgets.live_parser_button is ui.widgets.main_menu_buttons[4]
        assert ui.widgets.overview_menu_buttons[0].text() == "A1  DPS BAR"
        assert [button.text() for button in ui.widgets.analysis_menu_buttons] == [
            "B1  DAMAGE OUT", "B2  DAMAGE TAKEN", "B3  HEALS OUT", "B4  HEALS IN"]
        assert all(button.property("consoleRole") == "modeControl"
                   for button in ui.widgets.analysis_menu_buttons)
        assert all(button.property("accentIndex") == "1"
                   for button in ui.widgets.analysis_menu_buttons)
        assert ui.widgets.analysis_modified_chip.property("accentIndex") == "1"
        simple_mode = ui.window.findChild(QWidget, "analysisSimpleMode")
        advanced_mode = ui.window.findChild(QWidget, "analysisAdvancedMode")
        filter_row = ui.widgets.analysis_filter_row
        time_rule_row = ui.widgets.analysis_time_rule_row
        assert simple_mode is not None and simple_mode.isChecked()
        assert advanced_mode is not None and not advanced_mode.isChecked()
        assert filter_row.isHidden()
        assert time_rule_row.isHidden()
        assert not ui.widgets.analysis_lens_buttons[0].isHidden()
        assert all(button.isHidden() for button in ui.widgets.analysis_lens_buttons[1:])
        freeze_buttons = ui.window.findChildren(QWidget, "analysisFreezeButton")
        plot_style_buttons = ui.window.findChildren(QWidget, "analysisPlotStyleButton")
        clear_buttons = ui.window.findChildren(QWidget, "analysisClearButton")
        assert len(freeze_buttons) == 4
        assert len(plot_style_buttons) == 4
        assert len(clear_buttons) == 4
        assert all(button.property("consoleRole") == "actionButton"
                   for button in freeze_buttons + plot_style_buttons + clear_buttons)
        assert all(button.text() == "LIVE PLOT" for button in freeze_buttons)
        assert all(button.text() == "BARS" for button in plot_style_buttons)
        assert all(button.isHidden() for button in plot_style_buttons)
        assert all(plot.display_mode == "line" and not plot.frozen
                   for plot in ui.widgets.analysis_plots)
        advanced_mode.click()
        ui.app.processEvents()
        assert advanced_mode.isChecked() and not simple_mode.isChecked()
        assert not filter_row.isHidden()
        assert not time_rule_row.isHidden()
        assert all(not button.isHidden() for button in ui.widgets.analysis_lens_buttons)
        assert all(not button.isHidden() for button in plot_style_buttons)
        plot_style_buttons[0].click()
        ui.app.processEvents()
        assert sum(plot.display_mode == "bar" for plot in ui.widgets.analysis_plots) == 1
        assert plot_style_buttons[0].text() == "LINES"
        plot_style_buttons[0].click()
        ui.app.processEvents()
        assert all(plot.display_mode == "line" for plot in ui.widgets.analysis_plots)
        freeze_buttons[0].click()
        ui.app.processEvents()
        assert sum(plot.frozen for plot in ui.widgets.analysis_plots) == 1
        assert freeze_buttons[0].text() == "FROZEN"
        freeze_buttons[0].click()
        ui.app.processEvents()
        assert all(not plot.frozen for plot in ui.widgets.analysis_plots)
        simple_mode.click()
        ui.app.processEvents()
        assert simple_mode.isChecked() and not advanced_mode.isChecked()
        assert filter_row.isHidden()
        assert time_rule_row.isHidden()
        assert ui.tables.analysis_display_lens == "CORE"
        assert ui.window.findChild(
            QWidget, "analysisCopyButton").property("consoleRole") == "actionButton"
        assert ui.widgets.analysis_copy_combobox.property("consoleRole") == "compactCombo"
        assert [button.text() for button in ui.widgets.analysis_lens_buttons] == [
            "T1  CORE", "T2  EVENTS", "T3  DETAIL", "T4  ALL"]
        assert ui.tables.analysis_display_lens == "CORE"
        assert ui.widgets.analysis_lens_buttons[0].isChecked()
        assert all(table.property("consoleRole") == "analysisTree" for table in (
            ui.tables.damage_out_table, ui.tables.damage_in_table,
            ui.tables.heal_out_table, ui.tables.heal_in_table))

        ui.widgets.main_menu_buttons[1].click()
        ui.app.processEvents()
        assert ui.widgets.main_tabber.currentIndex() == 1
        assert ui.widgets.main_menu_buttons[1].isChecked()
        advanced_mode.click()
        ui.app.processEvents()
        assert time_rule_row.minimumSizeHint().width() <= time_rule_row.width()
        for index, button in enumerate(ui.widgets.analysis_menu_buttons):
            button.click()
            ui.app.processEvents()
            assert ui.widgets.analysis_graph_tabber.currentIndex() == index
            assert ui.widgets.analysis_tree_tabber.currentIndex() == index
            assert button.isChecked()
        ui.widgets.switch_analysis_tab(0)
        ui.widgets.analysis_lens_buttons[3].click()
        ui.app.processEvents()
        assert ui.tables.analysis_display_lens == "ALL"
        assert ui.widgets.analysis_lens_buttons[3].isChecked()
        ui.widgets.analysis_lens_buttons[0].click()
        ui.app.processEvents()
        assert ui.tables.analysis_display_lens == "CORE"
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
        assert ui.widgets.context_rail_segments[2].property("active") is True
        assert ui.widgets.navigation_buttons[2].property("visualActive") is True
        assert ui.widgets.navigation_buttons[4].property("popoutVisible") is True
        ui.widgets.set_live_parser_active(False)
        assert ui.widgets.context_rail_segments[2].property("active") is True
        assert ui.widgets.navigation_buttons[2].property("visualActive") is True
        ui.widgets.main_menu_buttons[4].click()
        ui.app.processEvents()
        assert ui.widgets.main_tabber.currentIndex() == 4
        assert ui.widgets.sidebar_tabber.currentIndex() == 3
        assert ui.window.findChild(QWidget, "commandConsoleSidebarLive").isVisible()
        assert ui.widgets.context_rail_segments[4].property("active") is True
        assert all(segment.property("active") is False
                   for segment in ui.widgets.context_rail_segments[:4])
        assert ui.widgets.navigation_buttons[4].property("visualActive") is True
        assert context_rail.property("activeAccent") == "#D94B55"
        assert ui.window.findChild(QWidget, "commandConsoleDrawerSection").text() == "LV"
        assert ui.window.findChild(QWidget, "commandConsoleDrawerTitle").text() == (
            "LIVE TELEMETRY")
        assert not ui.live_parser.popout_visible
        assert not ui.live_parser.isVisible()
        assert ui.window.findChild(QWidget, "commandConsoleLivePreviewPanel") is not None
        assert ui.widgets.live_parser_preview_status.text() == "NO TELEMETRY"
        log_settings = ui.window.findChild(QWidget, "commandConsoleLiveLogSettings")
        assert log_settings is not None
        log_settings.click()
        ui.app.processEvents()
        assert ui.widgets.main_tabber.currentIndex() == 3
        assert ui.widgets.settings_tabber.currentIndex() == 1
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
        assert ui.live_overlay is None
        assert "re_oscr.console" not in sys.modules
        assert "re_oscr.liveoverlay" not in sys.modules
        assert "re_oscr.globalhotkeys" not in sys.modules
        assert "PySide6.QtWebSockets" not in sys.modules
        assert default_shell is not None
        assert command_shell is None
        legacy_banner = ui.window.findChild(QWidget, "legacyBanner")
        assert legacy_banner is not None
        assert not legacy_banner.p.isNull()
        assert (legacy_banner.p.width(), legacy_banner.p.height()) == (2880, 126)
        original_scale = ui.config.ui_scale
        ui.config.ui_scale = 1.5
        assert ui.sidebar_item_width == int(
            ui.theme.opt.sidebar_item_width * ui.window.width() * ui.config.ui_scale)
        ui.config.ui_scale = original_scale
        assert not any(button.isCheckable() for button in ui.widgets.main_menu_buttons)
        assert ui.widgets.live_parser_button not in ui.widgets.main_menu_buttons
        assert ui.widgets.overview_menu_buttons[0].text() == "DPS Bar"
        assert ui.window.findChild(QWidget, "defaultAnalysisGraph") is not None
        assert ui.window.findChild(QWidget, "defaultAnalysisTelemetry") is not None
        assert ui.window.findChild(QWidget, "commandConsoleAnalysisHeading") is None
        assert ui.window.findChild(QWidget, "analysisWorkbenchFilter") is None
        assert ui.window.findChild(QWidget, "analysisWorkbenchAddFilter") is None
        assert ui.window.findChild(QWidget, "analysisWorkbenchClauseRow") is None
        assert ui.window.findChild(QWidget, "analysisWorkbenchClauseScroll") is None
        assert ui.window.findChild(QWidget, "analysisWorkbenchClauseContainer") is None
        assert ui.window.findChild(QWidget, "analysisWorkbenchRuleSet") is None
        assert ui.window.findChild(QWidget, "analysisWorkbenchRules") is None
        assert ui.window.findChild(QWidget, "analysisParserTruthChip") is None
        assert ui.window.findChild(QWidget, "analysisModifiedViewChip") is None
        assert ui.window.findChild(QWidget, "analysisWorkbenchEventCount") is None
        assert ui.window.findChild(QWidget, "analysisWorkbenchReset") is None
        assert ui.window.findChild(QWidget, "analysisClaDamageOutPreview") is None
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
        assert ui.window.findChild(QWidget, "commandConsoleLiveFeedToggle") is None
        assert ui.window.findChild(QWidget, "settingsLiveOverlayHotkey") is None
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
