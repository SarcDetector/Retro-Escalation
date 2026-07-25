"""Pure CLA v1.4 calculations over a frozen OSCR event snapshot.

The coprocessor is deliberately independent of Qt and the live OSCR ``Combat`` object.  OSCR
remains authoritative for combat selection; this module supplies CLA-compatible summary, damage,
healing, and default hierarchy calculations without ever creating a League upload source.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import json
from math import isfinite
import re
import struct
from typing import Any


ENGINE_ID = "re-oscr.cla-coprocessor"
ENGINE_VERSION = "2"
PROFILE_ID = "cla-v1.4.0"
PREVIEW_METRIC_IDS = (
    "DO-01", "DO-02", "DO-04", "DO-06", "DO-09", "DO-10", "DO-16", "DO-17",
)
DAMAGE_METRIC_IDS = tuple(f"DO-{number:02d}" for number in range(1, 22))
HEAL_METRIC_IDS = tuple(f"HEAL-{number:02d}" for number in range(1, 9))
SUMMARY_METRIC_IDS = tuple(f"SUM-{number:02d}" for number in range(1, 9))
BOUNDARY_DIFFERENCES = (
    "OSCR_SELECTED_COMBAT",
    "OSCR_COMBAT_SEPARATION",
    "OSCR_MINIMUM_COMBAT_SIZE",
    "OSCR_HIVE_TERMINAL",
    "OSCR_RECORD_NORMALIZATION",
    "OSCR_ELECTRICAL_OVERLOAD_DROPPED",
    "OSCR_LEAGUE_SOURCE",
)
MISSING_DURATION_SECONDS = ((1 << 63) - 1) / 1000.0


def _empty_transform_descriptor() -> dict[str, Any]:
    """Return a detached canonical parser-truth transform descriptor."""
    return {
        "domain": "re-oscr.transform.v1",
        "ordered_rules": [],
        "filters": [],
        "time": {"start_seconds": None, "end_seconds": None},
        "selected_ordinals": "all",
    }


class ClaCoprocessorError(ValueError):
    """A contained snapshot or calculation failure with stable diagnostic fields."""

    def __init__(self, detail: str, *, category: str, phase: str):
        super().__init__(detail)
        self.category = category
        self.phase = phase


@dataclass(frozen=True, slots=True)
class ValueSet:
    """All/shield/hull values in CLA's fixed presentation order."""

    all: float
    shield: float
    hull: float

    def to_dict(self) -> dict[str, float]:
        return {"all": self.all, "shield": self.shield, "hull": self.hull}


@dataclass(frozen=True, slots=True)
class OptionalValueSet:
    all: float | None
    shield: float | None
    hull: float | None

    def to_dict(self) -> dict[str, float | None]:
        return {"all": self.all, "shield": self.shield, "hull": self.hull}


@dataclass(frozen=True, slots=True)
class CountSet:
    all: int
    shield: int
    hull: int

    def to_dict(self) -> dict[str, int]:
        return {"all": self.all, "shield": self.shield, "hull": self.hull}


@dataclass(frozen=True, slots=True)
class DamageOutPreviewRow:
    player: str
    damage_out_duration_ms: int | None
    active_duration_ms: int | None
    dps: ValueSet
    total_damage: ValueSet
    resistance_percentage: float | None
    average_hit: OptionalValueSet
    hits: CountSet
    hits_per_second: ValueSet
    base_dps: float
    base_damage: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "player": self.player,
            "damage_out_duration_ms": self.damage_out_duration_ms,
            "active_duration_ms": self.active_duration_ms,
            "metrics": {
                "DO-01_dps": self.dps.to_dict(),
                "DO-02_total_damage": self.total_damage.to_dict(),
                "DO-04_resistance_percentage": self.resistance_percentage,
                "DO-06_average_hit": self.average_hit.to_dict(),
                "DO-09_hits": self.hits.to_dict(),
                "DO-10_hits_per_second": self.hits_per_second.to_dict(),
                "DO-16_base_dps": self.base_dps,
                "DO-17_base_damage": self.base_damage,
            },
        }


@dataclass(frozen=True, slots=True)
class ResultProvenance:
    snapshot_id: str
    result_id: str
    transform_digest: str
    product_version: str
    parser_version: str
    combat_start: str
    combat_end: str
    map_name: str | None
    difficulty: str | None
    build_revision: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "result_id": self.result_id,
            "engine_id": ENGINE_ID,
            "engine_version": ENGINE_VERSION,
            "profile_id": PROFILE_ID,
            "transform_digest": self.transform_digest,
            "transform": _empty_transform_descriptor(),
            "product_version": self.product_version,
            "build_revision": self.build_revision,
            "input": {
                "parser_distribution": "STO-OSCR",
                "parser_version": self.parser_version,
                "combat": {
                    "start": self.combat_start,
                    "end": self.combat_end,
                    "map": self.map_name,
                    "difficulty": self.difficulty,
                },
            },
            "boundary_differences": list(BOUNDARY_DIFFERENCES),
            "league_eligible": False,
        }


@dataclass(frozen=True, slots=True)
class DamageOutPreviewResult:
    event_count: int
    combat_duration_ms: int | None
    active_duration_ms: int
    rows: tuple[DamageOutPreviewRow, ...]
    provenance: ResultProvenance

    @property
    def audit_status(self) -> str:
        return "SOURCE-AUDITED DAMAGE OUT // FIELD-VALIDATED"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "re-oscr.cla-damage-out-preview.v1",
            "status": self.audit_status,
            "metric_ids": list(PREVIEW_METRIC_IDS),
            "event_count": self.event_count,
            "combat_duration_ms": self.combat_duration_ms,
            "active_duration_ms": self.active_duration_ms,
            "rows": [row.to_dict() for row in self.rows],
            "provenance": self.provenance.to_dict(),
        }

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, allow_nan=False, indent=indent)


@dataclass(frozen=True, slots=True)
class MaxOneHit:
    damage: float
    name: str
    source_ordinal: int | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "damage": self.damage,
            "name": self.name,
            "source_ordinal": self.source_ordinal,
        }


@dataclass(frozen=True, slots=True)
class NamedCount:
    name: str
    count: int

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "count": self.count}


