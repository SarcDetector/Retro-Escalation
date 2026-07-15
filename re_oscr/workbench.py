"""Read-only event indexing for Command Console Analysis modifiers.

The Workbench is deliberately downstream of OSCR.  This module snapshots the event stream that
the official parser actually consumed and exposes masks over that snapshot; it never changes a
``Combat``, a ``LogLine``, or one of OSCR's source models.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, replace
from datetime import timedelta
import json
from math import isfinite
import re
from typing import Any, Mapping
from weakref import ReferenceType, WeakKeyDictionary, ref

import numpy as np
from numpy.typing import NDArray

from OSCR.combat import Combat
from OSCR.constants import HEAL_TREE_HEADER, TREE_HEADER
from OSCR.datamodels import LogLine, TreeItem, TreeModel
from OSCR.parser import (
    analyze_combat,
    combine_children_damage_stats,
    combine_children_heal_stats,
)


QUEEN_NAME = "Borg Queen Octahedron"
HIVE_INTRO_ENTITY = "Space_Borg_Dreadnought_Hive_Intro"


class WorkbenchDataError(ValueError):
    """Raised when a combat is not ready to be indexed safely."""


def _validated_rule_text(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field} must be a string")
    value = value.strip()
    if not value:
        raise ValueError(f"{field} must not be empty")
    return value


@dataclass(frozen=True, slots=True)
class WorkbenchFilterClause:
    """One validated, read-only structured Workbench predicate.

    ``field`` and ``operator`` are normalized to upper-case tokens.  Text identity fields use
    case-insensitive matching over both their visible names and parser IDs.  ``TYPE`` defaults
    to exact matching (``CONTAINS`` remains available explicitly), ``FLAG`` is an exact token
    predicate restricted to Critical/Miss/Kill, and magnitude comparisons are inclusive over
    ``abs(LogLine.magnitude)``.

    ``MIN``/``MAX`` and the UI-facing ``MIN_MAGNITUDE``/``MAX_MAGNITUDE`` names are accepted as
    constructor aliases.  They normalize to ``field='MAGNITUDE'`` with ``operator='GTE'`` or
    ``operator='LTE'`` respectively.
    """

    field: str
    value: str | int | float
    operator: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.field, str):
            raise TypeError("field must be a string")
        field = self.field.strip().upper()
        operator = self.operator
        if operator is not None:
            if not isinstance(operator, str):
                raise TypeError("operator must be a string or None")
            operator = operator.strip().upper()
            if not operator:
                operator = None

        magnitude_aliases = {
            "MIN": "GTE",
            "MIN_MAGNITUDE": "GTE",
            "MAX": "LTE",
            "MAX_MAGNITUDE": "LTE",
        }
        if field in magnitude_aliases:
            alias_operator = magnitude_aliases[field]
            if operator is not None and operator != alias_operator:
                raise ValueError(f"{field} only supports {alias_operator}")
            field = "MAGNITUDE"
            operator = alias_operator

        identity_fields = {"ANY", "OWNER", "SOURCE", "TARGET", "EVENT"}
        if field in identity_fields:
            operator = operator or "CONTAINS"
            if operator != "CONTAINS":
                raise ValueError(f"{field} only supports CONTAINS")
            value = _validated_clause_text(self.value, field)
        elif field == "TYPE":
            operator = operator or "EXACT"
            if operator not in {"EXACT", "CONTAINS"}:
                raise ValueError("TYPE only supports EXACT or CONTAINS")
            value = _validated_clause_text(self.value, field)
        elif field == "FLAG":
            operator = operator or "HAS"
            if operator != "HAS":
                raise ValueError("FLAG only supports HAS")
            flag = _validated_clause_text(self.value, field).casefold()
            flag_names = {"critical": "Critical", "miss": "Miss", "kill": "Kill"}
            try:
                value = flag_names[flag]
            except KeyError as error:
                raise ValueError("FLAG must be Critical, Miss, or Kill") from error
        elif field == "MAGNITUDE":
            if operator not in {"GTE", "LTE"}:
                raise ValueError("MAGNITUDE requires GTE or LTE")
            if isinstance(self.value, bool):
                raise TypeError("magnitude threshold must be numeric")
            try:
                value = float(self.value)
            except (TypeError, ValueError) as error:
                raise TypeError("magnitude threshold must be numeric") from error
            if not isfinite(value) or value < 0:
                raise ValueError("magnitude threshold must be finite and non-negative")
        else:
            raise ValueError(
                "field must be ANY, OWNER, SOURCE, TARGET, EVENT, TYPE, FLAG, MIN, or MAX")

        object.__setattr__(self, "field", field)
        object.__setattr__(self, "operator", operator)
        object.__setattr__(self, "value", value)

    @property
    def display_label(self) -> str:
        """Return a compact human-readable label suitable for an active-filter chip."""
        if self.field == "MAGNITUDE":
            comparison = "≥" if self.operator == "GTE" else "≤"
            return f"|MAG| {comparison} {self.value:g}"
        if self.field == "FLAG":
            return f"FLAG: {self.value}"
        if self.field == "TYPE" and self.operator == "EXACT":
            return f"TYPE = {self.value}"
        return f"{self.field}: {self.value}"

    @property
    def summary(self) -> str:
        """Alias retained for consumers that call the chip text a summary."""
        return self.display_label


@dataclass(frozen=True, slots=True)
class WorkbenchRuleMatch:
    """One safe, declarative event/source matcher for a Workbench rule.

    Matching is case-insensitive against the original visible log-line name.  ``*`` is the only
    wildcard metacharacter; every other character is literal and the pattern is anchored to the
    complete value.  This deliberately small grammar keeps imported rule sets data-only.
    """

    field: str
    pattern: str

    def __post_init__(self) -> None:
        if not isinstance(self.field, str):
            raise TypeError("rule match field must be a string")
        field = self.field.strip().upper()
        aliases = {
            "EVENT": "EVENT",
            "EVENT_NAME": "EVENT",
            "SOURCE": "SOURCE",
            "SOURCE_NAME": "SOURCE",
        }
        try:
            field = aliases[field]
        except KeyError as error:
            raise ValueError("rule match field must be event_name or source_name") from error
        pattern = _validated_rule_text(self.pattern, "rule match pattern")
        object.__setattr__(self, "field", field)
        object.__setattr__(self, "pattern", pattern)

    @property
    def mode(self) -> str:
        return "WILDCARD" if "*" in self.pattern else "EXACT"

    def matches(self, line: LogLine) -> bool:
        """Match only original event/source display names from ``line``."""
        value = line.event_name if self.field == "EVENT" else line.source_name
        pattern = re.escape(self.pattern.casefold()).replace(r"\*", ".*")
        return re.fullmatch(pattern, value.casefold(), flags=re.DOTALL) is not None

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> WorkbenchRuleMatch:
        data = _strict_mapping(value, "rule match", {"field", "pattern"})
        _require_keys(data, "rule match", {"field", "pattern"})
        return cls(data["field"], data["pattern"])

    def to_dict(self) -> dict[str, str]:
        return {
            "field": "event_name" if self.field == "EVENT" else "source_name",
            "pattern": self.pattern,
        }


@dataclass(frozen=True, slots=True)
class WorkbenchRule:
    """One ordered custom-grouping or indirect-source reversal rule."""

    rule_type: str
    matches: tuple[WorkbenchRuleMatch, ...]
    label: str = ""
    enabled: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.rule_type, str):
            raise TypeError("rule type must be a string")
        rule_type = self.rule_type.strip().upper()
        if rule_type not in {"GROUP", "REVERSE"}:
            raise ValueError("rule type must be group or reverse")

        if isinstance(self.matches, WorkbenchRuleMatch):
            matches = (self.matches,)
        else:
            try:
                matches = tuple(self.matches)
            except TypeError as error:
                raise TypeError(
                    "rule matches must be an iterable of WorkbenchRuleMatch values") from error
        if not matches:
            raise ValueError("rule must contain at least one match")
        if not all(isinstance(match, WorkbenchRuleMatch) for match in matches):
            raise TypeError("rule matches must contain only WorkbenchRuleMatch values")

        if not isinstance(self.enabled, bool):
            raise TypeError("rule enabled must be a boolean")
        if rule_type == "GROUP":
            label = _validated_rule_text(self.label, "group label")
        else:
            if not isinstance(self.label, str):
                raise TypeError("reverse label must be a string")
            label = self.label.strip()

        object.__setattr__(self, "rule_type", rule_type)
        object.__setattr__(self, "matches", matches)
        object.__setattr__(self, "label", label)

    @property
    def type(self) -> str:
        """JSON-compatible alias for ``rule_type``."""
        return self.rule_type

    @property
    def display_label(self) -> str:
        if self.rule_type == "GROUP":
            return f"GROUP: {self.label}"
        label = self.label or self.matches[0].pattern
        return f"REVERSE: {label}"

    def matches_line(self, line: LogLine) -> bool:
        return self.enabled and any(match.matches(line) for match in self.matches)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> WorkbenchRule:
        data = _strict_mapping(
            value, "rule", {"type", "match", "matches", "label", "enabled"})
        _require_keys(data, "rule", {"type"})
        if "match" in data and "matches" in data:
            raise ValueError("rule must use match or matches, not both")
        if "match" in data:
            matches = (WorkbenchRuleMatch.from_dict(data["match"]),)
        elif "matches" in data:
            raw_matches = data["matches"]
            if not isinstance(raw_matches, list):
                raise TypeError("rule matches must be a JSON array")
            matches = tuple(WorkbenchRuleMatch.from_dict(match) for match in raw_matches)
        else:
            raise ValueError("rule is missing required key: match or matches")
        return cls(
            data["type"],
            matches,
            data.get("label", ""),
            data.get("enabled", False),
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "type": self.rule_type.casefold(),
            "enabled": self.enabled,
        }
        if len(self.matches) == 1:
            result["match"] = self.matches[0].to_dict()
        else:
            result["matches"] = [match.to_dict() for match in self.matches]
        if self.rule_type == "GROUP":
            result["label"] = self.label
        elif self.label:
            result["label"] = self.label
        return result


@dataclass(frozen=True, slots=True)
class WorkbenchRuleSet:
    """A strict versioned, ordered collection of declarative Workbench rules."""

    name: str
    rules: tuple[WorkbenchRule, ...]
    version: int = 1
    read_only: bool = False

    def __post_init__(self) -> None:
        name = _validated_rule_text(self.name, "rule-set name")
        if isinstance(self.version, bool) or not isinstance(self.version, int):
            raise TypeError("rule-set version must be an integer")
        if self.version != 1:
            raise ValueError(f"unsupported rule-set version: {self.version}")
        if not isinstance(self.read_only, bool):
            raise TypeError("rule-set read_only must be a boolean")
        try:
            rules = tuple(self.rules)
        except TypeError as error:
            raise TypeError("rule-set rules must be an iterable of WorkbenchRule values") from error
        if not all(isinstance(rule, WorkbenchRule) for rule in rules):
            raise TypeError("rule-set rules must contain only WorkbenchRule values")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "rules", rules)

    @property
    def enabled_rules(self) -> tuple[WorkbenchRule, ...]:
        return tuple(rule for rule in self.rules if rule.enabled)

    @classmethod
    def from_dict(
            cls, value: Mapping[str, Any], *, read_only: bool = False) -> WorkbenchRuleSet:
        data = _strict_mapping(value, "rule set", {"name", "version", "rules"})
        _require_keys(data, "rule set", {"name", "version", "rules"})
        if not isinstance(data["rules"], list):
            raise TypeError("rule-set rules must be a JSON array")
        return cls(
            data["name"],
            tuple(WorkbenchRule.from_dict(rule) for rule in data["rules"]),
            data["version"],
            read_only,
        )

    @classmethod
    def from_json(cls, text: str, *, read_only: bool = False) -> WorkbenchRuleSet:
        if not isinstance(text, str):
            raise TypeError("rule-set JSON must be a string")
        try:
            value = json.loads(text, object_pairs_hook=_reject_duplicate_json_keys)
        except json.JSONDecodeError as error:
            raise ValueError(f"invalid rule-set JSON: {error.msg}") from error
        return cls.from_dict(value, read_only=read_only)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "rules": [rule.to_dict() for rule in self.rules],
        }

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


BUNDLED_WORKBENCH_RULE_SET = WorkbenchRuleSet(
    "Community examples",
    (
        WorkbenchRule(
            "GROUP",
            (
                WorkbenchRuleMatch("EVENT", "Advanced Piezo*"),
                WorkbenchRuleMatch("EVENT", "Technical Overload"),
            ),
            "Advanced Piezo Beam Array",
        ),
        WorkbenchRule(
            "REVERSE",
            (WorkbenchRuleMatch("EVENT", "Tachyon Net Drones*"),),
            "Tachyon Net Drones",
        ),
        WorkbenchRule(
            "REVERSE",
            (WorkbenchRuleMatch("EVENT", "Spore-Infused Anomalies"),),
            "Spore-Infused Anomalies",
        ),
        WorkbenchRule(
            "GROUP",
            (
                WorkbenchRuleMatch("EVENT", "Dark Matter Laced Quantum Torpedo*"),
                WorkbenchRuleMatch("EVENT", "Dark Matter Dissolution"),
            ),
            "Dark Matter Laced Quantum Torpedo",
        ),
    ),
    read_only=True,
)
BUNDLED_WORKBENCH_RULE_SETS = (BUNDLED_WORKBENCH_RULE_SET,)


@dataclass(frozen=True, slots=True)
class WorkbenchState:
    """The complete, default-off modifier state shared by all four Analysis modes."""

    owner_query: str = ""
    source_query: str = ""
    target_query: str = ""
    event_query: str = ""
    text_query: str = ""
    clauses: tuple[WorkbenchFilterClause, ...] = ()
    rules: tuple[WorkbenchRule, ...] = ()
    start_seconds: float | None = None
    end_seconds: float | None = None

    def __post_init__(self) -> None:
        try:
            clauses = tuple(self.clauses)
        except TypeError as error:
            raise TypeError(
                "clauses must be an iterable of WorkbenchFilterClause values") from error
        if not all(isinstance(clause, WorkbenchFilterClause) for clause in clauses):
            raise TypeError("clauses must contain only WorkbenchFilterClause values")
        object.__setattr__(self, "clauses", clauses)

        try:
            rules = tuple(self.rules)
        except TypeError as error:
            raise TypeError("rules must be an iterable of WorkbenchRule values") from error
        if not all(isinstance(rule, WorkbenchRule) for rule in rules):
            raise TypeError("rules must contain only WorkbenchRule values")
        object.__setattr__(self, "rules", rules)

        for field_name in ("start_seconds", "end_seconds"):
            value = getattr(self, field_name)
            if value is not None and (not isfinite(value) or value < 0):
                raise ValueError(f"{field_name} must be finite and non-negative")
        if (self.start_seconds is not None and self.end_seconds is not None
                and self.start_seconds > self.end_seconds):
            raise ValueError("start_seconds must not be greater than end_seconds")

    @property
    def is_modified(self) -> bool:
        """Whether this state must be identified as a modified, non-League view."""
        return any((
            self.owner_query.strip(),
            self.source_query.strip(),
            self.target_query.strip(),
            self.event_query.strip(),
            self.text_query.strip(),
            bool(self.clauses),
            any(rule.enabled for rule in self.rules),
            self.start_seconds is not None,
            self.end_seconds is not None,
        ))

    @property
    def active_rules(self) -> tuple[WorkbenchRule, ...]:
        return tuple(rule for rule in self.rules if rule.enabled)

    def with_changes(self, **changes) -> WorkbenchState:
        """Return a changed state while leaving the current one untouched."""
        return replace(self, **changes)

    @classmethod
    def parser_truth(cls) -> WorkbenchState:
        """Return the single reset target for all Analysis modes."""
        return cls()


@dataclass(frozen=True, slots=True)
class WorkbenchQueryResult:
    """A read-only selection over one :class:`CombatEventIndex`."""

    index: CombatEventIndex
    state: WorkbenchState
    mask: NDArray[np.bool_]

    @property
    def count(self) -> int:
        return int(np.count_nonzero(self.mask))

    @property
    def lines(self) -> tuple[LogLine, ...]:
        selected = np.flatnonzero(self.mask)
        return tuple(self.index.lines[int(position)] for position in selected)

    @property
    def source_ordinals(self) -> NDArray[np.int64]:
        ordinals = self.index.source_ordinals[self.mask].copy()
        ordinals.setflags(write=False)
        return ordinals

    @property
    def is_parser_truth(self) -> bool:
        """Whether this result is the complete, unmodified parser event selection."""
        return (
            not self.state.is_modified
            and self.mask.size == len(self.index)
            and bool(np.all(self.mask))
        )


@dataclass(frozen=True, slots=True)
class WorkbenchCombatView:
    """Analysis-only combat selected by a Workbench query.

    This wrapper is deliberately not accepted by any League API.  Parser-truth views point to
    the official source ``Combat``; modified views contain a fresh ``Combat`` analyzed from a
    fresh deque by OSCR's own :func:`analyze_combat`.
    """

    source_combat: Combat
    combat: Combat
    state: WorkbenchState

    @property
    def is_modified(self) -> bool:
        return self.state.is_modified

    @property
    def league_eligible(self) -> bool:
        """Workbench views never form a League upload source."""
        return False


class CombatEventIndex:
    """An immutable column snapshot of OSCR's effective event stream for one combat."""

    def __init__(self, combat: Combat):
        if combat.start_time is None or combat.end_time is None:
            raise WorkbenchDataError("combat must have official start and end times")
        if combat.end_time < combat.start_time:
            raise WorkbenchDataError("combat end time precedes its start time")

        # Keep the cache weak in both directions.  A query can resolve its source while the
        # official parser still owns it, but an index never prolongs a Combat's lifetime.
        self._source_combat_ref: ReferenceType[Combat] = ref(combat)

        effective = tuple(_effective_lines(combat))
        self.lines: tuple[LogLine, ...] = tuple(line for _, line in effective)
        self.source_ordinals = _readonly_array(
            (ordinal for ordinal, _ in effective), np.int64)
        self.elapsed_seconds = _readonly_array(
            ((line.timestamp - combat.start_time).total_seconds() for line in self.lines),
            np.float64)
        self.timestamps = tuple(line.timestamp for line in self.lines)

        self.owner_names = _readonly_text(line.owner_name for line in self.lines)
        self.owner_ids = _readonly_text(line.owner_id for line in self.lines)
        self.source_names = _readonly_text(line.source_name for line in self.lines)
        self.source_ids = _readonly_text(line.source_id for line in self.lines)
        self.target_names = _readonly_text(line.target_name for line in self.lines)
        self.target_ids = _readonly_text(line.target_id for line in self.lines)
        self.event_names = _readonly_text(line.event_name for line in self.lines)
        self.event_ids = _readonly_text(line.event_id for line in self.lines)
        self.event_types = _readonly_text(line.type for line in self.lines)
        self.flags = _readonly_text(line.flags for line in self.lines)
        self.magnitudes = _readonly_array(
            (line.magnitude for line in self.lines), np.float64)
        self.absolute_magnitudes = _readonly_array(
            (abs(line.magnitude) for line in self.lines), np.float64)
        self.magnitudes2 = _readonly_array(
            (line.magnitude2 for line in self.lines), np.float64)

        # Case-fold once.  Querying then remains a small set of NumPy mask operations.
        # A field's visible label and stable parser identity are one search surface.  This
        # makes account handles/entity IDs discoverable without changing display values.
        self._owner_search = _readonly_identity_text(self.owner_names, self.owner_ids)
        self._source_search = _readonly_identity_text(self.source_names, self.source_ids)
        self._target_search = _readonly_identity_text(self.target_names, self.target_ids)
        self._event_search = _readonly_identity_text(self.event_names, self.event_ids)
        self._type_search = _readonly_text(value.casefold() for value in self.event_types)
        flag_tokens = tuple(
            frozenset(
                token.strip().casefold()
                for token in value.split("|")
                if token.strip()
            )
            for value in self.flags
        )
        self._flag_matches = tuple(
            (
                flag,
                _readonly_array((flag in tokens for tokens in flag_tokens), np.bool_),
            )
            for flag in ("critical", "miss", "kill")
        )

    def __len__(self) -> int:
        return len(self.lines)

    @property
    def source_combat(self) -> Combat | None:
        """Return the official source combat while it is still owned by the parser."""
        return self._source_combat_ref()

    def query(self, state: WorkbenchState | None = None) -> WorkbenchQueryResult:
        """Apply all populated filters with AND semantics and inclusive time bounds."""
        state = state or WorkbenchState.parser_truth()
        mask = np.ones(len(self), dtype=np.bool_)

        for text, column in (
                (state.owner_query, self._owner_search),
                (state.source_query, self._source_search),
                (state.target_query, self._target_search),
                (state.event_query, self._event_search)):
            needle = text.strip().casefold()
            if needle:
                mask &= np.char.find(column, needle) >= 0

        free_text = state.text_query.strip().casefold()
        if free_text:
            name_match = np.zeros(len(self), dtype=np.bool_)
            for column in (
                    self._owner_search, self._source_search,
                    self._target_search, self._event_search):
                name_match |= np.char.find(column, free_text) >= 0
            mask &= name_match

        for clause in state.clauses:
            mask &= self._clause_mask(clause)

        if state.start_seconds is not None:
            mask &= self.elapsed_seconds >= state.start_seconds
        if state.end_seconds is not None:
            mask &= self.elapsed_seconds <= state.end_seconds

        mask.setflags(write=False)
        return WorkbenchQueryResult(self, state, mask)

    def _clause_mask(self, clause: WorkbenchFilterClause) -> NDArray[np.bool_]:
        identity_columns = {
            "OWNER": self._owner_search,
            "SOURCE": self._source_search,
            "TARGET": self._target_search,
            "EVENT": self._event_search,
        }
        if clause.field == "ANY":
            matches = np.zeros(len(self), dtype=np.bool_)
            needle = str(clause.value).casefold()
            for column in identity_columns.values():
                matches |= np.char.find(column, needle) >= 0
            return matches
        if clause.field in identity_columns:
            needle = str(clause.value).casefold()
            return np.char.find(identity_columns[clause.field], needle) >= 0
        if clause.field == "TYPE":
            needle = str(clause.value).casefold()
            if clause.operator == "EXACT":
                return self._type_search == needle
            return np.char.find(self._type_search, needle) >= 0
        if clause.field == "FLAG":
            needle = str(clause.value).casefold()
            return next(matches for flag, matches in self._flag_matches if flag == needle)
        if clause.operator == "GTE":
            return self.absolute_magnitudes >= float(clause.value)
        return self.absolute_magnitudes <= float(clause.value)


