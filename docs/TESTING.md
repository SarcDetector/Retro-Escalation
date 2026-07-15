# Retro Escalation tester plan

## Status

The restart-based theme foundation and portable tester build are implemented. Command Console now
has its own application shell plus dedicated Overview, Analysis, and League Standings presentations
and a categorized Settings dashboard while retaining the shared parser, models, and callbacks. The
Live Parser still uses its inherited window layout. League Standings can browse maps, search
ladders, load local logs, and open or save downloaded parses. This document defines the acceptance
matrix for experimental builds.

## Test environments

Record the following for every report:

- RE-OSCR version or commit.
- Operating system and version.
- Display resolution and scaling percentage.
- RE-OSCR UI scale and Live Parser scale.
- Selected theme.
- Whether the settings file was new, migrated, or manually edited.

Primary target:

- Windows 11, current supported updates.

Secondary targets:

- Windows 10 where OSCR remains supported.
- One current Linux desktop environment after Windows behavior is stable.

## Reference combats

Reference logs are local test fixtures and must not be committed without explicit permission.

- Infected Space Elite: representative short space combat.
- Hive Space Elite: second space map with different event distribution.
- Bug Hunt Any: ground combat.

Parser results from a given log and settings combination must match between OSCR-UI Legacy and
Command Console. Visual ordering may only differ where the existing user-configurable sort setting
allows it.

## Startup and recovery

- [x] Fresh settings start in Command Console. (Automated)
- [x] Legacy `OSCR_UI_settings.ini` settings migrate to `RE_OSCR_settings.ini`. (Automated)
- [x] Command Console selection is stored on normal shutdown. (Automated)
- [x] Command Console appears after restart. (Automated)
- [x] Returning to OSCR-UI Legacy works after restart. (Automated)
- [x] Unknown theme ID falls back to OSCR-UI Legacy. (Automated)
- [x] Missing theme asset falls back safely. (Automated)
- [x] A theme exception is logged without preventing theme resolution. (Automated)

## Application smoke matrix

Run every item once in OSCR-UI Legacy and once in Command Console.

### Overview

- [x] Browse to a combat log. (Manual source-app visual check)
- [x] Analyze an Infected Space combat. (Manual source-app visual check)
- [ ] Select Infected Space, Hive Space, and Bug Hunt entries.
- [x] Switch between DPS Bar and DPS Graph. (Manual source-app visual check)
- [x] Collapse and restore the sidebar. (Manual source-app visual check)
- [x] Keep all five colour-rail segments visible while the sidebar is collapsed. (Automated and
  manual source-app visual check)
- [x] Match the sidebar accent to Overview, Analysis, League, and Settings. (Automated and manual
  source-app visual check)
- [ ] Collapse and restore the graph and table.
- [ ] Sort the Overview table.
- [ ] Scroll all columns horizontally.
- [ ] Copy and export results.

### Analysis

- [x] Open Damage Out, Damage Taken, Heals Out, and Heals In. (Automated)
- [x] Expand a Player tree to ability rows. (Manual source-app visual check)
- [ ] Expand Player and NPC trees through every available level.
- [x] Select an ability row and add its graph series. (Manual source-app visual check)
- [x] Freeze and unfreeze a graph. (Manual source-app visual check)
- [ ] Clear graph series.
- [x] Collapse and restore the graph panel. (Automated and manual source-app visual check)
- [x] Keep the identity column visible while horizontally scrolling every Analysis tree.
  (Automated)
- [x] Sort from the frozen identity header and add graph rows from the frozen identity column.
  (Automated)
- [x] Open each combat in parser-truth with all Workbench modifiers off. (Automated)
- [x] Filter by owner, source, target, event, free text, visible names, and parser IDs across all
  four modes. (Automated)
- [x] Apply inclusive typed time cuts, clear individual bounds, and reset to parser-truth.
  (Automated)
- [x] Apply ordered GROUP, REVERSE, and EXCLUDE rules; recompute exclusion duration/DPS locally;
  reopen the preferred rule set with all per-combat toggles off. (Automated)
- [x] Keep auto-enable default-off, persist an explicit preferred-rule opt-in, open fresh combats
  as labelled modified views when opted in, and let RESET restore parser truth for the current
  combat without erasing the preference. (Automated)