@dataclass(frozen=True, slots=True)
class DamageMetrics:
    """The 21 CLA v1.4 damage metric families for one hierarchy row."""

    dps: ValueSet
    total_damage: ValueSet
    damage_percentage: OptionalValueSet
    resistance_percentage: float | None
    max_one_hit: MaxOneHit
    average_hit: OptionalValueSet
    critical_percentage: float | None
    flanking_percentage: float | None
    hits: CountSet
    hits_per_second: ValueSet
    hits_percentage: OptionalValueSet
    misses: int
    accuracy_percentage: float | None
    kills: tuple[NamedCount, ...]
    damage_types: tuple[str, ...]
    base_dps: float
    base_damage: float
    total_crit_damage: float
    total_non_crit_hull_damage: float
    average_crit_hit: float | None
    average_non_crit_hull_hit: float | None

    @property
    def kill_count(self) -> int:
        return sum(kill.count for kill in self.kills)

    def to_dict(self) -> dict[str, Any]:
        return {
            "DO-01_dps": self.dps.to_dict(),
            "DO-02_total_damage": self.total_damage.to_dict(),
            "DO-03_damage_percentage": self.damage_percentage.to_dict(),
            "DO-04_resistance_percentage": self.resistance_percentage,
            "DO-05_max_one_hit": self.max_one_hit.to_dict(),
            "DO-06_average_hit": self.average_hit.to_dict(),
            "DO-07_critical_percentage": self.critical_percentage,
            "DO-08_flanking_percentage": self.flanking_percentage,
            "DO-09_hits": self.hits.to_dict(),
            "DO-10_hits_per_second": self.hits_per_second.to_dict(),
            "DO-11_hits_percentage": self.hits_percentage.to_dict(),
            "DO-12_misses": self.misses,
            "DO-13_accuracy_percentage": self.accuracy_percentage,
            "DO-14_kills": {
                "total": self.kill_count,
                "by_name": [kill.to_dict() for kill in self.kills],
            },
            "DO-15_damage_types": list(self.damage_types),
            "DO-16_base_dps": self.base_dps,
            "DO-17_base_damage": self.base_damage,
            "DO-18_total_crit_damage": self.total_crit_damage,
            "DO-19_total_non_crit_hull_damage": self.total_non_crit_hull_damage,
            "DO-20_average_crit_hit": self.average_crit_hit,
            "DO-21_average_non_crit_hull_hit": self.average_non_crit_hull_hit,
        }


@dataclass(frozen=True, slots=True)
class HealMetrics:
    """The eight CLA v1.4 healing metric families for one hierarchy row."""

    hps: ValueSet
    total_heal: ValueSet
    heal_percentage: OptionalValueSet
    average_heal: OptionalValueSet
    critical_percentage: float | None
    ticks: CountSet
    ticks_per_second: ValueSet
    ticks_percentage: OptionalValueSet

    def to_dict(self) -> dict[str, Any]:
        return {
            "HEAL-01_hps": self.hps.to_dict(),
            "HEAL-02_total_heal": self.total_heal.to_dict(),
            "HEAL-03_heal_percentage": self.heal_percentage.to_dict(),
            "HEAL-04_average_heal": self.average_heal.to_dict(),
            "HEAL-05_critical_percentage": self.critical_percentage,
            "HEAL-06_ticks": self.ticks.to_dict(),
            "HEAL-07_ticks_per_second": self.ticks_per_second.to_dict(),
            "HEAL-08_ticks_percentage": self.ticks_percentage.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class DamageAnalysisNode:
    name: str
    segment: str
    path: tuple[str, ...]
    metrics: DamageMetrics
    children: tuple["DamageAnalysisNode", ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "segment": self.segment,
            "path": list(self.path),
            "metrics": self.metrics.to_dict(),
            "children": [child.to_dict() for child in self.children],
        }


@dataclass(frozen=True, slots=True)
class HealAnalysisNode:
    name: str
    segment: str
    path: tuple[str, ...]
    metrics: HealMetrics
    children: tuple["HealAnalysisNode", ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "segment": self.segment,
            "path": list(self.path),
            "metrics": self.metrics.to_dict(),
            "children": [child.to_dict() for child in self.children],
        }


@dataclass(frozen=True, slots=True)
class PlayerSummary:
    player: str
    outgoing_dps: ValueSet
    total_outgoing_damage: ValueSet
    outgoing_damage_percentage: OptionalValueSet
    total_incoming_damage: ValueSet
    incoming_damage_percentage: OptionalValueSet
    combat_duration_ms: int
    combat_duration_percentage: float
    active_duration_ms: int
    deaths: int
    kills: int
    player_kills: int
    npc_kills: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "player": self.player,
            "SUM-01_outgoing_dps": self.outgoing_dps.to_dict(),
            "SUM-02_total_outgoing_damage": self.total_outgoing_damage.to_dict(),
            "SUM-02_outgoing_damage_percentage":
                self.outgoing_damage_percentage.to_dict(),
            "SUM-03_total_incoming_damage": self.total_incoming_damage.to_dict(),
            "SUM-03_incoming_damage_percentage":
                self.incoming_damage_percentage.to_dict(),
            "SUM-04_combat_duration_ms": self.combat_duration_ms,
            "SUM-04_combat_duration_percentage": self.combat_duration_percentage,
            "SUM-05_active_duration_ms": self.active_duration_ms,
            "SUM-06_deaths": self.deaths,
            "SUM-07_kills": self.kills,
            "SUM-07_player_kills": self.player_kills,
            "SUM-07_npc_kills": self.npc_kills,
        }


@dataclass(frozen=True, slots=True)
class ClaPlayerAnalysis:
    summary: PlayerSummary
    damage_out_duration_ms: int | None
    active_duration_ms: int | None
    damage_out: DamageAnalysisNode
    damage_in: DamageAnalysisNode
    heal_out: HealAnalysisNode
    heal_in: HealAnalysisNode

    @property
    def player(self) -> str:
        return self.summary.player

    def to_dict(self) -> dict[str, Any]:
        return {
            "player": self.player,
            "clocks": {
                "TIME-03_damage_out_duration_ms": self.damage_out_duration_ms,
                "TIME-04_active_duration_ms": self.active_duration_ms,
            },
            "summary": self.summary.to_dict(),
            "damage_out": self.damage_out.to_dict(),
            "damage_in": self.damage_in.to_dict(),
            "heal_out": self.heal_out.to_dict(),
            "heal_in": self.heal_in.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class TeamSummary:
    total_outgoing_damage: ValueSet
    total_incoming_damage: ValueSet
    total_outgoing_heal: ValueSet
    total_incoming_heal: ValueSet
    kills: int
    deaths: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_outgoing_damage": self.total_outgoing_damage.to_dict(),
            "total_incoming_damage": self.total_incoming_damage.to_dict(),
            "total_outgoing_heal": self.total_outgoing_heal.to_dict(),
            "total_incoming_heal": self.total_incoming_heal.to_dict(),
            "kills": self.kills,
            "deaths": self.deaths,
        }


@dataclass(frozen=True, slots=True)
class ClaAnalysisResult:
    event_count: int
    combat_duration_ms: int | None
    active_duration_ms: int
    team: TeamSummary
    players: tuple[ClaPlayerAnalysis, ...]
    provenance: ResultProvenance

    @property
    def audit_status(self) -> str:
        return "CLA v1.4 CALCULATION SLICES // FIELD-VALIDATED DAMAGE OUT"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "re-oscr.cla-analysis.v1",
            "status": self.audit_status,
            "metric_ids": {
                "summary": list(SUMMARY_METRIC_IDS),
                "damage": list(DAMAGE_METRIC_IDS),
                "healing": list(HEAL_METRIC_IDS),
            },
            "event_count": self.event_count,
            "clocks": {
                "TIME-01_combat_duration_ms": self.combat_duration_ms,
                "TIME-02_active_duration_ms": self.active_duration_ms,
            },
            "team": self.team.to_dict(),
            "players": [player.to_dict() for player in self.players],
            "provenance": self.provenance.to_dict(),
        }

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, allow_nan=False, indent=indent)


@dataclass(frozen=True, slots=True)
class _Event:
    ordinal: int
    timestamp: datetime
    owner_name: str
    owner_id: str
    source_name: str
    source_id: str
    target_name: str
    target_id: str
    event_name: str
    event_id: str
    event_type: str
    flags: str
    magnitude: float
    magnitude2: float