class WorkbenchIndexCache:
    """Lazy identity cache; repeated numeric ``Combat.id`` values never collide."""

    def __init__(self):
        self._indexes: WeakKeyDictionary[Combat, CombatEventIndex] = WeakKeyDictionary()

    def get(self, combat: Combat) -> CombatEventIndex:
        index = self._indexes.get(combat)
        if index is None:
            index = CombatEventIndex(combat)
            self._indexes[combat] = index
        return index

    def invalidate(self, combat: Combat) -> None:
        self._indexes.pop(combat, None)

    def clear(self) -> None:
        self._indexes.clear()

    def __len__(self) -> int:
        return len(self._indexes)


def derive_workbench_combat(result: WorkbenchQueryResult) -> WorkbenchCombatView:
    """Resolve an Analysis-only combat for ``result`` without mutating parser truth.

    All populated text and structured filters have already been combined with AND semantics by
    :meth:`CombatEventIndex.query`.  Time cuts are inclusive offsets from the source combat's
    official start.  A derived combat retains the source's outer start/end unless an explicit
    time cut is present; explicit bounds are clamped to the official combat interval.  Other
    filters select events but do not silently change that outer interval.

    An untouched result returns the official source combat and therefore avoids a lossy reparse.
    Every modified result receives a new ``Combat``, new deque, models, dictionaries, and graph
    arrays.  Empty selections bypass ``analyze_combat`` and receive four valid empty OSCR tree
    models, because OSCR's analyzer requires at least one line.
    """
    source = result.index.source_combat
    if source is None:
        raise WorkbenchDataError("source combat is no longer available")

    if result.is_parser_truth:
        return WorkbenchCombatView(source, source, result.state)

    derived = _new_display_combat(source, result.state)
    selected_lines = result.lines
    derived.log_data = deque(selected_lines)

    if selected_lines:
        analyze_combat(derived)
        _rebuild_display_graphs(derived, selected_lines)
        _project_rule_models(derived, selected_lines, result.state)
    else:
        _initialize_empty_models(derived)

    # Map detection describes the selected subset.  The shell needs the identity of the combat
    # the user selected instead, so restore these display-only identity fields after analysis.
    derived.map = source.map
    derived.difficulty = source.difficulty
    return WorkbenchCombatView(source, derived, result.state)