- [x] Keep filtered graph bins aligned to the displayed window, including fractional event
  timestamps. (Automated)
- [x] Keep frozen SOURCE rows aligned with metric rows when their fonts or content request
  different heights. (Automated; tester screenshot regression)
- [x] Use Core, Events, Detail, and All metric lenses without changing parser-owned tree data or
  saved column choices. (Automated)
- [x] Present Player and NPC top-level buckets as counted group headers while retaining their
  source/ability/event drill-down tree. (Automated)
- [x] Label modified copies and keep League upload coordinates parser-owned. (Automated)
- [x] Show selected Analysis rows as a live weighted line plot by default; switch to grouped bars
  for detailed comparison and freeze or resume selection without changing parser-owned data.
  (Automated)
- [x] Use Simple Analysis for Core telemetry and live plotting, then switch to Advanced to reveal
metric lenses, filters, time cuts, rule editing, and the detailed bar comparison. Active
modifier chips remain visible in both modes. (Automated)
- [x] Clone a selected Workbench rule; its enabled state, type, matches, and label are copied
immediately below the original. (Automated)
- [ ] Exercise every copy mode.
- [ ] Sort and horizontally scroll tables.

### League

- [x] Select a season and ladder from the Command Console League command bar; verify that its
  live status reflects the selection while OSCR-UI Legacy keeps sidebar selection controls.
  (Automated startup and command-state checks)
- [x] Keep the League rank, Name, and Handle visible while the remaining ladder metrics scroll;
  use the DPS meter toggle without changing the League model or sorter. (Automated)
- [x] Load the map list. (Live offscreen probe and manual source-app visual check)
- [x] Fetch a ladder. (Live offscreen probe and manual source-app visual check)
- [x] Search by handle. (Manual source-app visual check)
- [ ] Clear a live search.
- [ ] Load more rows.
- [x] Open a selected parse where permitted. (Automated, live probe, and manual source-app check)
- [x] Open a local log directly from League Standings. (Automated)
- [x] Save a downloaded parse to a chosen path. (Automated)

The optional live probe exercises the public League API and is intentionally excluded from the
offline unit-test suite:

```powershell
python -m tests.league_live_probe --standings
python -m tests.league_live_probe --local "C:\path\to\CombatLog.log"
```

### Settings

- [x] Open Core + Results, Live Parser, and Table Columns categories. (Automated and manual
  source-app visual check)
- [x] Retain every configured damage, heal, and Live Parser column toggle. (Automated)
- [x] Show custom palette and background-image controls only when their Custom options are
  selected; keep the Live Parser graph field disabled while its graph is off. (Automated)
- [ ] Change a numeric setting and confirm persistence.
- [ ] Exercise switches, sliders, and combo boxes.
- [ ] Change Overview, Analysis, and Live Parser columns and apply them.
- [ ] Change UI scale and restart.
- [ ] Change theme and verify the restart-required guidance.

### Live Parser

- [ ] Open and close the separate window.
- [ ] Start and stop parsing.
- [ ] Verify opacity, scale, and graph visibility.
- [ ] Switch graph field and player display.
- [ ] Resize and reposition the window, then restart.
- [ ] Copy results in each supported format.

## Visual checks

- [x] Command Console text and controls remain readable at 1280x960. (Manual source-app visual
  check)
- [x] Text, chart axes, and controls remain readable at 1280x720. (Offscreen visual check)
- [ ] Text and controls remain readable at other supported scales.
- [ ] Tables distinguish headers, selected rows, alternate rows, hover, and focus.
- [ ] Disabled controls are visibly disabled.
- [ ] Keyboard focus remains visible.
- [ ] Chart axes, gridlines, legends, and all five player colours are distinguishable.
- [ ] Scrollbars and splitter handles are discoverable.
- [ ] Dialogs and error messages remain readable.
- [ ] Background artwork, if enabled, does not reduce table or chart contrast.

## Issue report template

```text
Build/commit:
Operating system:
Display resolution and scaling:
RE-OSCR UI scale:
Theme:
Page or window:

What happened:

What was expected:

Steps to reproduce:
1.
2.
3.

Does the same problem occur in OSCR-UI Legacy? Yes / No / Not tested
Screenshot or log excerpt:
```

Do not attach complete combat logs publicly unless every participant has agreed. Prefer the
smallest relevant excerpt with player handles redacted.