@dataclass(frozen=True, slots=True)
class _Snapshot:
    snapshot_id: str
    parser_version: str
    combat_start: str
    combat_end: str
    map_name: str | None
    difficulty: str | None
    events: tuple[_Event, ...]


@dataclass(frozen=True, slots=True)
class _Entity:
    kind: str
    name: str | None

    @property
    def is_player(self) -> bool:
        return self.kind == "player"

    @property
    def is_none(self) -> bool:
        return self.kind == "none"


@dataclass(frozen=True, slots=True)
class _Damage:
    kind: str
    damage: float
    base_or_prevented: float

    @property
    def is_all_zero(self) -> bool:
        return self.damage == 0.0 and self.base_or_prevented == 0.0


@dataclass(frozen=True, slots=True)
class _Heal:
    kind: str
    amount: float


@dataclass(frozen=True, slots=True)
class _DamageHit:
    damage: _Damage
    flags: frozenset[str]
    damage_type: str
    kill_name: str
    ordinal: int


@dataclass(frozen=True, slots=True)
class _HealTick:
    heal: _Heal
    flags: frozenset[str]
    ordinal: int


@dataclass(slots=True)
class _DamageTotals:
    damage_all: float = 0.0
    damage_shield: float = 0.0
    damage_hull: float = 0.0
    base_damage: float = 0.0
    shield_drain: float = 0.0
    total_crit_damage: float = 0.0
    total_non_crit_hull_damage: float = 0.0
    hits_all: int = 0
    hits_shield: int = 0
    hits_hull: int = 0
    crits: int = 0
    flanks: int = 0
    misses: int = 0
    max_damage: float = 0.0
    max_name: str = "<unknown>"
    max_ordinal: int | None = None
    damage_types: list[str] = field(default_factory=list)
    kills: dict[str, int] = field(default_factory=dict)

    def merge(self, other: "_DamageTotals") -> None:
        self.damage_all += other.damage_all
        self.damage_shield += other.damage_shield
        self.damage_hull += other.damage_hull
        self.base_damage += other.base_damage
        self.shield_drain += other.shield_drain
        self.total_crit_damage += other.total_crit_damage
        self.total_non_crit_hull_damage += other.total_non_crit_hull_damage
        self.hits_all += other.hits_all
        self.hits_shield += other.hits_shield
        self.hits_hull += other.hits_hull
        self.crits += other.crits
        self.flanks += other.flanks
        self.misses += other.misses
        if self.max_damage < other.max_damage:
            self.max_damage = other.max_damage
            self.max_name = other.max_name
            self.max_ordinal = other.max_ordinal
        for damage_type in other.damage_types:
            if damage_type not in self.damage_types:
                self.damage_types.append(damage_type)
        for name, count in other.kills.items():
            self.kills[name] = self.kills.get(name, 0) + count


@dataclass(slots=True)
class _HealTotals:
    heal_all: float = 0.0
    heal_shield: float = 0.0
    heal_hull: float = 0.0
    ticks_all: int = 0
    ticks_shield: int = 0
    ticks_hull: int = 0
    crits: int = 0

    def merge(self, other: "_HealTotals") -> None:
        self.heal_all += other.heal_all
        self.heal_shield += other.heal_shield
        self.heal_hull += other.heal_hull
        self.ticks_all += other.ticks_all
        self.ticks_shield += other.ticks_shield
        self.ticks_hull += other.ticks_hull
        self.crits += other.crits


@dataclass(slots=True)
class _GroupBuilder:
    name: str
    segment: str
    leaf: bool = False
    children: dict[str, "_GroupBuilder"] = field(default_factory=dict)
    damage_hits: list[_DamageHit] = field(default_factory=list)
    heal_ticks: list[_HealTick] = field(default_factory=list)

    def _leaf_group(self, segment: tuple[str, str]) -> "_GroupBuilder":
        segment_type, name = segment
        candidate = self.children.get(name)
        if candidate is None:
            candidate = _GroupBuilder(name, segment_type, leaf=True)
            self.children[name] = candidate
            return candidate
        if candidate.leaf and candidate.segment == segment_type:
            return candidate
        return candidate._leaf_group(segment)

    def _branch_group(self, segment: tuple[str, str]) -> "_GroupBuilder":
        segment_type, name = segment
        candidate = self.children.get(name)
        if candidate is None:
            candidate = _GroupBuilder(name, segment_type)
            self.children[name] = candidate
            return candidate
        if not candidate.leaf and candidate.segment == segment_type:
            return candidate
        if candidate.leaf or (not candidate.leaf and candidate.segment == "value"):
            branch = _GroupBuilder(name, segment_type)
            branch.children[candidate.name] = candidate
            self.children[name] = branch
            return branch
        return candidate._branch_group(segment)

    def add_damage(self, path: list[tuple[str, str]], hit: _DamageHit) -> None:
        if len(path) == 1:
            self._leaf_group(path[0]).damage_hits.append(hit)
            return
        branch = self._branch_group(path[-1])
        branch.add_damage(path[:-1], hit)

    def add_heal(self, path: list[tuple[str, str]], tick: _HealTick) -> None:
        if len(path) == 1:
            self._leaf_group(path[0]).heal_ticks.append(tick)
            return
        branch = self._branch_group(path[-1])
        branch.add_heal(path[:-1], tick)


@dataclass(slots=True)
class _PlayerState:
    player: str
    damage_start: datetime | None = None
    damage_end: datetime | None = None
    active_start: datetime | None = None
    active_end: datetime | None = None
    damage_out: _GroupBuilder = field(init=False)
    damage_in: _GroupBuilder = field(init=False)
    heal_out: _GroupBuilder = field(init=False)
    heal_in: _GroupBuilder = field(init=False)

    def __post_init__(self) -> None:
        self.damage_out = _GroupBuilder(self.player, "group")
        self.damage_in = _GroupBuilder(self.player, "group")
        self.heal_out = _GroupBuilder(self.player, "group")
        self.heal_in = _GroupBuilder(self.player, "group")

    def update_active(self, timestamp: datetime) -> None:
        if self.active_start is None:
            self.active_start = timestamp
        self.active_end = timestamp

    def update_damage_clock(
            self, timestamp: datetime, damage: _Damage, flags: frozenset[str]) -> None:
        if "Immune" in flags or damage.is_all_zero:
            return
        if self.damage_start is None:
            self.damage_start = timestamp
        self.damage_end = timestamp


@dataclass(frozen=True, slots=True)
class _DamageBuilt:
    name: str
    segment: str
    path: tuple[str, ...]
    totals: _DamageTotals
    children: tuple["_DamageBuilt", ...]


@dataclass(frozen=True, slots=True)
class _HealBuilt:
    name: str
    segment: str
    path: tuple[str, ...]
    totals: _HealTotals
    children: tuple["_HealBuilt", ...]


