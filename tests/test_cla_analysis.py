"""Synthetic conformance checks for the dev16 CLA calculation slices."""

import json
import unittest

from re_oscr.clacoprocessor import (
    DAMAGE_METRIC_IDS,
    HEAL_METRIC_IDS,
    SUMMARY_METRIC_IDS,
    analyze_cla_profile,
)
from re_oscr.workbench import CombatEventIndex
from tests.test_workbench import make_combat, make_line


PRODUCT_VERSION = "11.1.0.dev16"
ALICE_ID = "P[1@10 Alice@pilot]"
ALLY_ID = "P[2@20 Ally@pilot]"


def analysis(lines):
    index = CombatEventIndex(make_combat(lines, end_seconds=20.0))
    return analyze_cla_profile(
        index.snapshot_json,
        index.snapshot_id,
        product_version=PRODUCT_VERSION,
    )


def player(result, name):
    return next(item for item in result.players if item.player == name)


class ClaAnalysisTests(unittest.TestCase):
    def test_all_scalar_slices_clocks_and_summary(self):
        result = analysis([
            make_line(
                1, owner_id=ALICE_ID, event_name="Beam", event_type="HitPoints",
                flags="Critical|Flank|Kill", magnitude=100, magnitude2=100),
            make_line(
                2, owner_id=ALICE_ID, event_name="Beam", event_type="Shield",
                magnitude=40, magnitude2=20),
            make_line(
                3, owner_id=ALICE_ID, event_name="Beam", event_type="Shield",
                magnitude=30, magnitude2=0),
            make_line(
                4, owner_id=ALICE_ID, event_name="Beam", event_type="HitPoints",
                flags="Immune|Critical|Miss|Kill", magnitude=999, magnitude2=999),
            make_line(
                5, owner_id=ALICE_ID, event_name="Beam", event_type="HitPoints",
                flags="Critical|Miss", magnitude=0, magnitude2=0),
            make_line(
                6, owner_id=ALICE_ID, target_name="Ally", target_id=ALLY_ID,
                event_name="Restore", event_type="HitPoints",
                magnitude=-80, magnitude2=0),
            make_line(
                7, owner_id=ALICE_ID, target_name="Ally", target_id=ALLY_ID,
                event_name="Restore", event_type="Shield", flags="Critical|Immune",
                magnitude=-20, magnitude2=0),
            make_line(
                9, owner_id=ALICE_ID, event_name="Beam", event_type="Plasma",
                flags="Miss", magnitude=200, magnitude2=250),
            make_line(
                10, owner_name="Enemy", owner_id="C[9 Enemy]",
                target_name="Alice", target_id=ALICE_ID,
                event_name="Attack", event_type="HitPoints", flags="Kill",
                magnitude=50, magnitude2=100),
        ])

        self.assertEqual(result.combat_duration_ms, 8000)
        self.assertEqual(result.active_duration_ms, 9000)
        alice = player(result, "Alice@pilot")
        ally = player(result, "Ally@pilot")
        self.assertEqual(alice.damage_out_duration_ms, 8000)
        self.assertEqual(alice.active_duration_ms, 9000)
        self.assertIsNone(ally.damage_out_duration_ms)
        self.assertIsNone(ally.active_duration_ms)

        damage = alice.damage_out.metrics
        self.assertEqual(damage.total_damage.to_dict(), {
            "all": 370.0, "shield": 70.0, "hull": 300.0})
        self.assertEqual(damage.hits.to_dict(), {"all": 6, "shield": 2, "hull": 4})
        self.assertEqual(damage.dps.all, 46.25)
        self.assertEqual(damage.base_damage, 350.0)
        self.assertEqual(damage.base_dps, 43.75)
        self.assertAlmostEqual(
            damage.resistance_percentage, (1.0 - 340.0 / 350.0) * 100.0)
        self.assertEqual(damage.critical_percentage, 50.0)
        self.assertEqual(damage.flanking_percentage, 25.0)
        self.assertEqual(damage.misses, 2)
        self.assertEqual(damage.accuracy_percentage, 50.0)
        self.assertEqual(damage.kill_count, 2)
        self.assertEqual(damage.kills[0].name, "Target")
        self.assertEqual(damage.damage_types, ("HitPoints", "Plasma"))
        self.assertEqual(damage.total_crit_damage, 100.0)
        self.assertEqual(damage.total_non_crit_hull_damage, 200.0)
        self.assertEqual(damage.average_crit_hit, 50.0)
        self.assertEqual(damage.average_non_crit_hull_hit, 100.0)
        self.assertEqual(damage.max_one_hit.damage, 999.0)
        self.assertEqual(damage.max_one_hit.name, "Beam")
        self.assertEqual(damage.max_one_hit.source_ordinal, 3)
        self.assertEqual(damage.damage_percentage.all, 100.0)
        self.assertEqual(damage.hits_percentage.all, 100.0)

        self.assertEqual([node.name for node in alice.damage_out.children], ["Beam"])
        self.assertEqual(
            [node.name for node in alice.damage_out.children[0].children], ["Target"])
        self.assertEqual(alice.damage_out.children[0].metrics.damage_percentage.all, 100.0)

        incoming = alice.damage_in.metrics
        self.assertEqual(incoming.total_damage.all, 50.0)
        self.assertAlmostEqual(incoming.dps.all, 50.0 / 9.0)
        self.assertEqual(incoming.kill_count, 1)
        self.assertEqual(alice.damage_in.children[0].name, "Enemy")
        self.assertEqual(alice.damage_in.children[0].children[0].name, "Attack")

        healing = alice.heal_out.metrics
        self.assertEqual(healing.total_heal.to_dict(), {
            "all": 100.0, "shield": 20.0, "hull": 80.0})
        self.assertEqual(healing.ticks.to_dict(), {"all": 2, "shield": 1, "hull": 1})
        self.assertEqual(healing.critical_percentage, 100.0)
        self.assertAlmostEqual(healing.hps.all, 100.0 / 9.0)
        self.assertEqual(alice.heal_out.children[0].name, "Ally@pilot")
        self.assertEqual(alice.heal_out.children[0].children[0].name, "Restore")

        self.assertEqual(ally.heal_in.metrics.total_heal.all, 100.0)
        self.assertEqual(
            ally.heal_in.metrics.hps.all,
            100.0 / (((1 << 63) - 1) / 1000.0),
        )
        self.assertEqual(ally.heal_in.metrics.critical_percentage, 100.0)

        self.assertEqual(alice.summary.combat_duration_ms, 8000)
        self.assertEqual(alice.summary.combat_duration_percentage, 100.0)
        self.assertEqual(alice.summary.active_duration_ms, 9000)
        self.assertEqual(alice.summary.kills, 2)
        self.assertEqual(alice.summary.player_kills, 0)
        self.assertEqual(alice.summary.npc_kills, 2)
        self.assertEqual(alice.summary.deaths, 1)
        self.assertEqual(result.team.total_outgoing_damage.all, 370.0)
        self.assertEqual(result.team.total_incoming_damage.all, 50.0)
        self.assertEqual(result.team.total_outgoing_heal.all, 100.0)
        self.assertEqual(result.team.total_incoming_heal.all, 100.0)
        self.assertEqual(result.team.kills, 2)
        self.assertEqual(result.team.deaths, 1)

    def test_indirect_hierarchies_and_duplicate_incoming_attribution(self):
        result = analysis([
            make_line(
                1, owner_id=ALICE_ID,
                source_name="Pet", source_id="C[5 Pet]",
                target_name="Drone", target_id="C[6 Drone]",
                event_name="Torpedo", magnitude=16, magnitude2=16),
            make_line(
                2, owner_name="Enemy", owner_id="C[9 Enemy]",
                source_name="Alice", source_id=ALICE_ID,
                target_name="Alice", target_id=ALICE_ID,
                event_name="Blast", magnitude=8, magnitude2=8),
            make_line(
                3, owner_id=ALICE_ID,
                source_name="Pet", source_id="C[5 Pet]",
                target_name="Ally", target_id=ALLY_ID,
                event_name="Repair", magnitude=-4, magnitude2=0),
        ])
        alice = player(result, "Alice@pilot")

        indirect = alice.damage_out.children[0]
        self.assertEqual(indirect.name, "Pet")
        self.assertEqual(indirect.children[0].name, "Torpedo")
        self.assertEqual(indirect.children[0].children[0].name, "Drone")

        # CLA independently dispatches target-player and indirect-player attribution.
        self.assertEqual(alice.damage_in.metrics.hits.all, 2)
        self.assertEqual(alice.damage_in.metrics.total_damage.all, 16.0)
        self.assertEqual(alice.damage_in.children[0].name, "Enemy")
        self.assertEqual(alice.damage_in.children[0].children[0].name, "Alice@pilot")
        self.assertEqual(
            alice.damage_in.children[0].children[0].children[0].name, "Blast")

        heal_target = alice.heal_out.children[0]
        self.assertEqual(heal_target.name, "Ally@pilot")
        self.assertEqual(heal_target.children[0].name, "Pet")
        self.assertEqual(heal_target.children[0].children[0].name, "Repair")

    def test_direct_self_damage_is_incoming_only(self):
        result = analysis([
            make_line(
                0, owner_id=ALICE_ID, source_name="", source_id="*",
                target_name="", target_id="*", event_name="Backlash",
                magnitude=32, magnitude2=32),
        ])
        alice = player(result, "Alice@pilot")
        self.assertEqual(alice.damage_out.metrics.hits.all, 0)
        self.assertEqual(alice.damage_in.metrics.hits.all, 1)
        self.assertEqual(alice.damage_in.metrics.total_damage.all, 32.0)
        self.assertEqual(result.combat_duration_ms, 0)

    def test_released_malformed_denominators_and_immune_heals_are_preserved(self):
        result = analysis([
            make_line(
                1, owner_id=ALICE_ID, event_name="Shield Crit",
                event_type="Shield", flags="Critical",
                magnitude=16, magnitude2=8),
            make_line(
                2, owner_id=ALICE_ID, target_name="Ally", target_id=ALLY_ID,
                event_name="Shield Restore", event_type="Shield",
                flags="Critical|Immune", magnitude=-8, magnitude2=0),
            make_line(
                3, owner_id=ALICE_ID, target_name="Ally", target_id=ALLY_ID,
                event_name="Shield Restore", event_type="Shield",
                flags="Critical", magnitude=-4, magnitude2=0),
            make_line(
                4, owner_id=ALICE_ID, target_name="Ally", target_id=ALLY_ID,
                event_name="Hull Restore", event_type="HitPoints",
                magnitude=-12, magnitude2=0),
        ])
        alice = player(result, "Alice@pilot")

        damage = alice.damage_out.metrics
        self.assertIsNone(damage.critical_percentage)
        self.assertEqual(damage.average_crit_hit, 0.0)
        self.assertEqual(damage.average_non_crit_hull_hit, 0.0)
        healing = alice.heal_out.metrics
        self.assertEqual(healing.total_heal.all, 24.0)
        self.assertEqual(healing.ticks.all, 3)
        self.assertEqual(healing.critical_percentage, 200.0)

    def test_same_name_hierarchy_collision_and_max_tie_are_deterministic(self):
        result = analysis([
            make_line(
                1, owner_id=ALICE_ID, target_name="Same",
                target_id="C[8 Same]", event_name="Same",
                magnitude=64, magnitude2=64),
            make_line(
                2, owner_id=ALICE_ID, target_name="Other",
                target_id="C[9 Other]", event_name="Second",
                magnitude=64, magnitude2=64),
        ])
        root = player(result, "Alice@pilot").damage_out

        self.assertEqual(root.children[0].name, "Same")
        self.assertEqual(root.children[0].segment, "value")
        self.assertEqual(root.children[0].children[0].name, "Same")
        self.assertEqual(root.children[0].children[0].segment, "group")
        self.assertEqual(root.metrics.max_one_hit.name, "Same")
        self.assertEqual(root.metrics.max_one_hit.source_ordinal, 0)

    def test_non_player_character_does_not_take_indirect_player_attribution(self):
        def incoming_hits(owner_id):
            result = analysis([
                make_line(
                    1, owner_name="Source", owner_id=owner_id,
                    source_name="Alice", source_id=ALICE_ID),
            ])
            matching = [
                item for item in result.players if item.player == "Alice@pilot"]
            return 0 if not matching else matching[0].damage_in.metrics.hits.all

        self.assertEqual(incoming_hits("C[7 Source]"), 1)
        self.assertEqual(incoming_hits("S[7 Source]"), 0)

    def test_all_zero_leaf_keeps_cla_unknown_max_provenance(self):
        result = analysis([
            make_line(
                1, owner_name="Enemy", owner_id="C[9 Enemy]",
                target_name="Alice", target_id=ALICE_ID,
                event_name="Zero", magnitude=0, magnitude2=0),
        ])

        maximum = player(result, "Alice@pilot").damage_in.metrics.max_one_hit
        self.assertEqual(maximum.damage, 0.0)
        self.assertEqual(maximum.name, "<unknown>")
        self.assertIsNone(maximum.source_ordinal)

    def test_raw_report_manifest_and_provenance_are_complete(self):
        result = analysis([make_line(1, owner_id=ALICE_ID)])
        payload = json.loads(result.to_json())

        self.assertEqual(payload["schema"], "re-oscr.cla-analysis.v1")
        self.assertEqual(payload["metric_ids"]["damage"], list(DAMAGE_METRIC_IDS))
        self.assertEqual(payload["metric_ids"]["healing"], list(HEAL_METRIC_IDS))
        self.assertEqual(payload["metric_ids"]["summary"], list(SUMMARY_METRIC_IDS))
        self.assertNotIn("SUM-09", payload["metric_ids"]["summary"])
        self.assertEqual(payload["provenance"]["engine_version"], "2")
        self.assertFalse(payload["provenance"]["league_eligible"])
        self.assertEqual(payload["players"][0]["player"], "Alice@pilot")


if __name__ == "__main__":
    unittest.main()
