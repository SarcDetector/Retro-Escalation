# RE-OSCR feature set

RE-OSCR — Retro Escalation is an independent Command Console frontend for the official
`STO-OSCR` combat-log parser. It makes combat telemetry easier to read, explore, and share while
leaving parser truth, parser models, and League upload inputs intact.

## At a glance

- **Command Console by default** — a data-first desktop workspace with five colour-coded areas:
  Overview, Analysis, League, Settings, and Live Parser.
- **OSCR-UI Legacy included** — the inherited appearance remains selectable for users who prefer
  it or need a known-good recovery path.
- **Analysis built for reading** — a clean Simple view for fast answers and an Advanced view when
  the full investigation is needed.
- **A local Workbench, not a parser fork** — create display-only filters and rules without
  rewriting combat data or affecting League uploads.
- **Portable ways to run** — Windows ZIP packages, Linux x86-64 portable archives, and a PyPI
  package for `pipx` installs.

## Five workspaces

| Workspace | What it is for |
|---|---|
| **01 Overview** | Read the encounter at a glance with meter rows, chart modes, drill-down, and the parser's existing result data. |
| **02 Analysis** | Investigate outgoing/incoming damage and healing through synchronized graphs and expandable telemetry trees. |
| **03 League** | Browse standings, filter handles, load local logs, and open or save selected parses while retaining League's existing workflow. |
| **04 Settings** | Organize core behavior, Live Parser behavior, palettes, and inherited table-column choices without hiding expert controls. |
| **05 Live Parser** | Use the existing live telemetry workflow from the Command Console. The dedicated overlay work is a later phase. |

## Analysis: quick when it needs to be, deep when it matters

### Simple view

Simple Analysis starts with Core telemetry and a live weighted-line graph. It is intended for the
common question: *what did the fight do, and where did the damage go?* The active modified-view
state remains visible, so there is no ambiguity about what is being shown.

### Advanced view

Advanced Analysis exposes the investigation controls without turning the normal view into a wall
of spreadsheet panels:

- Core, Events, Detail, and All metric lenses.
- Structured filters by owner, source, target, event, text, visible name, or parser ID.
- Inclusive time cuts for a specific portion of a combat.
- Live weighted lines or grouped-bar comparison, plus freeze and clear controls.
- Expandable Player and NPC trees with a pinned identity column for readable deep telemetry.

### Analysis Workbench

The Workbench is a display-only layer for local analysis:

- **GROUP** combines matching effects under a readable label.
- **REVERSE** moves an indirect effect above the sources that produced it.
- **EXCLUDE** removes matching events from this local view and recalculates its duration/DPS.
- Rule sets persist, selected rules can be cloned, and fresh combats remain parser-truth by
  default.
- Users who want the same presentation every combat can explicitly auto-enable checked rules.

Every modified view is visibly labelled. **RESET** returns the current combat to parser truth, and
League upload data always remains parser-owned.

## Design principles

RE-OSCR is designed as a combat meter rather than a generic spreadsheet:

- Data is the hero; visual chrome frames it instead of competing with it.
- Five accent colours are wayfinding for the five workspaces, not decoration.
- Tables use hierarchy, meter rows, and readable data grids; the full matrix is an expert choice,
  not the default landing state.
- Original RE-OSCR typography, layout, and artwork are used. No copied logos or interface trade
  dress are required.

## Installation and updates

| Platform | Recommended path |
|---|---|
| **Windows** | Download the portable Windows ZIP from the relevant GitHub release or workflow artifact, extract it somewhere writable, and run `RE-OSCR.exe`. |
| **Linux x86-64** | Download the portable archive from the Linux workflow, extract it, and run `./RE-OSCR`. |
| **Linux / macOS with Python** | Install published releases with `pipx install re-oscr`; development releases use `pipx install re-oscr --pip-args="--pre"`. Update with `pipx upgrade re-oscr`. |

Portable packages keep their settings beside the executable. `pipx` installs keep settings in the
normal per-user application-data location, so upgrades do not discard them.

## Boundaries and credit

RE-OSCR keeps `STO-OSCR` as a separate, unmodified parser dependency. It does not change parser
logic and does not replace parser truth with Workbench views. It is a GPL-3.0 community frontend,
independent from STOCD's official releases.

Analysis workflow ideas were informed by AnotherNathan's STO CombatLogAnalyzer (CLA), while the
RE-OSCR interface and implementation are original. See [CREDITS.md](CREDITS.md) for the complete
acknowledgements.