@dataclass(slots=True)
class _Accumulator:
    player: str
    damage_start: datetime | None = None
    damage_end: datetime | None = None
    active_start: datetime | None = None
    active_end: datetime | None = None
    damage_all: float = 0.0
    damage_shield: float = 0.0
    damage_hull: float = 0.0
    base_damage: float = 0.0
    shield_drain: float = 0.0
    hits_all: int = 0
    hits_shield: int = 0
    hits_hull: int = 0

    def update_active(self, timestamp: datetime) -> None:
        if self.active_start is None:
            self.active_start = timestamp
        self.active_end = timestamp

    def add_damage(self, event: _Event, damage: _Damage, flags: frozenset[str]) -> None:
        self.hits_all += 1
        if damage.kind == "hull":
            self.hits_hull += 1
        else:
            self.hits_shield += 1

        if "Immune" not in flags:
            if damage.kind == "hull":
                self.damage_hull += damage.damage
                self.base_damage += damage.base_or_prevented
            else:
                self.damage_shield += damage.damage
                if damage.kind == "shield_drain":
                    self.shield_drain += damage.damage
            self.damage_all = self.damage_hull + self.damage_shield

        if "Immune" in flags or damage.is_all_zero:
            return
        if self.damage_start is None:
            self.damage_start = event.timestamp
        self.damage_end = event.timestamp


_PLAYER_ID = re.compile(r"^P\[\d+@\d+\s+([^\]]+)\]$")


def analyze_cla_profile(
        snapshot_json: str, snapshot_id: str, *, product_version: str,
        build_revision: str | None = None) -> ClaAnalysisResult:
    """Calculate all dev16 CLA scalar slices and default hierarchies.

    The input is the immutable OSCR-selected event set.  No CLA combat separator, rule transform,
    parser mutation, or League path is invoked here.
    """
    snapshot = _decode_snapshot(snapshot_json, snapshot_id)
    if not product_version:
        raise ClaCoprocessorError(
            "product version is required for result provenance",
            category="PROVENANCE", phase="adapter")

    players: dict[str, _PlayerState] = {}
    player_names: set[str] = set()

    def player(entity: _Entity) -> _PlayerState | None:
        if not entity.is_player or entity.name is None:
            return None
        state = players.get(entity.name)
        if state is None:
            state = _PlayerState(entity.name)
            players[entity.name] = state
        return state

    combat_start: datetime | None = None
    combat_end: datetime | None = None
    first_timestamp = snapshot.events[0].timestamp if snapshot.events else None
    last_timestamp = first_timestamp

    for position, event in enumerate(snapshot.events):
        owner = _entity(event.owner_name, event.owner_id)
        indirect = _entity(event.source_name, event.source_id)
        target = _entity(event.target_name, event.target_id)
        flags = _flags(event.flags)
        damage = _classify_damage(event)
        heal = _classify_heal(event)

        # NameManager learns player identity from all three entity positions, while CLA creates
        # a Player row only when one of the source/target attribution arms requests it.
        player_names.update(
            entity.name for entity in (owner, indirect, target)
            if entity.is_player and entity.name is not None)
        owner_player = player(owner)
        target_player = player(target)
        indirect_player = (
            player(indirect)
            if indirect.is_player and owner.kind == "non_player" else None)

        if position == 0 and owner.is_player and damage is not None:
            # Released CLA seeds this clock in Combat::new before its immune/all-zero check.
            combat_start = event.timestamp
            combat_end = event.timestamp
        if (owner.is_player and damage is not None
                and "Immune" not in flags and not damage.is_all_zero):
            if combat_start is None:
                combat_start = event.timestamp
            combat_end = event.timestamp

        if owner_player is not None:
            # Damage-out exclusions are default-off in the pinned profile, so every outgoing
            # record establishes/extends active time before value dispatch.
            owner_player.update_active(event.timestamp)
            base_path = _default_grouping_path(event, indirect, target)
            target_name = (
                owner.name if indirect.is_none and target.is_none
                else target.name or indirect.name or "<unknown>")
            if damage is not None and not (indirect.is_none and target.is_none):
                path = [("group", target_name), *base_path]
                owner_player.damage_out.add_damage(
                    path, _damage_hit(event, damage, flags, path[0][1]))
                owner_player.update_damage_clock(event.timestamp, damage, flags)
            elif heal is not None:
                path = [*base_path, ("group", target_name)]
                owner_player.heal_out.add_heal(
                    path, _HealTick(heal, flags, event.ordinal))

        incoming_players: list[_PlayerState] = []
        if target_player is not None:
            incoming_players.append(target_player)
        if indirect_player is not None:
            incoming_players.append(indirect_player)
        if owner_player is not None and indirect.is_none and target.is_none:
            incoming_players.append(owner_player)

        # Deliberately do not de-duplicate this list: released CLA dispatches each matching
        # attribution arm independently.
        for incoming in incoming_players:
            path = [
                *_default_grouping_path(event, indirect, target),
                ("group", owner.name or "<unknown>"),
            ]
            if damage is not None:
                incoming.damage_in.add_damage(
                    path, _damage_hit(event, damage, flags, path[0][1]))
                incoming.update_active(event.timestamp)
            elif heal is not None:
                # Incoming healing does not establish the player's active clock.
                incoming.heal_in.add_heal(
                    path, _HealTick(heal, flags, event.ordinal))

        last_timestamp = event.timestamp

    active_duration_ms = 0
    if first_timestamp is not None and last_timestamp is not None:
        active_duration_ms = _duration_ms(
            first_timestamp, last_timestamp, "global active", "TIME-02")
    combat_duration_ms = (
        _duration_ms(combat_start, combat_end, "global combat", "TIME-01")
        if combat_start is not None and combat_end is not None else None
    )

    prepared = []
    for state in players.values():
        damage_duration_ms, active_player_duration_ms = _state_durations(state)
        damage_divisor = _duration_divisor(damage_duration_ms)
        active_divisor = _duration_divisor(active_player_duration_ms)
        prepared.append((
            state,
            damage_duration_ms,
            active_player_duration_ms,
            _build_damage_tree(state.damage_out, (state.player,)),
            _build_damage_tree(state.damage_in, (state.player,)),
            _build_heal_tree(state.heal_out, (state.player,)),
            _build_heal_tree(state.heal_in, (state.player,)),
        ))

    team_damage_out = _sum_damage_totals(item[3].totals for item in prepared)
    team_damage_in = _sum_damage_totals(item[4].totals for item in prepared)
    team_heal_out = _sum_heal_totals(item[5].totals for item in prepared)
    team_heal_in = _sum_heal_totals(item[6].totals for item in prepared)

    analyzed_players = []
    for (
            state, damage_duration_ms, active_player_duration_ms,
            damage_out_built, damage_in_built, heal_out_built, heal_in_built) in prepared:
        damage_divisor = _duration_divisor(damage_duration_ms)
        active_divisor = _duration_divisor(active_player_duration_ms)
        damage_out = _finish_damage_tree(
            damage_out_built, damage_divisor, team_damage_out)
        damage_in = _finish_damage_tree(
            damage_in_built, active_divisor, team_damage_in)
        heal_out = _finish_heal_tree(
            heal_out_built, active_divisor, team_heal_out)
        heal_in = _finish_heal_tree(
            heal_in_built, active_divisor, team_heal_in)

        player_combat_ms = damage_duration_ms or 0
        player_active_ms = active_player_duration_ms or 0
        combat_share = (
            0.0 if not combat_duration_ms
            else player_combat_ms / combat_duration_ms * 100.0)
        kills = damage_out.metrics.kill_count
        player_kills = sum(
            kill.count for kill in damage_out.metrics.kills
            if kill.name in player_names)
        deaths = damage_in.metrics.kill_count
        summary = PlayerSummary(
            state.player,
            damage_out.metrics.dps,
            damage_out.metrics.total_damage,
            damage_out.metrics.damage_percentage,
            damage_in.metrics.total_damage,
            damage_in.metrics.damage_percentage,
            player_combat_ms,
            combat_share,
            player_active_ms,
            deaths,
            kills,
            player_kills,
            kills - player_kills,
        )
        analyzed_players.append(ClaPlayerAnalysis(
            summary,
            damage_duration_ms,
            active_player_duration_ms,
            damage_out,
            damage_in,
            heal_out,
            heal_in,
        ))

    analyzed_players.sort(
        key=lambda item: (-item.damage_out.metrics.total_damage.all,
                          item.player.casefold()))
    team = TeamSummary(
        _damage_values(team_damage_out),
        _damage_values(team_damage_in),
        _heal_values(team_heal_out),
        _heal_values(team_heal_in),
        sum(player.summary.kills for player in analyzed_players),
        sum(player.summary.deaths for player in analyzed_players),
    )
    provenance = _result_provenance(
        snapshot, product_version=product_version, build_revision=build_revision)
    return ClaAnalysisResult(
        len(snapshot.events),
        combat_duration_ms,
        active_duration_ms,
        team,
        tuple(analyzed_players),
        provenance,
    )


