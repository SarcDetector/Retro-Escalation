# RE-OSCR — Retro Escalation

RE-OSCR is an alternative desktop frontend for the Open Source Combatlog Reader (`OSCR`) parser
used with Star Trek Online combat logs. Retro Escalation keeps the official `STO-OSCR` parser as
an external dependency and concentrates its changes in presentation, workflow, accessibility, and
packaging.

Current development features include:

- A restart-selected Command Console (default) or OSCR-UI Legacy appearance.
- A dedicated Command Console application shell with five segmented navigation controls and a
  persistent five-colour context rail plus page-matched sidebar accents.
- Dedicated Command Console Overview, Analysis, League Standings, and categorized Settings layouts
  that retain the inherited parser, charts, tables, tree drill-down, copy, upload, search, column,
  and collapse behavior.
- A fifth-tab Live Control Center with one inherited parser session, an embedded preview, the
  existing local popout, an optional Windows global visibility hotkey, and a read-only
  browser/OBS meter.
- Isolated RE-OSCR settings that do not modify an installed OSCR application.
- League Standings browsing with season/map selection, handle search, local-log loading, and
  selected-parse open/save actions.
- Portable Windows and Linux tester builds.

- [Project scope](docs/PROJECT_SCOPE.md)
- [Feature set](docs/FEATURES.md)
- [Feature poster (2560x1440 SVG)](docs/re-oscr-feature-poster.svg) ·
  [PNG](docs/re-oscr-feature-poster-2560x1440.png)
- [Credits](docs/CREDITS.md)
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

## Linux and macOS via PyPI

Published releases can be installed independently of a distribution package manager with
[`pipx`](https://pipx.pypa.io/):

```bash
pipx install re-oscr
re-oscr
```

Because the current PyPI release is a development release and no stable release exists yet,
`pipx install re-oscr` selects it normally. Once stable releases exist, plain installs stay on the
stable channel; opt in to a later development release with
`pipx install re-oscr --pip-args="--pre"`. `pipx upgrade re-oscr` updates the application without
touching its settings, which live in the normal per-user application-data directory. The portable
Windows and Linux packages continue to keep settings beside the executable.

## Windows portable build

```powershell
.\distribution\windows\build_retro_escalation.ps1 `
    -OutputRoot "E:\re-oscar\re-oscr theme switching" `
    -Package
```

The generated `RE-OSCR.exe` stores settings beside the executable and does not use the official
application's settings directory.

Windows packages are also built natively by the `Windows portable build` GitHub Actions workflow.
Download its ZIP and SHA-256 artifact from the relevant workflow run.

## Linux portable build

Linux packages are built natively on Ubuntu 22.04 by the `Linux portable build` GitHub Actions
workflow. The resulting `linux-x86_64.tar.gz` archive can be downloaded from the workflow run.

To build on a Linux workstation instead:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[pyinst]"
./distribution/linux/build_retro_escalation.sh --output-root dist --package
```

Extract the archive into a user-writable directory and run `./RE-OSCR`. Portable Linux settings
are stored beside the executable. See [`distribution/linux/README.md`](distribution/linux/README.md)
for runtime requirements and compatibility notes.

## Origin and licensing

RE-OSCR is produced and maintained by **Sarc**
([SarcDetector](https://github.com/SarcDetector)). See [Credits](docs/CREDITS.md) for the
project's parser, analysis, appearance, and licensing acknowledgements.

RE-OSCR began as a downstream fork of
[STOCD/OSCR-UI 11.1.0](https://github.com/STOCD/OSCR-UI). Its source history and GPLv3 licensing
are retained. It is an independent community frontend and is not an official STOCD release.

The parser is provided by the separate [STOCD/OSCR](https://github.com/STOCD/OSCR) project.

The redesigned Analysis workflow draws inspiration from
[STO_CombatLogAnalyzer (CLA)](https://github.com/AnotherNathan/STO_CombatLogAnalyzer), created by
AnotherNathan. RE-OSCR retains OSCR as its parser and implements its Analysis presentation
independently.
