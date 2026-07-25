"""Command Console presentation for CLA v1.4 coprocessor results."""

from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox, QDialog, QFileDialog, QHBoxLayout,
    QLabel, QPlainTextEdit, QPushButton, QTableView, QTabWidget, QTreeView, QVBoxLayout,
    QWidget,
)

from .clacoprocessor import (
    ClaAnalysisResult, CountSet, DamageAnalysisNode, DamageOutPreviewResult,
    HealAnalysisNode, OptionalValueSet, ValueSet,
)


HEADERS = (
    "PLAYER",
    "DAMAGE OUT CLOCK",
    "ACTIVE CLOCK",
    "DPS (A / S / H)",
    "TOTAL DAMAGE (A / S / H)",
    "RESISTANCE %",
    "AVERAGE HIT (A / S / H)",
    "HITS (A / S / H)",
    "HITS/S (A / S / H)",
    "BASE DPS",
    "BASE DAMAGE",
)

SUMMARY_HEADERS = (
    "PLAYER", "OUTGOING DPS", "OUT DAMAGE", "OUT %", "IN DAMAGE", "IN %",
    "COMBAT DURATION", "COMBAT %", "ACTIVE DURATION", "DEATHS", "KILLS",
    "PLAYER KILLS", "NPC KILLS",
)

DAMAGE_HEADERS = (
    "NAME", "DPS", "TOTAL DAMAGE", "DAMAGE %", "RESISTANCE %", "MAX ONE-HIT",
    "AVERAGE HIT", "CRITICAL %", "FLANKING %", "HITS", "HITS / S", "HITS %",
    "MISSES", "ACCURACY %", "KILLS", "DAMAGE TYPES", "BASE DPS", "BASE DAMAGE",
    "TOTAL CRIT DAMAGE", "TOTAL NON-CRIT HULL DAMAGE", "AVERAGE CRIT HIT",
    "AVERAGE NON-CRIT HULL HIT",
)

HEAL_HEADERS = (
    "NAME", "HPS", "TOTAL HEAL", "HEAL %", "AVERAGE HEAL", "CRITICAL %",
    "TICKS", "TICKS / S", "TICKS %",
)