def count_effective_events(combat: Combat) -> int:
    """Count parser-consumed events without constructing the full search index.

    The command-bar readout is visible before a user applies any modifier.  A
    lightweight pass keeps that readout truthful while preserving the
    Workbench cache's documented lazy allocation of its NumPy search columns.
    """
    if combat.start_time is None or combat.end_time is None:
        raise WorkbenchDataError("combat must have official start and end times")
    if combat.end_time < combat.start_time:
        raise WorkbenchDataError("combat end time precedes its start time")
    return sum(1 for _ordinal, _line in _effective_lines(combat))


def _new_display_combat(source: Combat, state: WorkbenchState) -> Combat:
    derived = Combat(
        graph_resolution=source.graph_resolution,
        id=source.id,
        # A Workbench combat is presentation data, never an upload coordinate.  Deliberately
        # omit the source path and byte offsets so a later wiring mistake cannot turn a
        # modified view into a League submission.  The wrapper retains ``source_combat`` for
        # display identity without exposing a second writable/upload path.
        log_file='',
    )
    derived.map = source.map
    derived.difficulty = source.difficulty
    derived.start_time, derived.end_time = _derived_time_window(source, state)
    return derived


def _derived_time_window(source: Combat, state: WorkbenchState):
    """Return inclusive explicit cut bounds, clamped to the official combat interval."""
    duration = (source.end_time - source.start_time).total_seconds()

    def clamp(offset: float) -> float:
        return min(max(offset, 0.0), duration)

    start_offset = clamp(state.start_seconds) if state.start_seconds is not None else 0.0
    end_offset = clamp(state.end_seconds) if state.end_seconds is not None else duration
    return (
        source.start_time + timedelta(seconds=start_offset),
        source.start_time + timedelta(seconds=end_offset),
    )


