# Retro Escalation tester plan

## Status

The restart-based theme foundation and portable tester build are implemented. Command Console now
has its own application shell and Overview presentation while retaining the shared parser, models,
and callbacks. Analysis, League, Settings, and Live Parser still use inherited page layouts inside
the new shell. League Standings can load local logs and open or save downloaded parses. This
document defines the acceptance matrix for experimental builds.

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

Parser results from a given log and settings combination must match between Default and Command
Console. Visual ordering may only differ where the existing user-configurable sort setting allows
it.

## Startup and recovery

- [x] Fresh settings start in Default. (Automated)
- [x] Legacy `OSCR_UI_settings.ini` settings migrate to `RE_OSCR_settings.ini`. (Automated)
- [x] Command Console selection is stored on normal shutdown. (Automated)
- [x] Command Console appears after restart. (Automated)
- [x] Returning to Default works after restart. (Automated)
- [x] Unknown theme ID falls back to Default. (Automated)
- [x] Missing theme asset falls back safely. (Automated)
- [x] A theme exception is logged without preventing theme resolution. (Automated)

## Application smoke matrix

Run every item once in Default and once in Command Console.

### Overview

- [x] Browse to a combat log. (Manual source-app visual check)
- [x] Analyze an Infected Space combat. (Manual source-app visual check)
- [ ] Select Infected Space, Hive Space, and Bug Hunt entries.
- [x] Switch between DPS Bar and DPS Graph. (Manual source-app visual check)
- [x] Collapse and restore the sidebar. (Manual source-app visual check)
- [ ] Collapse and restore the graph and table.
- [ ] Sort the Overview table.
- [ ] Scroll all columns horizontally.
- [ ] Copy and export results.

### Analysis

- [ ] Open Damage Out, Damage Taken, Heals Out, and Heals In.
- [ ] Expand Player and NPC trees through multiple levels.
- [ ] Select rows and add/remove graph series.
- [ ] Freeze and clear graphs.
- [ ] Exercise every copy mode.
- [ ] Sort and horizontally scroll tables.

### League

- [x] Load the map list. (Live offscreen probe)
- [x] Fetch a ladder. (Live offscreen probe)
- [ ] Search and clear.
- [ ] Load more rows.
- [x] Open a selected parse where permitted. (Automated and live offscreen probe)
- [x] Open a local log directly from League Standings. (Automated)
- [x] Save a downloaded parse to a chosen path. (Automated)

The optional live probe exercises the public League API and is intentionally excluded from the
offline unit-test suite:

```powershell
python -m tests.league_live_probe --standings
python -m tests.league_live_probe --local "C:\path\to\CombatLog.log"
```

### Settings

- [ ] Change a numeric setting and confirm persistence.
- [ ] Exercise switches, sliders, and combo boxes.
- [ ] Change Overview, Analysis, and Live Parser columns and apply them.
- [ ] Change UI scale and restart.
- [ ] Change language and restart.
- [ ] Change theme and verify the restart-required guidance.

### Live Parser

- [ ] Open and close the separate window.
- [ ] Start and stop parsing.
- [ ] Verify opacity, scale, and graph visibility.
- [ ] Switch graph field and player display.
- [ ] Resize and reposition the window, then restart.
- [ ] Copy results in each supported format.

## Visual checks

- [ ] Text and controls remain readable at minimum supported window size.
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

Does the same problem occur in Default? Yes / No / Not tested
Screenshot or log excerpt:
```

Do not attach complete combat logs publicly unless every participant has agreed. Prefer the
smallest relevant excerpt with player handles redacted.