class ClaAnalysisDialog(QDialog):
    """Read-only five-slice CLA analysis with complete raw provenance."""

    _DIRECTION_TABS = ("damage_out", "damage_in", "heal_out", "heal_in")

    def __init__(self, result: ClaAnalysisResult, parent=None):
        super().__init__(parent)
        self.result = result
        self._aspect = "all"
        self.models: dict[str, QStandardItemModel] = {}
        self.views: dict[str, QTableView | QTreeView] = {}

        self.setObjectName("claAnalysisDialog")
        self.setWindowTitle("RE-OSCR // CLA v1.4 Analysis")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.resize(1460, 760)

        layout = QVBoxLayout()
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        heading = QHBoxLayout()
        title = QLabel("CLA v1.4 // CALCULATION ANALYSIS")
        title.setObjectName("claAnalysisTitle")
        title.setProperty("consoleRole", "panelTitle")
        heading.addWidget(title)
        heading.addStretch(1)
        for text in (
                "CLA v1.4 PROFILE", "PARSER-TRUTH SNAPSHOT", "LEAGUE INELIGIBLE"):
            chip = QLabel(text)
            chip.setProperty("consoleRole", "statusChip")
            heading.addWidget(chip)
        layout.addLayout(heading)

        notice = QLabel(
            "All Summary, Damage Out, Damage In, Heal Out, and Heal In scalar families are "
            "calculated from the immutable OSCR-selected event set. Damage Out has real-combat "
            "field validation; anonymous synthetic fixtures cover all directions and edge "
            "contracts. Default CLA hierarchy is included. Rule transforms, graph emulation, "
            "and bit-exact Rust HashMap traversal are not claimed. This result cannot upload "
            "to the League.")
        notice.setObjectName("claAnalysisNotice")
        notice.setProperty("consoleRole", "muted")
        notice.setWordWrap(True)
        layout.addWidget(notice)

        provenance = result.provenance
        encounter = provenance.map_name or "UNIDENTIFIED ENCOUNTER"
        if provenance.difficulty:
            encounter = f"{encounter} [{provenance.difficulty}]"
        identity = QLabel(
            f"{encounter}  //  {provenance.combat_start}  //  "
            f"{result.event_count:,} EVENTS\n"
            f"BUILD {provenance.product_version}  //  "
            f"REVISION {provenance.build_revision or 'UNRECORDED SOURCE BUILD'}\n"
            f"SNAPSHOT {provenance.snapshot_id}  //  RESULT {provenance.result_id}")
        identity.setObjectName("claAnalysisIdentity")
        identity.setProperty("consoleRole", "eyebrow")
        identity.setWordWrap(True)
        identity.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(identity)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("VALUE ASPECT"))
        self.aspect_selector = QComboBox()
        self.aspect_selector.setObjectName("claAnalysisAspect")
        self.aspect_selector.addItem("ALL", "all")
        self.aspect_selector.addItem("SHIELD", "shield")
        self.aspect_selector.addItem("HULL", "hull")
        controls.addWidget(self.aspect_selector)
        controls.addStretch(1)
        layout.addLayout(controls)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("claAnalysisTabs")
        layout.addWidget(self.tabs, 1)

        self._add_summary_tab()
        self._add_direction_tab("damage_out", "DAMAGE OUT", damage=True)
        self._add_direction_tab("damage_in", "DAMAGE IN", damage=True)
        self._add_direction_tab("heal_out", "HEAL OUT", damage=False)
        self._add_direction_tab("heal_in", "HEAL IN", damage=False)
        self._add_provenance_tab()
        self.aspect_selector.currentIndexChanged.connect(self._aspect_changed)

        actions = QHBoxLayout()
        actions.addStretch(1)
        copy_tab = QPushButton("COPY TAB")
        copy_tab.setObjectName("claAnalysisCopyTab")
        copy_tab.setProperty("consoleRole", "actionButton")
        copy_tab.clicked.connect(self.copy_current_tab)
        actions.addWidget(copy_tab)
        copy_raw = QPushButton("COPY RAW JSON")
        copy_raw.setObjectName("claAnalysisCopyRaw")
        copy_raw.setProperty("consoleRole", "actionButton")
        copy_raw.clicked.connect(self.copy_raw_report)
        actions.addWidget(copy_raw)
        export_raw = QPushButton("EXPORT JSON...")
        export_raw.setObjectName("claAnalysisExportRaw")
        export_raw.setProperty("consoleRole", "actionButton")
        export_raw.clicked.connect(self.export_raw_report)
        actions.addWidget(export_raw)
        close_button = QPushButton("CLOSE")
        close_button.setObjectName("claAnalysisClose")
        close_button.setProperty("consoleRole", "actionButton")
        close_button.clicked.connect(self.close)
        actions.addWidget(close_button)
        layout.addLayout(actions)
        self.setLayout(layout)

    def _add_summary_tab(self) -> None:
        model = _build_summary_model(self.result)
        table = QTableView()
        table.setObjectName("claAnalysisSummary")
        table.setProperty("consoleRole", "analysisTree")
        _configure_table(table, model)
        self.models["summary"] = model
        self.views["summary"] = table
        self.tabs.addTab(table, "SUMMARY")

    def _add_direction_tab(self, key: str, label: str, *, damage: bool) -> None:
        tree = QTreeView()
        tree.setObjectName(f"claAnalysis{''.join(part.title() for part in key.split('_'))}")
        tree.setProperty("consoleRole", "analysisTree")
        tree.setUniformRowHeights(True)
        tree.setAllColumnsShowFocus(True)
        tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        tree.setSortingEnabled(False)
        self.views[key] = tree
        self.tabs.addTab(tree, label)
        self._rebuild_direction_model(key, damage=damage)

    def _add_provenance_tab(self) -> None:
        text = QPlainTextEdit()
        text.setObjectName("claAnalysisProvenance")
        text.setReadOnly(True)
        text.setPlainText(json.dumps(
            self.result.provenance.to_dict(),
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
        ))
        self.views["provenance"] = text  # type: ignore[assignment]
        self.tabs.addTab(text, "PROVENANCE")

    def _rebuild_direction_model(self, key: str, *, damage: bool) -> None:
        if damage:
            model = _build_damage_model(
                tuple(getattr(player, key) for player in self.result.players),
                self._aspect)
        else:
            model = _build_heal_model(
                tuple(getattr(player, key) for player in self.result.players),
                self._aspect)
        self.models[key] = model
        view = self.views[key]
        view.setModel(model)
        view.expandToDepth(0)
        view.resizeColumnToContents(0)

    def _aspect_changed(self, _index: int = -1) -> None:
        self._aspect = str(self.aspect_selector.currentData())
        self._rebuild_direction_model("damage_out", damage=True)
        self._rebuild_direction_model("damage_in", damage=True)
        self._rebuild_direction_model("heal_out", damage=False)
        self._rebuild_direction_model("heal_in", damage=False)

    def _current_key(self) -> str:
        index = self.tabs.currentIndex()
        return ("summary", *self._DIRECTION_TABS, "provenance")[index]

    def copy_current_tab(self) -> None:
        key = self._current_key()
        if key == "provenance":
            QApplication.clipboard().setText(json.dumps(
                self.result.provenance.to_dict(),
                ensure_ascii=False,
                allow_nan=False,
                indent=2,
            ))
            return
        model = self.models[key]
        lines = [
            "RE-OSCR CLA v1.4 ANALYSIS",
            f"TAB\t{key.upper().replace('_', ' ')}",
            f"ASPECT\t{self._aspect.upper()}",
            f"SNAPSHOT\t{self.result.provenance.snapshot_id}",
            f"RESULT\t{self.result.provenance.result_id}",
            "",
            "\t".join(
                model.headerData(column, Qt.Orientation.Horizontal) or ""
                for column in range(model.columnCount())),
        ]
        _append_model_rows(lines, model)
        QApplication.clipboard().setText("\n".join(lines))

    def copy_raw_report(self) -> None:
        QApplication.clipboard().setText(self.result.to_json())

    def export_raw_report(self) -> None:
        path, _selected = QFileDialog.getSaveFileName(
            self,
            "Export CLA v1.4 analysis",
            "re-oscr-cla-v1.4-analysis.json",
            "JSON files (*.json)",
        )
        if not path:
            return
        with open(path, "w", encoding="utf-8", newline="\n") as output:
            output.write(self.result.to_json())