def _initialize_empty_models(combat: Combat) -> None:
    combat.damage_out = TreeModel(TREE_HEADER)
    combat.damage_in = TreeModel(TREE_HEADER)
    combat.heals_out = TreeModel(HEAL_TREE_HEADER)
    combat.heals_in = TreeModel(HEAL_TREE_HEADER)
    combat.meta["log_duration"] = (combat.end_time - combat.start_time).total_seconds()
    combat.meta["player_duration"] = 0.0
    combat.meta["detection_info"] = []


def _effective_lines(combat: Combat):
    """Yield ``(source ordinal, line)`` pairs in the exact parser-consumed order."""
    source_lines = tuple(combat.log_data)
    # OSCR discovers Hive incrementally from damage rows it has already consumed.  Looking ahead
    # would incorrectly make a Queen kill before the intro entity terminal.
    seen_hive_intro = False
    for ordinal, line in enumerate(source_lines):
        if line.timestamp < combat.start_time:
            continue
        if line.timestamp > combat.end_time:
            break
        yield ordinal, line
        if not _is_heal_line(line) and HIVE_INTRO_ENTITY in line.target_id:
            seen_hive_intro = True
        # OSCR includes the terminal hit, then stops immediately.  This ordinal check matters:
        # the reference Hive log contains later events with the very same timestamp.
        if seen_hive_intro and _is_hive_terminal_kill(line):
            break