def _flags(value: str) -> frozenset[str]:
    return frozenset(value.strip().split("|")) if value.strip() else frozenset()


def _classify_heal(event: _Event) -> _Heal | None:
    flags = _flags(event.flags)
    event_type = event.event_type.strip()
    if event.magnitude < 0.0 and event_type == "HitPoints":
        return _Heal("hull", abs(event.magnitude))
    if (event_type == "Shield" and event.magnitude2 == 0.0
            and "ShieldBreak" not in flags and event.magnitude < 0.0):
        return _Heal("shield", abs(event.magnitude))
    return None


def _default_grouping_path(
        event: _Event, indirect: _Entity, target: _Entity) -> list[tuple[str, str]]:
    effect = event.event_name or "<unknown>"
    if indirect.is_none or target.is_none:
        return [("value", effect)]
    return [
        ("value", effect),
        ("group", indirect.name or "<unknown>"),
    ]


def _damage_hit(
        event: _Event, damage: _Damage, flags: frozenset[str],
        kill_name: str) -> _DamageHit:
    return _DamageHit(
        damage, flags, event.event_type, kill_name, event.ordinal)


def _state_durations(state: _PlayerState) -> tuple[int | None, int | None]:
    damage_duration_ms = None
    if state.damage_start is not None and state.damage_end is not None:
        damage_duration_ms = _duration_ms(
            state.damage_start, state.damage_end,
            f"{state.player} Damage Out", "TIME-03")
    active_duration_ms = None
    if state.active_start is not None and state.active_end is not None:
        active_duration_ms = _duration_ms(
            state.active_start, state.active_end,
            f"{state.player} active", "TIME-04")
    return damage_duration_ms, active_duration_ms


def _duration_divisor(duration_ms: int | None) -> float:
    if duration_ms is None:
        return MISSING_DURATION_SECONDS
    return max(duration_ms / 1000.0, 1.0)


def _leaf_damage_totals(builder: _GroupBuilder) -> _DamageTotals:
    totals = _DamageTotals()
    for hit in builder.damage_hits:
        damage = hit.damage
        totals.hits_all += 1
        if damage.kind == "hull":
            totals.hits_hull += 1
        else:
            totals.hits_shield += 1

        if totals.max_damage < damage.damage:
            totals.max_damage = damage.damage
            totals.max_name = builder.name
            totals.max_ordinal = hit.ordinal

        _add_leaf_damage_type(totals.damage_types, hit.damage_type)
        if "Kill" in hit.flags:
            totals.kills[hit.kill_name] = totals.kills.get(hit.kill_name, 0) + 1

        if "Immune" in hit.flags:
            continue
        if damage.kind == "hull":
            totals.damage_hull += damage.damage
            totals.base_damage += damage.base_or_prevented
            if "Critical" in hit.flags:
                totals.total_crit_damage += damage.damage
            else:
                totals.total_non_crit_hull_damage += damage.damage
        else:
            totals.damage_shield += damage.damage
            if damage.kind == "shield_drain":
                totals.shield_drain += damage.damage
        if "Critical" in hit.flags:
            totals.crits += 1
        if "Flank" in hit.flags:
            totals.flanks += 1
        if "Miss" in hit.flags:
            totals.misses += 1
    totals.damage_all = totals.damage_hull + totals.damage_shield
    return totals


def _add_leaf_damage_type(damage_types: list[str], damage_type: str) -> None:
    if not damage_type or damage_type in damage_types:
        return
    if damage_type == "Shield" and damage_types:
        return
    if damage_type != "Shield" and "Shield" in damage_types:
        damage_types.remove("Shield")
    damage_types.append(damage_type)


def _build_damage_tree(
        builder: _GroupBuilder, path: tuple[str, ...]) -> _DamageBuilt:
    if builder.leaf:
        totals = _leaf_damage_totals(builder)
        children: tuple[_DamageBuilt, ...] = ()
    else:
        totals = _DamageTotals()
        built_children = []
        for child in builder.children.values():
            built = _build_damage_tree(child, (*path, child.name))
            built_children.append(built)
            totals.merge(built.totals)
        children = tuple(built_children)
        if builder.segment == "value" and totals.hits_all:
            totals.max_name = builder.name
    return _DamageBuilt(builder.name, builder.segment, path, totals, children)


def _leaf_heal_totals(builder: _GroupBuilder) -> _HealTotals:
    totals = _HealTotals()
    for tick in builder.heal_ticks:
        if tick.heal.kind == "shield":
            totals.ticks_shield += 1
            totals.heal_shield += tick.heal.amount
        else:
            totals.ticks_hull += 1
            totals.heal_hull += tick.heal.amount
        if "Critical" in tick.flags:
            totals.crits += 1
    totals.ticks_all = totals.ticks_shield + totals.ticks_hull
    totals.heal_all = totals.heal_hull + totals.heal_shield
    return totals


def _build_heal_tree(
        builder: _GroupBuilder, path: tuple[str, ...]) -> _HealBuilt:
    if builder.leaf:
        totals = _leaf_heal_totals(builder)
        children: tuple[_HealBuilt, ...] = ()
    else:
        totals = _HealTotals()
        built_children = []
        for child in builder.children.values():
            built = _build_heal_tree(child, (*path, child.name))
            built_children.append(built)
            totals.merge(built.totals)
        children = tuple(built_children)
    return _HealBuilt(builder.name, builder.segment, path, totals, children)


def _sum_damage_totals(values) -> _DamageTotals:
    total = _DamageTotals()
    for value in values:
        total.merge(value)
    return total


def _sum_heal_totals(values) -> _HealTotals:
    total = _HealTotals()
    for value in values:
        total.merge(value)
    return total


def _damage_values(totals: _DamageTotals) -> ValueSet:
    return ValueSet(totals.damage_all, totals.damage_shield, totals.damage_hull)


def _heal_values(totals: _HealTotals) -> ValueSet:
    return ValueSet(totals.heal_all, totals.heal_shield, totals.heal_hull)


def _percentage(amount: float | int, total: float | int) -> float | None:
    return None if total == 0 else amount / total * 100.0


