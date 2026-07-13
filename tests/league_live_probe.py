"""Manual offscreen probe for local logs and public League parse downloads."""

import argparse
import json
import os
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from OSCRUI.app import OSCRUI  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--local", type=Path)
    source.add_argument("--league", type=int)
    source.add_argument("--standings", action="store_true")
    parser.add_argument("--timeout", type=float, default=90.0)
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="retro-escalation-probe-") as config_dir:
        ui = OSCRUI(
            args=SimpleNamespace(config_dir=config_dir),
            app_dir_path=str(project_root),
            version="league-live-probe",
        )
        errors = []
        ui.parser.parser_error.connect(lambda error: errors.append(repr(error)))

        # This probe validates one combat per source. Avoid starting the parser's optional
        # older-combat background pass so each input can be checked independently and quickly.
        ui.parser.analyze_log_background = lambda _amount=-1: None

        def wait_until(predicate, description: str):
            deadline = time.monotonic() + args.timeout
            while time.monotonic() < deadline:
                ui.app.processEvents()
                if predicate():
                    return
                time.sleep(0.02)
            raise TimeoutError(description)

        if args.standings:
            ui.widgets.switch_main_tab(2)
            ui.league.fetch_and_insert_maps()
            wait_until(
                lambda: ui.widgets.ladder_selector.count() > 0,
                "League seasons or maps did not populate")
            first_ladder = ui.widgets.ladder_selector.item(0)
            ui.league.show_ladder(first_ladder)
            wait_until(
                lambda: ui.league.ladder_table_model.rowCount(None) > 0,
                "League standings rows did not populate")
            ui.widgets.ladder_table.selectRow(0)
            log_id = ui.league._selected_combatlog_id()
            if log_id is None:
                raise RuntimeError("The first League row did not expose a combatlog id")
            ui.league.download_and_view_combat()
            wait_until(
                lambda: ui.parser.analyzed_combats.rowCount() > 0,
                "The selected League parse was not downloaded and parsed")
            log_path = Path(ui.parser.current_combat.log_file)
            hidden_path = True
            source_name = f"standings:{log_id}"
        elif args.league is not None:
            log_path = ui.league.download(args.league)
            if log_path is None:
                raise RuntimeError(f"League parse {args.league} could not be downloaded")
            hidden_path = True
            source_name = f"league:{args.league}"
        else:
            log_path = args.local.resolve()
            hidden_path = False
            source_name = str(log_path)

        if not args.standings:
            ui.parser.analyze_log_file(log_path, hidden_path=hidden_path)
            wait_until(
                lambda: (ui.parser._thread is not None
                         and not ui.parser._thread.is_alive()
                         and ui.parser.analyzed_combats.rowCount() > 0),
                f"No combat was parsed from {source_name}")
        ui.app.processEvents()

        if errors:
            raise RuntimeError("; ".join(errors))
        if ui.parser.analyzed_combats.rowCount() < 1:
            raise TimeoutError(f"No combat was parsed from {source_name}")

        combat = ui.parser.current_combat
        result = {
            "source": source_name,
            "downloaded_path": str(log_path) if args.local is None else None,
            "combat_count": ui.parser.analyzed_combats.rowCount(),
            "map": combat.map,
            "difficulty": combat.difficulty,
            "players": len(combat.players),
        }
        print(json.dumps(result, sort_keys=True))

        ui.window.close()
        ui.app.processEvents()
        ui.app.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