def _rebuild_display_graphs(combat: Combat, lines: tuple[LogLine, ...]) -> None:
    """Align derived Analysis graphs to the displayed combat window.

    OSCR correctly computes every table value, but its graph bins are intentionally relative to
    the first line in the supplied queue.  A Workbench filter can omit earlier lines while still
    retaining the source combat's outer time window.  Rebuild only the four derived display
    arrays against ``combat.start_time`` so a filtered event keeps its original timeline
    position.  Existing model indexes identify the same leaf rows OSCR populated; table data,
    parser-owned models, and source events remain untouched.
    """
    duration = max(int((combat.end_time - combat.start_time).total_seconds()) + 1, 1)
    models = (combat.damage_out, combat.damage_in, combat.heals_out, combat.heals_in)
    for model in models:
        _reset_graph_data(model._root, duration)

    for line in lines:
        second = int((line.timestamp - combat.start_time).total_seconds())
        if second < 0 or second >= duration:
            continue

        if _is_heal_line(line):
            outgoing_model = combat.heals_out
            incoming_model = combat.heals_in
        else:
            outgoing_model = combat.damage_out
            incoming_model = combat.damage_in

        attacker_id = (line.owner_id, line.source_id) if line.source_name else (line.owner_id,)
        outgoing_item = outgoing_model.target_index[attacker_id][line.event_name][line.target_id]

        target_id = (line.target_id,)
        source_id = line.source_id if line.source_name else line.owner_id
        source_ability_id = line.source_id + line.event_id
        incoming_item = incoming_model.ability_index[target_id][source_id][source_ability_id]

        magnitude = abs(line.magnitude)
        outgoing_item.graph_data[second] += magnitude
        incoming_item.graph_data[second] += magnitude

    for model in models:
        _aggregate_graph_data(model._root)


