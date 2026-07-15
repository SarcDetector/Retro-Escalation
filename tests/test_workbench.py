from collections import deque
from dataclasses import replace
from datetime import datetime, timedelta
import unittest
from unittest.mock import patch

import numpy as np

from OSCR.combat import Combat
from OSCR.datamodels import LogLine
from OSCR.parser import analyze_combat

from re_oscr.workbench import (
    BUNDLED_WORKBENCH_RULE_SETS,
    CombatEventIndex,
    derive_workbench_combat,
    WorkbenchDataError,
    WorkbenchFilterClause,
    WorkbenchIndexCache,
    WorkbenchRule,
    WorkbenchRuleMatch,
    WorkbenchRuleSet,
    WorkbenchState,
)


ORIGIN = datetime(2026, 7, 14, 12, 0, 0)


def make_line(
        seconds: float, *, owner_name: str = "Alice", owner_id: str = "P[1]",
        source_name: str = "", source_id: str = "", target_name: str = "Target",
        target_id: str = "C[1 Target]", event_name: str = "Beam", event_id: str = "Beam",
        event_type: str = "HitPoints", flags: str = "", magnitude: float = 100.0,
        magnitude2: float = 100.0) -> LogLine:
    return LogLine(
        timestamp=ORIGIN + timedelta(seconds=seconds),
        owner_name=owner_name,
        owner_id=owner_id,
        source_name=source_name,
        source_id=source_id,
        target_name=target_name,
        target_id=target_id,
        event_name=event_name,
        event_id=event_id,
        type=event_type,
        flags=flags,
        magnitude=float(magnitude),
        magnitude2=float(magnitude2),
    )


def make_combat(
        lines: list[LogLine], *, start_seconds: float = 0.0, end_seconds: float = 10.0,
        map_name: str = "Infected Space", combat_id: int = 0) -> Combat:
    combat = Combat(id=combat_id, log_file="synthetic.log")
    combat.start_time = ORIGIN + timedelta(seconds=start_seconds)
    combat.end_time = ORIGIN + timedelta(seconds=end_seconds)
    combat.map = map_name
    combat.log_data = deque(lines)
    return combat


def iter_identity_tree_items(model):
    pending = [model._player, model._npc]
    while pending:
        item = pending.pop()
        yield item
        pending.extend(item._children)


def tree_label(item) -> str:
    data = item.data
    if isinstance(data, tuple) and len(data) in (14, 22):
        data = data[0]
    if isinstance(data, tuple):
        return "".join(str(part) for part in data[:2])
    return str(data)


def child_with_label(item, label: str):
    return next(child for child in item._children if tree_label(child) == label)


