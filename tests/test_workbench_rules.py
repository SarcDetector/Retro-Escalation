"""Persistence and portability contracts for Analysis Workbench rule sets."""

from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

from re_oscr.workbench import (
    WorkbenchRule,
    WorkbenchRuleMatch,
    WorkbenchRuleSet,
)
from re_oscr.workbenchrules import (
    RULE_SET_STORE_FILENAME,
    RULE_SET_STORE_VERSION,
    WorkbenchRuleSetStore,
    WorkbenchRuleStoreError,
)


def sample_rule_set(
        name: str = "Focused weapons", *, enabled: bool = True) -> WorkbenchRuleSet:
    return WorkbenchRuleSet(
        name,
        (
            WorkbenchRule(
                "GROUP",
                (
                    WorkbenchRuleMatch("EVENT", "Advanced Piezo*"),
                    WorkbenchRuleMatch("EVENT", "Technical Overload"),
                ),
                "Advanced Piezo Beam Array",
                enabled=enabled,
            ),
            WorkbenchRule(
                "REVERSE",
                (WorkbenchRuleMatch("SOURCE", "Tachyon Net Drone*"),),
                "Tachyon Net Drones",
                enabled=enabled,
            ),
        ),
    )


class WorkbenchRuleSetStoreTests(unittest.TestCase):
    def test_save_and_load_persist_definitions_with_every_toggle_off(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = WorkbenchRuleSetStore(temp_dir)
            enabled = sample_rule_set()

            store.save((enabled,))

            path = Path(temp_dir, RULE_SET_STORE_FILENAME)
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(set(payload), {"version", "rule_sets"})
            self.assertEqual(payload["version"], RULE_SET_STORE_VERSION)
            self.assertEqual(len(payload["rule_sets"]), 1)
            self.assertTrue(all(
                rule["enabled"] is False
                for rule in payload["rule_sets"][0]["rules"]
            ))

            loaded = store.load()
            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0].name, enabled.name)
            self.assertFalse(loaded[0].read_only)
            self.assertEqual(loaded[0].enabled_rules, ())
            self.assertTrue(all(not rule.enabled for rule in loaded[0].rules))
            self.assertEqual(
                tuple((rule.rule_type, rule.matches, rule.label) for rule in loaded[0].rules),
                tuple((rule.rule_type, rule.matches, rule.label) for rule in enabled.rules),
            )

    def test_export_and_import_are_portable_strict_and_default_off(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir, "shared-rules.json")
            enabled = sample_rule_set("Shared telemetry")

            WorkbenchRuleSetStore.export_file(path, enabled)

            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(set(payload), {"name", "version", "rules"})
            self.assertTrue(all(rule["enabled"] is False for rule in payload["rules"]))
            imported = WorkbenchRuleSetStore.import_file(path)
            self.assertEqual(imported.name, enabled.name)
            self.assertFalse(imported.read_only)
            self.assertEqual(imported.enabled_rules, ())
            self.assertTrue(all(not rule.enabled for rule in imported.rules))

            path.write_text(
                '{"name":"Unsafe","version":1,"rules":[],"command":"run"}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(WorkbenchRuleStoreError, "unknown key"):
                WorkbenchRuleSetStore.import_file(path)

            path.write_text(
                '{"name":"One","name":"Two","version":1,"rules":[]}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(WorkbenchRuleStoreError, "duplicate JSON key"):
                WorkbenchRuleSetStore.import_file(path)

    def test_store_rejects_schema_drift_and_case_insensitive_duplicate_names(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = WorkbenchRuleSetStore(temp_dir)
            first = sample_rule_set("My Rules", enabled=False)
            duplicate = replace(first, name="my rules")

            with self.assertRaisesRegex(WorkbenchRuleStoreError, "must be unique"):
                store.save((first, duplicate))

            path = Path(temp_dir, RULE_SET_STORE_FILENAME)
            path.write_text(
                json.dumps({
                    "version": RULE_SET_STORE_VERSION,
                    "rule_sets": [],
                    "unexpected": True,
                }),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(WorkbenchRuleStoreError, "only version and rule_sets"):
                store.load()

            path.write_text(
                json.dumps({"version": 999, "rule_sets": []}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(WorkbenchRuleStoreError, "unsupported"):
                store.load()

            path.write_text(
                '{"version":true,"rule_sets":[]}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(WorkbenchRuleStoreError, "unsupported"):
                store.load()

            path.write_text(
                '{"version":1,"version":1,"rule_sets":[]}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(WorkbenchRuleStoreError, "duplicate JSON key"):
                store.load()

    def test_filesystem_failures_use_the_store_error_contract(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            occupied = Path(temp_dir, "not-a-directory")
            occupied.write_text("occupied", encoding="utf-8")

            with self.assertRaisesRegex(WorkbenchRuleStoreError, "Unable to save"):
                WorkbenchRuleSetStore(occupied).save((sample_rule_set(),))

            with self.assertRaisesRegex(WorkbenchRuleStoreError, "Unable to export"):
                WorkbenchRuleSetStore.export_file(
                    occupied / "rules.json", sample_rule_set())


if __name__ == "__main__":
    unittest.main()
