# RE-OSCR — Retro Escalation

RE-OSCR is an alternative desktop frontend for the Open Source Combatlog Reader (`OSCR`) parser
used with Star Trek Online combat logs. Retro Escalation keeps the official `STO-OSCR` parser as
an external dependency and concentrates its changes in presentation, workflow, accessibility, and
packaging.

Current development features include:

- A restart-selected Default or Command Console theme.
- A dedicated Command Console application shell with five segmented navigation controls and a
  persistent five-colour context rail plus page-matched sidebar accents.
- Dedicated Command Console Overview, Analysis, League Standings, and categorized Settings layouts
  that retain the inherited parser, charts, tables, tree drill-down, copy, upload, search, column,
  and collapse behavior.
- Isolated RE-OSCR settings that do not modify an installed OSCR application.
- League Standings browsing with season/map selection, handle search, local-log loading, and
  selected-parse open/save actions.
- A portable Windows tester build.

- [Project scope](docs/PROJECT_SCOPE.md)
- [Tester plan](docs/TESTING.md)
- [Development guide](docs/DEVELOPMENT.md)

## Parser dependency

RE-OSCR uses `STO-OSCR==11.0.0`. The `OSCR` name remains attached to the parser and its combat
analysis models. Retro Escalation does not currently fork or modify parser logic.

## Running from source

Python 3.13 or newer is required.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[pyinst]"
.\.venv\Scripts\re-oscr.exe
```

Run the offline regression suite with:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Windows portable build

```powershell
.\distribution\windows\build_retro_escalation.ps1 `
    -OutputRoot "E:\re-oscar\re-oscr theme switching" `
    -Package
```

The generated `RE-OSCR.exe` stores settings beside the executable and does not use the official
application's settings directory.

## Origin and licensing

RE-OSCR began as a downstream fork of
[STOCD/OSCR-UI 11.1.0](https://github.com/STOCD/OSCR-UI). Its source history and GPLv3 licensing
are retained. It is an independent community frontend and is not an official STOCD release.

The parser is provided by the separate [STOCD/OSCR](https://github.com/STOCD/OSCR) project.
