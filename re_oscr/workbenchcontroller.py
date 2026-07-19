"""Command Console controller for the fused Analysis Workbench."""

from __future__ import annotations

from dataclasses import replace
import json
from math import isfinite
from pathlib import Path

from PySide6.QtCore import QObject, QSignalBlocker, Qt, Signal, Slot
from PySide6.QtWidgets import QDialog, QPushButton

from OSCR.combat import Combat

from .clacoprocessor import (
    ClaCoprocessorError,
    DamageOutPreviewResult,
    analyze_damage_out_preview,
)
from .workbench import (
    BUNDLED_WORKBENCH_RULE_SETS,
    WorkbenchCombatView,
    WorkbenchDataError,
    WorkbenchFilterClause,
    WorkbenchIndexCache,
    WorkbenchQueryResult,
    WorkbenchRule,
    WorkbenchRuleSet,
    WorkbenchState,
    count_effective_events,
    derive_workbench_combat,
)
from .workbenchruleeditor import WorkbenchRuleEditor
from .workbenchrules import WorkbenchRuleSetStore, WorkbenchRuleStoreError


class AnalysisWorkbenchController(QObject):
    """Apply display-only modifiers while keeping parser and League truth isolated."""

    state_changed = Signal(object, int, int)
    view_failed = Signal(str)

    QUICK_FILTER_SCOPES = frozenset(("ANY", "OWNER", "SOURCE", "TARGET", "EVENT"))
    BUILDER_FILTER_SCOPES = frozenset((
        "TYPE", "FLAG", "MIN_MAGNITUDE", "MAX_MAGNITUDE"))
    FILTER_PLACEHOLDERS = {
        "TYPE": "TYPE, E.G. HITPOINTS",
        "FLAG": "CRITICAL, MISS, OR KILL",
        "MIN_MAGNITUDE": "MINIMUM ABSOLUTE MAGNITUDE",
        "MAX_MAGNITUDE": "MAXIMUM ABSOLUTE MAGNITUDE",
    }

    def __init__(
            self, parser, tables, widgets, config_dir: str | Path | None = None,
            settings=None, parent=None, product_version: str = "",
            build_revision: str | None = None):
        super().__init__()
        self.parser = parser
        self.tables = tables
        self.widgets = widgets
        self.parent = parent
        self.settings = settings
        self.product_version = product_version
        self.build_revision = build_revision
        self.cache = WorkbenchIndexCache()
        self.state = WorkbenchState.parser_truth()
        self.source_combat: Combat | None = None
        self.current_result: WorkbenchQueryResult | None = None
        self.current_view: WorkbenchCombatView | None = None
        self._controls_attached = False
        self._last_filter_scope = "ANY"
        self._rendered_clauses: tuple[WorkbenchFilterClause, ...] = ()
        self._rendered_rules: tuple[WorkbenchRule, ...] = ()
        self.rule_store = WorkbenchRuleSetStore(config_dir)
        self.rule_sets: tuple[WorkbenchRuleSet, ...] = BUNDLED_WORKBENCH_RULE_SETS
        self._custom_rule_sets: tuple[WorkbenchRuleSet, ...] = ()
        self._selected_rule_set_index = 0
        self._working_rule_set = _disabled_rule_set(self.rule_sets[0])
        self._rule_sets_loaded = False
        self._cla_preview_dialog = None
        self.parser.combat_displayed.connect(self.bind_combat)
        combat_cleared = getattr(self.parser, "combat_cleared", None)
        if combat_cleared is not None:
            combat_cleared.connect(self.unbind_combat)

    def attach_controls(self) -> None:
        """Connect controls after the Command Console Analysis page has constructed them."""
        if self._controls_attached:
            return
        if self.widgets.analysis_filter_scope is not None:
            self.widgets.analysis_filter_scope.currentIndexChanged.connect(
                self._filter_scope_changed)
        if self.widgets.analysis_filter_entry is not None:
            self.widgets.analysis_filter_entry.textChanged.connect(
                self._filter_text_changed)
        if self.widgets.analysis_filter_add_button is not None:
            self.widgets.analysis_filter_add_button.clicked.connect(
                self.add_filter_clause)
        if self.widgets.analysis_start_entry is not None:
            self.widgets.analysis_start_entry.editingFinished.connect(self._apply_controls)
            self.widgets.analysis_start_entry.textChanged.connect(
                self._time_text_changed)
        if self.widgets.analysis_end_entry is not None:
            self.widgets.analysis_end_entry.editingFinished.connect(self._apply_controls)
            self.widgets.analysis_end_entry.textChanged.connect(
                self._time_text_changed)
        if self.widgets.analysis_reset_button is not None:
            self.widgets.analysis_reset_button.clicked.connect(self.reset)
        cla_preview_button = getattr(self.widgets, "analysis_cla_preview_button", None)
        if cla_preview_button is not None:
            cla_preview_button.clicked.connect(self.open_cla_damage_out_preview)
        rule_selector = getattr(self.widgets, "analysis_rule_set_selector", None)
        if rule_selector is not None:
            rule_selector.currentIndexChanged.connect(self._rule_set_changed)
        rules_button = getattr(self.widgets, "analysis_rules_button", None)
        if rules_button is not None:
            rules_button.clicked.connect(self.edit_rules)
        self._controls_attached = True
        self._load_rule_sets()
        self._last_filter_scope = self._selected_filter_scope()
        self._update_filter_placeholder()
        self._update_controls(0, 0)

    @Slot(Combat)
    def bind_combat(self, combat: Combat) -> None:
        """Open parser truth or the user's explicit auto-enabled preferred rule profile."""
        self._close_cla_preview()
        self.source_combat = combat
        self.state = WorkbenchState.parser_truth()
        self.current_result = None
        self.current_view = None
        self._working_rule_set = self._rule_set_with_auto_preferences(
            self._selected_rule_set())
        self.tables.set_analysis_modified(False)
        self._reset_modifier_controls()
        self._clear_plots()
        total_count = self._source_event_count()
        visible_count = total_count or 0
        if self._working_rule_set.enabled_rules:
            candidate = WorkbenchState(rules=self._working_rule_set.enabled_rules)
            if self.apply_state(candidate):
                return
            self._working_rule_set = _disabled_rule_set(self._selected_rule_set())
        self._update_controls(visible_count, total_count)
        self.state_changed.emit(self.state, visible_count, visible_count)

    @Slot()
    def unbind_combat(self) -> None:
        """Drop every result tied to a parser that has begun loading a different log."""
        self._close_cla_preview()
        self.source_combat = None
        self.state = WorkbenchState.parser_truth()
        self.current_result = None
        self.current_view = None
        self.cache.clear()
        self._working_rule_set = _disabled_rule_set(self._selected_rule_set())
        self.tables.set_analysis_modified(False)
        self._reset_modifier_controls()
        self._clear_plots()
        self._update_controls(0, 0)
        self.state_changed.emit(self.state, 0, 0)

    @Slot(str)
    def apply_text_filter(self, text: str) -> None:
        """Compatibility entry point that applies all currently visible controls."""
        entry = self.widgets.analysis_filter_entry
        if entry is not None and entry.text() != text:
            blocker = QSignalBlocker(entry)
            entry.setText(text)
            del blocker
        self._apply_controls()

    @Slot(int)
    def _filter_scope_changed(self, _index: int) -> None:
        """Move quick queries directly; isolate structured builder drafts."""
        scope = self._selected_filter_scope()
        crosses_builder = (
            scope in self.BUILDER_FILTER_SCOPES
            or self._last_filter_scope in self.BUILDER_FILTER_SCOPES
        )
        self._last_filter_scope = scope
        if crosses_builder:
            entry = self.widgets.analysis_filter_entry
            if entry is not None and entry.text():
                blocker = QSignalBlocker(entry)
                entry.clear()
                del blocker
        self._update_filter_placeholder()
        self._update_add_filter_button()
        if crosses_builder or scope in self.QUICK_FILTER_SCOPES:
            self._apply_controls()

    @Slot(str)
    def _filter_text_changed(self, _text: str) -> None:
        """Apply quick search immediately; structured values wait for ADD FILTER."""
        self._update_add_filter_button()
        if self._selected_filter_scope() in self.QUICK_FILTER_SCOPES:
            self._apply_controls()

    @Slot()
    @Slot(str)
    @Slot(int)
    def _apply_controls(self, *_signal_arguments) -> None:
        """Build one complete modifier state and present it transactionally."""
        try:
            candidate = self._state_from_controls()
        except ValueError as error:
            self.view_failed.emit(str(error))
            return
        self.apply_state(candidate)

    @Slot(str)
    def _time_text_changed(self, text: str) -> None:
        """Apply a cleared bound immediately; non-empty edits wait for commit."""
        if not text.strip():
            self._apply_controls()

    def _state_from_controls(self) -> WorkbenchState:
        """Read the entire modifier strip without mutating the active state."""
        scope = self._selected_filter_scope()

        valid_scopes = self.QUICK_FILTER_SCOPES | self.BUILDER_FILTER_SCOPES
        if scope not in valid_scopes:
            raise ValueError(f"unknown Analysis filter scope: {scope or 'empty'}")

        if scope in self.QUICK_FILTER_SCOPES:
            entry = self.widgets.analysis_filter_entry
            query = entry.text() if entry is not None else ""
            query_fields = {
                "owner_query": "",
                "source_query": "",
                "target_query": "",
                "event_query": "",
                "text_query": "",
            }
            field_for_scope = {
                "ANY": "text_query",
                "OWNER": "owner_query",
                "SOURCE": "source_query",
                "TARGET": "target_query",
                "EVENT": "event_query",
            }
            query_fields[field_for_scope[scope]] = query
        else:
            # TYPE/FLAG/magnitude values are only drafts until ADD FILTER.  They
            # must not hide a formerly-live quick query behind builder controls.
            query_fields = {
                "owner_query": "",
                "source_query": "",
                "target_query": "",
                "event_query": "",
                "text_query": "",
            }

        start_seconds = self._optional_seconds(
            self.widgets.analysis_start_entry, "START")
        end_seconds = self._optional_seconds(
            self.widgets.analysis_end_entry, "END")
        if (start_seconds is not None and end_seconds is not None
                and start_seconds > end_seconds):
            raise ValueError("START must not be greater than END")

        return WorkbenchState(
            **query_fields,
            clauses=self.state.clauses,
            rules=self.state.rules,
            start_seconds=start_seconds,
            end_seconds=end_seconds,
        )

    def _selected_filter_scope(self) -> str:
        scope_widget = self.widgets.analysis_filter_scope
        if scope_widget is None:
            return "ANY"
        scope_data = scope_widget.currentData()
        scope = scope_data if scope_data is not None else scope_widget.currentText()
        return str(scope).strip().upper()

    @Slot()
    def add_filter_clause(self) -> None:
        """Validate and commit the current builder value as a persistent predicate."""
        entry = self.widgets.analysis_filter_entry
        if self.source_combat is None or entry is None or not entry.text().strip():
            self._update_add_filter_button()
            return

        scope = self._selected_filter_scope()
        raw_value = entry.text()
        try:
            clause = WorkbenchFilterClause(scope, raw_value)
            start_seconds = self._optional_seconds(
                self.widgets.analysis_start_entry, "START")
            end_seconds = self._optional_seconds(
                self.widgets.analysis_end_entry, "END")
            if (start_seconds is not None and end_seconds is not None
                    and start_seconds > end_seconds):
                raise ValueError("START must not be greater than END")
            candidate = WorkbenchState(
                clauses=(*self.state.clauses, clause),
                rules=self.state.rules,
                start_seconds=start_seconds,
                end_seconds=end_seconds,
            )
        except (TypeError, ValueError) as error:
            # Keep the accepted display and the complete draft intact so the user
            # can correct it in place.
            self.view_failed.emit(str(error))
            return

        if not self.apply_state(candidate):
            return

        # The candidate view is already accepted.  Clearing the builder only now
        # prevents its signals from creating a partial intermediate state.
        controls = tuple(control for control in (
            self.widgets.analysis_filter_scope,
            self.widgets.analysis_filter_entry,
        ) if control is not None)
        blockers = [QSignalBlocker(control) for control in controls]
        self._set_filter_scope_to_any()
        entry.clear()
        del blockers
        self._update_add_filter_button()

    @Slot(int)
    def remove_filter_clause(self, index: int) -> None:
        """Remove one accepted clause while preserving quick search and time cuts."""
        if index < 0 or index >= len(self.state.clauses):
            return
        clauses = list(self.state.clauses)
        del clauses[index]
        self.apply_state(self.state.with_changes(clauses=tuple(clauses)))

    @staticmethod
    def _optional_seconds(entry, label: str) -> float | None:
        if entry is None or not entry.text().strip():
            return None
        try:
            value = float(entry.text().strip())
        except ValueError as error:
            raise ValueError(
                f"{label} must be a finite non-negative number of seconds") from error
        if not isfinite(value) or value < 0:
            raise ValueError(
                f"{label} must be a finite non-negative number of seconds")
        return value

    def apply_state(self, candidate: WorkbenchState) -> bool:
        """Build a complete candidate view before transactionally presenting it."""
        if self.source_combat is None:
            return False
        if candidate == self.state:
            return True
        try:
            if candidate.is_modified:
                index = self.cache.get(self.source_combat)
                result = index.query(candidate)
                view = derive_workbench_combat(result)
                display_combat = view.combat
                selected_count = result.count
                total_count = len(index)
            else:
                result = None
                view = None
                display_combat = self.source_combat
                total_count = self._source_event_count()
                selected_count = total_count or 0
        except (WorkbenchDataError, ValueError) as error:
            self.view_failed.emit(str(error))
            return False

        self._clear_plots()
        self._close_cla_preview()
        self.parser.display_analysis(display_combat)
        self.tables.set_analysis_modified(candidate.is_modified)
        self.state = candidate
        self.current_result = result
        self.current_view = view
        self._update_controls(selected_count, total_count)
        self.state_changed.emit(candidate, selected_count, total_count or 0)
        return True

    @Slot()
    def reset(self) -> None:
        """Return every Analysis mode to the currently selected parser-truth combat."""
        self._working_rule_set = _disabled_rule_set(self._selected_rule_set())
        self._reset_modifier_controls()
        self.apply_state(WorkbenchState.parser_truth())

    @Slot(int)
    def _rule_set_changed(self, index: int) -> None:
        """Select a definition set with every per-combat rule safely defaulted off."""
        if index < 0 or index >= len(self.rule_sets):
            return
        previous_index = self._selected_rule_set_index
        previous_working = self._working_rule_set
        self._selected_rule_set_index = index
        self._working_rule_set = _disabled_rule_set(self.rule_sets[index])
        if self.source_combat is not None:
            if not self.apply_state(self.state.with_changes(rules=())):
                self._selected_rule_set_index = previous_index
                self._working_rule_set = previous_working
                self._set_rule_selector_index(previous_index)
        else:
            self.state = self.state.with_changes(rules=())
            self._update_controls(0, 0)
        self._remember_selected_rule_set()

    @Slot()
    def edit_rules(self) -> None:
        """Edit one immutable snapshot and apply its enabled rules transactionally."""
        dialog = WorkbenchRuleEditor(
            self.parent,
            self._working_rule_set,
            auto_enable=self._auto_enabled_for(self._selected_rule_set()),
            geometry=getattr(self.settings, 'state__workbench_rule_editor_geometry', None),
        )
        dialog_code = dialog.exec()
        if self.settings is not None and hasattr(dialog, 'saveGeometry'):
            self.settings.state__workbench_rule_editor_geometry = dialog.saveGeometry()
        edited = dialog.result_rule_set
        auto_enable = bool(getattr(dialog, "result_auto_enable", False))
        if hasattr(dialog, "setParent"):
            dialog.setParent(None)
        if hasattr(dialog, "deleteLater"):
            dialog.deleteLater()
        if dialog_code != QDialog.DialogCode.Accepted or edited is None:
            return

        previous_state = self.state
        source_definition = self._selected_rule_set()
        definitions_changed = (
            _rule_set_definition_signature(edited)
            != _rule_set_definition_signature(source_definition)
        )
        selected_index = self._selected_rule_set_index
        candidate_custom_sets = self._custom_rule_sets
        candidate_rule_sets = self.rule_sets
        if source_definition.read_only and definitions_changed:
            edited = replace(
                edited,
                name=self._unique_custom_name(edited.name),
                read_only=False,
            )
            custom_definition = _disabled_rule_set(edited)
            candidate_custom_sets = (*self._custom_rule_sets, custom_definition)
            candidate_rule_sets = (*BUNDLED_WORKBENCH_RULE_SETS, *candidate_custom_sets)
            selected_index = len(candidate_rule_sets) - 1
        elif not source_definition.read_only and definitions_changed:
            edited = replace(edited, read_only=False)
            custom_index = selected_index - len(BUNDLED_WORKBENCH_RULE_SETS)
            custom_sets = list(self._custom_rule_sets)
            if custom_index < 0 or custom_index >= len(custom_sets):
                self.view_failed.emit("Unable to locate the selected custom rule set")
                return
            custom_sets[custom_index] = _disabled_rule_set(edited)
            candidate_custom_sets = tuple(custom_sets)
            candidate_rule_sets = (*BUNDLED_WORKBENCH_RULE_SETS, *candidate_custom_sets)

        candidate = self.state.with_changes(rules=edited.enabled_rules)
        if self.source_combat is None:
            # Definitions can be managed before a combat is selected, but activation remains
            # per-combat and therefore safely defaults off.
            candidate = self.state.with_changes(rules=())
        elif not self.apply_state(candidate):
            return

        if definitions_changed and not self._save_custom_rule_sets(candidate_custom_sets):
            if self.source_combat is not None:
                # The accepted display predates persistence.  Restore it if the atomic write
                # fails so the selector, rule editor, and visible tree remain one transaction.
                self.apply_state(previous_state)
            return

        self._custom_rule_sets = candidate_custom_sets
        self.rule_sets = candidate_rule_sets
        self._selected_rule_set_index = selected_index
        self._working_rule_set = (
            _disabled_rule_set(edited) if self.source_combat is None else edited)
        if definitions_changed:
            self._populate_rule_set_selector(selected_index)
        self._remember_selected_rule_set()
        self._store_auto_preferences(edited, auto_enable)
        if self.source_combat is None:
            self.state = candidate
            self._update_controls(0, 0)

    @Slot(int)
    def remove_rule(self, index: int) -> None:
        """Disable one active rule while preserving filters and time cuts."""
        active_rules = self.state.active_rules
        if index < 0 or index >= len(active_rules):
            return
        active = active_rules[index]
        rules = list(self._working_rule_set.rules)
        matched_index = None
        for rule_index, rule in enumerate(rules):
            if rule is active:
                matched_index = rule_index
                break
        if matched_index is None:
            for rule_index, rule in enumerate(rules):
                if _same_rule_definition(rule, active):
                    matched_index = rule_index
                    break
        if matched_index is not None:
            rules[matched_index] = replace(rules[matched_index], enabled=False)
        previous = self._working_rule_set
        self._working_rule_set = replace(self._working_rule_set, rules=tuple(rules))
        removed = False
        candidate_rules = []
        for rule in self.state.rules:
            if not removed and rule is active:
                removed = True
                continue
            candidate_rules.append(rule)
        if not self.apply_state(self.state.with_changes(rules=tuple(candidate_rules))):
            self._working_rule_set = previous

    def _reset_modifier_controls(self) -> None:
        """Restore the modifier strip without triggering partial intermediate states."""
        controls = tuple(control for control in (
            self.widgets.analysis_filter_scope,
            self.widgets.analysis_filter_entry,
            self.widgets.analysis_start_entry,
            self.widgets.analysis_end_entry,
        ) if control is not None)
        blockers = [QSignalBlocker(control) for control in controls]

        self._set_filter_scope_to_any()
        for entry in (
                self.widgets.analysis_filter_entry,
                self.widgets.analysis_start_entry,
                self.widgets.analysis_end_entry):
            if entry is not None:
                entry.clear()

        # Keep every blocker alive until all related controls hold a coherent reset state.
        del blockers
        self._update_add_filter_button()

    def _set_filter_scope_to_any(self) -> None:
        scope = self.widgets.analysis_filter_scope
        if scope is None:
            return
        any_index = scope.findData("ANY")
        if any_index < 0:
            any_index = scope.findText("ANY")
        if any_index < 0 and scope.count():
            any_index = 0
        if any_index >= 0:
            scope.setCurrentIndex(any_index)
        self._last_filter_scope = "ANY"
        self._update_filter_placeholder()

    def _update_filter_placeholder(self) -> None:
        entry = self.widgets.analysis_filter_entry
        if entry is None:
            return
        entry.setPlaceholderText(self.FILTER_PLACEHOLDERS.get(
            self._selected_filter_scope(), "SEARCH COMBAT EVENTS"))

    def _clear_plots(self) -> None:
        for plot in self.widgets.analysis_plots:
            plot.clear()

    def build_cla_damage_out_preview(self) -> DamageOutPreviewResult:
        """Build the parser-truth-only dev15 preview without touching visible OSCR models."""
        if self.source_combat is None:
            raise WorkbenchDataError("select an OSCR combat before opening the CLA preview")
        if self.state.is_modified:
            raise WorkbenchDataError(
                "reset Analysis modifiers before opening the dev15 CLA preview")
        index = self.cache.get(self.source_combat)
        return analyze_damage_out_preview(
            index.snapshot_json,
            index.snapshot_id,
            product_version=self.product_version,
            build_revision=self.build_revision,
        )

    @Slot()
    def open_cla_damage_out_preview(self) -> None:
        """Open a dedicated, non-uploadable result surface for tester comparison."""
        try:
            result = self.build_cla_damage_out_preview()
        except (ClaCoprocessorError, WorkbenchDataError, ValueError) as error:
            self.view_failed.emit(str(error))
            return

        from .clapreview import ClaDamageOutPreviewDialog

        self._close_cla_preview()
        dialog = ClaDamageOutPreviewDialog(result, self.parent)
        self._cla_preview_dialog = dialog
        dialog.destroyed.connect(
            lambda _object=None, opened=dialog:
            self._forget_cla_preview(opened))
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _forget_cla_preview(self, dialog) -> None:
        if self._cla_preview_dialog is dialog:
            self._cla_preview_dialog = None

    def _close_cla_preview(self) -> None:
        dialog = self._cla_preview_dialog
        self._cla_preview_dialog = None
        if dialog is not None:
            dialog.close()

    def _source_event_count(self) -> int | None:
        """Return the parser-consumed event count when the combat can be indexed."""
        if self.source_combat is None:
            return None
        try:
            return count_effective_events(self.source_combat)
        except WorkbenchDataError:
            # Analysis remains usable for an incomplete/invalid combat even if
            # the display-only Workbench cannot truthfully count its events.
            return None

    def _update_controls(
            self, selected_count: int, total_count: int | None) -> None:
        has_combat = self.source_combat is not None
        modified = has_combat and self.state.is_modified
        if self.widgets.analysis_truth_chip is not None:
            self.widgets.analysis_truth_chip.setVisible(has_combat and not modified)
        if self.widgets.analysis_modified_chip is not None:
            self.widgets.analysis_modified_chip.setVisible(modified)
        if self.widgets.analysis_event_count_chip is not None:
            if modified:
                text = (
                    f"{selected_count:,} / {total_count:,} EVENTS"
                    if total_count is not None
                    else f"{selected_count:,} EVENTS // MODIFIED"
                )
            elif has_combat:
                text = (
                    f"{total_count:,} EVENTS"
                    if total_count is not None else "PARSER OUTPUT"
                )
            else:
                text = "NO COMBAT"
            self.widgets.analysis_event_count_chip.setText(text)
        if self.widgets.analysis_reset_button is not None:
            self.widgets.analysis_reset_button.setEnabled(modified)
        cla_preview_button = getattr(self.widgets, "analysis_cla_preview_button", None)
        if cla_preview_button is not None:
            cla_preview_button.setEnabled(has_combat and not modified)
            if modified:
                cla_preview_button.setToolTip(
                    "Reset Analysis modifiers before opening the dev15 CLA preview")
            else:
                cla_preview_button.setToolTip(
                    "Open the source-audited Damage Out technical preview for the unmodified "
                    "OSCR-selected combat")
        self._sync_modifier_chips()
        self._update_add_filter_button()

    def _update_add_filter_button(self) -> None:
        button = self.widgets.analysis_filter_add_button
        if button is None:
            return
        entry = self.widgets.analysis_filter_entry
        has_value = entry is not None and bool(entry.text().strip())
        button.setEnabled(self.source_combat is not None and has_value)

    def _sync_modifier_chips(self) -> None:
        """Rebuild filter and rule chips from the single accepted state."""
        layout = self.widgets.analysis_filter_clause_layout
        row = self.widgets.analysis_filter_clause_row
        if layout is None:
            if row is not None:
                row.setVisible(False)
            self.widgets.analysis_filter_clause_buttons = []
            setattr(self.widgets, "analysis_rule_chip_buttons", [])
            return

        clauses = tuple(self.state.clauses)
        rules = self.state.active_rules
        if clauses == self._rendered_clauses and rules == self._rendered_rules:
            if row is not None:
                row.setVisible(bool(clauses or rules))
            return

        all_buttons = (
            *self.widgets.analysis_filter_clause_buttons,
            *getattr(self.widgets, "analysis_rule_chip_buttons", ()),
        )
        for button in all_buttons:
            layout.removeWidget(button)
            button.setParent(None)
            button.deleteLater()

        buttons = []
        parent = self.widgets.analysis_filter_clause_container
        for index, clause in enumerate(clauses):
            button = QPushButton(f"{clause.display_label}  X", parent)
            button.setObjectName(f"analysisWorkbenchClause{index}")
            button.setProperty("consoleRole", "filterClauseChip")
            button.setToolTip(f"Remove filter: {clause.display_label}")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(
                lambda _checked=False, clause_index=index:
                self.remove_filter_clause(clause_index))
            layout.addWidget(button)
            buttons.append(button)

        self.widgets.analysis_filter_clause_buttons = buttons
        rule_buttons = []
        for index, rule in enumerate(rules):
            button = QPushButton(f"{rule.display_label}  X", parent)
            button.setObjectName(f"analysisWorkbenchRuleChip{index}")
            button.setProperty("consoleRole", "filterClauseChip")
            button.setProperty("modifierType", "rule")
            button.setToolTip(f"Disable rule: {rule.display_label}")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(
                lambda _checked=False, rule_index=index:
                self.remove_rule(rule_index))
            layout.addWidget(button)
            rule_buttons.append(button)
        self.widgets.analysis_rule_chip_buttons = rule_buttons
        self._rendered_clauses = clauses
        self._rendered_rules = rules
        if row is not None:
            row.setVisible(bool(buttons or rule_buttons))

    def _load_rule_sets(self) -> None:
        if self._rule_sets_loaded:
            return
        try:
            self._custom_rule_sets = self.rule_store.load()
        except WorkbenchRuleStoreError as error:
            self._custom_rule_sets = ()
            self.view_failed.emit(str(error))
        self.rule_sets = (*BUNDLED_WORKBENCH_RULE_SETS, *self._custom_rule_sets)
        preferred_name = str(
            getattr(self.settings, "workbench_rule_set", "") or "").casefold()
        selected_index = next(
            (
                index for index, rule_set in enumerate(self.rule_sets)
                if rule_set.name.casefold() == preferred_name
            ),
            0,
        )
        self._selected_rule_set_index = selected_index
        self._working_rule_set = self._rule_set_with_auto_preferences(
            self.rule_sets[selected_index])
        self._populate_rule_set_selector(selected_index)
        self._remember_selected_rule_set()
        self._rule_sets_loaded = True

    def _populate_rule_set_selector(self, selected_index: int) -> None:
        selector = getattr(self.widgets, "analysis_rule_set_selector", None)
        if selector is None:
            return
        blocker = QSignalBlocker(selector)
        selector.clear()
        for rule_set in self.rule_sets:
            suffix = " // BUNDLED" if rule_set.read_only else " // CUSTOM"
            selector.addItem(rule_set.name.upper() + suffix)
        if selector.count():
            selector.setCurrentIndex(min(max(selected_index, 0), selector.count() - 1))
            selector.setEnabled(True)
        del blocker
        self._selected_rule_set_index = selector.currentIndex()
        rules_button = getattr(self.widgets, "analysis_rules_button", None)
        if rules_button is not None:
            rules_button.setEnabled(bool(self.rule_sets))

    def _selected_rule_set(self) -> WorkbenchRuleSet:
        if 0 <= self._selected_rule_set_index < len(self.rule_sets):
            return self.rule_sets[self._selected_rule_set_index]
        return BUNDLED_WORKBENCH_RULE_SETS[0]

    def _set_rule_selector_index(self, index: int) -> None:
        selector = getattr(self.widgets, "analysis_rule_set_selector", None)
        if selector is None or not 0 <= index < selector.count():
            return
        blocker = QSignalBlocker(selector)
        selector.setCurrentIndex(index)
        del blocker

    def _unique_custom_name(self, requested: str) -> str:
        names = {rule_set.name.casefold() for rule_set in self.rule_sets}
        base = requested.strip() or "Custom Rules"
        if base.casefold() not in names:
            return base
        if self._selected_rule_set().read_only:
            base = f"{base} Custom"
        candidate = base
        suffix = 2
        while candidate.casefold() in names:
            candidate = f"{base} {suffix}"
            suffix += 1
        return candidate

    def _save_custom_rule_sets(
            self, rule_sets: tuple[WorkbenchRuleSet, ...] | None = None) -> bool:
        try:
            self.rule_store.save(
                self._custom_rule_sets if rule_sets is None else rule_sets)
        except WorkbenchRuleStoreError as error:
            self.view_failed.emit(str(error))
            return False
        return True

    def _remember_selected_rule_set(self) -> None:
        """Remember the preferred definition set, never its per-combat ON toggles."""
        if self.settings is not None:
            self.settings.workbench_rule_set = self._selected_rule_set().name

    def _auto_enabled_for(self, rule_set: WorkbenchRuleSet) -> bool:
        if self.settings is None:
            return False
        return (
            bool(getattr(self.settings, "workbench_auto_enable_rules", False))
            and str(getattr(
                self.settings, "workbench_auto_rule_set", "") or "").casefold()
            == rule_set.name.casefold()
        )

    def _rule_set_with_auto_preferences(
            self, rule_set: WorkbenchRuleSet) -> WorkbenchRuleSet:
        disabled = _disabled_rule_set(rule_set)
        if not self._auto_enabled_for(rule_set):
            return disabled
        raw_rules = str(getattr(
            self.settings, "workbench_auto_rules", "[]") or "[]")
        try:
            stored_keys = json.loads(raw_rules)
        except (TypeError, ValueError):
            stored_keys = []
        if not isinstance(stored_keys, list):
            stored_keys = []
        keys = {value for value in stored_keys if isinstance(value, str)}
        return replace(
            disabled,
            rules=tuple(
                replace(rule, enabled=_rule_preference_key(rule) in keys)
                for rule in disabled.rules
            ),
        )

    def _store_auto_preferences(
            self, rule_set: WorkbenchRuleSet, enabled: bool) -> None:
        if self.settings is None:
            return
        self.settings.workbench_auto_enable_rules = bool(enabled)
        self.settings.workbench_auto_rule_set = rule_set.name
        self.settings.workbench_auto_rules = json.dumps([
            _rule_preference_key(rule)
            for rule in rule_set.rules
            if rule.enabled
        ], separators=(",", ":"))


def _disabled_rule_set(rule_set: WorkbenchRuleSet) -> WorkbenchRuleSet:
    return replace(
        rule_set,
        rules=tuple(replace(rule, enabled=False) for rule in rule_set.rules),
    )


def _rule_set_definition_signature(rule_set: WorkbenchRuleSet):
    return (
        rule_set.name.casefold(),
        tuple(
            (rule.rule_type, rule.matches, rule.label)
            for rule in rule_set.rules
        ),
    )


def _same_rule_definition(left: WorkbenchRule, right: WorkbenchRule) -> bool:
    return (
        left.rule_type == right.rule_type
        and left.matches == right.matches
        and left.label == right.label
    )


def _rule_preference_key(rule: WorkbenchRule) -> str:
    """Return a stable identity unaffected by enable state or rule ordering."""
    return json.dumps(
        replace(rule, enabled=False).to_dict(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


__all__ = ("AnalysisWorkbenchController",)