def _configure_table(table: QTableView, model: QStandardItemModel) -> None:
    table.setModel(model)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
    table.setSortingEnabled(True)
    table.verticalHeader().hide()
    table.resizeColumnsToContents()


def _aspect_value(values: ValueSet | OptionalValueSet | CountSet, aspect: str):
    return getattr(values, aspect)


def _number(value: float, precision: int = 2) -> str:
    return f"{value:,.{precision}f}".replace(",", "'")


def _optional_number(value: float | None, precision: int = 3) -> str:
    return "" if value is None else _number(value, precision)


def _build_summary_model(result: ClaAnalysisResult) -> QStandardItemModel:
    model = QStandardItemModel(0, len(SUMMARY_HEADERS))
    model.setHorizontalHeaderLabels(SUMMARY_HEADERS)
    model.setSortRole(Qt.ItemDataRole.UserRole)
    for analyzed in result.players:
        row = analyzed.summary
        model.appendRow([
            _item(row.player, row.player.casefold()),
            _item(_number(row.outgoing_dps.all), row.outgoing_dps.all),
            _item(_number(row.total_outgoing_damage.all), row.total_outgoing_damage.all),
            _item(_optional_number(row.outgoing_damage_percentage.all),
                  row.outgoing_damage_percentage.all or 0.0),
            _item(_number(row.total_incoming_damage.all), row.total_incoming_damage.all),
            _item(_optional_number(row.incoming_damage_percentage.all),
                  row.incoming_damage_percentage.all or 0.0),
            _item(_format_duration(row.combat_duration_ms), row.combat_duration_ms),
            _item(_number(row.combat_duration_percentage, 3),
                  row.combat_duration_percentage),
            _item(_format_duration(row.active_duration_ms), row.active_duration_ms),
            _item(f"{row.deaths:,}", row.deaths),
            _item(f"{row.kills:,}", row.kills),
            _item(f"{row.player_kills:,}", row.player_kills),
            _item(f"{row.npc_kills:,}", row.npc_kills),
        ])
    return model


def _build_damage_model(
        roots: tuple[DamageAnalysisNode, ...], aspect: str) -> QStandardItemModel:
    model = QStandardItemModel(0, len(DAMAGE_HEADERS))
    model.setHorizontalHeaderLabels(DAMAGE_HEADERS)
    model.setSortRole(Qt.ItemDataRole.UserRole)
    for root in roots:
        _append_damage_node(model.invisibleRootItem(), root, aspect)
    return model