class WorkbenchStateTests(unittest.TestCase):
    def test_default_state_is_parser_truth_and_changes_do_not_mutate_it(self):
        state = WorkbenchState.parser_truth()

        self.assertFalse(state.is_modified)
        changed = state.with_changes(text_query="beam", start_seconds=1.0)
        self.assertTrue(changed.is_modified)
        self.assertEqual(state, WorkbenchState())

    def test_invalid_time_windows_are_rejected(self):
        with self.assertRaises(ValueError):
            WorkbenchState(start_seconds=3.0, end_seconds=2.0)
        with self.assertRaises(ValueError):
            WorkbenchState(start_seconds=float("inf"))
        with self.assertRaises(ValueError):
            WorkbenchState(end_seconds=-0.01)

    def test_structured_clauses_are_immutable_normalized_and_mark_state_modified(self):
        clause = WorkbenchFilterClause(" min_magnitude ", "1000")
        state = WorkbenchState(clauses=[clause])

        self.assertEqual(clause.field, "MAGNITUDE")
        self.assertEqual(clause.operator, "GTE")
        self.assertEqual(clause.value, 1000.0)
        self.assertEqual(clause.display_label, "|MAG| ≥ 1000")
        self.assertEqual(clause.summary, clause.display_label)
        self.assertEqual(state.clauses, (clause,))
        self.assertTrue(state.is_modified)
        self.assertFalse(WorkbenchState.parser_truth().is_modified)

        with self.assertRaisesRegex(TypeError, "WorkbenchFilterClause"):
            WorkbenchState(clauses=("not a clause",))

    def test_structured_clause_validation_rejects_ambiguous_or_unsafe_values(self):
        invalid = (
            lambda: WorkbenchFilterClause("OWNER", ""),
            lambda: WorkbenchFilterClause("UNKNOWN", "value"),
            lambda: WorkbenchFilterClause("OWNER", "Alice", "EXACT"),
            lambda: WorkbenchFilterClause("TYPE", "HitPoints", "GTE"),
            lambda: WorkbenchFilterClause("FLAG", "Flank"),
            lambda: WorkbenchFilterClause("MIN", -1),
            lambda: WorkbenchFilterClause("MAX", float("nan")),
            lambda: WorkbenchFilterClause("MIN", True),
            lambda: WorkbenchFilterClause("MAGNITUDE", 5),
        )
        for construct in invalid:
            with self.subTest(construct=construct):
                with self.assertRaises((TypeError, ValueError)):
                    construct()

    def test_type_and_flag_clauses_expose_normalized_operator_semantics(self):
        exact_type = WorkbenchFilterClause("type", " HitPoints ")
        contains_type = WorkbenchFilterClause("TYPE", "point", "contains")
        flag = WorkbenchFilterClause("flag", "cRiTiCaL")
        maximum = WorkbenchFilterClause("MAX", 42)

        self.assertEqual((exact_type.field, exact_type.operator, exact_type.value), (
            "TYPE", "EXACT", "HitPoints"))
        self.assertEqual(contains_type.operator, "CONTAINS")
        self.assertEqual((flag.operator, flag.value), ("HAS", "Critical"))
        self.assertEqual((maximum.field, maximum.operator, maximum.value), (
            "MAGNITUDE", "LTE", 42.0))

    def test_only_enabled_rules_mark_state_modified(self):
        disabled = WorkbenchRule(
            "group", WorkbenchRuleMatch("event", "Beam"), "Beams")
        enabled = replace(disabled, enabled=True)

        self.assertFalse(WorkbenchState(rules=(disabled,)).is_modified)
        state = WorkbenchState(rules=[disabled, enabled])
        self.assertTrue(state.is_modified)
        self.assertEqual(state.rules, (disabled, enabled))
        self.assertEqual(state.active_rules, (enabled,))

        with self.assertRaisesRegex(TypeError, "WorkbenchRule"):
            WorkbenchState(rules=("unsafe",))

    def test_disabled_rules_keep_the_exact_parser_truth_combat(self):
        source = analyze_combat(make_combat([make_line(0, event_name="Beam Array")]))
        disabled = WorkbenchRule(
            "GROUP", WorkbenchRuleMatch("EVENT", "Beam*"), "Beams")

        view = derive_workbench_combat(
            CombatEventIndex(source).query(WorkbenchState(rules=(disabled,))))

        self.assertIs(view.combat, source)
        self.assertIs(view.source_combat, source)
        self.assertFalse(view.is_modified)


