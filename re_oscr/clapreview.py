"""Command Console presentation for the dev15 CLA Damage Out technical preview."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QDialog, QHBoxLayout, QLabel, QPushButton,
    QTableView, QVBoxLayout,
)

from .clacoprocessor import (
    CountSet, DamageOutPreviewResult, OptionalValueSet, ValueSet,
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
            "SOURCE-AUDITED; GOLDEN VERIFICATION PENDING. OSCR selected the combat and event "
            "set. This preview cannot upload to the League and does not claim complete CLA "
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
            "SOURCE-AUDITED // GOLDEN VERIFICATION PENDING // "
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


__all__ = ("ClaDamageOutPreviewDialog", "HEADERS")