def _reset_graph_data(item, duration: int) -> None:
    item.graph_data = np.zeros(duration, dtype=np.float64)
    for child in item._children:
        _reset_graph_data(child, duration)


def _aggregate_graph_data(item) -> NDArray[np.float64]:
    if item._children:
        item.graph_data = np.sum(
            [_aggregate_graph_data(child) for child in item._children],
            axis=0,
            dtype=np.float64,
        )
    return item.graph_data


@dataclass(frozen=True, slots=True)
class _ProjectionLeaf:
    """One unique official leaf plus its display-only rule placement."""

    line: LogLine
    leaf: TreeItem
    actor: TreeItem
    actor_key: tuple[str, ...]
    source_label: object
    group_index: int | None
    group_rule: WorkbenchRule | None
    reversed_source: bool


def _project_rule_models(
        combat: Combat, lines: tuple[LogLine, ...], state: WorkbenchState) -> None:
    """Replace only derived model roots with grouped/reversed display projections.

    The official analyzer has already produced every metric and leaf graph.  This stage copies
    those completed leaves into fresh trees and uses the parser's own branch aggregation helpers;
    neither the selected ``LogLine`` objects nor an official source model is modified.
    """
    if not state.active_rules:
        return
    damage_lines = tuple(line for line in lines if not _is_heal_line(line))
    heal_lines = tuple(line for line in lines if _is_heal_line(line))
    combat.damage_out = _project_rule_model(
        combat.damage_out, damage_lines, state.rules, outgoing=True, healing=False)
    combat.damage_in = _project_rule_model(
        combat.damage_in, damage_lines, state.rules, outgoing=False, healing=False)
    combat.heals_out = _project_rule_model(
        combat.heals_out, heal_lines, state.rules, outgoing=True, healing=True)
    combat.heals_in = _project_rule_model(
        combat.heals_in, heal_lines, state.rules, outgoing=False, healing=True)


