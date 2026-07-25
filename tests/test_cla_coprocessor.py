"""Contracts retained for the dev15 CLA Damage Out compatibility projection."""

import hashlib
import json
import math
import unittest
from unittest.mock import patch

from re_oscr.clacoprocessor import (
    ClaCoprocessorError,
    PROFILE_ID,
    analyze_damage_out_preview,
)
from re_oscr.workbench import CombatEventIndex, WorkbenchDataError
from tests.test_workbench import make_combat, make_line


PRODUCT_VERSION = "11.1.0.dev15"
PLAYER_ID = "P[1@10 Alice@handle]"


def preview(lines):
    index = CombatEventIndex(make_combat(lines, end_seconds=20.0))
    return analyze_damage_out_preview(
        index.snapshot_json,
        index.snapshot_id,
        product_version=PRODUCT_VERSION,
    )


class SnapshotIdentityTests(unittest.TestCase):
    def assert_invalid_snapshot_json(self, snapshot_json):
        snapshot_id = "sha256:" + hashlib.sha256(snapshot_json.encode("utf-8")).hexdigest()
        with self.assertRaises(ClaCoprocessorError) as caught:
            analyze_damage_out_preview(
                snapshot_json,
                snapshot_id,
                product_version=PRODUCT_VERSION,
            )
        self.assertEqual(caught.exception.category, "INVALID_SNAPSHOT")
        self.assertEqual(caught.exception.phase, "decode")

    def test_snapshot_identity_is_canonical_stable_and_preserves_binary64_bits(self):
        combat = make_combat([
            make_line(
                1, owner_id=PLAYER_ID, magnitude=-0.0, magnitude2=100.0,
                event_name="Negative Zero"),
        ])

        first = CombatEventIndex(combat)
        second = CombatEventIndex(combat)
        payload = first.snapshot_payload

        self.assertEqual(first.snapshot_json, second.snapshot_json)
        self.assertEqual(first.snapshot_id, second.snapshot_id)
        self.assertEqual(
            first.snapshot_id,
            "sha256:" + hashlib.sha256(first.snapshot_json.encode("utf-8")).hexdigest(),
        )
        self.assertEqual(payload["domain"], "re-oscr.snapshot.v1")
        self.assertEqual(payload["parser_version"], "11.0.0")
        self.assertEqual(payload["event_count"], 1)
        self.assertEqual(payload["events"][0][12], "8000000000000000")
        self.assertEqual(payload["events"][0][0], 0)

    def test_snapshot_identity_preserves_nullable_metadata_without_normalizing_text(self):
        combat = make_combat([], map_name="  Infected Space  ")
        combat.difficulty = ""

        payload = CombatEventIndex(combat).snapshot_payload

        self.assertEqual(payload["combat"]["map"], "  Infected Space  ")
        self.assertEqual(payload["combat"]["difficulty"], "")

    def test_calculation_uses_frozen_json_not_rewriteable_numpy_columns(self):
        index = CombatEventIndex(make_combat([
            make_line(1, owner_id=PLAYER_ID, magnitude=100.0, magnitude2=100.0),
        ]))
        index.magnitudes.setflags(write=True)
        index.magnitudes[0] = 999_999.0

        result = analyze_damage_out_preview(
            index.snapshot_json,
            index.snapshot_id,
            product_version=PRODUCT_VERSION,
        )

        self.assertEqual(result.rows[0].total_damage.all, 100.0)

    def test_snapshot_rejects_sub_millisecond_and_nonfinite_values(self):
        with self.assertRaisesRegex(WorkbenchDataError, "whole millisecond"):
            CombatEventIndex(make_combat([
                make_line(0.0005, owner_id=PLAYER_ID),
            ]))
        with self.assertRaisesRegex(WorkbenchDataError, "non-finite magnitude"):
            CombatEventIndex(make_combat([
                make_line(1, owner_id=PLAYER_ID, magnitude=math.inf),
            ]))

    def test_snapshot_rejects_loaded_and_installed_parser_version_mismatch(self):
        with patch("re_oscr.workbench.distribution_version", return_value="99.0.0"):
            with self.assertRaisesRegex(WorkbenchDataError, "does not match"):
                CombatEventIndex(make_combat([
                    make_line(1, owner_id=PLAYER_ID),
                ]))

    def test_engine_rejects_tampered_snapshot_identity(self):
        index = CombatEventIndex(make_combat([
            make_line(1, owner_id=PLAYER_ID),
        ]))

        with self.assertRaises(ClaCoprocessorError) as caught:
            analyze_damage_out_preview(
                index.snapshot_json + " ",
                index.snapshot_id,
                product_version=PRODUCT_VERSION,
            )

        self.assertEqual(caught.exception.category, "SNAPSHOT_ID_MISMATCH")
        self.assertEqual(caught.exception.phase, "decode")

    def test_engine_rejects_semantic_aliases_and_nonstandard_json(self):
        index = CombatEventIndex(make_combat([
            make_line(1, owner_id=PLAYER_ID, magnitude=0.1, magnitude2=0.1),
        ]))
        payload = index.snapshot_payload
        pretty = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)
        duplicate = '{"domain":"duplicate",' + index.snapshot_json[1:]
        scalar = "[]"
        nonstandard = index.snapshot_json.replace('"event_count":1', '"event_count":NaN')
        boolean_count_payload = json.loads(index.snapshot_json)
        boolean_count_payload["event_count"] = True
        boolean_count = json.dumps(
            boolean_count_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        uppercase_bits_payload = json.loads(index.snapshot_json)
        uppercase_bits_payload["events"][0][12] = (
            uppercase_bits_payload["events"][0][12].upper())
        uppercase_bits = json.dumps(
            uppercase_bits_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

        for label, candidate in (
                ("pretty", pretty),
                ("duplicate", duplicate),
                ("scalar", scalar),
                ("nonstandard", nonstandard),
                ("boolean count", boolean_count),
                ("uppercase bits", uppercase_bits)):
            with self.subTest(label=label):
                self.assert_invalid_snapshot_json(candidate)


class DamageOutPreviewTests(unittest.TestCase):
    def test_source_audited_scalar_fixture(self):
        result = preview([
            make_line(
                1, owner_id=PLAYER_ID, event_name="Fallback Hull",
                event_type="HitPoints", magnitude=100, magnitude2=0),
            make_line(
                1, owner_id=PLAYER_ID, event_name="Shield Hit",
                event_type="Shield", magnitude=40, magnitude2=20),
            make_line(
                3, owner_id=PLAYER_ID, event_name="Shield Drain",
                event_type="Shield", magnitude=30, magnitude2=0),
            make_line(
                5, owner_id=PLAYER_ID, event_name="Immune Hull",
                event_type="HitPoints", flags="Immune", magnitude=999, magnitude2=999),
            make_line(
                7, owner_id=PLAYER_ID, event_name="All Zero",
                event_type="HitPoints", magnitude=0, magnitude2=0),
            make_line(
                9, owner_id=PLAYER_ID, event_name="Critical Hull",
                event_type="HitPoints", flags="Critical", magnitude=200, magnitude2=250),
        ])

        self.assertEqual(result.event_count, 6)
        self.assertEqual(result.combat_duration_ms, 8000)
        self.assertEqual(result.active_duration_ms, 8000)
        self.assertEqual(len(result.rows), 1)
        row = result.rows[0]
        self.assertEqual(row.player, "Alice@handle")
        self.assertEqual(row.damage_out_duration_ms, 8000)
        self.assertEqual(row.active_duration_ms, 8000)
        self.assertEqual(row.total_damage.to_dict(), {
            "all": 370.0, "shield": 70.0, "hull": 300.0})
        self.assertEqual(row.hits.to_dict(), {"all": 6, "shield": 2, "hull": 4})
        self.assertEqual(row.dps.to_dict(), {
            "all": 46.25, "shield": 8.75, "hull": 37.5})
        self.assertEqual(row.hits_per_second.to_dict(), {
            "all": 0.75, "shield": 0.25, "hull": 0.5})
        self.assertEqual(row.base_damage, 350.0)
        self.assertEqual(row.base_dps, 43.75)
        self.assertAlmostEqual(row.average_hit.all, 370.0 / 6.0)
        self.assertEqual(row.average_hit.shield, 35.0)
        self.assertEqual(row.average_hit.hull, 75.0)
        self.assertAlmostEqual(
            row.resistance_percentage,
            100.0 * (1.0 - 340.0 / 350.0),
        )

    def test_first_record_quirk_and_missing_player_clock_are_explicit(self):
        result = preview([
            make_line(
                0, owner_id=PLAYER_ID, flags="Immune",
                magnitude=500, magnitude2=500),
            make_line(
                5, owner_id=PLAYER_ID, event_type="HitPoints",
                magnitude=-50, magnitude2=0),
        ])

        row = result.rows[0]
        self.assertEqual(result.combat_duration_ms, 0)
        self.assertEqual(result.active_duration_ms, 5000)
        self.assertIsNone(row.damage_out_duration_ms)
        self.assertEqual(row.active_duration_ms, 5000)
        self.assertEqual(row.hits.all, 1)
        self.assertEqual(row.total_damage.all, 0.0)
        self.assertEqual(row.hits_per_second.all, 1 / (((1 << 63) - 1) / 1000.0))

    def test_one_point_clock_uses_one_second_floor(self):
        result = preview([
            make_line(3, owner_id=PLAYER_ID, magnitude=125, magnitude2=125),
        ])

        row = result.rows[0]
        self.assertEqual(row.damage_out_duration_ms, 0)
        self.assertEqual(row.dps.all, 125.0)
        self.assertEqual(row.hits_per_second.all, 1.0)

    def test_value_type_is_trimmed_before_heal_and_shield_classification(self):
        result = preview([
            make_line(
                1, owner_id=PLAYER_ID, event_type=" HitPoints ",
                magnitude=-50, magnitude2=0),
            make_line(
                3, owner_id=PLAYER_ID, event_type=" Shield ",
                magnitude=40, magnitude2=20),
        ])

        row = result.rows[0]
        self.assertEqual(row.total_damage.to_dict(), {
            "all": 40.0, "shield": 40.0, "hull": 0.0})
        self.assertEqual(row.hits.to_dict(), {"all": 1, "shield": 1, "hull": 0})

    def test_non_player_character_does_not_take_non_player_incoming_attribution(self):
        def active_duration(owner_id):
            result = preview([
                make_line(
                    1, owner_name="NPC", owner_id=owner_id,
                    source_name="Alice", source_id=PLAYER_ID),
                make_line(10, owner_id=PLAYER_ID),
            ])
            return result.rows[0].active_duration_ms

        self.assertEqual(active_duration("C[1 NPC]"), 9000)
        self.assertEqual(active_duration("S[1 NPC]"), 0)

    def test_direct_self_damage_affects_global_clock_but_not_player_damage_out(self):
        result = preview([
            make_line(
                0, owner_id=PLAYER_ID, source_name="", source_id="*",
                target_name="", target_id="*", magnitude=400, magnitude2=400),
            make_line(3, owner_id=PLAYER_ID, magnitude=100, magnitude2=100),
        ])

        self.assertEqual(result.combat_duration_ms, 3000)
        self.assertEqual(result.rows[0].total_damage.all, 100.0)
        self.assertEqual(result.rows[0].hits.all, 1)

    def test_processing_order_backwards_range_is_contained(self):
        index = CombatEventIndex(make_combat([
            make_line(5, owner_id=PLAYER_ID),
            make_line(1, owner_id=PLAYER_ID),
        ]))

        with self.assertRaises(ClaCoprocessorError) as caught:
            analyze_damage_out_preview(
                index.snapshot_json,
                index.snapshot_id,
                product_version=PRODUCT_VERSION,
            )

        self.assertEqual(caught.exception.category, "INVALID_CLOCK_RANGE")
        self.assertEqual(caught.exception.phase, "TIME-02")

    def test_backwards_active_clock_is_validated_for_heal_only_player(self):
        bob_id = "P[2@20 Bob@handle]"
        index = CombatEventIndex(make_combat([
            make_line(0, owner_name="Bob", owner_id=bob_id),
            make_line(
                5, owner_id=PLAYER_ID, event_type="HitPoints",
                magnitude=-50, magnitude2=0),
            make_line(
                1, owner_id=PLAYER_ID, event_type="HitPoints",
                magnitude=-25, magnitude2=0),
            make_line(10, owner_name="Bob", owner_id=bob_id),
        ]))

        with self.assertRaises(ClaCoprocessorError) as caught:
            analyze_damage_out_preview(
                index.snapshot_json,
                index.snapshot_id,
                product_version=PRODUCT_VERSION,
            )

        self.assertEqual(caught.exception.category, "INVALID_CLOCK_RANGE")
        self.assertEqual(caught.exception.phase, "TIME-04")

    def test_provenance_is_stable_explicit_and_never_upload_eligible(self):
        result = preview([
            make_line(1, owner_id=PLAYER_ID),
        ])
        provenance = result.provenance.to_dict()

        self.assertEqual(provenance["profile_id"], PROFILE_ID)
        self.assertEqual(provenance["product_version"], PRODUCT_VERSION)
        self.assertEqual(provenance["input"]["parser_version"], "11.0.0")
        self.assertEqual(provenance["input"]["combat"]["map"], "Infected Space")
        self.assertFalse(provenance["league_eligible"])
        self.assertIn("OSCR_LEAGUE_SOURCE", provenance["boundary_differences"])
        self.assertIn(
            "OSCR_ELECTRICAL_OVERLOAD_DROPPED",
            provenance["boundary_differences"],
        )
        self.assertEqual(provenance["transform"]["selected_ordinals"], "all")
        self.assertRegex(provenance["snapshot_id"], r"^sha256:[0-9a-f]{64}$")
        self.assertRegex(provenance["result_id"], r"^sha256:[0-9a-f]{64}$")
        self.assertIn("FIELD-VALIDATED", result.audit_status)
        self.assertEqual(json.loads(result.to_json())["rows"][0]["player"], "Alice@handle")


if __name__ == "__main__":
    unittest.main()
