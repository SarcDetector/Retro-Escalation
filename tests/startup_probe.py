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
    assert ui.widgets.league_open_local_button.text() == "Open Local Log..."
    assert ui.widgets.league_open_parse_button.text() == "Open Selected Parse"
    assert ui.widgets.league_save_parse_button.text() == "Save Selected Parse..."

    command_shell = ui.window.findChild(QWidget, "commandConsoleApplicationShell")
    default_shell = ui.window.findChild(QWidget, "defaultApplicationShell")
    if expected_theme_id == COMMAND_CONSOLE_THEME_ID:
        assert command_shell is not None
        assert default_shell is None
        assert ui.window.findChild(QWidget, "commandConsoleBrandMark").text() == "RE"
        assert ui.window.findChild(QWidget, "commandConsoleBrandTitle").text() == (
            "OPEN SOURCE COMBATLOG READER")
        assert ui.window.findChild(QWidget, "commandConsoleColourRail") is not None
        assert ui.window.findChild(QWidget, "commandConsoleOverviewGraphPanel") is not None
        assert ui.window.findChild(QWidget, "commandConsoleOverviewTablePanel") is not None
        assert len(ui.widgets.main_menu_buttons) == 4
        assert all(button.isCheckable() for button in ui.widgets.main_menu_buttons)
        assert ui.widgets.main_menu_buttons[0].isChecked()
        assert ui.widgets.overview_menu_buttons[0].text() == "A1  DPS BAR"

        ui.widgets.main_menu_buttons[1].click()
        ui.app.processEvents()
        assert ui.widgets.main_tabber.currentIndex() == 1
        assert ui.widgets.main_menu_buttons[1].isChecked()
        ui.widgets.main_menu_buttons[0].click()
        ui.app.processEvents()
        assert ui.widgets.main_tabber.currentIndex() == 0
        assert ui.widgets.main_menu_buttons[0].isChecked()
    else:
        assert default_shell is not None
        assert command_shell is None
        assert not any(button.isCheckable() for button in ui.widgets.main_menu_buttons)
        assert ui.widgets.overview_menu_buttons[0].text() == "DPS Bar"

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