def _percentage_values(
        values: ValueSet, totals: ValueSet) -> OptionalValueSet:
    return OptionalValueSet(
        _percentage(values.all, totals.all),
        _percentage(values.shield, totals.shield),
        _percentage(values.hull, totals.hull),
    )


def _damage_metrics(
        totals: _DamageTotals, divisor: float,
        parent: _DamageTotals) -> DamageMetrics:
    damage = _damage_values(totals)
    parent_damage = _damage_values(parent)
    hits = CountSet(totals.hits_all, totals.hits_shield, totals.hits_hull)
    parent_hits = ValueSet(
        float(parent.hits_all), float(parent.hits_shield), float(parent.hits_hull))
    hit_values = ValueSet(float(hits.all), float(hits.shield), float(hits.hull))
    resistance = None
    if totals.base_damage != 0.0:
        resistance = (
            1.0 - (damage.all - totals.shield_drain) / totals.base_damage) * 100.0
    non_crit_count = (totals.hits_hull - totals.crits) % (1 << 64)
    return DamageMetrics(
        ValueSet(
            damage.all / divisor, damage.shield / divisor, damage.hull / divisor),
        damage,
        _percentage_values(damage, parent_damage),
        resistance,
        MaxOneHit(totals.max_damage, totals.max_name, totals.max_ordinal),
        OptionalValueSet(
            _average(damage.all, hits.all),
            _average(damage.shield, hits.shield),
            _average(damage.hull, hits.hull),
        ),
        _percentage(totals.crits, totals.hits_hull),
        _percentage(totals.flanks, totals.hits_hull),
        hits,
        ValueSet(
            hits.all / divisor, hits.shield / divisor, hits.hull / divisor),
        _percentage_values(hit_values, parent_hits),
        totals.misses,
        (None if totals.hits_hull == 0
         else 100.0 - totals.misses / totals.hits_hull * 100.0),
        tuple(NamedCount(name, count) for name, count in totals.kills.items()),
        tuple(totals.damage_types),
        totals.base_damage / divisor,
        totals.base_damage,
        totals.total_crit_damage,
        totals.total_non_crit_hull_damage,
        _average(totals.total_crit_damage, totals.crits),
        _average(totals.total_non_crit_hull_damage, non_crit_count),
    )


def _finish_damage_tree(
        built: _DamageBuilt, divisor: float,
        parent: _DamageTotals) -> DamageAnalysisNode:
    return DamageAnalysisNode(
        built.name,
        built.segment,
        built.path,
        _damage_metrics(built.totals, divisor, parent),
        tuple(
            _finish_damage_tree(child, divisor, built.totals)
            for child in built.children),
    )


def _heal_metrics(
        totals: _HealTotals, divisor: float,
        parent: _HealTotals) -> HealMetrics:
    heal = _heal_values(totals)
    parent_heal = _heal_values(parent)
    ticks = CountSet(totals.ticks_all, totals.ticks_shield, totals.ticks_hull)
    tick_values = ValueSet(float(ticks.all), float(ticks.shield), float(ticks.hull))
    parent_ticks = ValueSet(
        float(parent.ticks_all), float(parent.ticks_shield), float(parent.ticks_hull))
    return HealMetrics(
        ValueSet(heal.all / divisor, heal.shield / divisor, heal.hull / divisor),
        heal,
        _percentage_values(heal, parent_heal),
        OptionalValueSet(
            _average(heal.all, ticks.all),
            _average(heal.shield, ticks.shield),
            _average(heal.hull, ticks.hull),
        ),
        _percentage(totals.crits, totals.ticks_hull),
        ticks,
        ValueSet(
            ticks.all / divisor, ticks.shield / divisor, ticks.hull / divisor),
        _percentage_values(tick_values, parent_ticks),
    )


def _finish_heal_tree(
        built: _HealBuilt, divisor: float,
        parent: _HealTotals) -> HealAnalysisNode:
    return HealAnalysisNode(
        built.name,
        built.segment,
        built.path,
        _heal_metrics(built.totals, divisor, parent),
        tuple(
            _finish_heal_tree(child, divisor, built.totals)
            for child in built.children),
    )


def _result_provenance(
        snapshot: _Snapshot, *, product_version: str,
        build_revision: str | None) -> ResultProvenance:
    transform_json = _canonical_identity_json(_empty_transform_descriptor())
    transform_digest = "sha256:" + hashlib.sha256(transform_json.encode("utf-8")).hexdigest()
    result_identity = {
        "domain": "re-oscr.result.v1",
        "snapshot_id": snapshot.snapshot_id,
        "engine_id": ENGINE_ID,
        "engine_version": ENGINE_VERSION,
        "profile_id": PROFILE_ID,
        "transform_digest": transform_digest,
    }
    result_id = "sha256:" + hashlib.sha256(
        _canonical_identity_json(result_identity).encode("utf-8")).hexdigest()
    return ResultProvenance(
        snapshot_id=snapshot.snapshot_id,
        result_id=result_id,
        transform_digest=transform_digest,
        product_version=product_version,
        parser_version=snapshot.parser_version,
        combat_start=snapshot.combat_start,
        combat_end=snapshot.combat_end,
        map_name=snapshot.map_name,
        difficulty=snapshot.difficulty,
        build_revision=build_revision,
    )


