# CLA compatibility parity ledger

Status: **SOURCE AUDIT COMPLETE; IMPLEMENTATION NOT STARTED**

Audit date: 2026-07-16

RE-OSCR baseline: [v11.1.0.dev12](baselines/v11.1.0.dev12.md)

This is the living compatibility inventory for evolving RE-OSCR Analysis toward CLA without
replacing the OSCR parser. It records what CLA calculates, whether the selected OSCR combat
contains the required inputs, what dev12 already presents, and what must be proven with golden
fixtures.

The compatibility promise is deliberately precise:

> **CLA-compatible calculations on the selected OSCR combat.**

It is not an alternate CLA parser and it is not a promise that OSCR and CLA will discover the same
combat from every raw log file.

## Pinned evidence

The compatibility target is the official
[CLA v1.4.0 source](https://github.com/AnotherNathan/STO_CombatLogAnalyzer/tree/89e9ac5af52a91e3533b2bc252a656f772c73daa),
commit [`89e9ac5af52a91e3533b2bc252a656f772c73daa`](https://github.com/AnotherNathan/STO_CombatLogAnalyzer/commit/89e9ac5af52a91e3533b2bc252a656f772c73daa),
released 2026-02-28. Its core analyzer remains unchanged on the audited 2026-05-15 master commit
[`24edc6136bf772f95c5b67bf718c7401f91c82fd`](https://github.com/AnotherNathan/STO_CombatLogAnalyzer/commit/24edc6136bf772f95c5b67bf718c7401f91c82fd);
later master changes are presentation and formatting work.

The local CLA source archive was read directly, not treated as a black-box application. After
newline normalization its 74 tracked files match that audited master commit, and its analyzer code
is identical to the pinned v1.4.0 analyzer. Observed exports are reserved for harness evidence.

Primary CLA sources:

- **C-PARSE** — [record classification](https://github.com/AnotherNathan/STO_CombatLogAnalyzer/blob/89e9ac5af52a91e3533b2bc252a656f772c73daa/src/analyzer/parser.rs)
- **C-TIME** — [combat ownership, timing, and attribution](https://github.com/AnotherNathan/STO_CombatLogAnalyzer/blob/89e9ac5af52a91e3533b2bc252a656f772c73daa/src/analyzer/mod.rs)
- **C-DMG** — [damage accumulation and formulas](https://github.com/AnotherNathan/STO_CombatLogAnalyzer/blob/89e9ac5af52a91e3533b2bc252a656f772c73daa/src/analyzer/damage.rs)
- **C-HEAL** — [healing accumulation and formulas](https://github.com/AnotherNathan/STO_CombatLogAnalyzer/blob/89e9ac5af52a91e3533b2bc252a656f772c73daa/src/analyzer/heal.rs)
- **C-GROUP** — [hierarchy and parent-relative aggregation](https://github.com/AnotherNathan/STO_CombatLogAnalyzer/blob/89e9ac5af52a91e3533b2bc252a656f772c73daa/src/analyzer/groups.rs)
- **C-RULE** — [rule matching semantics](https://github.com/AnotherNathan/STO_CombatLogAnalyzer/blob/89e9ac5af52a91e3533b2bc252a656f772c73daa/src/analyzer/settings.rs)
- **C-DTABLE** — [Damage table labels and tooltips](https://github.com/AnotherNathan/STO_CombatLogAnalyzer/blob/89e9ac5af52a91e3533b2bc252a656f772c73daa/src/app/main_tabs/tables/damage_table.rs)
- **C-HTABLE** — [Healing table labels and tooltips](https://github.com/AnotherNathan/STO_CombatLogAnalyzer/blob/89e9ac5af52a91e3533b2bc252a656f772c73daa/src/app/main_tabs/tables/heal_table.rs)
- **C-GRAPH** — [Gaussian line algorithm](https://github.com/AnotherNathan/STO_CombatLogAnalyzer/blob/89e9ac5af52a91e3533b2bc252a656f772c73daa/src/app/main_tabs/diagrams/value_per_second_graph.rs)
- **C-SERIES** — [graph data and time slicing](https://github.com/AnotherNathan/STO_CombatLogAnalyzer/blob/89e9ac5af52a91e3533b2bc252a656f772c73daa/src/app/main_tabs/diagrams/common.rs)
- **C-BARS** — [time-slice bar charts](https://github.com/AnotherNathan/STO_CombatLogAnalyzer/blob/89e9ac5af52a91e3533b2bc252a656f772c73daa/src/app/main_tabs/diagrams/values_chart.rs)
- **C-SUMMARY** — [summary calculations and table behavior](https://github.com/AnotherNathan/STO_CombatLogAnalyzer/blob/89e9ac5af52a91e3533b2bc252a656f772c73daa/src/app/main_tabs/tables/summary_table.rs)
- **C-COPY** — [summary copy behavior](https://github.com/AnotherNathan/STO_CombatLogAnalyzer/blob/89e9ac5af52a91e3533b2bc252a656f772c73daa/src/app/summary_copy.rs)
- **C-FORMAT** — [numeric formatter](https://github.com/AnotherNathan/STO_CombatLogAnalyzer/blob/89e9ac5af52a91e3533b2bc252a656f772c73daa/src/helpers/number_formatting.rs)

The upstream input is pinned to
[STO-OSCR v11.0.0](https://pypi.org/project/STO-OSCR/11.0.0/),
commit `7262b8c904659224f685b9d6799d0105b339752c`. Relevant modules are `OSCR/datamodels.py`,
`OSCR/main.py`, `OSCR/parser.py`, `OSCR/combat.py`, and `OSCR/constants.py`. RE-OSCR's current
immutable handoff is [`CombatEventIndex`](../re_oscr/workbench.py).

## Obligation and progress vocabulary

Compatibility obligation and implementation progress are separate axes:

| Obligation | Meaning |
|---|---|
| `EXACT` | The `cla-v1.4.0` profile must reproduce the pinned source behavior. |
| `BOUNDARY DIFFERENCE` | Protected OSCR parser authority deliberately determines the input or identity instead. |
| `BLOCKED` | OSCR does not retain the required input and the parser boundary forbids reconstructing it. |
| `SOURCE-UNDEFINED` | The pinned source does not define one stable outcome, such as equal-key unstable ordering. |

| Progress | Meaning |
|---|---|
| `AUDITED` | Behavior is identified in pinned source, but no RE implementation claim is made. |
| `DERIVABLE` | The selected OSCR event snapshot contains the inputs needed for an original implementation. |
| `PARTIAL` | Dev12 has a related feature, but its semantics or formula are not compatible yet. |
| `IMPLEMENTED` | Behavior exists with the intended semantics, but lacks golden proof. |
| `VERIFIED` | Named golden fixtures pass the declared comparator. |

`RE EXTENSION` is a separate disposition, not a compatibility obligation: labelled RE-OSCR
behavior composes outside the CLA calculation profile and is recorded in transform provenance.

No metric in this document is `VERIFIED` yet. `PARTIAL` describes progress only; it never weakens
an `EXACT` obligation.

## Compatibility definition and divergence policy

The pinned CLA source is the definition oracle. UI observations, screenshots, copied tables, and
exports are evidence for the golden harness, not substitutes for reading the formula and control
flow that produced them. A later local CLA checkout may be used to detect upstream change, but it
must not silently move this profile away from the pinned v1.4.0 commit.

The calculation profile ID is `cla-v1.4.0`. Under that label:

1. Behavior is reproduced bug-for-bug wherever the pinned released source is deterministic,
   including unintuitive clocks, denominator choices, and known graph-bucket quirks.
2. A cleaner formula or repaired bug belongs to RE-OSCR's native presentation or a separately
   named and versioned profile. It must never be smuggled into `cla-v1.4.0` as "close enough."
3. OSCR's selected event set remains the hard input ceiling. Differences caused before the
   snapshot are recorded as provenance and intentional parser-boundary differences, not hidden by
   adjusting the calculation.
4. A source-undefined outcome must state the equivalence class that can be verified. It cannot use
   a broad tolerance to hide a deterministic disagreement.
5. Any semantic change to a released compatibility profile creates a new profile version. Existing
   verified results remain attributable to the exact profile that produced them.

## Authority and event-set ceiling

| Area | Decision | Obligation |
|---|---|---|
| Selected combat and event order | OSCR owns the combat; calculations consume the exact effective sequence snapshotted by `CombatEventIndex`, including source ordinals. | `BOUNDARY DIFFERENCE` |
| Combat separation | RE-OSCR's default is 45 seconds and remains user-configurable through OSCR; CLA defaults to 90 seconds. No second separator is introduced. | `BOUNDARY DIFFERENCE` |
| Minimum combat size | OSCR's 20-line default remains authoritative; CLA has no equivalent minimum. | `BOUNDARY DIFFERENCE` |
| Hive terminal | OSCR's Queen-kill cutoff remains authoritative. Post-terminal records are outside the official OSCR effective event set and are deliberately unavailable to compatible calculations. | `BOUNDARY DIFFERENCE` |
| Broken/quoted records | OSCR's repair, skip, and normalization behavior remains authoritative. | `BOUNDARY DIFFERENCE` |
| `Electrical Overload` | OSCR drops this banned event before adding it to `Combat.log_data`; downstream parity is impossible without reading the raw log again. | `BLOCKED` |
| League source | League accepts only the parser-owned current combat and continues to upload its official byte range. A transient weak `Combat` reference may support UI coordination outside immutable results, but persisted provenance contains only `snapshot_id` and frozen non-coordinate metadata. | `BOUNDARY DIFFERENCE` |

These limits must be visible in future result provenance. A compatible result must never be labelled
as an identical CLA parse.

## Immutable input map

`CombatEventIndex` copies OSCR's effective event stream into a read-only column snapshot. It retains
the source `Combat` only through a weak reference for current provenance and UI coordination. The
future compatibility engine contract is stricter: it receives only the event snapshot and an
explicit calculation profile, and it must not consume `source_combat`, a log path, or `file_pos`.
The mapping to CLA terminology is complete for ordinary calculations:

| CLA concept | OSCR snapshot field | Availability / note |
|---|---|---|
| Timestamp | `timestamps`, `elapsed_seconds` | Exact parsed timestamp and offset within the OSCR combat. |
| Direct source / owner entity | `owner_names`, `owner_ids` | OSCR calls CLA's direct source the owner; it is a player for Damage Out attribution but can also be an NPC. |
| Indirect source / pet / anomaly | `source_names`, `source_ids` | OSCR calls CLA's indirect source the source. |
| Target | `target_names`, `target_ids` | Display name and parser identity retained. |
| Damage or heal name | `event_names`, `event_ids` | Both visible label and internal ID retained. |
| Value type | `event_types` | Includes `Shield`, `HitPoints`, damage types, and blank miss types. |
| Flags | `flags` | Critical, Flank, Kill, Immune, ShieldBreak, and Miss can be tokenized. |
| Actual amount | `magnitudes` | Sign and raw floating value retained. |
| Base/prevented amount | `magnitudes2` | Sign and raw floating value retained. |
| Event ordinal | `source_ordinals` | Same-time duplicate records have no upstream event UID; ordinal is required. A stable snapshot identity/hash does not exist yet and must be added by the later coprocessor contract. |

CLA entity kind, missing-entity state, and unique-name matching are recoverable from the retained
raw ID strings, but are not yet exposed as dedicated snapshot arrays. The coprocessor input adapter
must extract and freeze those values instead of consulting the source `Combat`.

The completed OSCR trees are not sufficient for compatibility math by themselves. They already
apply OSCR-specific duration, base-damage, immune, drain, critical, accuracy, and aggregation
rules. CLA-compatible calculations therefore derive directly from the immutable event snapshot,
without parsing log text and without writing back to OSCR.

## Snapshot identity and result provenance contract

Dev12 does not yet implement a stable snapshot identity. Before coprocessor results can ship, the
adapter must freeze the official start/end, nullable map/difficulty, runtime parser version, and
events at `CombatEventIndex` construction. Hashing must never dereference `source_combat` later.

The snapshot payload has this fixed semantic shape:

```json
{
  "domain": "re-oscr.snapshot.v1",
  "input_contract": "oscr-effective-logline.v1",
  "parser_distribution": "STO-OSCR",
  "parser_version": "11.0.0",
  "combat": {"start": "...", "end": "...", "map": null, "difficulty": null},
  "event_count": 0,
  "events": []
}
```

`map` and `difficulty` keys are always present and use `null` when absent. Each event is a fixed-order
array of `[source_ordinal, timestamp, owner_name, owner_id, source_name, source_id, target_name,
target_id, event_name, event_id, type, flags, magnitude_bits, magnitude2_bits]`. Events remain in
parser order.

Before hashing, floating fields become exactly 16 lowercase hexadecimal digits containing their
big-endian IEEE-754 binary64 bits. Timestamps use fixed `YYYY-MM-DDTHH:MM:SS.ffffff` strings. The
`cla-v1.4.0` input contract requires whole-millisecond timestamps and rejects synthetic
sub-millisecond values rather than silently truncating them; production OSCR timestamps satisfy
this constraint. `NaN` and infinity are also rejected. `ERROR_CONTAINMENT` fixtures prove the snapshot
validation category and phase. The resulting JSON is canonicalized with RFC 8785 and hashed as
`snapshot_id = "sha256:" + 64 lowercase hexadecimal SHA-256 digits`.

Parser `Combat.id`, object identity, weak references, derived arrays, log paths, and byte offsets are
not content identity. Runtime parser version comes from `from OSCR import OSCR; OSCR.__version__`.
Installed `STO-OSCR` distribution metadata may cross-check it when present but cannot be assumed in
a packaged executable; a present-but-different value is a provenance error. An upstream parser
change therefore cannot masquerade as a coprocessor regression.

Immutable provenance retains the canonical transform descriptor as well as its digest. It includes
transform schema, ordered full rule definitions and enabled states, filters/queries, time bounds,
and selected source ordinals. The canonical empty descriptor is:

```json
{
  "domain": "re-oscr.transform.v1",
  "ordered_rules": [],
  "filters": [],
  "time": {"start_seconds": null, "end_seconds": null},
  "selected_ordinals": "all"
}
```

It is retained, RFC 8785-canonicalized, and hashed as
`transform_digest = "sha256:" + 64 lowercase hexadecimal SHA-256 digits`. The result identity hashes
this explicit RFC 8785 payload:

```json
{
  "domain": "re-oscr.result.v1",
  "snapshot_id": "sha256:...",
  "engine_id": "re-oscr.cla-coprocessor",
  "engine_version": "1",
  "profile_id": "cla-v1.4.0",
  "transform_digest": "sha256:..."
}
```

`result_id` uses the same `sha256:` plus 64-lowercase-hexadecimal representation.

CLA-compatible calculations use engine ID `re-oscr.cla-coprocessor`; native OSCR results use
`re-oscr.oscr-native`. Result provenance also records the canonical transform descriptor, every
declared boundary difference, the injected RE-OSCR product version, and an optional nullable build
revision. Product version comes from `RetroEscalationLauncher.__version__` at the adapter boundary;
the pure engine must not import the Qt launcher/application. Installed RE-OSCR metadata is packaging
evidence only and may be absent or stale. Product/build provenance does not alter an otherwise
identical calculation identity, and none of these fields grants League upload authority.

## Parity gate 1: duration and rate clocks

Clock semantics are resolved before any damage, healing, or graph metric. The compatibility engine
does not run CLA's 90-second separator or compress quiet gaps; OSCR has already selected the one
official combat snapshot. Within that fixed event set, the CLA clocks are:

| ID | Clock | CLA v1.4.0 behavior on the selected OSCR event set | Obligation / progress |
|---|---|---|---|
| `TIME-01` | Global **Combat Duration** | CLA's global summary clock, not a table-rate divisor. Normally first-to-last not-CLA-all-zero, non-immune damage whose `record.source` is a Player (`owner_*` in the snapshot). Direct self-damage counts and player exclusions do not affect it. `Combat::new` has a released first-record quirk: if the first record is Player-source damage, it seeds the clock before checking Immune or all-zero; later updates do check. | `EXACT` / `DERIVABLE`; OSCR encounter extent is a `BOUNDARY DIFFERENCE`. |
| `TIME-02` | Global Active Duration | First to last successfully parsed valid record. In native CLA it drives separation and the Active Duration display, but no table rate. Over the fixed snapshot it is the first-to-last effective OSCR event. | `EXACT` / `DERIVABLE`; independently discovered CLA extent is a `BOUNDARY DIFFERENCE`. |
| `TIME-03` | Player Damage Out divisor | First-to-last not-CLA-all-zero, non-immune, non-self outgoing damage remaining after that player's exclusion rules. Intervening quiet gaps remain in the duration. | `EXACT` / `DERIVABLE`. |
| `TIME-04` | Player Active divisor | First-to-last outgoing record after exclusion, including heals and self/immune/all-zero records, or incoming damage including immune/all-zero damage. Incoming healing alone does not establish or extend it. | `EXACT` / `DERIVABLE`. |
| `TIME-05` | Rate-to-clock map | Every nested Damage Out row shares its player `TIME-03`; Damage In, Heal Out, and Heal In share that player's `TIME-04`. No child row invents a shorter clock. | `EXACT` / `DERIVABLE`. |
| `TIME-06` | Missing and zero ranges | Either missing optional player range becomes Chrono 0.4.44's `Duration::MAX` (`i64::MAX` milliseconds) for metric calculation, while its summary display is zero. Incoming-heal-only HPS therefore approaches zero. A one-point range is zero and then uses the one-second rate floor. A missing global `TIME-01` displays as zero. | `EXACT` / `DERIVABLE`; golden edge fixtures required. |
| `TIME-07` | Separation and gaps | Native CLA truncates its configured separation seconds to an integer and starts a new combat only when the gap after the previous valid record is strictly greater than the threshold; equality stays in one combat, invalid records do not refresh the endpoint, and no clock subtracts idle gaps. The compatibility engine does not rerun this separator. | Source behavior `EXACT` / `AUDITED`; selected OSCR boundary is a `BOUNDARY DIFFERENCE`. |
| `TIME-08` | Graph-series extent | Gaussian rate lines use the selected series' own first-to-last event timestamps and minimum one-second span, not `TIME-01`, `TIME-03`, or `TIME-04`. | `EXACT` / `DERIVABLE`. |
| `TIME-09` | Processing order | CLA overwrites each range's end in record-processing order; it does not sort or take timestamp minima/maxima, and signed millisecond offsets are cast to `u32`. A malformed backwards player range panics when converted for metrics. RE-OSCR must detect that same invalid range and return no numeric result. | Range construction and failure condition `EXACT` / `DERIVABLE`; typed containment disposition `RE EXTENSION`. |

Every scalar rate divides by `max(selected_clock, 1 second)`. A one-timestamp range therefore has
duration zero but uses a one-second divisor. The harness must prove every clock independently before
any dependent rate can become `VERIFIED`.

## CLA damage classification

Classification happens before absolute values are accumulated:

1. Negative `HitPoints` is a hull heal.
2. `Shield` with `magnitude2 == 0` and no `ShieldBreak` is a shield heal when magnitude is negative,
   or shield drain when magnitude is positive.
3. Other `Shield` records are shield damage; `magnitude2` is damage prevented from reaching hull.
4. Other records are hull damage. When `magnitude2 == 0`, CLA substitutes magnitude as base damage.
5. Direct self-damage is excluded from Damage Out and is still eligible for Damage In attribution.
6. Damage Out exclusion rules are applied before outgoing damage/heal classification and before
   the player's active/combat clocks are updated.

This differs from OSCR 11.0.0 in several places, so existing OSCR tree columns cannot simply be
renamed as CLA-compatible columns.

## Damage metric ledger

For the formulas below:

- `Dh`, `Ds`, `D` are hull, shield, and total damage (`D = Dh + Ds`).
- `B` is total hull base damage.
- `R` is shield-drain damage, included in `Ds` but excluded from resistance comparison.
- `Nh`, `Ns`, `N` are hull, shield, and total record counts (`N = Nh + Ns`).
- `C`, `F`, `M` are non-immune critical, flank, and miss flag counts.
- `Tdo` is the player's `TIME-03` Damage Out duration; every descendant row uses that same clock.
- `rate(x, t) = x / max(t, 1 second)`.
- Percentage and average values are blank when their denominator is zero.
- All/shield/hull variants shown in CLA cells are one metric family, not three unrelated formulas.

Every formula and source-defined edge in this table is an `EXACT` obligation. The final column
describes implementation progress and the nearest dev12 behavior; it does not grant latitude.

| ID | CLA label | Compatibility rule | OSCR availability | Dev12 / progress |
|---|---|---|---|---|
| `DO-01` | DPS | `rate(D, Tdo)`; shield/hull variants divide by the same clock. | Event amounts + timestamps. | OSCR DPS exists, clock differs: `DERIVABLE`. |
| `DO-02` | Total Damage | `D = Dh + Ds`; drain remains shield damage; immune damage contributes zero. | Directly derivable. | Related OSCR total exists: `DERIVABLE`. |
| `DO-03` | Damage % | Row damage divided by immediate parent damage; player root uses team total. | Hierarchy + totals. | No matching tree share: `DERIVABLE`. |
| `DO-04` | Resistance % | `100 × (1 - (D - R) / B)`; blank when `B == 0`. | Both magnitudes + drain classification. | OSCR Debuff is not this metric: `DERIVABLE`. |
| `DO-05` | Max One-Hit | Largest absolute stored shield or hull hit with CLA hierarchy-selected tooltip provenance, often the effect name but not necessarily the raw direct source; CLA replaces it only for a strictly larger value. RE may additionally retain the source ordinal. | Per-event amounts, hierarchy names, and ordinal. | Value exists, provenance differs: `DERIVABLE`. |
| `DO-06` | Average Hit | `D/N`; shield and hull use their corresponding totals/counts. | Totals + record counts. | Not exposed with CLA denominator: `DERIVABLE`. |
| `DO-07` | Critical % | `100 × C/Nh`. | Flags + hull classification. | OSCR removes misses from its denominator: `DERIVABLE`. |
| `DO-08` | Flanking % | `100 × F/Nh`. | Flags + hull classification. | OSCR removes misses from its denominator: `DERIVABLE`. |
| `DO-09` | Hits | Every damage record; a normal shield+hull attack counts twice. Immune records still count. | Exact record count. | Related OSCR Attacks exists: `DERIVABLE`. |
| `DO-10` | Hits / s | `rate(N, Tdo)`. | Counts + clock. | No dev12 equivalent using the CLA clock: `DERIVABLE`. |
| `DO-11` | Hits % | Row hit count divided by immediate parent hit count. | Hierarchy + counts. | Not exposed: `DERIVABLE`. |
| `DO-12` | Misses | Non-immune records carrying `Miss`. | Flags + immune classification. | Related OSCR count differs at edges: `DERIVABLE`. |
| `DO-13` | Accuracy % | `100 × (1 - M/Nh)`. | Hull hits + misses. | OSCR uses successful/hull with different edge handling: `DERIVABLE`. |
| `DO-14` | Kills | Added Damage Out records carrying `Kill`, detailed by killed target. | Flags + target identity. | Related OSCR total exists: `DERIVABLE`. |
| `DO-15` | Damage Types | Distinct raw types; blank ignored; `Shield` suppressed when another substantive type exists. | Raw `type`. | Not presented with CLA union rule: `DERIVABLE`. |
| `DO-16` | Base DPS | `rate(B, Tdo)`. | Hull `magnitude2`, with CLA zero fallback. | OSCR fallback/clock differ: `DERIVABLE`. |
| `DO-17` | Base Damage | Sum of CLA-classified hull base damage; shield drain excluded. | Both magnitudes + type/flags. | Existing OSCR base differs: `DERIVABLE`. |
| `DO-18` | Total Crit Damage | Critical hull damage only. | Per-event flags and hull damage. | Not exposed: `DERIVABLE`. |
| `DO-19` | Total Non-Crit Hull Damage | Noncritical hull damage only. | Per-event flags and hull damage. | Not exposed: `DERIVABLE`. |
| `DO-20` | Average Crit Hit | Total critical hull damage divided by `C`. | `DO-18` + count. | Not exposed: `DERIVABLE`. |
| `DO-21` | Average Non-Crit Hull Hit | Noncritical hull damage divided by `(Nh - C)`. The official optimized release wraps the unsigned subtraction modulo `2^64` when malformed flags make `C > Nh`. | `DO-19` + counts. | Released behavior `DERIVABLE`; malformed fixture required. |

Damage In uses the same 21 metric formulas and hierarchy machinery. Its rates use the player's CLA
active duration rather than a separate incoming-damage duration. This is derivable, but no Damage
In row is considered verified until separate golden fixtures cover attribution and clocks.

### Damage edge behavior to freeze

- Hit counts increment before the Immune check. Immune records contribute no damage, base damage,
  crit, flank, or miss. They remain in hit counts, Average Hit denominators, Hits % denominators,
  and the hull-hit denominators used by Critical %, Flanking %, and Accuracy; they contribute zero
  to Damage % totals and Resistance inputs.
- Max One-Hit is updated from the stored hit list before immune damage is removed from totals.
- CLA-all-zero records count as hits but do not extend the Damage Out clock. By classification,
  `CLA-all-zero` means hull actual and base are both zero, shield actual and prevented are both
  zero, or drain actual is zero. Actual zero with a nonzero base/prevented value is therefore not
  all-zero and can extend the clock.
- Kill detail is recorded when an event is added, including unusual zero/immune Kill records.
- CLA counts Critical/Flank/Miss flags on any non-immune damage record but divides the percentages
  by hull hits. Normal logs place these flags on hull records. If malformed flags make `C > Nh`,
  `cla-v1.4.0` reproduces the official optimized release's wrapping unsigned subtraction; a debug
  build's overflow panic is not the released compatibility target.
- A one-timestamp range has duration zero, but every rate uses the one-second floor.

## Healing metric ledger

CLA uses the same hierarchy engine for Healing Out and Healing In. Let `H`, `Hh`, `Hs` be total,
hull, and shield healing; `Q`, `Qh`, `Qs` the tick counts; `HC` critical tick count; and `Ta` the
player active duration.

Every source-defined healing formula is an `EXACT` obligation; all eight are currently
`DERIVABLE` from the snapshot.

| ID | CLA label | Compatibility rule | Progress |
|---|---|---|---|
| `HEAL-01` | HPS | `rate(H, Ta)` with shield/hull variants. | `DERIVABLE` |
| `HEAL-02` | Total Heal | `H = Hh + Hs`. | `DERIVABLE` |
| `HEAL-03` | Heal % | Row heal divided by immediate parent heal; player root uses team total. | `DERIVABLE` |
| `HEAL-04` | Average Heal | `H/Q`; shield/hull variants use corresponding totals/counts. | `DERIVABLE` |
| `HEAL-05` | Critical % | `100 × HC/Qh`. | `DERIVABLE` |
| `HEAL-06` | Ticks | Every classified heal record, split all/shield/hull. | `DERIVABLE` |
| `HEAL-07` | Ticks / s | `rate(Q, Ta)` with shield/hull variants. | `DERIVABLE` |
| `HEAL-08` | Ticks % | Row ticks divided by immediate parent ticks. | `DERIVABLE` |

Incoming healing alone does not establish the CLA player active clock. This unintuitive behavior is
an exact compatibility obligation; a golden comparison verifies it rather than deciding it.
`HealMetrics` does not filter Immune flags: an immune-flagged classified heal contributes amount,
tick, critical count, and graph data. `HC` counts critical shield and hull ticks while `HEAL-05`
divides by hull ticks `Qh`, so malformed shield-critical records can produce more than 100%.

## Summary ledger

Every source-defined summary calculation is an `EXACT` obligation.

| ID | CLA summary behavior | Obligation / progress |
|---|---|---|
| `SUM-01` | Outgoing DPS from the Damage Out metric family. | `EXACT` / `DERIVABLE`. |
| `SUM-02` | Total outgoing damage and team-relative outgoing share. | `EXACT` / `DERIVABLE`. |
| `SUM-03` | Total incoming damage and team-relative incoming share. | `EXACT` / `DERIVABLE`. |
| `SUM-04` | Player combat duration and its share of CLA combat duration. | Formula `EXACT` / `DERIVABLE`; encounter extent is a `BOUNDARY DIFFERENCE`. |
| `SUM-05` | Player active duration. | `EXACT` / `DERIVABLE`. |
| `SUM-06` | Deaths from incoming Kill records. | `EXACT` / `DERIVABLE`. |
| `SUM-07` | Kills, split into player and NPC targets. | `EXACT` / `DERIVABLE`. |
| `SUM-08` | Team outgoing/incoming totals and total kills/deaths. | `EXACT` / `DERIVABLE` on the OSCR event set. |
| `SUM-09` | CLA-formatted combat identity depends on the pinned CLA combat-name rule profile. OSCR remains authoritative for official map and difficulty identity. | CLA label `EXACT` / `DERIVABLE` with the pinned rule profile; official identity is a `BOUNDARY DIFFERENCE`. |
| `SUM-10` | Summary charts for DPS, outgoing damage, and incoming damage. | `EXACT` / `PARTIAL`; dev12 has related charts. |
| `SUM-11` | Summary-copy field and selected-aspect ordering, sorting, headers, separators, handle extraction, duration, blank-selection behavior, and suffix formatting. Damage Resistance Out/In can be included. | `EXACT` / `DERIVABLE`; copy parity not started. |

## Hierarchy and rule ledger

Default CLA shapes:

| Domain | Direct event | Indirect event |
|---|---|---|
| Damage Out | Player → Effect → Target | Player → Indirect Source → Effect → Target |
| Damage In | Player → Attacker → Effect | Player → Attacker → Indirect Source → Effect |
| Heal Out | Player → Target → Effect | Player → Target → Indirect Source → Effect |
| Heal In | Player → Source → Effect | Player → Source → Indirect Source → Effect |

The first seven rule rows are `EXACT` obligations. `PARTIAL` records only the state of dev12.

| ID | CLA behavior | Dev12 comparison | Obligation / progress |
|---|---|---|---|
| `RULE-01` | Reversal swaps `Indirect Source → Effect` to `Effect → Indirect Source`. | RE has display-only REVERSE. | `EXACT` / `PARTIAL` — equality unproved. |
| `RULE-02` | A custom group adds a named parent; first matching enabled group wins. | RE has ordered GROUP with first-match behavior. | `EXACT` / `PARTIAL` — hierarchy golden needed. |
| `RULE-03` | Damage Out exclusion matches any enabled rule inside `Player.add_out_value`, before outgoing damage/heal dispatch and that player's clocks; target-side incoming remains, and a matching outgoing heal is also suppressed. | RE removes the event from the shared derived deque before OSCR reanalysis, affecting all four modes. Its surviving outer window is global, after which OSCR recomputes actor clocks. | `EXACT` / `PARTIAL` — material semantic difference; the global Workbench mask cannot implement CLA exclusion parity. |
| `RULE-04` | Aspects: source/target name or unique name, indirect name or unique name, effect name. | RE currently matches event or source. | `EXACT` / `PARTIAL`. |
| `RULE-05` | Methods: Equals, Starts With, Ends With, Contains; case-sensitive. | RE uses case-folded exact/literal-star patterns. | `EXACT` / `PARTIAL`. |
| `RULE-06` | Rules inside a named custom group are OR; custom groups are ordered. Reversal/exclusion use any match. | RE supports ordered rule sets but has a different JSON dialect. | `EXACT` / `PARTIAL`. |
| `RULE-07` | Damage Out expands one additional target level. | RE exposes target drill-down through OSCR trees. | `EXACT` / `PARTIAL` — exact shape unproved. |
| `RULE-08` | CLA's bundled reversal/group/exclusion examples start disabled. | RE definitions/imports default off; explicit local auto-enable is an RE feature. | Default-off `EXACT` / `IMPLEMENTED`; auto-enable is an RE extension. |
| `RULE-09` | Typed filters and inclusive time cuts are not CLA v1.4 rule features. | RE intentionally adds both as labelled display transforms outside the calculation profile. | Obligation `N/A` / `IMPLEMENTED`; disposition `RE EXTENSION`, transform provenance required. |

Rule transforms must not silently alter parser truth or League inputs, regardless of future profile.

## Graph and selection ledger

Source-defined graph data, binning, and selection behavior are `EXACT` obligations. RE-OSCR may
retain its own visual styling.

| ID | CLA behavior | Dev12 comparison | Obligation / progress |
|---|---|---|---|
| `GRAPH-01` | Damage diagrams: DPS, Damage, Damage Resistance, Hits/s, Hits Count. | RE has weighted lines and detailed bars, but not the complete set. | `EXACT` / `PARTIAL`. |
| `GRAPH-02` | Healing diagrams: HPS, Heal, Heal Ticks/s, Heal Ticks Count. | RE has related event curves. | `EXACT` / `PARTIAL`. |
| `GRAPH-03` | DPS, Hits/s, HPS, and Heal Ticks/s are Gaussian-convolved event impulses, not cumulative averages. Default sigma `0.4 s`. | Current weighting is not proven equal. | `EXACT` / `DERIVABLE`. |
| `GRAPH-04` | CLA v1.4 creates `round(max(duration, 1 s) * 10)` points, minimum 10, distributed over inclusive first-to-last or minimum-span endpoints. Same-time values merge for graphing. | Snapshot retains exact timestamps. | `EXACT` / `DERIVABLE`. |
| `GRAPH-05` | Weight is `(GaussianPDF - 0.001) × 1.001`; scanning stops once weight is nonpositive. | Formula not implemented. | `EXACT` / `DERIVABLE`. |
| `GRAPH-06` | Damage/Heal/Hits/Ticks bars use half-open time slices; default one second; zero bins omitted. | Detailed bars exist with different binning. | `EXACT` / `PARTIAL`. |
| `GRAPH-07` | Damage Resistance bars apply `DO-04` within each time slice and omit slices with no base damage. | Not implemented. | `EXACT` / `DERIVABLE`. |
| `GRAPH-08` | No selection shows players; selecting a group plots immediate children; Ctrl-selection compares arbitrary individual rows. | RE plots selections but exact group/Ctrl behavior is unproved. | `EXACT` / `PARTIAL`. |
| `GRAPH-09` | CLA v1.4 computes `first_time_slice = round(start_s * 1000) / slice_ms` with integer division, then `end = first_time_slice + slice_ms`; the missing multiply can emit leading empty slices and shift centers for late-starting series. | `cla-v1.4.0` reproduces the quirk; corrected bins belong only to another profile. | `EXACT` / `DERIVABLE`. |

The v1.4 released line width is 2.0. That is a presentation reference, not a calculation contract;
RE-OSCR retains its own design system unless a tester comparison shows a readability regression.

## Formatting and copy obligations

Visual skin and layout remain RE-OSCR's. Values used to claim compatibility—including blank states,
displayed numeric strings, tooltips, and copied output—are source-defined `EXACT` obligations.
Post-v1.4 master formatting options are not part of the `cla-v1.4.0` profile.

| ID | Pinned v1.4.0 behavior | Obligation / progress |
|---|---|---|
| `FMT-01` | Damage totals, DPS, averages, max/base values, critical totals, and critical averages use 2 decimals. Percentages, resistance, Hits/s, Hits %, and Accuracy use 3. Counts are integers. | `EXACT` / `DERIVABLE`. |
| `FMT-02` | Healing totals, HPS, and averages use 2 decimals. Percentages, Ticks/s, and Ticks % use 3. Counts are integers. Optional values with no denominator are blank, not zero. | `EXACT` / `DERIVABLE`. |
| `FMT-03` | Summary damage and DPS use 2 decimals; shares use 3; durations use exact `MM:SS.mmm` or `HH:MM:SS.mmm` forms. CLA formats through `NaiveTime`, so the hour field wraps modulo 24. | `EXACT` / `DERIVABLE`. |
| `FMT-04` | v1.4 diagram tooltip x/y values use 2 decimals and axes use 0. | `EXACT` / `DERIVABLE`. |
| `FMT-05` | Summary copy has source-defined field/aspect order, first-aspect sort, headers, separators, 1-decimal percentages, duration text, handle extraction, blank-selection behavior, and automated suffixes. | `EXACT` / `DERIVABLE`. |
| `FMT-06` | CLA's formatter uses apostrophe thousands separators, Rust half-away-from-zero rounding at precision 0, separate fractional formatting at nonzero precision, sign reapplication, fixed suffix thresholds/precision, `<too large>`, and its released carry/negative-zero quirks. | `EXACT` / `DERIVABLE`. |

## Golden comparator contract

A row becomes `VERIFIED` only through a named raw-result comparator. Rounded UI text is never the
numerical oracle, and a tolerance cannot excuse a different clock, formula, event set, aggregation
order, or graph topology.

| Comparator | Metrics | Required comparison |
|---|---|---|
| `EXACT_STRUCTURE` | Event membership/order, source ordinals, attribution, hierarchy paths/order, labels, flags, damage-type sets, blank values, rule matches, and max-hit provenance | Exact equality. |
| `EXACT_COUNT` | Hits, shield/hull hits, misses, criticals, flanks, kills, deaths, heal ticks, and distinct-item counts | Exact integer equality. |
| `EXACT_TIME_MS` | Clock endpoints/durations, event offsets, and bar bucket boundaries | Exact integer milliseconds before float conversion. |
| `EXACT_AMOUNT` | Hull, shield, base, drain, critical, noncritical, healing, max-hit, row, player, and team totals | Exact IEEE-754 bit equality; `+0.0` and `-0.0` are distinct when the pinned source exposes the sign. Synthetic proof fixtures use exactly representable magnitudes and fixed event order. |
| `FP_BASIC` | DPS, HPS, Base DPS, Hits/s, Ticks/s, averages, shares, resistance, accuracy, critical %, flank %, and tiny `TIME-06` rates | Signed zero requires exact IEEE-754 bits. Otherwise require the expected sign and `abs(actual - expected) <= max(8 * ulp(actual), 8 * ulp(expected))`. This is cross-runtime allowance, not permission for a different algorithm. |
| `GRAPH_POINT` | Gaussian and sampled lines | Series identity, length, topology, cutoff, and zero/nonzero state are exact. Sampled x is within 8 ULP; nonzero y error is at most `max(64 ULP, 1e-12 * max(1, abs(expected)))`. |
| `STRING_EXACT` | Final cells, blanks, durations, suffixes, separators, signs, tooltips, and summary-copy output | Byte-for-byte UTF-8 equality after the raw metric passes its comparator. |
| `ERROR_CONTAINMENT` | Snapshot validation and contained upstream failure paths such as `TIME-09` | Exact RE-OSCR error category and phase, no numeric fallback, and no process crash. Source condition detection remains an `EXACT` obligation; safe containment has disposition `RE EXTENSION`. |
| `SOURCE_UNDEFINED_SET` | Only outcomes the source genuinely leaves unstable, such as equal-key unstable sort order | Exact equivalence-class or multiset equality with the undefined dimension recorded. |

Every verified row records the fixture, raw expected value, comparator ID, calculation profile,
engine version, and oracle source. Expected values come from independently hand-calculated fixtures
or raw CLA instrumentation; rounded CLA cells are presentation evidence only. Arbitrary-decimal
real logs remain regression evidence unless raw values and aggregation order satisfy the declared
comparator. They do not replace the exact synthetic fixtures.

## Golden fixture queue

No golden fixture is complete yet. The first harness should cover these in order:

1. Normal global Combat Duration plus first-record Immune, all-zero, direct-self, and source-side
   excluded seed cases.
2. Staggered players proving global duration, player Damage Out, player Active, and descendant
   rate-clock selection independently.
3. Incoming-heal-only, incoming heal before later activation, all-immune/all-zero Damage Out, and
   missing-player-range sentinel behavior.
4. Exactly-at-threshold versus threshold-plus-one-millisecond gaps, invalid-record separation,
   wall-clock gap retention, and the fixed OSCR event-set boundary.
5. Out-of-order timestamps proving processing order, the exact invalid player-range condition, and
   the typed RE-OSCR containment path.
6. Single hull hit and the one-second divisor floor.
7. Normal shield+hull pair counting as two hits.
8. Positive shield drain.
9. Hull damage with `magnitude2 == 0` base fallback.
10. Critical, flank, miss, and kill flags, including release-mode `(Nh - C)` wrapping.
11. Immune and zero damage records, including every denominator behavior.
12. Direct self-damage attribution.
13. Indirect source, default hierarchy, and reversal.
14. Overlapping custom groups proving first-match ordering.
15. Exclusion proving source-side outgoing removal with target-side incoming and global-clock
    retention.
16. Damage In and both healing directions, including immune heals and shield-critical percentages
    above 100%.
17. Same-timestamp Gaussian merge, one-event line, cutoff topology, and all four rate series.
18. Exact bucket boundary plus a late-starting series reproducing the v1.4 origin defect.
19. Blank versus zero; every fixed precision around half-unit boundaries; fractional carry;
    negative zero; suffix thresholds; the one-hour transition; and the modulo-24-hour wrap.
20. Exact summary-copy selection, sort, header, separator, suffix, and blank-selection behavior.
21. Explicit parser-boundary cases: 45–90-second gap, `Electrical Overload`, short combat, Hive
    post-Queen data, and broken/quoted record normalization.

## Future profile state presentation

The Analysis profile switch controls real calculation state, so its indicator is an earned console
chip under the no-fake-readouts rule. It displays the active, versioned state—such as
`OSCR NATIVE` or `CLA COMPATIBLE v1.4`—and the same value is recorded in copy/export provenance.

Profile state and Workbench modification state are independent. If a filtered or ruled view uses
the CLA profile, both `CLA COMPATIBLE v1.4` and `MODIFIED VIEW` remain visible. Switching profiles
recalculates from the same immutable snapshot; it does not rerun or replace OSCR, mutate parser
truth, or create a League upload source.

## First implementation slice unlocked by this ledger

The first complete vertical slice is **Damage Out on the OSCR-selected event set**:

- all 21 Damage table metric families;
- CLA classification, player clock, parent-relative hierarchy, and empty-value behavior;
- direct/indirect/target attribution;
- rule ordering and the CLA exclusion edge;
- Damage Out graphs only after the table values pass the golden harness;
- explicit provenance stating that OSCR supplied the combat and events.

The first real-log proof milestone is Raman's tester fixture once its exact input, permission, raw
CLA oracle output, and hashes are archived. Acceptance is: **the same OSCR-selected combat, the same
`cla-v1.4.0` Damage Out raw results and strings, presented in RE-OSCR meter rows**. That fixture is
high-value regression and demonstration evidence; it supplements rather than replaces the exact
synthetic fixtures.

The engine contract, profile selector, result provenance model, and golden-harness implementation
are the next planned steps. They are intentionally not smuggled into this audit document as
already-shipped features.
