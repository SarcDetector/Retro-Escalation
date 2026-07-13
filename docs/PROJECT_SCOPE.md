# Retro Escalation project scope

## Purpose

Retro Escalation will test whether OSCR-UI can support a startup-selected visual theme without
changing parser behavior or degrading the existing interface. Work begins from the unmodified
OSCR-UI 11.1.0 release.

The first implementation is a fork experiment. Upstream acceptance is not required to develop or
test it. Architectural changes that prove small, safe, and generally useful may later be proposed
to STOCD independently of the Retro Escalation artwork.

## Product terminology

- **Default**: the current OSCR-UI appearance and behavior.
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
- A theme failure must never prevent the user from reaching OSCR with Default styling.
- Existing settings files without a theme value continue to load normally.
- Existing callbacks, models, sorting, copying, exporting, league operations, and Live Parser
  behavior remain in scope for regression testing.
- Modified distributions remain GPLv3 and include corresponding source and modification notices.

## Baseline observations

- Theme construction is centralized in `OSCRUI/app.py`.
- `AppTheme` already accepts alternate theme data and theme options.
- Tables, graphs, dialogs, the sidebar, status bar, and Live Parser already receive an `AppTheme`
  instance explicitly.
- Styling is nevertheless broad: theme values or styles are consumed at roughly 246 source
  locations.
- Main-window and page layouts are constructed directly in the 1,140-line `OSCRUI/app.py`.
- OSCR-UI 11.1.0 has packaging workflows but no committed automated test suite.

These observations make a built-in theme registry feasible while making a full replacement UI a
separate, substantially larger project.

## Milestone 0: protected baseline

Goal: establish evidence that the fork still behaves like OSCR-UI 11.1.0 before theme work.

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

Goal: select a built-in theme at application startup without changing any layout.

Proposed architecture:

```text
OSCRUI/
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
- Selecting Command Console, closing OSCR normally, and reopening selects Command Console.
- Invalid IDs and deliberately broken test themes start safely in Default.
- Switching back to Default restores the original appearance after restart.

## Milestone 2: Command Console coverage on existing layouts

Goal: express the Retro Escalation identity using OSCR's current widgets and layouts.

In scope:

- Dark surfaces and high-contrast text.
- Orange, gold, purple, cyan, and red accent roles.
- Rounded buttons and panels where Qt stylesheets support them reliably.
- Navigation, tabs, inputs, scrollbars, splitters, status indicators, and dialogs.
- Overview and Analysis table readability, selection, hover, and alternate rows.
- Pyqtgraph backgrounds, axes, grids, legends, bars, lines, and colour cycles.
- Live Parser window, table, graph, resize grip, opacity, and scaling.
- Original RE branding assets that do not use protected logos or copied interface artwork.
- Optional bundled background artwork only if it remains readable and behaves safely when absent.

Out of scope:

- Replacing the main navigation layout with the browser prototype's segmented dashboard.
- Metric summary cards.
- Rearranging Overview charts and tables.
- Splitting telemetry into new table models or changing data columns.
- Rebuilding Settings into categories or cards.
- Adding the browser prototype's Analysis readout panel.
- Runtime theme switching.
- Downloading or executing third-party themes.

Exit criteria:

- All manual tester cases pass in both themes.
- Tables remain legible at supported UI scales and window sizes.
- Charts remain distinguishable with five players and dense combat data.
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
- Alternative UI providers or plugin APIs.
- Dashboard cards, grouped telemetry, reorganized Settings, and other structural concepts from the
  browser prototype.

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
