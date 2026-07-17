# Retro Escalation project scope

## Purpose

RE-OSCR is an independently maintained alternative frontend for the official `STO-OSCR` parser.
It began from an upstream GPLv3 frontend baseline, but its development and release process does
not depend on upstream accepting a theme, plugin, or modular-UI architecture.

The official parser remains an external dependency. RE-OSCR does not fork or modify its parser
logic; this project owns the frontend experience, workflows, themes, and packaging around it.

## Product terminology

- **RE-OSCR**: the Retro Escalation frontend application and distributable.
- **OSCR**: the separate parser dependency and its analysis models.
- **Legacy**: the appearance and behavior inherited from the upstream GPLv3 frontend baseline
  (internal theme ID `default`, kept for settings compatibility). Called "Default" in earlier
  revisions of this document.
- **Command Console**: the Retro Escalation visual identity and, as of 2026-07-14, the default
  experience.
- **Theme system**: startup selection, validation, asset routing, and construction of an
  `AppTheme` instance.
- **UI redesign**: structural changes to pages, layouts, navigation, settings, or data grouping.
  These are not part of the initial theme-system milestone.

## Non-negotiable boundaries

Amended 2026-07-14: Command Console became the default experience. The original boundary
("Default remains the default choice") belonged to the theme-switcher era; RE-OSCR is now a
distinct product whose inherited look is a compatibility option.

- Do not change STO-OSCR parser logic.
- Command Console is the default experience. Fresh installs and settings files without an
  explicit theme choice resolve to Command Console; an explicit `default` value selects
  Legacy. (Baseline tests asserting the old fresh-install default must be updated with
  this change.)
- Legacy must retain its existing theme data, layout, and behavior. RE-OSCR identity artwork may
  be replaced without changing its geometry.
- Structural theme switches (Command Console ↔ Legacy) apply through an in-app
  "Apply and relaunch" action; appearance changes within Command Console (rail presets,
  palette, background) apply live once the dev7 stylesheet architecture lands.
- A missing `theme_id` setting resolves to Command Console. An explicitly saved unknown,
  incompatible, or malformed theme ID falls back to Legacy.
- An unknown, missing, or malformed Command Console rail preset falls back to the Command Console
  Default palette; a palette failure does not switch the structural theme.
- A theme construction failure must never prevent the user from reaching RE-OSCR: Legacy remains
  the guaranteed-bootable path.
- Existing settings files continue to load normally, and the legacy `OSCR_UI_settings.ini`
  filename is migrated once to `RE_OSCR_settings.ini`.
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
- The inherited upstream GPLv3 frontend baseline had packaging workflows but no committed
  automated test suite.

These observations made a built-in theme registry feasible as RE-OSCR's first step. Progressive
replacement of inherited layouts remains a larger set of later milestones.

## Milestone 0: protected baseline

Status: complete on the `retro-escalation` branch.

Goal: establish evidence that the inherited frontend still behaves like the upstream GPLv3
frontend baseline before
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

Implemented architecture:

```text
re_oscr/
  theme.py                 Existing AppTheme and Legacy theme
  themes/
    __init__.py
    registry.py            Known theme IDs, labels, factories and fallback
    command_console.py     Theme overrides and options
assets/
  ...                      Existing Legacy assets
theme_assets/
  command_console/
    ...                    Optional theme-specific assets
```

The initial registry is built-in and allow-listed. It is not a general Python plugin loader.

Required behavior:

1. Add a string setting such as `theme_id`, defaulting to `command_console` when the key is absent.
2. Resolve the saved ID through a small theme registry before GUI construction.
3. Construct Legacy through the existing path when `default` is explicitly selected or
   when Command Console cannot be constructed safely.
4. Construct Command Console from the legacy theme plus validated overrides, avoiding a duplicated
   copy of the entire legacy theme tree.
5. Route optional theme assets through a distinct Qt search path.
6. Catch theme construction and asset errors, log them, and continue with Legacy.
7. Add a Settings selector with an Apply-and-relaunch action for structural theme changes.

Exit criteria:

- A fresh install starts in Command Console.
- Existing settings files without a `theme_id` start in Command Console.
- Explicitly selecting Legacy and relaunching restores the inherited appearance.
- Invalid IDs and deliberately broken test themes start safely in Legacy.
- Switching back to Command Console restores the RE-OSCR experience after relaunch.

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
- A functionally unchanged Legacy shell and Overview structure selected through the same startup
  registry, with only RE-OSCR identity artwork replacing the inherited banner and icon.
- Original RE branding assets that do not use protected logos or copied interface artwork.
- Five-rail palette presets, user-entered colours, and a validated Custom preset.
- Digital-grid, no-background, and user-selected local background modes. No generated or licensed
  background artwork is bundled.

Out of scope:

- Metric summary cards.
- Splitting telemetry into new table models or changing data columns.
- Adding the browser prototype's Analysis readout panel.
- Rebuilding the inherited Live Parser window layout.
- Hot structural theme switching without relaunch.
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
- The Legacy startup probe still exposes the inherited shell, Overview, Analysis, and League
  controls.
- No parser outputs differ between Legacy and Command Console for the same logs and settings.

## Milestone 3: tester release

Goal: publish explicitly experimental Windows and Linux builds for community feedback.

Deliverables:

- Versioned source tag and GPL-compliant source availability.
- Windows and Linux x86-64 build artifacts attached to a GitHub prerelease.
- SHA-256 checksum.
- Known-issues list and rollback instructions.
- Feedback template requesting OS version, scale, theme, page, screenshot, and reproduction steps.
- Clear statement that the build is independently maintained and is not an upstream parser release.

Exit criteria:

- Clean installation and startup on at least two Windows systems plus the Linux CI environment.
- Legacy and Command Console can each complete the smoke checklist.
- A broken or manually invalidated theme setting recovers to Legacy.

## Later possibilities, deliberately parked

- External declarative theme packages.
- Theme manifests and compatibility versions.
- Third-party UI-provider or executable-plugin APIs.

Each parked feature requires a separate scope decision. None is required to prove the startup
theme foundation.

## Principal risks

| Risk | Impact | Initial mitigation |
|---|---|---|
| Legacy appearance changes unintentionally | High | Keep the existing legacy construction path and capture baseline screenshots |
| Theme tree is incomplete | High | Overlay validated overrides on the legacy theme and test required keys |
| Theme asset missing in packaged build | High | Separate asset prefix, packaging check, and Legacy fallback |
| QSS behavior differs across platforms | Medium | Windows-first tester matrix, then Linux verification |
| Pyqtgraph uses colours outside QSS | High | Treat charts as a separate explicit theme surface |
| UI scale exposes clipping or unreadable text | High | Test 0.5, 1.0, and 1.5 scale values plus minimum window size |
| External plugins create a security/support burden | High | Built-in allow-listed registry only for the MVP |
| Fork drifts from upstream | Medium | Keep `upstream` remote and isolate changes into small commits |

## Initial implementation issue set (complete)

1. Add baseline import/config tests and Windows development instructions.
2. Add `theme_id` setting with backward-compatible persistence tests.
3. Add theme registry and guaranteed Legacy fallback.
4. Add a minimal no-op alternate theme fixture for lifecycle testing.
5. Add the structural theme selector and relaunch-required lifecycle to Settings.
6. Add Command Console theme overrides in small widget-family commits.
7. Add chart and Live Parser theme coverage.
8. Build and run the tester matrix.
9. Publish the first prerelease and collect structured feedback.