def _append_damage_node(parent: QStandardItem, node: DamageAnalysisNode, aspect: str) -> None:
    metric = node.metrics
    total_damage = _aspect_value(metric.total_damage, aspect)
    dps = _aspect_value(metric.dps, aspect)
    damage_share = _aspect_value(metric.damage_percentage, aspect)
    average = _aspect_value(metric.average_hit, aspect)
    hits = _aspect_value(metric.hits, aspect)
    hits_rate = _aspect_value(metric.hits_per_second, aspect)
    hits_share = _aspect_value(metric.hits_percentage, aspect)
    max_hit = metric.max_one_hit
    name = _item(node.name, node.name.casefold(), " -> ".join(node.path))
    max_item = _item(
        _number(max_hit.damage), max_hit.damage,
        f"{max_hit.name}; source ordinal={max_hit.source_ordinal!r}")
    cells = [
        name,
        _item(_number(dps), dps),
        _item(_number(total_damage), total_damage),
        _item(_optional_number(damage_share), damage_share or 0.0),
        _item(_optional_number(metric.resistance_percentage),
              metric.resistance_percentage or 0.0),
        max_item,
        _item(_optional_number(average, 2), average or 0.0),
        _item(_optional_number(metric.critical_percentage),
              metric.critical_percentage or 0.0),
        _item(_optional_number(metric.flanking_percentage),
              metric.flanking_percentage or 0.0),
        _item(f"{hits:,}", hits),
        _item(_number(hits_rate, 3), hits_rate),
        _item(_optional_number(hits_share), hits_share or 0.0),
        _item(f"{metric.misses:,}", metric.misses),
        _item(_optional_number(metric.accuracy_percentage),
              metric.accuracy_percentage or 0.0),
        _item(f"{metric.kill_count:,}", metric.kill_count,
              ", ".join(f"{kill.name}: {kill.count}" for kill in metric.kills)),
        _item(
            (metric.damage_types[0] if len(metric.damage_types) == 1
             else "<mixed>" if metric.damage_types else ""),
            tuple(value.casefold() for value in metric.damage_types),
            "\n".join(metric.damage_types)),
        _item(_number(metric.base_dps), metric.base_dps),
        _item(_number(metric.base_damage), metric.base_damage),
        _item(_number(metric.total_crit_damage), metric.total_crit_damage),
        _item(_number(metric.total_non_crit_hull_damage),
              metric.total_non_crit_hull_damage),
        _item(_optional_number(metric.average_crit_hit, 2),
              metric.average_crit_hit or 0.0),
        _item(_optional_number(metric.average_non_crit_hull_hit, 2),
              metric.average_non_crit_hull_hit or 0.0),
    ]
    parent.appendRow(cells)
    for child in node.children:
        _append_damage_node(name, child, aspect)


def _build_heal_model(
        roots: tuple[HealAnalysisNode, ...], aspect: str) -> QStandardItemModel:
    model = QStandardItemModel(0, len(HEAL_HEADERS))
    model.setHorizontalHeaderLabels(HEAL_HEADERS)
    model.setSortRole(Qt.ItemDataRole.UserRole)
    for root in roots:
        _append_heal_node(model.invisibleRootItem(), root, aspect)
    return model


def _append_heal_node(parent: QStandardItem, node: HealAnalysisNode, aspect: str) -> None:
    metric = node.metrics
    hps = _aspect_value(metric.hps, aspect)
    total = _aspect_value(metric.total_heal, aspect)
    share = _aspect_value(metric.heal_percentage, aspect)
    average = _aspect_value(metric.average_heal, aspect)
    ticks = _aspect_value(metric.ticks, aspect)
    ticks_rate = _aspect_value(metric.ticks_per_second, aspect)
    ticks_share = _aspect_value(metric.ticks_percentage, aspect)
    name = _item(node.name, node.name.casefold(), " -> ".join(node.path))
    cells = [
        name,
        _item(_number(hps), hps),
        _item(_number(total), total),
        _item(_optional_number(share), share or 0.0),
        _item(_optional_number(average, 2), average or 0.0),
        _item(_optional_number(metric.critical_percentage),
              metric.critical_percentage or 0.0),
        _item(f"{ticks:,}", ticks),
        _item(_number(ticks_rate, 3), ticks_rate),
        _item(_optional_number(ticks_share), ticks_share or 0.0),
    ]
    parent.appendRow(cells)
    for child in node.children:
        _append_heal_node(name, child, aspect)


