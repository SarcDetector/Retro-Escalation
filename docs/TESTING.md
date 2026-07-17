# Retro Escalation tester plan

## Status

The restart-based theme foundation and portable tester build are implemented. Command Console now
has its own application shell plus dedicated Overview, Analysis, League Standings, Settings, and
Live Control Center presentations while retaining the shared parser, models, and callbacks. The
inherited Live Parser popout remains available from that page. League Standings can browse maps,
search ladders, load local logs, and open or save downloaded parses. This document defines the
acceptance matrix for experimental builds.

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

Parser results from a given log and settings combination must match between Legacy and
Command Console. Visual ordering may only differ where the existing user-configurable sort setting
allows it.

## Startup and recovery

- [x] Fresh settings start in Command Console. (Automated)
- [x] Legacy `OSCR_UI_settings.ini` settings migrate to `RE_OSCR_settings.ini`. (Automated)
- [x] Command Console selection is stored on normal shutdown. (Automated)
- [x] Command Console appears after restart. (Automated)
- [x] Returning to Legacy works after restart. (Automated)
- [x] Unknown theme ID falls back to Legacy. (Automated)
- [x] Missing theme asset falls back safely. (Automated)
- [x] A theme exception is logged without preventing theme resolution. (Automated)

## Application smoke matrix

Run every item once in Legacy and once in Command Console.

### Overview

- [x] Browse to a combat log. (Manual source-app visual check)
- [x] Analyze an Infected Space combat. (Manual source-app visual check)
- [ ] Select Infected Space, Hive Space, and Bug Hunt entries.
- [x] Switch between DPS Bar and DPS Graph. (Manual source-app visual check)
- [x] Collapse and restore the sidebar. (Manual source-app visual check)
- [x] Keep all five colour-rail segments visible while the sidebar is collapsed. (Automated and
  manual source-app visual check)
- [x] Match the sidebar accent to Overview, Analysis, League, Settings, and Live Parser.
  (Automated and manual source-app visual check)
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
  live status reflects the selection while Legacy keeps sidebar selection controls.
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

- [x] Open Core + Results, the Live Parser pointer, and Table Columns categories. (Automated and
  manual source-app visual check)
- [x] Retain every configured damage and heal column toggle; keep Live Parser columns on the
  dedicated Live page under their existing settings keys. (Automated)
- [x] Show custom palette and background-image controls only when their Custom options are
  selected; keep the Live Parser graph field disabled while its graph is off. (Automated)
- [ ] Change a numeric setting and confirm persistence.
- [ ] Exercise switches, sliders, and combo boxes.
- [ ] Change Overview and Analysis columns and apply them; change Live Parser columns from page 05.
- [ ] Change UI scale and restart.
- [ ] Change theme and verify the restart-required guidance.

### Live Parser

- [x] Make 05 a real Command Console page without showing the popout; keep Legacy's
  inherited direct toggle. (Automated)
- [x] Keep page selection, parser activity, and popout visibility independent; hiding the popout
  or navigating elsewhere does not stop parsing. (Automated)
- [x] Drive the embedded preview and popout from one normalized OSCR live-parser snapshot; clear
  stale preview rows when telemetry is empty. (Automated)
- [x] Keep all existing `liveparser__` keys and defaults unchanged, with one set of page controls
  for graph, field, columns, display name, copy, auto-start, scale, and opacity. (Automated)
- [x] Keep direct window close synchronized: Command Console hides without stopping; Legacy
  retains close-and-stop. (Automated)
- [x] Register, replace, restore, clear, and shut down Windows global-hotkey bindings
  transactionally; reject unsafe bare keys, reserved F12, and multi-key sequences. (Automated;
  native Windows smoke plus fake-backend regression tests)
- [x] Verify both visibility modes and prove that neither one stops the inherited parser.
  (Automated)
- [x] Start a real authenticated localhost websocket client, receive schema-v1 telemetry, reject
  client messages, and dispose connected clients cleanly. (Automated)
- [x] Generate the complete OBS folder, carry the active palette and selected metrics, sanitize
  non-finite data, and remove all telemetry from hidden frames. (Automated)
- [x] Reject wildcard, hostname, public, IPv6, stale-adapter, and privileged-port feed choices;
  require explicit confirmation for unencrypted LAN mode and never auto-start LAN. (Automated)
- [x] Load hotkey and browser-feed services only in Command Console; keep Legacy isolated
  from QtWebSockets and the new controller modules. (Automated subprocess startup checks)
- [ ] Open and close the separate window.
- [ ] Start and stop parsing.
- [ ] Verify opacity, scale, and graph visibility.
- [ ] Switch graph field and player display.
- [ ] Resize and reposition the window, then restart.
- [ ] Copy results in each supported format.
- [ ] Assign a global visibility hotkey, focus or minimize RE-OSCR, and verify it while STO owns
  keyboard focus.
- [ ] Add the generated `overlay.html` as an OBS Browser source using Local file; verify
  transparency, reconnect, selected metrics, palette changes, and both visibility modes.
- [ ] Select a private LAN adapter, confirm the unencrypted feed warning, and connect from a
  second device without opening any other interface.
- [ ] Apply a small custom CSS file, refresh the OBS Browser source, then verify a broken or
  oversized file falls back to the bundled style.

## Visual checks

- [x] Command Console text and controls remain readable at 1280x960. (Manual source-app visual
  check)
- [x] Text, chart axes, and controls remain readable at 1280x720. (Offscreen visual check)
- [x] Live Control Center split layout remains readable at 1280x720 and 1800x1000 with graph
  disabled and no configured combat log. (Offscreen visual checks)
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

Does the same problem occur in Legacy? Yes / No / Not tested
Screenshot or log excerpt:
```

Do not attach complete combat logs publicly unless every participant has agreed. Prefer the
smallest relevant excerpt with player handles redacted.