class WorkbenchRuleTests(unittest.TestCase):
    def test_matchers_normalize_fields_and_use_anchored_literal_star_globs(self):
        exact = WorkbenchRuleMatch(" event_name ", " beam?i ")
        wildcard = WorkbenchRuleMatch("SOURCE_NAME", "drone *")
        line = make_line(
            0, event_name="Beam?I", source_name="Drone Alpha", source_id="C[drone]")

        self.assertEqual((exact.field, exact.pattern, exact.mode), (
            "EVENT", "beam?i", "EXACT"))
        self.assertTrue(exact.matches(line))
        self.assertFalse(exact.matches(line._replace(event_name="BeamXI")))
        self.assertTrue(wildcard.matches(line))
        self.assertFalse(wildcard.matches(line._replace(source_name="My Drone Alpha")))

    def test_rule_set_accepts_singular_and_multiple_matches_and_round_trips(self):
        value = {
            "name": "ISE rules",
            "version": 1,
            "rules": [
                {
                    "type": "group",
                    "matches": [
                        {"field": "event_name", "pattern": "Advanced Piezo*"},
                        {"field": "event_name", "pattern": "Technical Overload"},
                    ],
                    "label": "Advanced Piezo Beam Array",
                    "enabled": True,
                },
                {
                    "type": "reverse",
                    "match": {"field": "source_name", "pattern": "Tachyon Drone*"},
                    "enabled": False,
                },
            ],
        }

        rule_set = WorkbenchRuleSet.from_dict(value)
        restored = WorkbenchRuleSet.from_json(rule_set.to_json())

        self.assertEqual(restored, rule_set)
        self.assertEqual(rule_set.rules[0].display_label, (
            "GROUP: Advanced Piezo Beam Array"))
        self.assertEqual(rule_set.rules[1].display_label, "REVERSE: Tachyon Drone*")
        self.assertIn("matches", rule_set.to_dict()["rules"][0])
        self.assertIn("match", rule_set.to_dict()["rules"][1])

    def test_rule_set_json_validation_is_strict_and_transaction_safe(self):
        invalid_values = (
            {"name": "Rules", "version": 2, "rules": []},
            {"name": "Rules", "version": 1, "rules": [], "code": "run()"},
            {
                "name": "Rules", "version": 1,
                "rules": [{
                    "type": "group",
                    "match": {"field": "target_name", "pattern": "Target"},
                    "label": "Targets",
                }],
            },
            {
                "name": "Rules", "version": 1,
                "rules": [{
                    "type": "reverse",
                    "match": {"field": "event_name", "pattern": "Beam"},
                    "matches": [{"field": "event_name", "pattern": "Beam"}],
                }],
            },
            {
                "name": "Rules", "version": 1,
                "rules": [{
                    "type": "group",
                    "match": {"field": "event_name", "pattern": "Beam"},
                    "label": "",
                }],
            },
        )
        for value in invalid_values:
            with self.subTest(value=value):
                with self.assertRaises((TypeError, ValueError)):
                    WorkbenchRuleSet.from_dict(value)

        with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
            WorkbenchRuleSet.from_json(
                '{"name":"First","name":"Second","version":1,"rules":[]}')

    def test_bundled_examples_are_read_only_ordered_and_default_off(self):
        self.assertEqual(len(BUNDLED_WORKBENCH_RULE_SETS), 1)
        bundled = BUNDLED_WORKBENCH_RULE_SETS[0]
        self.assertTrue(bundled.read_only)
        self.assertEqual(
            [rule.label for rule in bundled.rules[:2]],
            ["Advanced Piezo Beam Array", "Tachyon Net Drones"],
        )
        self.assertTrue(all(not rule.enabled for rule in bundled.rules))


