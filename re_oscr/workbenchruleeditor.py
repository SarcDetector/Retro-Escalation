"""Capped, data-only editor for Analysis Workbench rule sets."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from .workbench import WorkbenchRule, WorkbenchRuleMatch, WorkbenchRuleSet
from .workbenchrules import WorkbenchRuleSetStore, WorkbenchRuleStoreError


class WorkbenchRuleEditor(QDialog):
    """Edit one immutable rule-set snapshot and return a validated replacement.

    The dialog never mutates its input.  All table values are converted back through the strict
    immutable Workbench constructors before the dialog can be accepted or exported.
    """

    def __init__(
            self, parent, rule_set: WorkbenchRuleSet, *, auto_enable: bool = False,
            geometry=None):
        super().__init__(parent)
        self.setObjectName("analysisWorkbenchRuleEditor")
        self.setProperty("consoleRole", "ruleEditorDialog")
        self.setWindowTitle("Analysis Workbench Rules")
        self.setModal(True)
        self.resize(900, 460)
        self._source_read_only = rule_set.read_only
        self.result_rule_set: WorkbenchRuleSet | None = None
        self.result_auto_enable = bool(auto_enable)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(10)

        cap = QFrame(self)
        cap.setProperty("consoleRole", "ruleEditorCap")
        cap_layout = QVBoxLayout(cap)
        cap_layout.setContentsMargins(10, 8, 10, 8)
        eyebrow = QLabel("ANALYSIS WORKBENCH // ORDERED RULE SET", cap)
        eyebrow.setProperty("consoleRole", "eyebrow")
        cap_layout.addWidget(eyebrow)
        title = QLabel("GROUPING, SOURCE REVERSAL & EXCLUSIONS", cap)
        title.setProperty("consoleRole", "sectionTitle")
        cap_layout.addWidget(title)
        outer.addWidget(cap)

        name_row = QHBoxLayout()
        name_label = QLabel("RULE SET")
        name_label.setProperty("consoleRole", "eyebrow")
        name_row.addWidget(name_label)
        self.name_entry = QLineEdit(rule_set.name, self)
        self.name_entry.setObjectName("analysisWorkbenchRuleSetName")
        self.name_entry.setProperty("consoleRole", "workbenchFilter")
        name_row.addWidget(self.name_entry, 1)
        if rule_set.read_only:
            notice = QLabel("BUNDLED // EDITING CREATES A CUSTOM COPY")
            notice.setProperty("consoleRole", "muted")
            name_row.addWidget(notice)
        outer.addLayout(name_row)

        self.table = QTableWidget(0, 4, self)
        self.table.setObjectName("analysisWorkbenchRuleTable")
        self.table.setProperty("consoleRole", "ruleEditorTable")
        self.table.setHorizontalHeaderLabels(("ON", "TYPE", "MATCHES", "LABEL"))
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 48)
        self.table.setColumnWidth(1, 112)
        self.table.setColumnWidth(2, 390)
        outer.addWidget(self.table, 1)

        edit_row = QHBoxLayout()
        for text, callback, object_name in (
                ("ADD", self._add_rule, "analysisWorkbenchRuleAdd"),
                ("DELETE", self._delete_rule, "analysisWorkbenchRuleDelete"),
                ("MOVE UP", lambda: self._move_rule(-1), "analysisWorkbenchRuleUp"),
                ("MOVE DOWN", lambda: self._move_rule(1), "analysisWorkbenchRuleDown")):
            button = QPushButton(text, self)
            button.setObjectName(object_name)
            button.setProperty("consoleRole", "actionButton")
            button.clicked.connect(callback)
            edit_row.addWidget(button)
        edit_row.addStretch(1)
        import_button = QPushButton("IMPORT", self)
        import_button.setObjectName("analysisWorkbenchRuleImport")
        import_button.setProperty("consoleRole", "actionButton")
        import_button.clicked.connect(self._import_rule_set)
        edit_row.addWidget(import_button)
        export_button = QPushButton("EXPORT", self)
        export_button.setObjectName("analysisWorkbenchRuleExport")
        export_button.setProperty("consoleRole", "actionButton")
        export_button.clicked.connect(self._export_rule_set)
        edit_row.addWidget(export_button)
        outer.addLayout(edit_row)

        help_label = QLabel(
            "MATCHES: use EVENT:pattern or SOURCE:pattern; separate multiple matches with ; . "
            "* is the only wildcard. GROUP merges effects, REVERSE places an indirect effect "
            "above its sources, and EXCLUDE removes matching events from this local view.\n"
            "Rule definitions and the selected set are saved. Fresh combats start with rules "
            "OFF by default; the explicit option below can reuse the checked rules.")
        help_label.setWordWrap(True)
        help_label.setProperty("consoleRole", "muted")
        outer.addWidget(help_label)

        self.auto_enable_toggle = QPushButton(self)
        self.auto_enable_toggle.setObjectName("analysisWorkbenchRuleAutoEnable")
        self.auto_enable_toggle.setProperty("consoleRole", "actionButton")
        self.auto_enable_toggle.setProperty("toggleAction", True)
        self.auto_enable_toggle.setProperty("accentIndex", "1")
        self.auto_enable_toggle.setCheckable(True)
        self.auto_enable_toggle.setChecked(auto_enable)
        self.auto_enable_toggle.toggled.connect(self._sync_auto_enable_text)
        self.auto_enable_toggle.setToolTip(
            "Opt in to opening each fresh combat as a clearly labelled MODIFIED VIEW. "
            "League uploads continue to use parser-truth data.")
        self._sync_auto_enable_text(auto_enable)
        outer.addWidget(self.auto_enable_toggle)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        outer.addWidget(self.buttons)

        self._populate(rule_set.rules)
        if geometry:
            self.restoreGeometry(geometry)

    def accept(self) -> None:
        try:
            self.result_rule_set = self._rule_set_from_controls()
        except (TypeError, ValueError) as error:
            self._show_error(str(error))
            return
        self.result_auto_enable = self.auto_enable_toggle.isChecked()
        super().accept()

    def _sync_auto_enable_text(self, enabled: bool) -> None:
        state = "ON" if enabled else "OFF"
        self.auto_enable_toggle.setText(
            f"AUTO-ENABLE CHECKED RULES ON FRESH COMBATS // {state}")

    def _populate(self, rules: tuple[WorkbenchRule, ...]) -> None:
        self.table.setRowCount(0)
        for rule in rules:
            self._append_rule(rule)
        if self.table.rowCount():
            self.table.selectRow(0)

    def _append_rule(self, rule: WorkbenchRule) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)

        enabled_item = QTableWidgetItem()
        enabled_item.setFlags(
            Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsUserCheckable)
        enabled_item.setCheckState(
            Qt.CheckState.Checked if rule.enabled else Qt.CheckState.Unchecked)
        self.table.setItem(row, 0, enabled_item)

        type_combo = QComboBox(self.table)
        type_combo.setProperty("consoleRole", "compactCombo")
        type_combo.addItems(("GROUP", "REVERSE", "EXCLUDE"))
        type_combo.setCurrentText(rule.rule_type)
        type_combo.currentTextChanged.connect(
            lambda _value, combo=type_combo: self._sync_label_requirement(combo))
        self.table.setCellWidget(row, 1, type_combo)

        matches = QLineEdit(self._matches_text(rule), self.table)
        matches.setProperty("consoleRole", "workbenchFilter")
        self.table.setCellWidget(row, 2, matches)

        label = QLineEdit(rule.label, self.table)
        label.setProperty("consoleRole", "workbenchFilter")
        label.setPlaceholderText(
            "GROUP LABEL" if rule.rule_type == "GROUP" else "OPTIONAL CHIP LABEL")
        self.table.setCellWidget(row, 3, label)

    @staticmethod
    def _matches_text(rule: WorkbenchRule) -> str:
        return "; ".join(f"{match.field}:{match.pattern}" for match in rule.matches)

    def _sync_label_requirement(self, combo: QComboBox) -> None:
        for row in range(self.table.rowCount()):
            if self.table.cellWidget(row, 1) is not combo:
                continue
            label = self.table.cellWidget(row, 3)
            if isinstance(label, QLineEdit):
                label.setPlaceholderText(
                    "GROUP LABEL" if combo.currentText() == "GROUP"
                    else "OPTIONAL CHIP LABEL")
            return

    def _add_rule(self) -> None:
        self._append_rule(WorkbenchRule(
            "GROUP", (WorkbenchRuleMatch("EVENT", "*"),), "New Group"))
        self.table.selectRow(self.table.rowCount() - 1)

    def _delete_rule(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        self.table.removeRow(row)
        if self.table.rowCount():
            self.table.selectRow(min(row, self.table.rowCount() - 1))

    def _move_rule(self, offset: int) -> None:
        row = self.table.currentRow()
        destination = row + offset
        if row < 0 or destination < 0 or destination >= self.table.rowCount():
            return
        try:
            rules = list(self._rules_from_table())
        except (TypeError, ValueError) as error:
            self._show_error(str(error))
            return
        rules[row], rules[destination] = rules[destination], rules[row]
        self._populate(tuple(rules))
        self.table.selectRow(destination)

    def _rules_from_table(self) -> tuple[WorkbenchRule, ...]:
        return tuple(self._rule_from_row(row) for row in range(self.table.rowCount()))

    def _rule_from_row(self, row: int) -> WorkbenchRule:
        enabled_item = self.table.item(row, 0)
        type_combo = self.table.cellWidget(row, 1)
        matches_entry = self.table.cellWidget(row, 2)
        label_entry = self.table.cellWidget(row, 3)
        if not isinstance(type_combo, QComboBox):
            raise ValueError(f"rule {row + 1} has no type")
        if not isinstance(matches_entry, QLineEdit):
            raise ValueError(f"rule {row + 1} has no matches")
        if not isinstance(label_entry, QLineEdit):
            raise ValueError(f"rule {row + 1} has no label")
        matches = []
        for raw_match in matches_entry.text().split(";"):
            raw_match = raw_match.strip()
            if not raw_match:
                continue
            field, separator, pattern = raw_match.partition(":")
            if not separator:
                raise ValueError(
                    f"rule {row + 1} match must use EVENT:pattern or SOURCE:pattern")
            matches.append(WorkbenchRuleMatch(field, pattern))
        return WorkbenchRule(
            type_combo.currentText(),
            tuple(matches),
            label_entry.text(),
            enabled=(
                enabled_item is not None
                and enabled_item.checkState() == Qt.CheckState.Checked),
        )

    def _rule_set_from_controls(self) -> WorkbenchRuleSet:
        return WorkbenchRuleSet(
            self.name_entry.text(),
            self._rules_from_table(),
            version=1,
            read_only=self._source_read_only,
        )

    def _import_rule_set(self) -> None:
        path, _selected_filter = QFileDialog.getOpenFileName(
            self, "Import Workbench Rule Set", "", "Workbench Rules (*.json)")
        if not path:
            return
        try:
            imported = WorkbenchRuleSetStore.import_file(path)
        except WorkbenchRuleStoreError as error:
            self._show_error(str(error))
            return
        self.name_entry.setText(imported.name)
        self._populate(imported.rules)

    def _export_rule_set(self) -> None:
        try:
            rule_set = self._rule_set_from_controls()
        except (TypeError, ValueError) as error:
            self._show_error(str(error))
            return
        initial_name = _safe_filename(rule_set.name) + ".json"
        path, _selected_filter = QFileDialog.getSaveFileName(
            self, "Export Workbench Rule Set", initial_name,
            "Workbench Rules (*.json)")
        if not path:
            return
        destination = Path(path)
        if destination.suffix.casefold() != ".json":
            destination = destination.with_suffix(".json")
        try:
            WorkbenchRuleSetStore.export_file(destination, rule_set)
        except WorkbenchRuleStoreError as error:
            self._show_error(str(error))

    def _show_error(self, detail: str) -> None:
        QMessageBox.warning(self, "Workbench Rule Set", detail)


def _safe_filename(name: str) -> str:
    safe = "".join(character for character in name if character.isalnum() or character in "-_ ")
    return safe.strip().replace(" ", "_") or "workbench_rules"


__all__ = ("WorkbenchRuleEditor",)