def analyze_damage_out_preview(
        snapshot_json: str, snapshot_id: str, *, product_version: str,
        build_revision: str | None = None) -> DamageOutPreviewResult:
    """Calculate the dev15 parser-truth Damage Out preview from frozen JSON only."""
    snapshot = _decode_snapshot(snapshot_json, snapshot_id)
    if not product_version:
        raise ClaCoprocessorError(
            "product version is required for result provenance",
            category="PROVENANCE", phase="adapter")

    accumulators: dict[str, _Accumulator] = {}

    def player(entity: _Entity) -> _Accumulator | None:
        if not entity.is_player or entity.name is None:
            return None
        return accumulators.setdefault(entity.name, _Accumulator(entity.name))

    combat_start: datetime | None = None
    combat_end: datetime | None = None
    first_timestamp = snapshot.events[0].timestamp if snapshot.events else None
    last_timestamp = first_timestamp

    for position, event in enumerate(snapshot.events):
        owner = _entity(event.owner_name, event.owner_id)
        indirect = _entity(event.source_name, event.source_id)
        target = _entity(event.target_name, event.target_id)
        damage = _classify_damage(event)
        flags = frozenset(event.flags.strip().split("|")) if event.flags.strip() else frozenset()

        if position == 0 and owner.is_player and damage is not None:
            # CLA v1.4 seeds Combat::combat_time before its later immune/all-zero check.
            combat_start = event.timestamp
            combat_end = event.timestamp
        if owner.is_player and damage is not None and (
                "Immune" not in flags and not damage.is_all_zero):
            if combat_start is None:
                combat_start = event.timestamp
            combat_end = event.timestamp

        owner_player = player(owner)
        if owner_player is not None:
            # Player::add_out_value updates active time for every outgoing record.
            owner_player.update_active(event.timestamp)

        if damage is not None:
            incoming_players: list[_Accumulator] = []
            target_player = player(target)
            if target_player is not None:
                incoming_players.append(target_player)
            indirect_player = player(indirect)
            if indirect_player is not None and owner.kind == "non_player":
                incoming_players.append(indirect_player)
            if owner_player is not None and indirect.is_none and target.is_none:
                incoming_players.append(owner_player)
            for incoming in incoming_players:
                incoming.update_active(event.timestamp)

        direct_self = indirect.is_none and target.is_none
        if owner_player is not None and damage is not None and not direct_self:
            owner_player.add_damage(event, damage, flags)

        last_timestamp = event.timestamp

    active_duration_ms = 0
    if first_timestamp is not None and last_timestamp is not None:
        active_duration_ms = _duration_ms(
            first_timestamp, last_timestamp, "global active", "TIME-02")
    combat_duration_ms = (
        _duration_ms(combat_start, combat_end, "global combat", "TIME-01")
        if combat_start is not None and combat_end is not None else None
    )

    # CLA recalculates every discovered player, including players with no Damage Out row.
    # Validate those clocks before filtering the preview so an upstream TIME-09 failure cannot
    # disappear merely because the affected player was heal-only or incoming-only.
    for accumulator in accumulators.values():
        _accumulator_durations(accumulator)

    rows = tuple(
        _finish_row(accumulator)
        for accumulator in accumulators.values()
        if accumulator.hits_all
    )
    rows = tuple(sorted(rows, key=lambda row: (-row.total_damage.all, row.player.casefold())))

    transform_json = _canonical_identity_json(_empty_transform_descriptor())
    transform_digest = "sha256:" + hashlib.sha256(transform_json.encode("utf-8")).hexdigest()
    result_identity = {
        "domain": "re-oscr.result.v1",
        "snapshot_id": snapshot.snapshot_id,
        "engine_id": ENGINE_ID,
        "engine_version": ENGINE_VERSION,
        "profile_id": PROFILE_ID,
        "transform_digest": transform_digest,
    }
    result_id = "sha256:" + hashlib.sha256(
        _canonical_identity_json(result_identity).encode("utf-8")).hexdigest()
    provenance = ResultProvenance(
        snapshot_id=snapshot.snapshot_id,
        result_id=result_id,
        transform_digest=transform_digest,
        product_version=product_version,
        parser_version=snapshot.parser_version,
        combat_start=snapshot.combat_start,
        combat_end=snapshot.combat_end,
        map_name=snapshot.map_name,
        difficulty=snapshot.difficulty,
        build_revision=build_revision,
    )
    return DamageOutPreviewResult(
        len(snapshot.events), combat_duration_ms, active_duration_ms, rows, provenance)


def _finish_row(accumulator: _Accumulator) -> DamageOutPreviewRow:
    damage_duration_ms, active_duration_ms = _accumulator_durations(accumulator)

    divisor = (
        MISSING_DURATION_SECONDS
        if damage_duration_ms is None else max(damage_duration_ms / 1000.0, 1.0)
    )
    damage = ValueSet(
        accumulator.damage_all, accumulator.damage_shield, accumulator.damage_hull)
    hits = CountSet(
        accumulator.hits_all, accumulator.hits_shield, accumulator.hits_hull)
    dps = ValueSet(*(value / divisor for value in (
        damage.all, damage.shield, damage.hull)))
    hits_per_second = ValueSet(*(value / divisor for value in (
        hits.all, hits.shield, hits.hull)))
    average_hit = OptionalValueSet(
        _average(damage.all, hits.all),
        _average(damage.shield, hits.shield),
        _average(damage.hull, hits.hull),
    )
    resistance = None
    if accumulator.base_damage != 0.0:
        resistance = 100.0 * (
            1.0 - (damage.all - accumulator.shield_drain) / accumulator.base_damage)
    return DamageOutPreviewRow(
        accumulator.player,
        damage_duration_ms,
        active_duration_ms,
        dps,
        damage,
        resistance,
        average_hit,
        hits,
        hits_per_second,
        accumulator.base_damage / divisor,
        accumulator.base_damage,
    )


def _accumulator_durations(
        accumulator: _Accumulator) -> tuple[int | None, int | None]:
    damage_duration_ms = None
    if accumulator.damage_start is not None and accumulator.damage_end is not None:
        damage_duration_ms = _duration_ms(
            accumulator.damage_start, accumulator.damage_end,
            f"{accumulator.player} Damage Out", "TIME-03")
    active_duration_ms = None
    if accumulator.active_start is not None and accumulator.active_end is not None:
        active_duration_ms = _duration_ms(
            accumulator.active_start, accumulator.active_end,
            f"{accumulator.player} active", "TIME-04")
    return damage_duration_ms, active_duration_ms


def _average(total: float, count: int) -> float | None:
    return None if count == 0 else total / count


def _duration_ms(
        start: datetime, end: datetime, label: str, clock_id: str) -> int:
    delta = end - start
    milliseconds = (
        delta.days * 86_400_000
        + delta.seconds * 1000
        + delta.microseconds // 1000
    )
    if milliseconds < 0:
        raise ClaCoprocessorError(
            f"{label} range ends before it starts",
            category="INVALID_CLOCK_RANGE", phase=clock_id)
    return milliseconds


def _classify_damage(event: _Event) -> _Damage | None:
    flags = frozenset(event.flags.strip().split("|")) if event.flags.strip() else frozenset()
    event_type = event.event_type.strip()
    if event.magnitude < 0.0 and event_type == "HitPoints":
        return None
    if event_type == "Shield":
        if event.magnitude2 == 0.0 and "ShieldBreak" not in flags:
            if event.magnitude < 0.0:
                return None
            if event.magnitude > 0.0:
                return _Damage("shield_drain", abs(event.magnitude), 0.0)
        return _Damage("shield", abs(event.magnitude), abs(event.magnitude2))
    base_damage = event.magnitude if event.magnitude2 == 0.0 else event.magnitude2
    return _Damage("hull", abs(event.magnitude), abs(base_damage))


def _entity(name: str, identity: str) -> _Entity:
    if not name and identity in {"", "*"}:
        return _Entity("none", None)
    player_match = _PLAYER_ID.fullmatch(identity)
    if player_match is not None:
        return _Entity("player", player_match.group(1))
    if identity.startswith("P["):
        # OSCR's synthetic/test combats can carry shortened IDs that CLA itself would reject.
        # Retaining the visible name keeps the adapter deterministic without claiming raw-log
        # parser equivalence for malformed identity strings.
        return _Entity("player", name or identity)
    if identity.startswith("C["):
        return _Entity("non_player", name or identity)
    if identity.startswith("S["):
        return _Entity("non_player_character", name or identity)
    return _Entity("none" if not name else "other", name or None)