class CombatEventIndexTests(unittest.TestCase):
    def test_snapshot_uses_inclusive_official_bounds_and_preserves_source_order(self):
        lines = [
            make_line(-1, event_name="Before"),
            make_line(0, event_name="Start"),
            make_line(5, event_name="Middle A"),
            make_line(5, event_name="Middle B"),
            make_line(10, event_name="End"),
            make_line(11, event_name="After"),
        ]
        combat = make_combat(lines)

        index = CombatEventIndex(combat)

        self.assertEqual(
            [line.event_name for line in index.lines],
            ["Start", "Middle A", "Middle B", "End"],
        )
        np.testing.assert_array_equal(index.source_ordinals, [1, 2, 3, 4])
        np.testing.assert_allclose(index.elapsed_seconds, [0.0, 5.0, 5.0, 10.0])

    def test_snapshot_arrays_and_results_are_read_only_and_detached(self):
        combat = make_combat([make_line(0), make_line(1)])
        index = CombatEventIndex(combat)
        result = index.query()

        with self.assertRaises(ValueError):
            index.magnitudes[0] = 999
        with self.assertRaises(ValueError):
            result.mask[0] = False
        with self.assertRaises(ValueError):
            result.source_ordinals[0] = 99

        combat.log_data.append(make_line(2, event_name="Appended"))
        self.assertEqual(len(index), 2)
        self.assertEqual(result.count, 2)

    def test_queries_compose_with_and_semantics_and_inclusive_time_bounds(self):
        combat = make_combat([
            make_line(
                1, owner_name="Alice", source_name="Drone Alpha",
                target_name="Gateway", event_name="Plasma Beam"),
            make_line(
                2, owner_name="Alice", source_name="Drone Beta",
                target_name="Gateway", event_name="Plasma Torpedo"),
            make_line(
                3, owner_name="Bob", source_name="Drone Alpha",
                target_name="Sphere", event_name="Plasma Beam"),
            make_line(
                4, owner_name="Alice", source_name="Drone Alpha",
                target_name="Gateway", event_name="Phaser Beam"),
        ])
        index = CombatEventIndex(combat)
        state = WorkbenchState(
            owner_query="ALIce",
            source_query="alpha",
            target_query="gate",
            event_query="beam",
            text_query="plasma",
            start_seconds=1.0,
            end_seconds=1.0,
        )

        result = index.query(state)

        self.assertEqual(result.count, 1)
        self.assertEqual(result.lines[0].event_name, "Plasma Beam")
        np.testing.assert_array_equal(result.source_ordinals, [0])

    def test_free_text_searches_all_name_fields_and_empty_results_are_safe(self):
        index = CombatEventIndex(make_combat([
            make_line(1, owner_name="Captain Nova"),
            make_line(2, source_name="Hangar Pet"),
            make_line(3, target_name="Nanite Sphere"),
            make_line(4, event_name="Focused Burst"),
        ]))

        self.assertEqual(index.query(WorkbenchState(text_query="sphere")).count, 1)
        empty = index.query(WorkbenchState(owner_query="missing"))
        self.assertEqual(empty.count, 0)
        self.assertEqual(empty.lines, ())
        self.assertEqual(empty.mask.shape, (4,))

    def test_scoped_and_free_text_search_visible_names_and_parser_ids(self):
        index = CombatEventIndex(make_combat([
            make_line(
                1, owner_name="Captain Nova", owner_id="P[7@nova#1234]",
                source_name="Hangar Pet", source_id="C[44 Pet_Entity]",
                target_name="Nanite Sphere", target_id="C[88 Borg_Target]",
                event_name="Focused Burst", event_id="Power_Focused_Burst"),
        ]))

        self.assertEqual(index.query(WorkbenchState(owner_query="@nova#1234")).count, 1)
        self.assertEqual(index.query(WorkbenchState(source_query="pet_entity")).count, 1)
        self.assertEqual(index.query(WorkbenchState(target_query="borg_target")).count, 1)
        self.assertEqual(index.query(WorkbenchState(event_query="power_focused")).count, 1)
        self.assertEqual(index.query(WorkbenchState(text_query="@nova#1234")).count, 1)

    def test_structured_identity_clauses_compose_with_quick_filters_and_search_ids(self):
        index = CombatEventIndex(make_combat([
            make_line(
                1, owner_name="Captain Nova", owner_id="P[7@nova#1234]",
                source_name="Hangar Pet", source_id="C[44 Pet_Entity]",
                target_name="Nanite Sphere", target_id="C[88 Borg_Target]",
                event_name="Focused Burst", event_id="Power_Focused_Burst"),
            make_line(
                2, owner_name="Captain Nova", owner_id="P[7@nova#1234]",
                source_name="Hangar Pet", source_id="C[44 Pet_Entity]",
                target_name="Gateway", target_id="C[99 Gateway]",
                event_name="Focused Burst", event_id="Power_Focused_Burst"),
            make_line(3, owner_name="Someone Else", event_name="Focused Burst"),
        ]))
        state = WorkbenchState(
            owner_query="nova",
            clauses=(
                WorkbenchFilterClause("ANY", "pet_entity"),
                WorkbenchFilterClause("OWNER", "@NOVA#1234"),
                WorkbenchFilterClause("SOURCE", "hangar"),
                WorkbenchFilterClause("TARGET", "borg_target"),
                WorkbenchFilterClause("EVENT", "power_focused"),
            ),
        )

        result = index.query(state)

        self.assertEqual(result.count, 1)
        self.assertEqual(result.lines[0].target_name, "Nanite Sphere")

    def test_structured_type_flag_and_absolute_magnitude_clauses_are_inclusive(self):
        index = CombatEventIndex(make_combat([
            make_line(
                1, event_type="HitPoints", flags=" Critical | Kill ", magnitude=100),
            make_line(
                2, event_type="HitPoints", flags="CriticalFailure", magnitude=-150),
            make_line(
                3, event_type="Shield", flags="critical", magnitude=-200),
            make_line(
                4, event_type="HitPoints", flags="Miss", magnitude=250),
        ]))
        state = WorkbenchState(clauses=(
            WorkbenchFilterClause("TYPE", "hitpoints"),
            WorkbenchFilterClause("FLAG", "critical"),
            WorkbenchFilterClause("MIN", 100),
            WorkbenchFilterClause("MAX_MAGNITUDE", "100"),
        ))

        result = index.query(state)

        self.assertEqual(result.count, 1)
        self.assertEqual(result.lines[0].magnitude, 100.0)
        self.assertEqual(index.query(WorkbenchState(clauses=(
            WorkbenchFilterClause("TYPE", "point", "CONTAINS"),
        ))).count, 3)

    def test_new_structured_arrays_are_read_only(self):
        index = CombatEventIndex(make_combat([
            make_line(1, flags="Critical", magnitude=-10),
        ]))

        with self.assertRaises(ValueError):
            index.absolute_magnitudes[0] = 20
        for _flag, matches in index._flag_matches:
            with self.assertRaises(ValueError):
                matches[0] = False

    def test_hive_snapshot_stops_at_terminal_queen_kill_ordinal(self):
        queen_kill = make_line(
            10, target_name="Borg Queen Octahedron", target_id="C[queen]",
            event_name="Terminal Hit", flags="Critical|Kill")
        same_timestamp_tail = make_line(10, event_name="Same Timestamp Tail", magnitude=9_999_999)
        combat = make_combat([
            make_line(0, target_id="C[377 Space_Borg_Dreadnought_Hive_Intro]"),
            queen_kill,
            same_timestamp_tail,
            make_line(11, event_name="Later Tail", magnitude=9_999_999),
        ], map_name="Hive Space")

        index = CombatEventIndex(combat)

        self.assertEqual([line.event_name for line in index.lines], ["Beam", "Terminal Hit"])
        self.assertEqual(len(combat.log_data), 4)

    def test_hive_detection_does_not_look_ahead_past_an_earlier_queen_kill(self):
        combat = make_combat([
            make_line(
                0, target_name="Borg Queen Octahedron", target_id="C[first queen]",
                event_name="Early Queen", flags="Kill"),
            make_line(
                1, target_id="C[377 Space_Borg_Dreadnought_Hive_Intro]",
                event_name="Intro"),
            make_line(2, event_name="After Intro"),
            make_line(
                3, target_name="Borg Queen Octahedron", target_id="C[second queen]",
                event_name="Terminal Queen", flags="Kill"),
            make_line(4, event_name="Excluded Tail"),
        ], end_seconds=4, map_name="Hive Space")

        self.assertEqual(
            [line.event_name for line in CombatEventIndex(combat).lines],
            ["Early Queen", "Intro", "After Intro", "Terminal Queen"],
        )

    def test_non_hive_queen_event_does_not_truncate_equal_timestamp_lines(self):
        combat = make_combat([
            make_line(
                10, target_name="Borg Queen Octahedron", event_name="Queen",
                flags="Kill"),
            make_line(10, event_name="Still Included"),
        ], start_seconds=10, end_seconds=10, map_name="Other")

        self.assertEqual(len(CombatEventIndex(combat)), 2)

    def test_hive_detection_uses_parser_entity_semantics_not_display_label(self):
        combat = make_combat([
            make_line(
                10, target_id="C[377 Space_Borg_Dreadnought_Hive_Intro]",
                event_name="Intro"),
            make_line(
                10, target_name="Borg Queen Octahedron", event_name="Terminal",
                flags="Kill"),
            make_line(10, event_name="Excluded"),
        ], start_seconds=10, end_seconds=10, map_name="Stale Display Label")

        self.assertEqual(
            [line.event_name for line in CombatEventIndex(combat).lines],
            ["Intro", "Terminal"],
        )

    def test_hive_heal_with_kill_flag_does_not_trigger_damage_branch_stop(self):
        combat = make_combat([
            make_line(
                10, target_id="C[377 Space_Borg_Dreadnought_Hive_Intro]",
                event_name="Intro"),
            make_line(
                10, target_name="Borg Queen Octahedron", event_name="Queen Heal",
                event_type="HitPoints", flags="Kill", magnitude=-100, magnitude2=0),
            make_line(10, event_name="Still Included"),
        ], start_seconds=10, end_seconds=10, map_name="Hive Space")

        self.assertEqual(len(CombatEventIndex(combat)), 3)

    def test_unfinished_or_reversed_combats_are_rejected(self):
        combat = Combat()
        with self.assertRaises(WorkbenchDataError):
            CombatEventIndex(combat)
        combat.start_time = ORIGIN + timedelta(seconds=2)
        combat.end_time = ORIGIN + timedelta(seconds=1)
        with self.assertRaises(WorkbenchDataError):
            CombatEventIndex(combat)


