"""Read-only event indexing for Command Console Analysis modifiers.

The Workbench is deliberately downstream of OSCR.  This module snapshots the event stream that
the official parser actually consumed and exposes masks over that snapshot; it never changes a
``Combat``, a ``LogLine``, or one of OSCR's source models.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, replace
from datetime import timedelta
from math import isfinite
from weakref import ReferenceType, WeakKeyDictionary, ref

import numpy as np
from numpy.typing import NDArray

from OSCR.combat import Combat
from OSCR.constants import HEAL_TREE_HEADER, TREE_HEADER
from OSCR.datamodels import LogLine, TreeModel
from OSCR.parser import analyze_combat


QUEEN_NAME = "Borg Queen Octahedron"
HIVE_INTRO_ENTITY = "Space_Borg_Dreadnought_Hive_Intro"


class WorkbenchDataError(ValueError):
    """Raised when a combat is not ready to be indexed safely."""


@dataclass(frozen=True, slots=True)
class WorkbenchState:
    """The complete, default-off modifier state shared by all four Analysis modes."""

    owner_query: str = ""
    source_query: str = ""
    target_query: str = ""
    event_query: str = ""
    text_query: str = ""
    start_seconds: float | None = None
    end_seconds: float | None = None

    def __post_init__(self) -> None:
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
            self.start_seconds is not None,
            self.end_seconds is not None,
        ))

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
        self.magnitudes2 = _readonly_array(
            (line.magnitude2 for line in self.lines), np.float64)

        # Case-fold once.  Querying then remains a small set of NumPy mask operations.
        # A field's visible label and stable parser identity are one search surface.  This
        # makes account handles/entity IDs discoverable without changing display values.
        self._owner_search = _readonly_identity_text(self.owner_names, self.owner_ids)
        self._source_search = _readonly_identity_text(self.source_names, self.source_ids)
        self._target_search = _readonly_identity_text(self.target_names, self.target_ids)
        self._event_search = _readonly_identity_text(self.event_names, self.event_ids)

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

        if state.start_seconds is not None:
            mask &= self.elapsed_seconds >= state.start_seconds
        if state.end_seconds is not None:
            mask &= self.elapsed_seconds <= state.end_seconds

        mask.setflags(write=False)
        return WorkbenchQueryResult(self, state, mask)


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
    "CombatEventIndex",
    "count_effective_events",
    "derive_workbench_combat",
    "WorkbenchCombatView",
    "WorkbenchDataError",
    "WorkbenchIndexCache",
    "WorkbenchQueryResult",
    "WorkbenchState",
)
