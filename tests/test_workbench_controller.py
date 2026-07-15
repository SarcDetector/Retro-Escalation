import os
from dataclasses import replace
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
)

from OSCR.parser import analyze_combat

from re_oscr.workbench import (
    BUNDLED_WORKBENCH_RULE_SETS,
    WorkbenchFilterClause,
    WorkbenchRule,
    WorkbenchRuleMatch,
    WorkbenchRuleSet,
    WorkbenchState,
)
from re_oscr.workbenchcontroller import AnalysisWorkbenchController
from re_oscr.workbenchrules import WorkbenchRuleSetStore
from tests.test_workbench import make_combat, make_line


class FakeParserBridge(QObject):
    combat_displayed = Signal(object)

    def __init__(self, source_combat):
        super().__init__()
        self._parser = SimpleNamespace(
            current_combat=source_combat,
            combats=[source_combat],
        )
        self.displayed_analysis = []

    def display_analysis(self, combat):
        self.displayed_analysis.append(combat)


class FakeTables:
    def __init__(self):
        self.modified_states = []

    def set_analysis_modified(self, modified):
        self.modified_states.append(bool(modified))


class FakePlot:
    def __init__(self):
        self.clear_count = 0

    def clear(self):
        self.clear_count += 1


class FakeWidgets:
    def __init__(self):
        self.analysis_filter_scope = QComboBox()
        for scope in (
                "ANY", "OWNER", "SOURCE", "TARGET", "EVENT", "TYPE", "FLAG",
                "MIN_MAGNITUDE", "MAX_MAGNITUDE"):
            self.analysis_filter_scope.addItem(scope, scope)
        self.analysis_filter_entry = QLineEdit()
        self.analysis_filter_add_button = QPushButton("ADD FILTER")
        self.analysis_filter_clause_row = QFrame()
        self.analysis_filter_clause_row.hide()
        self.analysis_filter_clause_container = QFrame(
            self.analysis_filter_clause_row)
        self.analysis_filter_clause_layout = QHBoxLayout(
            self.analysis_filter_clause_container)
        self.analysis_filter_clause_buttons = []
        self.analysis_rule_set_selector = QComboBox()
        self.analysis_rules_button = QPushButton("RULES")
        self.analysis_rule_chip_buttons = []
        self.analysis_start_entry = QLineEdit()
        self.analysis_end_entry = QLineEdit()
        self.analysis_truth_chip = QLabel()
        self.analysis_modified_chip = QLabel()
        self.analysis_event_count_chip = QLabel()
        self.analysis_reset_button = QPushButton()
        self.analysis_plots = [FakePlot() for _ in range(4)]


def analyzed_combat(*, combat_id=0, owner_names=("Alice", "Bob", "Alice")):
    combat = make_combat(
        [
            make_line(float(index), owner_name=owner, event_name=f"Beam {index}")
            for index, owner in enumerate(owner_names)
        ],
        end_seconds=float(len(owner_names) - 1),
        combat_id=combat_id,
    )
    combat.file_pos = [100 + combat_id, 200 + combat_id]
    return analyze_combat(combat)


class AnalysisWorkbenchControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.source = analyzed_combat(combat_id=7)
        self.source_lines = tuple(self.source.log_data)
        self.source_roots = tuple(self.source.root_items)
        self.source_file_pos = list(self.source.file_pos)
        self.parser = FakeParserBridge(self.source)
        self.tables = FakeTables()
        self.widgets = FakeWidgets()
        self.controller = AnalysisWorkbenchController(
            self.parser, self.tables, self.widgets)
        self.controller.attach_controls()

    def bind_source(self):
        self.parser.combat_displayed.emit(self.source)

    def draft_filter(self, scope, value):
        index = self.widgets.analysis_filter_scope.findData(scope)
        self.assertGreaterEqual(index, 0)
        self.widgets.analysis_filter_scope.setCurrentIndex(index)
        self.widgets.analysis_filter_entry.setText(value)

    def add_filter(self, scope, value):
        self.draft_filter(scope, value)
        self.widgets.analysis_filter_add_button.click()

    def edited_bundled_rules(self, *enabled_indices):
        enabled = set(enabled_indices)
        working = self.controller._working_rule_set
        return replace(
            working,
            rules=tuple(
                replace(rule, enabled=index in enabled)
                for index, rule in enumerate(working.rules)
            ),
        )

    def accept_rule_editor(self, edited):
        dialog = SimpleNamespace(
            result_rule_set=edited,
            exec=lambda: QDialog.DialogCode.Accepted,
        )
        with patch(
                "re_oscr.workbenchcontroller.WorkbenchRuleEditor",
                return_value=dialog):
            self.controller.edit_rules()

    def test_binding_official_combat_starts_in_parser_truth_state(self):
        self.bind_source()

        self.assertIs(self.controller.source_combat, self.source)
        self.assertEqual(self.controller.state, WorkbenchState.parser_truth())
        self.assertIsNone(self.controller.current_result)
        self.assertIsNone(self.controller.current_view)
        self.assertFalse(self.widgets.analysis_truth_chip.isHidden())
        self.assertTrue(self.widgets.analysis_modified_chip.isHidden())
        self.assertEqual(self.widgets.analysis_event_count_chip.text(), "3 EVENTS")
        self.assertEqual(len(self.controller.cache), 0)
        self.assertFalse(self.widgets.analysis_reset_button.isEnabled())
        self.assertEqual(self.tables.modified_states[-1], False)
        self.assertTrue(all(plot.clear_count == 1 for plot in self.widgets.analysis_plots))

    def test_bundled_rule_selector_loads_read_only_definitions_default_off(self):
        self.assertEqual(
            self.widgets.analysis_rule_set_selector.count(),
            len(BUNDLED_WORKBENCH_RULE_SETS),
        )
        self.assertEqual(
            self.widgets.analysis_rule_set_selector.itemText(0),
            "COMMUNITY EXAMPLES // BUNDLED",
        )
        self.assertTrue(self.widgets.analysis_rules_button.isEnabled())
        self.assertTrue(self.controller._working_rule_set.read_only)
        self.assertEqual(self.controller._working_rule_set.enabled_rules, ())
        self.assertEqual(self.controller.state, WorkbenchState.parser_truth())

    def test_custom_rule_set_loads_into_selector_but_activation_remains_per_combat(self):
        custom = WorkbenchRuleSet(
            "My combat rules",
            (
                WorkbenchRule(
                    "GROUP", (WorkbenchRuleMatch("EVENT", "Beam*"),),
                    "Beam weapons", enabled=True),
            ),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            WorkbenchRuleSetStore(temp_dir).save((custom,))
            widgets = FakeWidgets()
            controller = AnalysisWorkbenchController(
                self.parser, self.tables, widgets, config_dir=temp_dir)
            controller.attach_controls()

            self.assertEqual(widgets.analysis_rule_set_selector.count(), 2)
            self.assertEqual(
                widgets.analysis_rule_set_selector.itemText(1),
                "MY COMBAT RULES // CUSTOM",
            )
            widgets.analysis_rule_set_selector.setCurrentIndex(1)
            self.assertEqual(controller._working_rule_set.enabled_rules, ())
            self.assertEqual(controller.state.rules, ())

            self.parser.combat_displayed.emit(self.source)
            self.assertEqual(controller.state, WorkbenchState.parser_truth())
            self.assertEqual(controller._working_rule_set.enabled_rules, ())
            self.assertEqual(widgets.analysis_rule_chip_buttons, [])

            # Disconnect this temporary controller before its temporary store disappears.
            self.parser.combat_displayed.disconnect(controller.bind_combat)

    def test_enabled_rule_applies_as_modified_view_and_chip_disables_only_that_rule(self):
        self.bind_source()
        enabled = self.edited_bundled_rules(0)

        self.accept_rule_editor(enabled)

        self.assertEqual(self.controller.state.rules, enabled.enabled_rules)
        self.assertTrue(self.controller.state.is_modified)
        self.assertIsNotNone(self.controller.current_view)
        self.assertIsNot(self.parser.displayed_analysis[-1], self.source)
        self.assertEqual(len(self.widgets.analysis_rule_chip_buttons), 1)
        chip = self.widgets.analysis_rule_chip_buttons[0]
        self.assertEqual(chip.property("consoleRole"), "filterClauseChip")
        self.assertEqual(chip.property("modifierType"), "rule")
        self.assertIn(enabled.enabled_rules[0].display_label, chip.text())
        self.assertFalse(self.widgets.analysis_filter_clause_row.isHidden())
        self.assertTrue(self.widgets.analysis_reset_button.isEnabled())

        chip.click()

        self.assertEqual(self.controller.state.rules, ())
        self.assertEqual(self.controller._working_rule_set.enabled_rules, ())
        self.assertEqual(self.widgets.analysis_rule_chip_buttons, [])
        self.assertTrue(self.widgets.analysis_filter_clause_row.isHidden())
        self.assertIs(self.parser.displayed_analysis[-1], self.source)
        self.assertFalse(self.tables.modified_states[-1])
        self.assertTrue(self.controller._working_rule_set.read_only)

    def test_reset_and_combat_switch_disable_rule_toggles_and_remove_chips(self):
        self.bind_source()
        self.accept_rule_editor(self.edited_bundled_rules(0, 1))
        self.assertEqual(len(self.widgets.analysis_rule_chip_buttons), 2)

        self.controller.reset()

        self.assertEqual(self.controller.state, WorkbenchState.parser_truth())
        self.assertEqual(self.controller._working_rule_set.enabled_rules, ())
        self.assertEqual(self.widgets.analysis_rule_chip_buttons, [])
        self.assertTrue(self.widgets.analysis_filter_clause_row.isHidden())

        self.accept_rule_editor(self.edited_bundled_rules(0))
        self.assertEqual(len(self.widgets.analysis_rule_chip_buttons), 1)
        second = analyzed_combat(combat_id=81, owner_names=("Carol", "Dan"))
        self.parser._parser.current_combat = second
        self.parser._parser.combats.append(second)

        self.parser.combat_displayed.emit(second)

        self.assertIs(self.controller.source_combat, second)
        self.assertEqual(self.controller.state, WorkbenchState.parser_truth())
        self.assertEqual(self.controller._working_rule_set.enabled_rules, ())
        self.assertEqual(self.widgets.analysis_rule_chip_buttons, [])
        self.assertTrue(self.widgets.analysis_filter_clause_row.isHidden())

    def test_rule_editor_cancel_and_failed_apply_leave_accepted_state_unchanged(self):
        self.bind_source()
        self.widgets.analysis_filter_entry.setText("Alice")
        accepted_state = self.controller.state
        accepted_display = self.parser.displayed_analysis[-1]
        accepted_working = self.controller._working_rule_set
        edited = self.edited_bundled_rules(0)

        rejected_dialog = SimpleNamespace(
            result_rule_set=edited,
            exec=lambda: QDialog.DialogCode.Rejected,
        )
        with patch(
                "re_oscr.workbenchcontroller.WorkbenchRuleEditor",
                return_value=rejected_dialog):
            self.controller.edit_rules()

        self.assertEqual(self.controller.state, accepted_state)
        self.assertIs(self.parser.displayed_analysis[-1], accepted_display)
        self.assertEqual(self.controller._working_rule_set, accepted_working)

        accepted_dialog = SimpleNamespace(
            result_rule_set=edited,
            exec=lambda: QDialog.DialogCode.Accepted,
        )
        with (
                patch(
                    "re_oscr.workbenchcontroller.WorkbenchRuleEditor",
                    return_value=accepted_dialog),
                patch.object(self.controller, "apply_state", return_value=False)):
            self.controller.edit_rules()

        self.assertEqual(self.controller.state, accepted_state)
        self.assertIs(self.parser.displayed_analysis[-1], accepted_display)
        self.assertEqual(self.controller._working_rule_set, accepted_working)
        self.assertEqual(self.widgets.analysis_rule_chip_buttons, [])

    def test_add_button_requires_combat_and_nonblank_value(self):
        self.assertFalse(self.widgets.analysis_filter_add_button.isEnabled())

        self.widgets.analysis_filter_entry.setText("Alice")
        self.assertFalse(self.widgets.analysis_filter_add_button.isEnabled())

        self.bind_source()
        self.assertFalse(self.widgets.analysis_filter_add_button.isEnabled())
        self.widgets.analysis_filter_entry.setText("Alice")
        self.assertTrue(self.widgets.analysis_filter_add_button.isEnabled())
        self.widgets.analysis_filter_entry.setText("   ")
        self.assertFalse(self.widgets.analysis_filter_add_button.isEnabled())

    def test_structured_builder_is_inert_until_add_then_updates_all_modes_once(self):
        self.bind_source()
        self.draft_filter("TYPE", "HitPoints")

        self.assertEqual(self.controller.state, WorkbenchState.parser_truth())
        self.assertIsNone(self.controller.current_result)
        self.assertEqual(self.parser.displayed_analysis, [])

        self.widgets.analysis_filter_add_button.click()

        clause = WorkbenchFilterClause("TYPE", "HitPoints")
        self.assertEqual(self.controller.state, WorkbenchState(clauses=(clause,)))
        self.assertEqual(self.controller.current_result.count, 3)
        self.assertEqual(len(self.parser.displayed_analysis), 1)
        derived = self.parser.displayed_analysis[-1]
        for model in (
                derived.damage_out, derived.damage_in,
                derived.heals_out, derived.heals_in):
            self.assertIsNotNone(model)
        self.assertEqual(self.widgets.analysis_filter_scope.currentData(), "ANY")
        self.assertEqual(self.widgets.analysis_filter_entry.text(), "")
        self.assertFalse(self.widgets.analysis_filter_add_button.isEnabled())
        self.assertFalse(self.widgets.analysis_filter_clause_row.isHidden())
        self.assertEqual(len(self.widgets.analysis_filter_clause_buttons), 1)
        chip = self.widgets.analysis_filter_clause_buttons[0]
        self.assertEqual(chip.property("consoleRole"), "filterClauseChip")
        self.assertIn(clause.display_label, chip.text())

    def test_entering_or_changing_builder_clears_hidden_quick_query_and_draft(self):
        self.bind_source()
        self.widgets.analysis_filter_entry.setText("Alice")
        self.assertEqual(self.controller.state, WorkbenchState(text_query="Alice"))

        self.draft_filter("TYPE", "HitPoints")

        self.assertEqual(self.controller.state, WorkbenchState.parser_truth())
        self.assertEqual(self.widgets.analysis_filter_entry.text(), "HitPoints")
        self.assertEqual(
            self.widgets.analysis_filter_entry.placeholderText(),
            "TYPE, E.G. HITPOINTS",
        )

        flag_index = self.widgets.analysis_filter_scope.findData("FLAG")
        self.widgets.analysis_filter_scope.setCurrentIndex(flag_index)

        self.assertEqual(self.controller.state, WorkbenchState.parser_truth())
        self.assertEqual(self.widgets.analysis_filter_entry.text(), "")
        self.assertEqual(
            self.widgets.analysis_filter_entry.placeholderText(),
            "CRITICAL, MISS, OR KILL",
        )

    def test_multiple_structured_clauses_are_anded_and_preserve_time_cut(self):
        self.source = analyze_combat(make_combat([
            make_line(
                0, owner_name="Alice", event_type="HitPoints",
                flags="Critical", magnitude=100),
            make_line(
                1, owner_name="Alice", event_type="Shield",
                flags="Critical", magnitude=300),
            make_line(
                2, owner_name="Bob", event_type="HitPoints",
                flags="Miss", magnitude=200),
        ], end_seconds=2, combat_id=17))
        self.parser._parser.current_combat = self.source
        self.parser._parser.combats = [self.source]
        self.bind_source()
        self.widgets.analysis_start_entry.setText("1")
        self.widgets.analysis_start_entry.editingFinished.emit()

        self.add_filter("TYPE", "HitPoints")
        self.assertEqual(self.controller.current_result.count, 1)
        self.add_filter("MAX_MAGNITUDE", "250")

        self.assertEqual(len(self.controller.state.clauses), 2)
        self.assertEqual(self.controller.state.start_seconds, 1.0)
        self.assertEqual(self.controller.current_result.count, 1)
        self.assertEqual(
            self.controller.current_result.lines[0].owner_name, "Bob")
        self.assertEqual(len(self.widgets.analysis_filter_clause_buttons), 2)

    def test_clause_chip_removes_only_its_clause_and_hides_empty_row(self):
        self.bind_source()
        self.add_filter("TYPE", "HitPoints")
        self.add_filter("MIN_MAGNITUDE", "50")
        self.widgets.analysis_filter_scope.setCurrentText("OWNER")
        self.widgets.analysis_filter_entry.setText("Alice")
        self.widgets.analysis_start_entry.setText("1")
        self.widgets.analysis_start_entry.editingFinished.emit()

        self.widgets.analysis_filter_clause_buttons[0].click()

        self.assertEqual(
            self.controller.state.clauses,
            (WorkbenchFilterClause("MIN_MAGNITUDE", 50),),
        )
        self.assertEqual(self.controller.state.owner_query, "Alice")
        self.assertEqual(self.controller.state.start_seconds, 1.0)
        self.assertFalse(self.widgets.analysis_filter_clause_row.isHidden())
        self.assertEqual(len(self.widgets.analysis_filter_clause_buttons), 1)

        self.widgets.analysis_filter_clause_buttons[0].click()

        self.assertEqual(self.controller.state.clauses, ())
        self.assertEqual(self.controller.state.owner_query, "Alice")
        self.assertEqual(self.controller.state.start_seconds, 1.0)
        self.assertTrue(self.widgets.analysis_filter_clause_row.isHidden())
        self.assertEqual(self.widgets.analysis_filter_clause_buttons, [])

    def test_invalid_structured_add_is_transactional_and_keeps_draft(self):
        self.bind_source()
        self.widgets.analysis_filter_entry.setText("Alice")
        errors = []
        self.controller.view_failed.connect(errors.append)

        for scope, value in (("FLAG", "Flank"), ("MIN_MAGNITUDE", "many")):
            with self.subTest(scope=scope, value=value):
                self.draft_filter(scope, value)
                accepted_state = self.controller.state
                accepted_display = self.parser.displayed_analysis[-1]
                display_count = len(self.parser.displayed_analysis)
                self.widgets.analysis_filter_add_button.click()
                self.assertEqual(self.controller.state, accepted_state)
                self.assertIs(self.parser.displayed_analysis[-1], accepted_display)
                self.assertEqual(len(self.parser.displayed_analysis), display_count)
                self.assertEqual(self.widgets.analysis_filter_scope.currentData(), scope)
                self.assertEqual(self.widgets.analysis_filter_entry.text(), value)
                self.assertEqual(self.widgets.analysis_filter_clause_buttons, [])

        self.assertEqual(len(errors), 2)
        self.assertIn("FLAG", errors[0])
        self.assertIn("numeric", errors[1])

    def test_structured_empty_match_is_safe(self):
        self.bind_source()

        self.add_filter("TYPE", "NoSuchType")

        self.assertEqual(self.controller.current_result.count, 0)
        self.assertEqual(self.widgets.analysis_event_count_chip.text(), "0 / 3 EVENTS")
        self.assertEqual(len(self.widgets.analysis_filter_clause_buttons), 1)

    def test_quick_search_stays_live_and_composes_with_persistent_clauses(self):
        self.bind_source()
        self.add_filter("TYPE", "HitPoints")
        accepted_chip = self.widgets.analysis_filter_clause_buttons[0]
        displays_before_search = len(self.parser.displayed_analysis)

        self.widgets.analysis_filter_scope.setCurrentText("OWNER")
        self.widgets.analysis_filter_entry.setText("Alice")

        self.assertEqual(
            self.controller.state,
            WorkbenchState(
                owner_query="Alice",
                clauses=(WorkbenchFilterClause("TYPE", "HitPoints"),),
            ),
        )
        self.assertEqual(self.controller.current_result.count, 2)
        self.assertGreater(len(self.parser.displayed_analysis), displays_before_search)
        self.assertEqual(len(self.widgets.analysis_filter_clause_buttons), 1)
        self.assertIs(self.widgets.analysis_filter_clause_buttons[0], accepted_chip)

    def test_filter_builds_display_only_view_without_replacing_parser_truth(self):
        self.bind_source()
        parser_combat_list = self.parser._parser.combats

        self.widgets.analysis_filter_entry.setText("Alice")

        self.assertTrue(self.controller.state.is_modified)
        self.assertEqual(self.controller.current_result.count, 2)
        self.assertEqual(len(self.controller.cache), 1)
        derived = self.controller.current_view.combat
        self.assertIs(self.parser.displayed_analysis[-1], derived)
        self.assertIsNot(derived, self.source)
        self.assertFalse(self.controller.current_view.league_eligible)

        self.assertIs(self.parser._parser.current_combat, self.source)
        self.assertIs(self.parser._parser.combats, parser_combat_list)
        self.assertEqual(self.parser._parser.combats, [self.source])
        self.assertEqual(tuple(self.source.log_data), self.source_lines)
        self.assertEqual(tuple(self.source.root_items), self.source_roots)
        self.assertEqual(self.source.file_pos, self.source_file_pos)

        self.assertTrue(self.widgets.analysis_truth_chip.isHidden())
        self.assertFalse(self.widgets.analysis_modified_chip.isHidden())
        self.assertEqual(self.widgets.analysis_event_count_chip.text(), "2 / 3 EVENTS")
        self.assertTrue(self.widgets.analysis_reset_button.isEnabled())
        self.assertEqual(self.tables.modified_states[-1], True)
        self.assertTrue(all(plot.clear_count == 2 for plot in self.widgets.analysis_plots))

    def test_reset_restores_exact_source_and_clears_modified_context(self):
        self.bind_source()
        self.add_filter("TYPE", "HitPoints")
        self.assertFalse(self.widgets.analysis_filter_clause_row.isHidden())

        self.widgets.analysis_reset_button.click()

        self.assertEqual(self.widgets.analysis_filter_entry.text(), "")
        self.assertEqual(self.widgets.analysis_filter_scope.currentData(), "ANY")
        self.assertEqual(self.widgets.analysis_start_entry.text(), "")
        self.assertEqual(self.widgets.analysis_end_entry.text(), "")
        self.assertEqual(self.controller.state, WorkbenchState.parser_truth())
        self.assertIsNone(self.controller.current_result)
        self.assertIsNone(self.controller.current_view)
        self.assertIs(self.parser.displayed_analysis[-1], self.source)
        self.assertEqual(self.tables.modified_states[-1], False)
        self.assertFalse(self.widgets.analysis_truth_chip.isHidden())
        self.assertTrue(self.widgets.analysis_modified_chip.isHidden())
        self.assertEqual(self.widgets.analysis_event_count_chip.text(), "3 EVENTS")
        self.assertFalse(self.widgets.analysis_reset_button.isEnabled())
        self.assertTrue(self.widgets.analysis_filter_clause_row.isHidden())
        self.assertEqual(self.widgets.analysis_filter_clause_buttons, [])
        self.assertTrue(all(plot.clear_count == 3 for plot in self.widgets.analysis_plots))

    def test_empty_filter_is_a_safe_modified_display(self):
        self.bind_source()

        applied = self.controller.apply_state(WorkbenchState(owner_query="missing"))

        self.assertTrue(applied)
        self.assertEqual(self.controller.current_result.count, 0)
        self.assertIsNot(self.parser.displayed_analysis[-1], self.source)
        self.assertEqual(self.widgets.analysis_event_count_chip.text(), "0 / 3 EVENTS")
        for model in (
                self.parser.displayed_analysis[-1].damage_out,
                self.parser.displayed_analysis[-1].damage_in,
                self.parser.displayed_analysis[-1].heals_out,
                self.parser.displayed_analysis[-1].heals_in):
            self.assertEqual(model._player.child_count, 0)
            self.assertEqual(model._npc.child_count, 0)

    def test_selecting_another_official_combat_resets_all_modifiers(self):
        self.bind_source()
        self.add_filter("TYPE", "HitPoints")
        self.assertEqual(len(self.widgets.analysis_filter_clause_buttons), 1)
        second = analyzed_combat(combat_id=8, owner_names=("Carol", "Dan"))

        self.parser._parser.current_combat = second
        self.parser._parser.combats.append(second)
        self.parser.combat_displayed.emit(second)

        self.assertIs(self.controller.source_combat, second)
        self.assertEqual(self.controller.state, WorkbenchState.parser_truth())
        self.assertEqual(self.widgets.analysis_filter_entry.text(), "")
        self.assertEqual(self.widgets.analysis_filter_scope.currentData(), "ANY")
        self.assertEqual(self.widgets.analysis_start_entry.text(), "")
        self.assertEqual(self.widgets.analysis_end_entry.text(), "")
        self.assertIsNone(self.controller.current_view)
        self.assertIsNone(self.controller.current_result)
        self.assertEqual(self.tables.modified_states[-1], False)
        self.assertEqual(self.widgets.analysis_event_count_chip.text(), "2 EVENTS")
        self.assertTrue(self.widgets.analysis_filter_clause_row.isHidden())
        self.assertEqual(self.widgets.analysis_filter_clause_buttons, [])

    def test_failed_candidate_is_transactional_and_emits_error(self):
        unfinished = make_combat([make_line(0)])
        unfinished.end_time = None
        errors = []
        self.controller.view_failed.connect(errors.append)
        self.parser.combat_displayed.emit(unfinished)

        applied = self.controller.apply_state(WorkbenchState(text_query="beam"))

        self.assertFalse(applied)
        self.assertEqual(len(errors), 1)
        self.assertEqual(self.controller.state, WorkbenchState.parser_truth())
        self.assertIsNone(self.controller.current_view)
        self.assertEqual(self.parser.displayed_analysis, [])

    def test_scope_query_and_time_cut_form_one_complete_state(self):
        self.bind_source()
        self.widgets.analysis_filter_scope.setCurrentText("OWNER")
        self.widgets.analysis_filter_entry.setText("Alice")
        self.widgets.analysis_start_entry.setText("1")
        self.widgets.analysis_start_entry.editingFinished.emit()

        self.assertEqual(
            self.controller.state,
            WorkbenchState(owner_query="Alice", start_seconds=1.0),
        )
        self.assertEqual(self.controller.current_result.count, 1)

        self.widgets.analysis_end_entry.setText("2")
        self.widgets.analysis_end_entry.editingFinished.emit()

        self.assertEqual(
            self.controller.state,
            WorkbenchState(
                owner_query="Alice", start_seconds=1.0, end_seconds=2.0),
        )
        self.assertEqual(self.controller.current_result.count, 1)

    def test_changing_scope_moves_query_without_losing_time_cut(self):
        self.bind_source()
        self.widgets.analysis_start_entry.setText("1")
        self.widgets.analysis_start_entry.editingFinished.emit()
        self.widgets.analysis_filter_entry.setText("Beam")
        self.widgets.analysis_filter_scope.setCurrentText("EVENT")

        self.assertEqual(
            self.controller.state,
            WorkbenchState(event_query="Beam", start_seconds=1.0),
        )
        self.assertEqual(self.controller.current_result.count, 2)

    def test_clearing_time_bound_applies_without_leaving_the_field(self):
        self.bind_source()
        self.widgets.analysis_start_entry.setText("1")
        self.widgets.analysis_start_entry.editingFinished.emit()
        displays_before_clear = len(self.parser.displayed_analysis)

        self.widgets.analysis_start_entry.clear()

        self.assertEqual(self.controller.state, WorkbenchState.parser_truth())
        self.assertEqual(len(self.parser.displayed_analysis), displays_before_clear + 1)
        self.assertIs(self.parser.displayed_analysis[-1], self.source)

    def test_invalid_time_controls_do_not_replace_current_display(self):
        self.bind_source()
        self.widgets.analysis_filter_entry.setText("Alice")
        accepted_state = self.controller.state
        accepted_display = self.parser.displayed_analysis[-1]
        display_count = len(self.parser.displayed_analysis)
        errors = []
        self.controller.view_failed.connect(errors.append)

        invalid_values = ("not-a-number", "-1", "nan", "inf")
        for invalid in invalid_values:
            self.widgets.analysis_start_entry.setText(invalid)
            self.widgets.analysis_start_entry.editingFinished.emit()
            self.assertEqual(self.controller.state, accepted_state)
            self.assertIs(self.parser.displayed_analysis[-1], accepted_display)
            self.assertEqual(len(self.parser.displayed_analysis), display_count)

        self.widgets.analysis_start_entry.setText("2")
        self.widgets.analysis_end_entry.setText("1")
        self.widgets.analysis_end_entry.editingFinished.emit()

        self.assertEqual(self.controller.state, accepted_state)
        self.assertIs(self.parser.displayed_analysis[-1], accepted_display)
        self.assertEqual(len(self.parser.displayed_analysis), display_count)
        self.assertEqual(len(errors), len(invalid_values) + 1)
        self.assertIn("START must not be greater than END", errors[-1])

    def test_reset_blocks_control_signals_until_coherent_truth_state(self):
        self.bind_source()
        self.widgets.analysis_filter_scope.setCurrentText("TARGET")
        self.widgets.analysis_filter_entry.setText("Alice")
        self.widgets.analysis_start_entry.setText("1")
        self.widgets.analysis_start_entry.editingFinished.emit()
        displays_before_reset = len(self.parser.displayed_analysis)

        self.controller.reset()

        self.assertEqual(
            len(self.parser.displayed_analysis), displays_before_reset + 1)
        self.assertEqual(self.widgets.analysis_filter_scope.currentData(), "ANY")
        self.assertEqual(self.widgets.analysis_filter_entry.text(), "")
        self.assertEqual(self.widgets.analysis_start_entry.text(), "")
        self.assertEqual(self.widgets.analysis_end_entry.text(), "")
        self.assertEqual(self.controller.state, WorkbenchState.parser_truth())


if __name__ == "__main__":
    unittest.main()