def _project_rule_model(
        source_model: TreeModel, lines: tuple[LogLine, ...],
        rules: tuple[WorkbenchRule, ...], *, outgoing: bool, healing: bool) -> TreeModel:
    """Build one rule-aware tree while retaining all official leaf values exactly once."""
    header = HEAL_TREE_HEADER if healing else TREE_HEADER
    leaf_specs: dict[int, _ProjectionLeaf] = {}
    any_structural_match = False

    for line in lines:
        group_match = _first_matching_rule(rules, "GROUP", line)
        reverse_match = _first_matching_rule(rules, "REVERSE", line)
        reversed_source = reverse_match is not None and bool(line.source_name)
        any_structural_match |= group_match is not None or reversed_source
        if outgoing:
            spec = _outgoing_projection_leaf(
                source_model, line, group_match, reversed_source, len(header))
        else:
            spec = _incoming_projection_leaf(
                source_model, line, group_match, reversed_source, len(header))

        leaf_identity = id(spec.leaf)
        previous = leaf_specs.get(leaf_identity)
        if previous is not None:
            previous_signature = (
                previous.group_index,
                previous.reversed_source,
                previous.source_label,
            )
            current_signature = (spec.group_index, spec.reversed_source, spec.source_label)
            if current_signature != previous_signature:
                raise WorkbenchDataError(
                    "one parser leaf matched conflicting grouping rules")
            continue
        leaf_specs[leaf_identity] = spec

    # An enabled but inapplicable rule still marks the view modified, but it must not disturb the
    # official hierarchy merely by being present.
    if not any_structural_match:
        return source_model

    projected = TreeModel(header)
    duration = len(source_model._root.graph_data)
    for root_item in (projected._root, projected._player, projected._npc):
        root_item.graph_data = np.zeros(duration, dtype=np.float64)

    branches: dict[tuple[int, object], TreeItem] = {}
    actors: dict[tuple[bool, tuple[str, ...]], TreeItem] = {}

    for spec in leaf_specs.values():
        player_category = spec.actor.parent is source_model._player
        category = projected._player if player_category else projected._npc
        actor_cache_key = (player_category, spec.actor_key)
        actor = actors.get(actor_cache_key)
        if actor is None:
            actor = TreeItem(_row_identity(spec.actor.data, len(header)), category)
            category.append_child(actor)
            actors[actor_cache_key] = actor
            projected.actor_index[spec.actor_key] = actor

        parent = actor
        if spec.group_rule is not None:
            parent = _projection_branch(
                parent,
                ("group", spec.group_index, spec.group_rule.label),
                spec.group_rule.label,
                branches,
            )

        if spec.reversed_source:
            parent = _projection_branch(
                parent,
                ("event", spec.line.event_name, spec.line.event_id),
                spec.line.event_name,
                branches,
            )
            if outgoing:
                parent = _projection_branch(
                    parent,
                    ("source", spec.line.source_name, spec.line.source_id),
                    spec.source_label,
                    branches,
                )
                leaf_data = spec.leaf.data
            else:
                # Incoming tables already use the target as their actor.  The existing official
                # event leaf supplies the values; replacing only its identity makes source the
                # child without changing a single metric.
                leaf_data = _row_with_identity(spec.leaf.data, spec.source_label, len(header))
        elif spec.group_rule is not None:
            if spec.line.source_name or not outgoing:
                parent = _projection_branch(
                    parent,
                    (
                        "source",
                        spec.line.source_name or spec.line.owner_name,
                        spec.line.source_id or spec.line.owner_id,
                    ),
                    spec.source_label,
                    branches,
                )
            parent = _projection_branch(
                parent,
                ("event", spec.line.event_name, spec.line.event_id),
                spec.line.event_name,
                branches,
            )
            leaf_data = spec.leaf.data
        else:
            for original in _branch_path(spec.actor, spec.leaf):
                parent = _projection_branch(
                    parent,
                    ("original", id(original)),
                    _row_identity(original.data, len(header)),
                    branches,
                )
            leaf_data = spec.leaf.data

        leaf = TreeItem(tuple(leaf_data), parent)
        leaf.graph_data = np.array(spec.leaf.graph_data, dtype=np.float64, copy=True)
        parent.append_child(leaf)

    for category in (projected._player, projected._npc):
        for actor in category._children:
            _complete_projection_branch(actor, healing)
    _aggregate_graph_data(projected._root)
    return projected


def _first_matching_rule(
        rules: tuple[WorkbenchRule, ...], rule_type: str,
        line: LogLine) -> tuple[int, WorkbenchRule] | None:
    for index, rule in enumerate(rules):
        if rule.rule_type == rule_type and rule.matches_line(line):
            return index, rule
    return None


def _outgoing_projection_leaf(
        model: TreeModel, line: LogLine,
        group_match: tuple[int, WorkbenchRule] | None,
        reversed_source: bool, header_length: int) -> _ProjectionLeaf:
    actor_key = (line.owner_id,)
    attacker_key = (line.owner_id, line.source_id) if line.source_name else actor_key
    try:
        actor = model.actor_index[actor_key]
        leaf = model.target_index[attacker_key][line.event_name][line.target_id]
    except KeyError as error:
        raise WorkbenchDataError("official outgoing tree is missing a selected event") from error

    if line.source_name:
        source_item = model.pet_index.get(attacker_key)
        source_label = (
            _row_identity(source_item.data, header_length)
            if source_item is not None else line.source_name
        )
    else:
        source_label = _row_identity(actor.data, header_length)
    group_index, group_rule = group_match or (None, None)
    return _ProjectionLeaf(
        line, leaf, actor, actor_key, source_label,
        group_index, group_rule, reversed_source)