def _append_model_rows(
        lines: list[str], model: QStandardItemModel,
        parent: QStandardItem | None = None, depth: int = 0) -> None:
    parent = parent or model.invisibleRootItem()
    for row in range(parent.rowCount()):
        values = []
        for column in range(model.columnCount()):
            item = parent.child(row, column)
            text = item.text() if item is not None else ""
            if column == 0:
                text = f"{'  ' * depth}{text}"
            values.append(text)
        lines.append("\t".join(values))
        first = parent.child(row, 0)
        if first is not None:
            _append_model_rows(lines, model, first, depth + 1)


class ClaDamageOutPreviewDialog(QDialog):
    """Read-only preview table with a copyable raw result/provenance report."""

    def __init__(self, result: DamageOutPreviewResult, parent=None):
        super().__init__(parent)
        self.result = result
        self.setObjectName("claDamageOutPreviewDialog")
        self.setWindowTitle("RE-OSCR // CLA v1.4 Damage Out Preview")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.resize(1180, 540)

        layout = QVBoxLayout()
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        title = QLabel("CLA v1.4 // DAMAGE OUT TECHNICAL PREVIEW")
        title.setObjectName("claDamageOutPreviewTitle")
        title.setProperty("consoleRole", "panelTitle")
        layout.addWidget(title)

        warning = QLabel(
            "SOURCE-AUDITED; DAMAGE OUT FIELD-VALIDATED. OSCR selected the combat and event "
            "set. This compatibility view cannot upload to the League and does not claim complete CLA "
            "parity. Values are player-root results; hierarchy, flags, graphs, exact CLA "
            "display formatting, and exact hierarchy aggregation traversal are not included "
            "in dev15. Arbitrary binary64 sums may therefore expose comparison differences.")
        warning.setObjectName("claDamageOutPreviewWarning")
        warning.setProperty("consoleRole", "muted")
        warning.setWordWrap(True)
        layout.addWidget(warning)

        provenance = result.provenance
        encounter = provenance.map_name or "UNIDENTIFIED ENCOUNTER"
        if provenance.difficulty:
            encounter = f"{encounter} [{provenance.difficulty}]"
        identity = QLabel(
            f"{encounter}  //  {provenance.combat_start}  //  {result.event_count:,} EVENTS\n"
            f"BUILD {provenance.product_version}  //  "
            f"REVISION {provenance.build_revision or 'UNRECORDED SOURCE BUILD'}\n"
            f"SNAPSHOT {provenance.snapshot_id}  //  "
            f"RESULT {provenance.result_id}")
        identity.setObjectName("claDamageOutPreviewIdentity")
        identity.setProperty("consoleRole", "eyebrow")
        identity.setWordWrap(True)
        identity.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        identity.setToolTip(
            "The stable snapshot identifies OSCR's effective selected-combat events; the result "
            "identity also fixes the engine, profile, and empty transform descriptor.")
        layout.addWidget(identity)

        self.model = self._build_model(result)
        self.table = QTableView()
        self.table.setObjectName("claDamageOutPreviewTable")
        self.table.setProperty("consoleRole", "analysisTree")
        self.table.setModel(self.model)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.resizeColumnsToContents()
        layout.addWidget(self.table, 1)

        actions = QHBoxLayout()
        actions.addStretch(1)
        copy_table = QPushButton("COPY ROUNDED TABLE")
        copy_table.setObjectName("claDamageOutPreviewCopyTable")
        copy_table.setProperty("consoleRole", "actionButton")
        copy_table.setToolTip(
            "Copy visibly rounded display values with preview status and provenance. "
            "This table is not an exact-value comparison oracle; use COPY RAW REPORT.")
        copy_table.clicked.connect(self.copy_table)
        actions.addWidget(copy_table)
        copy_raw = QPushButton("COPY RAW REPORT")
        copy_raw.setObjectName("claDamageOutPreviewCopyRaw")
        copy_raw.setProperty("consoleRole", "actionButton")
        copy_raw.setToolTip(
            "Copy unrounded values, clocks, metric IDs, snapshot/result identities, and boundary "
            "differences as JSON")
        copy_raw.clicked.connect(self.copy_raw_report)
        actions.addWidget(copy_raw)
        close_button = QPushButton("CLOSE")
        close_button.setObjectName("claDamageOutPreviewClose")
        close_button.setProperty("consoleRole", "actionButton")
        close_button.clicked.connect(self.close)
        actions.addWidget(close_button)
        layout.addLayout(actions)

        self.setLayout(layout)

    @staticmethod
    def _build_model(result: DamageOutPreviewResult) -> QStandardItemModel:
        model = QStandardItemModel(0, len(HEADERS))
        model.setHorizontalHeaderLabels(HEADERS)
        model.setSortRole(Qt.ItemDataRole.UserRole)
        for row in result.rows:
            cells = (
                _item(row.player, row.player.casefold()),
                _item(_format_duration(row.damage_out_duration_ms),
                      row.damage_out_duration_ms if row.damage_out_duration_ms is not None else -1),
                _item(_format_duration(row.active_duration_ms),
                      row.active_duration_ms if row.active_duration_ms is not None else -1),
                _value_set_item(row.dps, 2),
                _value_set_item(row.total_damage, 2),
                _optional_item(row.resistance_percentage, 3),
                _optional_value_set_item(row.average_hit, 2),
                _count_set_item(row.hits),
                _value_set_item(row.hits_per_second, 3),
                _item(f"{row.base_dps:,.2f}", row.base_dps, repr(row.base_dps)),
                _item(f"{row.base_damage:,.2f}", row.base_damage, repr(row.base_damage)),
            )
            model.appendRow(list(cells))
        return model

    def copy_table(self) -> None:
        provenance = self.result.provenance
        lines = [
            "RE-OSCR CLA v1.4 DAMAGE OUT TECHNICAL PREVIEW",
            "SOURCE-AUDITED // DAMAGE OUT FIELD-VALIDATED // "
            "ROUNDED DISPLAY VALUES, NOT AN ORACLE",
            f"BUILD\t{provenance.product_version}",
            f"REVISION\t{provenance.build_revision or 'UNRECORDED SOURCE BUILD'}",
            f"SNAPSHOT\t{provenance.snapshot_id}",
            f"RESULT\t{provenance.result_id}",
            "",
            "\t".join(HEADERS),
        ]
        for row in range(self.model.rowCount()):
            lines.append("\t".join(
                self.model.index(row, column).data(Qt.ItemDataRole.DisplayRole) or ""
                for column in range(self.model.columnCount())
            ))
        QApplication.clipboard().setText("\n".join(lines))

    def copy_raw_report(self) -> None:
        QApplication.clipboard().setText(self.result.to_json())


