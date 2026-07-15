"""Command Console controller for the fused Analysis Workbench."""

from __future__ import annotations

from math import isfinite

from PySide6.QtCore import QObject, QSignalBlocker, Qt, Signal, Slot
from PySide6.QtWidgets import QPushButton

from OSCR.combat import Combat

from .workbench import (
    WorkbenchCombatView,
    WorkbenchDataError,
    WorkbenchFilterClause,
    WorkbenchIndexCache,
    WorkbenchQueryResult,
    WorkbenchState,
    count_effective_events,
    derive_workbench_combat,
)


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

    def __init__(self, parser, tables, widgets):
        super().__init__()
        self.parser = parser
        self.tables = tables
        self.widgets = widgets
        self.cache = WorkbenchIndexCache()
        self.state = WorkbenchState.parser_truth()
        self.source_combat: Combat | None = None
        self.current_result: WorkbenchQueryResult | None = None
        self.current_view: WorkbenchCombatView | None = None
        self._controls_attached = False
        self._last_filter_scope = "ANY"
        self._rendered_clauses: tuple[WorkbenchFilterClause, ...] = ()
        self.parser.combat_displayed.connect(self.bind_combat)

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
        self._controls_attached = True
        self._last_filter_scope = self._selected_filter_scope()
        self._update_filter_placeholder()
        self._update_controls(0, 0)

    @Slot(Combat)
    def bind_combat(self, combat: Combat) -> None:
        """Reset modifiers whenever the user displays a different official combat."""
        self.source_combat = combat
        self.state = WorkbenchState.parser_truth()
        self.current_result = None
        self.current_view = None
        self.tables.set_analysis_modified(False)
        self._reset_modifier_controls()
        self._clear_plots()
        total_count = self._source_event_count()
        visible_count = total_count or 0
        self._update_controls(visible_count, total_count)
        self.state_changed.emit(self.state, visible_count, visible_count)

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
        self._reset_modifier_controls()
        self.apply_state(WorkbenchState.parser_truth())

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
        self._sync_clause_chips()
        self._update_add_filter_button()

    def _update_add_filter_button(self) -> None:
        button = self.widgets.analysis_filter_add_button
        if button is None:
            return
        entry = self.widgets.analysis_filter_entry
        has_value = entry is not None and bool(entry.text().strip())
        button.setEnabled(self.source_combat is not None and has_value)

    def _sync_clause_chips(self) -> None:
        """Rebuild removable chips from the single accepted state."""
        layout = self.widgets.analysis_filter_clause_layout
        row = self.widgets.analysis_filter_clause_row
        if layout is None:
            if row is not None:
                row.setVisible(False)
            self.widgets.analysis_filter_clause_buttons = []
            return

        clauses = tuple(self.state.clauses)
        if clauses == self._rendered_clauses:
            if row is not None:
                row.setVisible(bool(clauses))
            return

        for button in self.widgets.analysis_filter_clause_buttons:
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
        self._rendered_clauses = clauses
        if row is not None:
            row.setVisible(bool(buttons))


__all__ = ("AnalysisWorkbenchController",)