def _decode_snapshot(snapshot_json: str, snapshot_id: str) -> _Snapshot:
    if not isinstance(snapshot_json, str) or not snapshot_json:
        raise ClaCoprocessorError(
            "snapshot JSON must be a non-empty string",
            category="INVALID_SNAPSHOT", phase="decode")
    actual_id = "sha256:" + hashlib.sha256(snapshot_json.encode("utf-8")).hexdigest()
    if snapshot_id != actual_id:
        raise ClaCoprocessorError(
            "snapshot identity does not match its canonical payload",
            category="SNAPSHOT_ID_MISMATCH", phase="decode")
    try:
        payload = json.loads(
            snapshot_json,
            object_pairs_hook=_reject_duplicate_json_pairs,
            parse_constant=_reject_json_constant,
        )
    except (json.JSONDecodeError, ValueError) as error:
        detail = error.msg if isinstance(error, json.JSONDecodeError) else str(error)
        raise ClaCoprocessorError(
            f"snapshot JSON is invalid: {detail}",
            category="INVALID_SNAPSHOT", phase="decode") from error
    if not isinstance(payload, dict):
        raise ClaCoprocessorError(
            "snapshot root must be an object",
            category="INVALID_SNAPSHOT", phase="decode")
    if snapshot_json != _canonical_identity_json(payload):
        raise ClaCoprocessorError(
            "snapshot JSON is not in canonical identity form",
            category="INVALID_SNAPSHOT", phase="decode")
    if set(payload) != {
            "combat", "domain", "event_count", "events", "input_contract",
            "parser_distribution", "parser_version"}:
        raise ClaCoprocessorError(
            "snapshot root fields do not match the supported schema",
            category="INVALID_SNAPSHOT", phase="decode")
    if payload.get("domain") != "re-oscr.snapshot.v1":
        raise ClaCoprocessorError(
            "unsupported snapshot domain",
            category="INVALID_SNAPSHOT", phase="decode")
    if (payload.get("input_contract") != "oscr-effective-logline.v1"
            or payload.get("parser_distribution") != "STO-OSCR"
            or not isinstance(payload.get("parser_version"), str)
            or not payload["parser_version"]):
        raise ClaCoprocessorError(
            "snapshot parser contract is invalid",
            category="INVALID_SNAPSHOT", phase="decode")
    raw_events = payload.get("events")
    event_count = payload.get("event_count")
    if (not isinstance(raw_events, list)
            or isinstance(event_count, bool) or not isinstance(event_count, int)
            or event_count != len(raw_events)):
        raise ClaCoprocessorError(
            "snapshot event count is inconsistent",
            category="INVALID_SNAPSHOT", phase="decode")
    combat = payload.get("combat")
    if not isinstance(combat, dict) or set(combat) != {
            "difficulty", "end", "map", "start"}:
        raise ClaCoprocessorError(
            "snapshot combat metadata is missing",
            category="INVALID_SNAPSHOT", phase="decode")
    combat_start = combat.get("start")
    combat_end = combat.get("end")
    map_name = combat.get("map")
    difficulty = combat.get("difficulty")
    if (not isinstance(combat_start, str) or not isinstance(combat_end, str)
            or (map_name is not None and not isinstance(map_name, str))
            or (difficulty is not None and not isinstance(difficulty, str))):
        raise ClaCoprocessorError(
            "snapshot combat metadata is invalid",
            category="INVALID_SNAPSHOT", phase="decode")
    try:
        combat_start_time = datetime.strptime(combat_start, "%Y-%m-%dT%H:%M:%S.%f")
        combat_end_time = datetime.strptime(combat_end, "%Y-%m-%dT%H:%M:%S.%f")
    except ValueError as error:
        raise ClaCoprocessorError(
            "snapshot combat timestamps are invalid",
            category="INVALID_SNAPSHOT", phase="decode") from error
    if (_canonical_timestamp(combat_start_time) != combat_start
            or _canonical_timestamp(combat_end_time) != combat_end):
        raise ClaCoprocessorError(
            "snapshot combat timestamps are not canonical",
            category="INVALID_SNAPSHOT", phase="decode")
    if combat_end_time < combat_start_time:
        raise ClaCoprocessorError(
            "snapshot combat end precedes its start",
            category="INVALID_SNAPSHOT", phase="decode")

    events = []
    previous_ordinal = -1
    for position, raw in enumerate(raw_events):
        if not isinstance(raw, list) or len(raw) != 14:
            raise ClaCoprocessorError(
                f"snapshot event {position} has an invalid shape",
                category="INVALID_SNAPSHOT", phase="decode")
        if (isinstance(raw[0], bool) or not isinstance(raw[0], int)
                or not all(isinstance(value, str) for value in raw[1:14])):
            raise ClaCoprocessorError(
                f"snapshot event {position} contains an invalid field type",
                category="INVALID_SNAPSHOT", phase="decode")
        try:
            timestamp = datetime.strptime(raw[1], "%Y-%m-%dT%H:%M:%S.%f")
            magnitude = _float_from_bits(raw[12])
            magnitude2 = _float_from_bits(raw[13])
            event = _Event(
                raw[0], timestamp,
                *raw[2:12],
                magnitude, magnitude2,
            )
        except (TypeError, ValueError, struct.error) as error:
            raise ClaCoprocessorError(
                f"snapshot event {position} is invalid",
                category="INVALID_SNAPSHOT", phase="decode") from error
        if _canonical_timestamp(timestamp) != raw[1]:
            raise ClaCoprocessorError(
                f"snapshot event {position} timestamp is not canonical",
                category="INVALID_SNAPSHOT", phase="decode")
        if event.ordinal <= previous_ordinal:
            raise ClaCoprocessorError(
                f"snapshot event {position} source ordinal is not strictly increasing",
                category="INVALID_SNAPSHOT", phase="decode")
        if event.ordinal != position:
            raise ClaCoprocessorError(
                f"snapshot event {position} source ordinal is not canonical",
                category="INVALID_SNAPSHOT", phase="decode")
        if event.timestamp.microsecond % 1000:
            raise ClaCoprocessorError(
                f"snapshot event {position} timestamp is not a whole millisecond",
                category="INVALID_SNAPSHOT", phase="decode")
        if not combat_start_time <= event.timestamp <= combat_end_time:
            raise ClaCoprocessorError(
                f"snapshot event {position} falls outside the official combat bounds",
                category="INVALID_SNAPSHOT", phase="decode")
        previous_ordinal = event.ordinal
        events.append(event)
    return _Snapshot(
        actual_id,
        payload["parser_version"],
        combat_start,
        combat_end,
        map_name,
        difficulty,
        tuple(events),
    )


def _float_from_bits(value: object) -> float:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{16}", value) is None:
        raise ValueError("binary64 value must contain 16 hexadecimal digits")
    decoded = struct.unpack(">d", bytes.fromhex(value))[0]
    if not isfinite(decoded):
        raise ValueError("binary64 value must be finite")
    return decoded


def _reject_duplicate_json_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, member in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON object key: {key}")
        value[key] = member
    return value


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant: {value}")


def _canonical_timestamp(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%S.%f")


def _canonical_identity_json(value: dict[str, Any]) -> str:
    return json.dumps(
        value, ensure_ascii=False, allow_nan=False,
        sort_keys=True, separators=(",", ":"))


__all__ = (
    "BOUNDARY_DIFFERENCES",
    "ClaAnalysisResult",
    "ClaCoprocessorError",
    "ClaPlayerAnalysis",
    "CountSet",
    "DAMAGE_METRIC_IDS",
    "DamageAnalysisNode",
    "DamageMetrics",
    "DamageOutPreviewResult",
    "DamageOutPreviewRow",
    "ENGINE_ID",
    "ENGINE_VERSION",
    "HEAL_METRIC_IDS",
    "HealAnalysisNode",
    "HealMetrics",
    "MaxOneHit",
    "NamedCount",
    "OptionalValueSet",
    "PREVIEW_METRIC_IDS",
    "PROFILE_ID",
    "PlayerSummary",
    "ResultProvenance",
    "SUMMARY_METRIC_IDS",
    "TeamSummary",
    "ValueSet",
    "analyze_cla_profile",
    "analyze_damage_out_preview",
)