def _item(text: str, sort_value, tooltip: str | None = None) -> QStandardItem:
    item = QStandardItem(text)
    item.setEditable(False)
    item.setData(sort_value, Qt.ItemDataRole.UserRole)
    if tooltip:
        item.setToolTip(tooltip)
    return item


def _format_duration(milliseconds: int | None) -> str:
    if milliseconds is None:
        return "00:00.000 // MISSING"
    total_seconds, millis = divmod(milliseconds, 1000)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"
    return f"{minutes:02d}:{seconds:02d}.{millis:03d}"


def _value_set_text(values: ValueSet, precision: int) -> str:
    return (
        f"{values.all:,.{precision}f} / "
        f"{values.shield:,.{precision}f} / "
        f"{values.hull:,.{precision}f}")


def _value_set_item(values: ValueSet, precision: int) -> QStandardItem:
    return _item(
        _value_set_text(values, precision), values.all,
        f"raw all={values.all!r}; shield={values.shield!r}; hull={values.hull!r}")


def _optional_value_set_item(
        values: OptionalValueSet, precision: int) -> QStandardItem:
    def formatted(value: float | None) -> str:
        return "" if value is None else f"{value:,.{precision}f}"

    text = f"{formatted(values.all)} / {formatted(values.shield)} / {formatted(values.hull)}"
    return _item(
        text, values.all if values.all is not None else float("-inf"),
        f"raw all={values.all!r}; shield={values.shield!r}; hull={values.hull!r}")


def _count_set_item(values: CountSet) -> QStandardItem:
    return _item(
        f"{values.all:,} / {values.shield:,} / {values.hull:,}", values.all,
        f"raw all={values.all}; shield={values.shield}; hull={values.hull}")


def _optional_item(value: float | None, precision: int) -> QStandardItem:
    if value is None:
        return _item("", float("-inf"), "blank: denominator is zero")
    return _item(f"{value:,.{precision}f}", value, repr(value))


__all__ = (
    "ClaAnalysisDialog",
    "ClaDamageOutPreviewDialog",
    "DAMAGE_HEADERS",
    "HEADERS",
    "HEAL_HEADERS",
    "SUMMARY_HEADERS",
)
