# Retro Escalation tester plan

## Status

No Retro Escalation desktop changes are implemented yet. This document defines the acceptance
matrix that must be completed before distributing the first experimental build.

## Test environments

Record the following for every report:

- Retro Escalation version or commit.
- Operating system and version.
- Display resolution and scaling percentage.
- OSCR UI scale and Live Parser scale.
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

- [ ] Fresh settings start in Default.
- [ ] Existing OSCR-UI 11.1.0 settings start without migration errors.
- [ ] Command Console selection is stored on normal shutdown.
- [ ] Command Console appears after restart.
- [ ] Returning to Default works after restart.
- [ ] Unknown theme ID falls back to Default.
- [ ] Missing theme asset falls back safely or displays a defined neutral substitute.
- [ ] A theme exception is logged without preventing application startup.

## Application smoke matrix

Run every item once in Default and once in Command Console.

### Overview

- [ ] Browse to a combat log.
- [ ] Analyze multiple combats.
- [ ] Select Infected Space, Hive Space, and Bug Hunt entries.
- [ ] Switch between DPS Bar, DPS Graph, and Damage Graph.
- [ ] Collapse and restore the sidebar, graph, and table.
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

- [ ] Load the map list.
- [ ] Fetch a ladder.
- [ ] Search and clear.
- [ ] Load more rows.
- [ ] Open a parse where permitted.

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
OSCR UI scale:
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
