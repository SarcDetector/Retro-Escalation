# Retro Escalation project scope

## Purpose

RE-OSCR is an independently maintained alternative frontend for the official `STO-OSCR` parser.
It began from the OSCR-UI 11.1.0 frontend baseline, but its development and release process does
not depend on upstream accepting a theme, plugin, or modular-UI architecture.

The official parser remains an external dependency. RE-OSCR does not fork or modify its parser
logic; this project owns the frontend experience, workflows, themes, and packaging around it.

## Product terminology

- **RE-OSCR**: the Retro Escalation frontend application and distributable.
- **OSCR**: the separate parser dependency and its analysis models.
- **Default**: the inherited OSCR-UI 11.1.0 appearance and behavior.
- **Command Console**: the optional Retro Escalation visual theme.
- **Theme system**: startup selection, validation, asset routing, and construction of an
  `AppTheme` instance.
- **UI redesign**: structural changes to pages, layouts, navigation, settings, or data grouping.
  These are not part of the initial theme-system milestone.

## Non-negotiable boundaries

- Do not change STO-OSCR parser logic.
- Default remains the default choice.
- Default must retain its existing theme data, assets, layout, and behavior.
- Theme selection takes effect after restart; hot switching is not required.
- Unknown, missing, incompatible, or malformed theme selections fall back to Default.
- A theme failure must never prevent the user from reaching RE-OSCR with Default styling.
- Existing settings files without a theme value continue to load normally, and the legacy
  `OSCR_UI_settings.ini` filename is migrated once to `RE_OSCR_settings.ini`.
- Existing callbacks, models, sorting, copying, exporting, league operations, and Live Parser
  behavior remain in scope for regression testing.
- Modified distributions remain GPLv3 and include corresponding source and modification notices.

## Baseline observations

- Theme construction is centralized in `re_oscr/app.py`.
- `AppTheme` already accepts alternate theme data and theme options.
- Tables, graphs, dialogs, the sidebar, status bar, and Live Parser already receive an `AppTheme`
  instance explicitly.
- Styling is nevertheless broad: theme values or styles are consumed at roughly 246 source
  locations.
- Main-window and page layouts are constructed directly in `re_oscr/app.py`.
- The inherited OSCR-UI 11.1.0 frontend had packaging workflows but no committed automated test
  suite.

These observations made a built-in theme registry feasible as RE-OSCR's first step. Progressive
replacement of inherited layouts remains a larger set of later milestones.

## Milestone 0: protected baseline

Status: complete on the `retro-escalation` branch.

Goal: establish evidence that the inherited frontend still behaves like OSCR-UI 11.1.0 before
RE-OSCR theme work.

Deliverables:

- Document a reproducible Python 3.13+ development environment.
- Add import and configuration checks.
- Add unit coverage for loading and storing existing settings.
- Add a minimal offscreen Qt startup smoke check where the CI environment supports it.
- Record a manual baseline checklist for Overview, Analysis, League, Settings, and Live Parser.
- Produce an unchanged Windows development build before styling changes.

Exit criteria:

- Baseline checks pass on the development branch.
- The reference combat logs can be analyzed without errors.
- No generated logs, personal settings, or parse data are committed.

## Milestone 1: startup theme foundation

Status: implemented and included in the portable tester build.

Goal: select a built-in theme at application startup without changing any layout.

Proposed architecture:

```text
re_oscr/
  theme.py                 Existing AppTheme and Default theme
  themes/
    __init__.py
    registry.py            Known theme IDs, labels, factories and fallback
    command_console.py     Theme overrides and options
assets/
  ...                      Existing Default assets
theme_assets/
  command_console/
    ...                    Optional theme-specific assets
```

The initial registry is built-in and allow-listed. It is not a general Python plugin loader.

Required behavior:

1. Add a string setting such as `theme_id`, defaulting to `default`.
2. Resolve the saved ID through a small theme registry before GUI construction.
3. Construct Default through the existing path when no alternate theme is selected.
4. Construct Command Console from Default plus validated overrides, avoiding a duplicated copy of
   the entire Default theme tree.
5. Route optional theme assets through a distinct Qt search path.
6. Catch theme construction and asset errors, log them, and continue with Default.
7. Add a Settings selector labelled as restart-required.

Exit criteria:

- A fresh install starts in Default.
- Existing settings files start in Default.
- Selecting Command Console, closing RE-OSCR normally, and reopening selects Command Console.
- Invalid IDs and deliberately broken test themes start safely in Default.
- Switching back to Default restores the original appearance after restart.

## Milestone 2: Command Console shell and core telemetry views

Status: implemented on the current development branch.

Goal: prove that RE-OSCR can own a structurally distinct application shell and page presentation
without changing parser logic or losing the inherited workflows.

In scope:

- Dark surfaces and high-contrast text.
- Orange, gold, purple, cyan, and red accent roles.
- A dedicated masthead with original RE branding and no copied logos, fonts, or interface artwork.
- Five large segmented controls for Overview, Analysis, League, Settings, and Live Parser.
- A persistent five-colour context rail surrounding the collapsible sidebar, with a readable
  page-matched sidebar tint and border.
- Dedicated Overview, Analysis, League Standings, and Settings presentation modules with rounded
  chart, table, and control panels.
- Command-style Overview graph modes while retaining all three inherited plots.
- Command-style Analysis modes while retaining Damage Out, Damage Taken, Heals Out, and Heals In.
- Command-style League ladder browser while retaining season/map selection, sorting, handle search,
  row expansion, local-log loading, and selected-parse open/save actions.
- Categorized Settings work areas for core behavior, Live Parser behavior, and all inherited column
  visibility controls.
- Player and NPC tree drill-down, event graph selection, freeze, clear, copy, and focus controls.
- Pyqtgraph backgrounds, axes, legends, bars, lines, and a five-player colour cycle.
- Shared parser callbacks, models, sorting, copying, uploading, and saved splitter state.
- An unchanged Default shell and Overview structure selected through the same startup registry.
- Original RE branding assets that do not use protected logos or copied interface artwork.
- Optional bundled background artwork only if it remains readable and behaves safely when absent.

Out of scope:

- Metric summary cards.
- Splitting telemetry into new table models or changing data columns.
- Adding the browser prototype's Analysis readout panel.
- Rebuilding the inherited Live Parser window layout.
- Five-rail palette presets and user-entered colours.
- Custom background selection.
- Runtime theme switching.
- Downloading or executing third-party themes.

Exit criteria:

- Command Console starts at 1280x720 or larger without clipping its five primary controls.
- The sidebar collapses and restores through the existing callback while the five-colour rail
  remains visible.
- Sidebar tint and border follow the active Overview, Analysis, League, or Settings accent.
- A local Infected Space log browses, analyzes, and populates charts and tables.
- All three Overview plot modes remain reachable.
- All four Analysis modes synchronize their graph and tree panels.
- Damage and healing models retain their distinct headers and drill-down behavior.
- League map selection, ladder retrieval, handle filtering, and selected-parse loading remain usable.
- All inherited Settings fields and column toggles remain reachable in the categorized dashboard.
- The Default startup probe still exposes the inherited shell, Overview, Analysis, and League
  controls.
- No parser outputs differ between Default and Command Console for the same logs and settings.

## Milestone 3: tester release

Goal: publish an explicitly experimental Windows build for community feedback.

Deliverables:

- Versioned source tag and GPL-compliant source availability.
- Windows build artifact attached to a GitHub prerelease.
- SHA-256 checksum.
- Known-issues list and rollback instructions.
- Feedback template requesting OS version, scale, theme, page, screenshot, and reproduction steps.
- Clear statement that the build is unofficial and unsupported by STOCD.

Exit criteria:

- Clean installation and startup on at least two Windows systems.
- Default and Command Console can each complete the smoke checklist.
- A broken or manually invalidated theme setting recovers to Default.

## Later possibilities, deliberately parked

- User-editable five-rail colour presets.
- Custom background selection and persistence.
- External declarative theme packages.
- Theme manifests and compatibility versions.
- Third-party UI-provider or executable-plugin APIs.
- Dashboard metric cards, grouped telemetry, and the remaining structural concepts from the browser
  prototype.

Each parked feature requires a separate scope decision. None is required to prove the startup
theme foundation.

## Principal risks

| Risk | Impact | Initial mitigation |
|---|---|---|
| Default appearance changes unintentionally | High | Keep the existing Default construction path and capture baseline screenshots |
| Theme tree is incomplete | High | Overlay validated overrides on Default and test required keys |
| Theme asset missing in packaged build | High | Separate asset prefix, packaging check, and Default fallback |
| QSS behavior differs across platforms | Medium | Windows-first tester matrix, then Linux verification |
| Pyqtgraph uses colours outside QSS | High | Treat charts as a separate explicit theme surface |
| UI scale exposes clipping or unreadable text | High | Test 0.5, 1.0, and 1.5 scale values plus minimum window size |
| External plugins create a security/support burden | High | Built-in allow-listed registry only for the MVP |
| Fork drifts from upstream | Medium | Keep `upstream` remote and isolate changes into small commits |

## First implementation issue set

1. Add baseline import/config tests and Windows development instructions.
2. Add `theme_id` setting with backward-compatible persistence tests.
3. Add theme registry and guaranteed Default fallback.
4. Add a minimal no-op alternate theme fixture for lifecycle testing.
5. Add restart-required selector to Settings.
6. Add Command Console theme overrides in small widget-family commits.
7. Add chart and Live Parser theme coverage.
8. Build and run the tester matrix.
9. Publish the first prerelease and collect structured feedback.
