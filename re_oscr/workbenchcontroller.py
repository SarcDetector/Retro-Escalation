"""Command Console controller for the fused Analysis Workbench."""

from __future__ import annotations

from math import isfinite

from PySide6.QtCore import QObject, QSignalBlocker, Signal, Slot

from OSCR.combat import Combat

from .workbench import (
    WorkbenchCombatView,
    WorkbenchDataError,
    WorkbenchIndexCache,
    WorkbenchQueryResult,
    WorkbenchState,
    derive_workbench_combat,
)


class AnalysisWorkbenchController(QObject):
    """Apply display-only modifiers while keeping parser and League truth isolated."""

    state_changed = Signal(object, int, int)
    view_failed = Signal(str)

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
        self.parser.combat_displayed.connect(self.bind_combat)

    def attach_controls(self) -> None:
        """Connect controls after the Command Console Analysis page has constructed them."""
        if self._controls_attached:
            return
        if self.widgets.analysis_filter_scope is not None:
            self.widgets.analysis_filter_scope.currentIndexChanged.connect(
                self._apply_controls)
        if self.widgets.analysis_filter_entry is not None:
            self.widgets.analysis_filter_entry.textChanged.connect(self._apply_controls)
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
        scope_widget = self.widgets.analysis_filter_scope
        if scope_widget is None:
            scope = "ANY"
        else:
            scope_data = scope_widget.currentData()
            scope = str(scope_data if scope_data is not None else scope_widget.currentText())
            scope = scope.strip().upper()

        if scope not in {"ANY", "OWNER", "SOURCE", "TARGET", "EVENT"}:
            raise ValueError(f"unknown Analysis filter scope: {scope or 'empty'}")

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

        start_seconds = self._optional_seconds(
            self.widgets.analysis_start_entry, "START")
        end_seconds = self._optional_seconds(
            self.widgets.analysis_end_entry, "END")
        if (start_seconds is not None and end_seconds is not None
                and start_seconds > end_seconds):
            raise ValueError("START must not be greater than END")

        return WorkbenchState(
            **query_fields,
            start_seconds=start_seconds,
            end_seconds=end_seconds,
        )

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
                selected_count = 0
                total_count = 0
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
        self.state_changed.emit(candidate, selected_count, total_count)
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

        scope = self.widgets.analysis_filter_scope
        if scope is not None:
            any_index = scope.findData("ANY")
            if any_index < 0:
                any_index = scope.findText("ANY")
            if any_index < 0 and scope.count():
                any_index = 0
            if any_index >= 0:
                scope.setCurrentIndex(any_index)
        for entry in (
                self.widgets.analysis_filter_entry,
                self.widgets.analysis_start_entry,
                self.widgets.analysis_end_entry):
            if entry is not None:
                entry.clear()

        # Keep every blocker alive until all related controls hold a coherent reset state.
        del blockers

    def _clear_plots(self) -> None:
        for plot in self.widgets.analysis_plots:
            plot.clear()

    def _update_controls(self, selected_count: int, total_count: int) -> None:
        has_combat = self.source_combat is not None
        modified = has_combat and self.state.is_modified
        if self.widgets.analysis_truth_chip is not None:
            self.widgets.analysis_truth_chip.setVisible(has_combat and not modified)
        if self.widgets.analysis_modified_chip is not None:
            self.widgets.analysis_modified_chip.setVisible(modified)
        if self.widgets.analysis_event_count_chip is not None:
            if modified:
                text = f"{selected_count:,} / {total_count:,} EVENTS"
            elif has_combat:
                text = "PARSER OUTPUT"
            else:
                text = "NO COMBAT"
            self.widgets.analysis_event_count_chip.setText(text)
        if self.widgets.analysis_reset_button is not None:
            self.widgets.analysis_reset_button.setEnabled(modified)


__all__ = ("AnalysisWorkbenchController",)
