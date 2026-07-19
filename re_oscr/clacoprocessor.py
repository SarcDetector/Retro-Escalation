"""Pure CLA v1.4 calculation preview over a frozen OSCR event snapshot.

This module is deliberately independent of Qt and the live OSCR ``Combat`` object.  Dev15 uses
it for a narrow, source-audited Damage Out preview; it is not yet a complete CLA-compatible
profile and it never creates a League upload source.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from math import isfinite
import re
import struct
from typing import Any


ENGINE_ID = "re-oscr.cla-coprocessor"
ENGINE_VERSION = "1"
PROFILE_ID = "cla-v1.4.0"
PREVIEW_METRIC_IDS = (
    "DO-01", "DO-02", "DO-04", "DO-06", "DO-09", "DO-10", "DO-16", "DO-17",
)
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
        return "SOURCE-AUDITED TECH PREVIEW // GOLDEN VERIFICATION PENDING"

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
    "ClaCoprocessorError",
    "CountSet",
    "DamageOutPreviewResult",
    "DamageOutPreviewRow",
    "ENGINE_ID",
    "ENGINE_VERSION",
    "OptionalValueSet",
    "PREVIEW_METRIC_IDS",
    "PROFILE_ID",
    "ResultProvenance",
    "ValueSet",
    "analyze_damage_out_preview",
)