class WorkbenchIndexCacheTests(unittest.TestCase):
    def test_cache_is_lazy_identity_based_and_individually_invalidated(self):
        first = make_combat([make_line(0, event_name="First")], combat_id=7)
        second = make_combat([make_line(0, event_name="Second")], combat_id=7)
        cache = WorkbenchIndexCache()

        first_index = cache.get(first)
        self.assertIs(cache.get(first), first_index)
        self.assertIsNot(cache.get(second), first_index)
        self.assertEqual(len(cache), 2)

        cache.invalidate(first)
        self.assertEqual(len(cache), 1)
        self.assertIsNot(cache.get(first), first_index)
        cache.clear()
        self.assertEqual(len(cache), 0)


class WorkbenchCombatDerivationTests(unittest.TestCase):
    def test_parser_truth_uses_source_combat_and_is_never_a_league_source(self):
        source = analyze_combat(make_combat([make_line(0), make_line(1)]))

        view = derive_workbench_combat(CombatEventIndex(source).query())

        self.assertIs(view.source_combat, source)
        self.assertIs(view.combat, source)
        self.assertFalse(view.is_modified)
        self.assertFalse(view.league_eligible)

    def test_modified_full_selection_has_parser_parity_and_no_upload_coordinates(self):
        source = make_combat(
            [make_line(0), make_line(1)], combat_id=12, map_name="Reference Map")
        source.file_pos = [123, 456]
        source.difficulty = "Elite"
        analyze_combat(source)
        source.map = "Reference Map"
        source.difficulty = "Elite"

        result = CombatEventIndex(source).query(WorkbenchState(event_query="beam"))
        view = derive_workbench_combat(result)
        derived = view.combat

        self.assertIsNot(derived, source)
        self.assertTrue(view.is_modified)
        self.assertFalse(view.league_eligible)
        self.assertEqual(derived.get_export(), source.get_export())
        self.assertEqual(
            (derived.id, derived.map, derived.difficulty),
            (source.id, source.map, source.difficulty),
        )
        self.assertEqual(derived.log_file, '')
        self.assertEqual(derived.file_pos, [None, None])

    def test_modified_derivation_does_not_mutate_or_share_source_containers(self):
        source = analyze_combat(make_combat([make_line(0), make_line(1), make_line(2)]))
        source.file_pos = [10, 20]
        source_lines = tuple(source.log_data)
        source_file_pos = list(source.file_pos)
        source_meta = {
            key: tuple(value) if isinstance(value, list) else value
            for key, value in source.meta.items()
        }
        source_roots = source.root_items

        view = derive_workbench_combat(
            CombatEventIndex(source).query(WorkbenchState(start_seconds=1.0)))
        derived = view.combat

        self.assertEqual(tuple(source.log_data), source_lines)
        self.assertEqual(source.file_pos, source_file_pos)
        self.assertEqual({
            key: tuple(value) if isinstance(value, list) else value
            for key, value in source.meta.items()
        }, source_meta)
        self.assertEqual(source.root_items, source_roots)
        self.assertIsNot(derived.log_data, source.log_data)
        for derived_model, source_model in zip(
                (derived.damage_out, derived.damage_in, derived.heals_out, derived.heals_in),
                (source.damage_out, source.damage_in, source.heals_out, source.heals_in)):
            self.assertIsNot(derived_model, source_model)
            self.assertIsNot(derived_model._root, source_model._root)
        for name in ("meta", "players", "critters", "overview_graphs"):
            self.assertIsNot(getattr(derived, name), getattr(source, name))

    def test_empty_modified_selection_builds_four_safe_empty_models(self):
        source = analyze_combat(make_combat([make_line(0), make_line(1)]))
        result = CombatEventIndex(source).query(WorkbenchState(owner_query="missing"))

        with patch("re_oscr.workbench.analyze_combat") as analyzer:
            view = derive_workbench_combat(result)

        analyzer.assert_not_called()
        self.assertTrue(view.is_modified)
        self.assertIsNot(view.combat, source)
        for model in (
                view.combat.damage_out, view.combat.damage_in,
                view.combat.heals_out, view.combat.heals_in):
            self.assertIsNotNone(model._root)
            self.assertEqual(model._root.child_count, 2)
            self.assertEqual(model._player.child_count, 0)
            self.assertEqual(model._npc.child_count, 0)

    def test_time_cuts_are_inclusive_and_filters_do_not_shrink_outer_bounds(self):
        source = analyze_combat(make_combat([
            make_line(0, owner_name="Other"),
            make_line(2),
            make_line(5),
            make_line(8),
            make_line(10, owner_name="Other"),
        ]))
        index = CombatEventIndex(source)

        cut = derive_workbench_combat(index.query(WorkbenchState(
            owner_query="Alice", start_seconds=2.0, end_seconds=8.0))).combat
        self.assertEqual([line.timestamp for line in cut.log_data], [
            ORIGIN + timedelta(seconds=2),
            ORIGIN + timedelta(seconds=5),
            ORIGIN + timedelta(seconds=8),
        ])
        self.assertEqual(cut.start_time, ORIGIN + timedelta(seconds=2))
        self.assertEqual(cut.end_time, ORIGIN + timedelta(seconds=8))

        filtered = derive_workbench_combat(
            index.query(WorkbenchState(owner_query="Alice"))).combat
        self.assertEqual(filtered.start_time, source.start_time)
        self.assertEqual(filtered.end_time, source.end_time)

    def test_filtered_graphs_keep_fractional_events_on_the_display_window_timeline(self):
        source = analyze_combat(make_combat([
            make_line(0, owner_name="Other", event_name="Boundary"),
            make_line(5.4, event_name="Focused", event_id="Focused Damage", magnitude=100),
            make_line(
                6.2, event_name="Focused", event_id="Focused Heal",
                event_type="HitPoints", magnitude=-200, magnitude2=0),
            make_line(10, owner_name="Other", event_name="Boundary"),
        ]))
        derived = derive_workbench_combat(CombatEventIndex(source).query(WorkbenchState(
            event_query="focused", start_seconds=3.0, end_seconds=10.0,
        ))).combat

        expectations = (
            (derived.damage_out, 2, 100.0),
            (derived.damage_in, 2, 100.0),
            (derived.heals_out, 3, 200.0),
            (derived.heals_in, 3, 200.0),
        )
        for model, expected_second, expected_magnitude in expectations:
            populated_items = 0
            for item in iter_identity_tree_items(model):
                self.assertEqual(len(item.graph_data), 8)
                if not np.any(item.graph_data):
                    continue
                populated_items += 1
                np.testing.assert_array_equal(
                    np.flatnonzero(item.graph_data), [expected_second])
                self.assertEqual(item.graph_data[expected_second], expected_magnitude)
            self.assertGreater(populated_items, 0)

    def test_hive_derivation_stops_at_terminal_ordinal_and_preserves_source(self):
        source = make_combat([
            make_line(0, target_id="C[377 Space_Borg_Dreadnought_Hive_Intro]"),
            make_line(
                10, target_name="Borg Queen Octahedron", target_id="C[queen Borg_Queen]",
                event_name="Terminal Hit", flags="Critical|Kill"),
            make_line(10, event_name="Same Timestamp Tail"),
            make_line(11, event_name="Later Tail"),
        ], end_seconds=11, map_name="Hive Space")
        analyze_combat(source)
        source.map = "Hive Space"
        source_lines = tuple(source.log_data)

        derived = derive_workbench_combat(
            CombatEventIndex(source).query(WorkbenchState(text_query="i"))).combat

        self.assertEqual(
            [line.event_name for line in derived.log_data], ["Beam", "Terminal Hit"])
        self.assertEqual(tuple(source.log_data), source_lines)
        self.assertIsNot(derived.damage_out, source.damage_out)

    def test_custom_group_preserves_original_effect_children_totals_and_graphs(self):
        source = analyze_combat(make_combat([
            make_line(
                0, event_name="Advanced Piezo Beam", event_id="Piezo",
                magnitude=100, flags="Critical"),
            make_line(
                1, event_name="Technical Overload", event_id="Overload",
                magnitude=250),
            make_line(2, event_name="Other Beam", event_id="Other", magnitude=50),
        ]))
        source_lines = tuple(source.log_data)
        source_root = source.damage_out._root
        source_actor = source.damage_out._player._children[0]
        rule = WorkbenchRule(
            "group",
            (
                WorkbenchRuleMatch("event", "Advanced Piezo*"),
                WorkbenchRuleMatch("event", "Technical Overload"),
            ),
            "Advanced Piezo Beam Array",
            True,
        )
        result = CombatEventIndex(source).query(WorkbenchState(rules=(rule,)))

        derived = derive_workbench_combat(result).combat
        actor = derived.damage_out._player._children[0]
        group = child_with_label(actor, "Advanced Piezo Beam Array")

        self.assertEqual(result.count, 3)
        self.assertEqual(
            [tree_label(child) for child in group._children],
            ["Advanced Piezo Beam", "Technical Overload"],
        )
        self.assertEqual(tree_label(group._children[0]._children[0]), "Target 1")
        self.assertEqual(actor.data[1:], source_actor.data[1:])
        np.testing.assert_array_equal(actor.graph_data, source_actor.graph_data)
        self.assertEqual(tuple(source.log_data), source_lines)
        self.assertIs(source.damage_out._root, source_root)
        self.assertIsNot(derived.damage_out, source.damage_out)

    def test_reverse_and_group_compose_for_all_four_analysis_models(self):
        lines = [
            make_line(
                0, source_name="Drone Alpha", source_id="C[10 Drone]",
                target_name="Target", target_id="C[1 Target]",
                event_name="Tachyon Net Drones", event_id="Tachyon", magnitude=100),
            make_line(
                1, source_name="Drone Beta", source_id="C[11 Drone]",
                target_name="Target", target_id="C[1 Target]",
                event_name="Tachyon Net Drones", event_id="Tachyon", magnitude=200),
            make_line(
                2, source_name="Drone Alpha", source_id="C[10 Drone]",
                target_name="Ally", target_id="P[2]",
                event_name="Tachyon Net Drones", event_id="Tachyon Heal",
                event_type="HitPoints", magnitude=-30, magnitude2=0),
            make_line(
                3, source_name="Drone Beta", source_id="C[11 Drone]",
                target_name="Ally", target_id="P[2]",
                event_name="Tachyon Net Drones", event_id="Tachyon Heal",
                event_type="HitPoints", magnitude=-70, magnitude2=0),
        ]
        source = analyze_combat(make_combat(lines))
        original_models = (
            source.damage_out, source.damage_in, source.heals_out, source.heals_in)
        group = WorkbenchRule(
            "GROUP", WorkbenchRuleMatch("EVENT", "Tachyon Net*"),
            "Tachyon Systems", True)
        reverse = WorkbenchRule(
            "REVERSE", WorkbenchRuleMatch("EVENT", "Tachyon Net*"),
            "Tachyon Net Drones", True)

        derived = derive_workbench_combat(CombatEventIndex(source).query(
            WorkbenchState(rules=(group, reverse)))).combat

        actor_specs = (
            (original_models[0]._player._children[0], derived.damage_out._player._children[0]),
            (original_models[1]._npc._children[0], derived.damage_in._npc._children[0]),
            (original_models[2]._player._children[0], derived.heals_out._player._children[0]),
            (original_models[3]._player._children[0], derived.heals_in._player._children[0]),
        )
        for original_actor, projected_actor in actor_specs:
            with self.subTest(actor=tree_label(projected_actor)):
                wrapper = child_with_label(projected_actor, "Tachyon Systems")
                effect = child_with_label(wrapper, "Tachyon Net Drones")
                self.assertEqual(len(effect._children), 2)
                source_labels = {tree_label(child) for child in effect._children}
                self.assertTrue(any(
                    label.startswith("Drone Alpha") for label in source_labels))
                self.assertTrue(any(
                    label.startswith("Drone Beta") for label in source_labels))
                self.assertEqual(projected_actor.data[1:], original_actor.data[1:])
                np.testing.assert_array_equal(
                    projected_actor.graph_data, original_actor.graph_data)

        # Outgoing reversal retains target leaves; incoming reversal ends at source rows.
        damage_out_effect = child_with_label(
            child_with_label(derived.damage_out._player._children[0], "Tachyon Systems"),
            "Tachyon Net Drones",
        )
        self.assertTrue(all(source_row.child_count == 1 for source_row in damage_out_effect._children))
        damage_in_effect = child_with_label(
            child_with_label(derived.damage_in._npc._children[0], "Tachyon Systems"),
            "Tachyon Net Drones",
        )
        self.assertTrue(all(source_row.child_count == 0 for source_row in damage_in_effect._children))

    def test_first_enabled_group_rule_wins_and_reordering_is_deterministic(self):
        source = analyze_combat(make_combat([make_line(0, event_name="Beam Array")]))
        broad = WorkbenchRule(
            "GROUP", WorkbenchRuleMatch("EVENT", "Beam*"), "Broad", True)
        exact = WorkbenchRule(
            "GROUP", WorkbenchRuleMatch("EVENT", "Beam Array"), "Exact", True)
        index = CombatEventIndex(source)

        broad_first = derive_workbench_combat(
            index.query(WorkbenchState(rules=(broad, exact)))).combat
        exact_first = derive_workbench_combat(
            index.query(WorkbenchState(rules=(exact, broad)))).combat

        self.assertEqual(
            tree_label(broad_first.damage_out._player._children[0]._children[0]), "Broad")
        self.assertEqual(
            tree_label(exact_first.damage_out._player._children[0]._children[0]), "Exact")
        self.assertEqual(
            broad_first.damage_out._player._children[0].data[2],
            exact_first.damage_out._player._children[0].data[2],
        )


if __name__ == "__main__":
    unittest.main()