def _incoming_projection_leaf(
        model: TreeModel, line: LogLine,
        group_match: tuple[int, WorkbenchRule] | None,
        reversed_source: bool, header_length: int) -> _ProjectionLeaf:
    actor_key = (line.target_id,)
    source_key = line.source_id if line.source_name else line.owner_id
    ability_key = line.source_id + line.event_id
    try:
        actor = model.actor_index[actor_key]
        source_item = model.source_index[actor_key][source_key]
        leaf = model.ability_index[actor_key][source_key][ability_key]
    except KeyError as error:
        raise WorkbenchDataError("official incoming tree is missing a selected event") from error
    source_label = _row_identity(source_item.data, header_length)
    group_index, group_rule = group_match or (None, None)
    return _ProjectionLeaf(
        line, leaf, actor, actor_key, source_label,
        group_index, group_rule, reversed_source)


def _projection_branch(
        parent: TreeItem, key: object, label: object,
        branches: dict[tuple[int, object], TreeItem]) -> TreeItem:
    cache_key = (id(parent), key)
    branch = branches.get(cache_key)
    if branch is None:
        branch = TreeItem(label, parent)
        parent.append_child(branch)
        branches[cache_key] = branch
    return branch


def _branch_path(actor: TreeItem, leaf: TreeItem) -> tuple[TreeItem, ...]:
    path: list[TreeItem] = []
    current = leaf.parent
    while current is not actor:
        if current is None:
            raise WorkbenchDataError("official leaf is detached from its actor")
        path.append(current)
        current = current.parent
    path.reverse()
    return tuple(path)


def _row_identity(data: object, header_length: int) -> object:
    if isinstance(data, tuple) and len(data) == header_length:
        return data[0]
    return data


def _row_with_identity(data: object, identity: object, header_length: int) -> tuple:
    if not isinstance(data, tuple) or len(data) != header_length:
        raise WorkbenchDataError("official leaf does not contain completed parser metrics")
    row = list(data)
    row[0] = identity
    return tuple(row)


def _complete_projection_branch(item: TreeItem, healing: bool) -> None:
    for child in item._children:
        if child._children:
            _complete_projection_branch(child, healing)
    if not item._children:
        return
    if healing:
        combine_children_heal_stats(item)
    else:
        combine_children_damage_stats(item)
    item.graph_data = np.sum(
        [child.graph_data for child in item._children],
        axis=0,
        dtype=np.float64,
    )


def _is_hive_terminal_kill(line: LogLine) -> bool:
    # OSCR evaluates the Queen stop predicate only inside its damage branch.
    if _is_heal_line(line):
        return False
    if "Kill" not in line.flags:
        return False
    return (
        line.target_name == QUEEN_NAME
        or (
            line.target_id == "*"
            and (line.owner_name == QUEEN_NAME or line.source_name == QUEEN_NAME)
        )
    )


def _is_heal_line(line: LogLine) -> bool:
    is_shield_line = line.type == "Shield"
    return (
        (line.type == "HitPoints" and line.magnitude < 0)
        or (is_shield_line and line.magnitude < 0 and line.magnitude2 >= 0)
    )


def _validated_clause_text(value, field: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field} value must be a string")
    value = value.strip()
    if not value:
        raise ValueError(f"{field} value must not be empty")
    return value


def _strict_mapping(
        value: object, label: str, allowed_keys: set[str]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{label} must be a JSON object")
    data = dict(value)
    unknown = set(data) - allowed_keys
    if unknown:
        names = ", ".join(sorted(str(key) for key in unknown))
        raise ValueError(f"{label} contains unknown keys: {names}")
    return data


def _require_keys(data: Mapping[str, Any], label: str, required: set[str]) -> None:
    missing = required - set(data)
    if missing:
        names = ", ".join(sorted(missing))
        raise ValueError(f"{label} is missing required keys: {names}")


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _readonly_text(values) -> NDArray[np.str_]:
    array = np.asarray(tuple(values), dtype=np.str_)
    array.setflags(write=False)
    return array


def _readonly_identity_text(
        names: NDArray[np.str_], identities: NDArray[np.str_]) -> NDArray[np.str_]:
    return _readonly_text(
        f"{name}\n{identity}".casefold()
        for name, identity in zip(names, identities)
    )


def _readonly_array(values, dtype):
    array = np.fromiter(values, dtype=dtype)
    array.setflags(write=False)
    return array


__all__ = (
    "BUNDLED_WORKBENCH_RULE_SET",
    "BUNDLED_WORKBENCH_RULE_SETS",
    "CombatEventIndex",
    "count_effective_events",
    "derive_workbench_combat",
    "WorkbenchCombatView",
    "WorkbenchDataError",
    "WorkbenchFilterClause",
    "WorkbenchIndexCache",
    "WorkbenchQueryResult",
    "WorkbenchRule",
    "WorkbenchRuleMatch",
    "WorkbenchRuleSet",
    "WorkbenchState",
)
