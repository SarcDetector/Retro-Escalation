"""Read-only Command Console presentation for the Overview telemetry table.

The parser-owned :class:`OverviewTableModel` deliberately remains the source of
truth.  This module adds one synthetic identity column in front of the existing
metric columns, exposes derived presentation roles, and provides the companion
view used to keep that identity column visible while the metrics scroll.

The expected model chain is::

    OverviewTableModel -> SortingProxy -> OverviewDisplayProxy -> table views

``OverviewDisplayProxy`` never writes through to either source model.  Source
column numbers therefore stay stable for settings and parser-facing code; use
``view_column_for_source()`` and ``sort_by_source_column()`` at the view boundary.
"""

from __future__ import annotations

from math import isfinite
from numbers import Real
from typing import Iterable

from PySide6.QtCore import (
    QAbstractItemModel,
    QAbstractProxyModel,
    QMimeData,
    QModelIndex,
    Property,
    QPersistentModelIndex,
    QRect,
    QSize,
    Qt,
    QTimer,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QPainter,
    QPalette,
    QResizeEvent,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFrame,
    QHeaderView,
    QStyle,
    QStyleOptionHeader,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableView,
    QTreeView,
    QWidget,
)

from .tokens import BORDERS, SURFACES, TEXT, ConsoleTokens, blend, px


_FIRST_PRESENTATION_ROLE = Qt.ItemDataRole.UserRole.value + 1
RankRole = _FIRST_PRESENTATION_ROLE
IdentityRole = _FIRST_PRESENTATION_ROLE + 1
BarFractionRole = _FIRST_PRESENTATION_ROLE + 2
FormattedMagnitudeRole = _FIRST_PRESENTATION_ROLE + 3
RawValueRole = _FIRST_PRESENTATION_ROLE + 4


class OverviewDisplayProxy(QAbstractProxyModel):
    """Read-only facade adding a synthetic rank-and-operator column.

    The source model must be the existing ``SortingProxy``.  Keeping the sorter
    immediately above ``OverviewTableModel`` is important because its legacy
    comparison implementation reads the source model's raw ``_data`` directly.
    """

    IDENTITY_COLUMN = 0
    SOURCE_COLUMN_OFFSET = 1

    RankRole = RankRole
    IdentityRole = IdentityRole
    BarFractionRole = BarFractionRole
    FormattedMagnitudeRole = FormattedMagnitudeRole
    RawValueRole = RawValueRole

    _DERIVED_ROLES = (
        RankRole,
        IdentityRole,
        BarFractionRole,
        FormattedMagnitudeRole,
        RawValueRole,
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self._source_connections: list[tuple[object, object]] = []
        self._layout_indexes: list[QModelIndex] = []
        self._layout_anchors: list[tuple[QPersistentModelIndex, int]] = []
        self._layout_hint = QAbstractItemModel.LayoutChangeHint.NoLayoutChangeHint
        self._row_move_active = False
        self._column_move_active = False

    # -- Model shape and mapping -------------------------------------------------

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        source = self.sourceModel()
        if parent.isValid() or source is None:
            return 0
        return source.rowCount(QModelIndex())

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        source = self.sourceModel()
        if parent.isValid() or source is None:
            return 0
        return source.columnCount(QModelIndex()) + self.SOURCE_COLUMN_OFFSET

    def index(
            self, row: int, column: int,
            parent: QModelIndex = QModelIndex()) -> QModelIndex:
        if (
                parent.isValid()
                or row < 0
                or column < 0
                or row >= self.rowCount()
                or column >= self.columnCount()):
            return QModelIndex()
        return self.createIndex(row, column)

    def parent(self, _child: QModelIndex) -> QModelIndex:
        return QModelIndex()

    def mapToSource(self, proxy_index: QModelIndex) -> QModelIndex:
        source = self.sourceModel()
        if (
                source is None
                or not proxy_index.isValid()
                or proxy_index.model() is not self
                or proxy_index.column() == self.IDENTITY_COLUMN):
            return QModelIndex()
        source_column = proxy_index.column() - self.SOURCE_COLUMN_OFFSET
        return source.index(proxy_index.row(), source_column, QModelIndex())

    def mapFromSource(self, source_index: QModelIndex) -> QModelIndex:
        source = self.sourceModel()
        if (
                source is None
                or not source_index.isValid()
                or source_index.model() is not source):
            return QModelIndex()
        return self.index(
            source_index.row(), source_index.column() + self.SOURCE_COLUMN_OFFSET)

    @classmethod
    def view_column_for_source(cls, source_column: int) -> int:
        """Translate a stable parser/source column to its displayed column."""
        if source_column < 0:
            raise ValueError("source column must be non-negative")
        return source_column + cls.SOURCE_COLUMN_OFFSET

    @classmethod
    def source_column_for_view(cls, view_column: int) -> int | None:
        """Return the source column, or ``None`` for the synthetic identity."""
        if view_column < 0:
            raise ValueError("view column must be non-negative")
        if view_column == cls.IDENTITY_COLUMN:
            return None
        return view_column - cls.SOURCE_COLUMN_OFFSET

    # -- Read-only presentation data -------------------------------------------

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        identity = self._identity_for_row(index.row())
        if role == self.RankRole:
            return index.row() + 1
        if role == self.IdentityRole:
            return identity
        if role == self.BarFractionRole:
            return self._bar_fraction(index.row())

        if index.column() == self.IDENTITY_COLUMN:
            if role in (
                    Qt.ItemDataRole.DisplayRole,
                    Qt.ItemDataRole.ToolTipRole,
                    self.FormattedMagnitudeRole):
                return identity
            if role == self.RawValueRole:
                return None
            if role == Qt.ItemDataRole.TextAlignmentRole:
                return int(
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            if role == Qt.ItemDataRole.FontRole:
                source = self.sourceModel()
                if source is not None:
                    return source.headerData(
                        index.row(), Qt.Orientation.Vertical, role)
            return None

        source_index = self.mapToSource(index)
        source = self.sourceModel()
        if source is None or not source_index.isValid():
            return None
        if role == self.RawValueRole:
            return self._raw_value(source_index)
        if role == self.FormattedMagnitudeRole:
            return self._formatted_value(source_index)
        return source.data(source_index, role)

    def itemData(self, index: QModelIndex) -> dict[int, object]:
        if not index.isValid():
            return {}
        source = self.sourceModel()
        source_index = self.mapToSource(index)
        values = (
            dict(source.itemData(source_index))
            if source is not None and source_index.isValid()
            else {}
        )
        for role in self._DERIVED_ROLES:
            value = self.data(index, role)
            if value is not None:
                values[role] = value
        if index.column() == self.IDENTITY_COLUMN:
            for role in (
                    Qt.ItemDataRole.DisplayRole,
                    Qt.ItemDataRole.ToolTipRole,
                    Qt.ItemDataRole.TextAlignmentRole):
                value = self.data(index, role)
                if value is not None:
                    values[role.value] = value
        return values

    def roleNames(self) -> dict[int, bytes]:
        names = dict(super().roleNames())
        names.update({
            self.RankRole: b"rank",
            self.IdentityRole: b"identity",
            self.BarFractionRole: b"barFraction",
            self.FormattedMagnitudeRole: b"formattedMagnitude",
            self.RawValueRole: b"rawValue",
        })
        return names

    def headerData(
            self, section: int, orientation: Qt.Orientation,
            role: int = Qt.ItemDataRole.DisplayRole):
        source = self.sourceModel()
        if source is None:
            return None
        if orientation == Qt.Orientation.Horizontal:
            if section == self.IDENTITY_COLUMN:
                if role == Qt.ItemDataRole.DisplayRole:
                    return "Operator"
                if role == Qt.ItemDataRole.TextAlignmentRole:
                    return int(
                        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                return None
            return source.headerData(
                section - self.SOURCE_COLUMN_OFFSET, orientation, role)
        return source.headerData(section, orientation, role)

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        if index.column() == self.IDENTITY_COLUMN:
            return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        source = self.sourceModel()
        source_index = self.mapToSource(index)
        if source is None or not source_index.isValid():
            return Qt.ItemFlag.NoItemFlags
        flags = source.flags(source_index)
        flags &= ~Qt.ItemFlag.ItemIsEditable
        flags &= ~Qt.ItemFlag.ItemIsDragEnabled
        flags &= ~Qt.ItemFlag.ItemIsDropEnabled
        return flags

    def sort(
            self, column: int,
            order: Qt.SortOrder = Qt.SortOrder.AscendingOrder) -> None:
        """Map a displayed metric column back to the legacy sorter.

        The identity column represents visible rank rather than a source field,
        so sorting it is intentionally a no-op.
        """
        source_column = self.source_column_for_view(column)
        if source_column is not None:
            self.sort_source_column(source_column, order)

    def sort_source_column(
            self, source_column: int,
            order: Qt.SortOrder = Qt.SortOrder.AscendingOrder) -> None:
        source = self.sourceModel()
        if source is None:
            return
        if source_column < 0 or source_column >= source.columnCount():
            raise IndexError(f"source column {source_column} is out of range")
        source.sort(source_column, order)

    # Explicitly reject every writable route exposed by QAbstractProxyModel.
    def setData(self, *_args, **_kwargs) -> bool:
        return False

    def setItemData(self, *_args, **_kwargs) -> bool:
        return False

    def clearItemData(self, *_args, **_kwargs) -> bool:
        return False

    def setHeaderData(self, *_args, **_kwargs) -> bool:
        return False

    def insertRows(self, *_args, **_kwargs) -> bool:
        return False

    def insertColumns(self, *_args, **_kwargs) -> bool:
        return False

    def removeRows(self, *_args, **_kwargs) -> bool:
        return False

    def removeColumns(self, *_args, **_kwargs) -> bool:
        return False

    def moveRows(self, *_args, **_kwargs) -> bool:
        return False

    def moveColumns(self, *_args, **_kwargs) -> bool:
        return False

    def dropMimeData(
            self, _data: QMimeData, _action: Qt.DropAction, _row: int,
            _column: int, _parent: QModelIndex) -> bool:
        return False

    def supportedDropActions(self) -> Qt.DropActions:
        return Qt.DropAction.IgnoreAction

    def supportedDragActions(self) -> Qt.DropActions:
        return Qt.DropAction.IgnoreAction

    # -- Source inspection ------------------------------------------------------

    def _identity_for_row(self, row: int) -> str:
        source = self.sourceModel()
        if source is None or row < 0 or row >= source.rowCount():
            return ""
        value = source.headerData(
            row, Qt.Orientation.Vertical, Qt.ItemDataRole.DisplayRole)
        return "" if value is None else str(value)

    def _base_model_and_index(
            self, source_index: QModelIndex) -> tuple[object | None, QModelIndex]:
        """Map through SortingProxy without importing or modifying it."""
        sorter = self.sourceModel()
        if sorter is None or not source_index.isValid():
            return None, QModelIndex()
        source_model_getter = getattr(sorter, "sourceModel", None)
        map_to_source = getattr(sorter, "mapToSource", None)
        if callable(source_model_getter) and callable(map_to_source):
            base_model = source_model_getter()
            base_index = map_to_source(source_index)
            if base_model is not None and base_index.isValid():
                return base_model, base_index
        return sorter, source_index

    def _raw_value(self, source_index: QModelIndex):
        base_model, base_index = self._base_model_and_index(source_index)
        if base_model is None or not base_index.isValid():
            return None
        rows = getattr(base_model, "_data", None)
        if rows is not None:
            try:
                return rows[base_index.row()][base_index.column()]
            except (IndexError, TypeError):
                return None
        return base_model.data(base_index, Qt.ItemDataRole.DisplayRole)

    def _magnitude_columns(self) -> frozenset[int]:
        source = self.sourceModel()
        if source is None:
            return frozenset()
        source_model_getter = getattr(source, "sourceModel", None)
        base_model = source_model_getter() if callable(source_model_getter) else source
        return frozenset(getattr(base_model, "MAGNITUDE_COLUMNS", ()))

    def _formatted_value(self, source_index: QModelIndex):
        source = self.sourceModel()
        if source is None:
            return None
        raw_value = self._raw_value(source_index)
        if source_index.column() not in self._magnitude_columns() or not isinstance(raw_value, Real):
            return source.data(source_index, Qt.ItemDataRole.DisplayRole)
        value = float(raw_value)
        if not isfinite(value):
            return source.data(source_index, Qt.ItemDataRole.DisplayRole)
        absolute = abs(value)
        if absolute >= 1_000_000_000:
            return f"{value / 1_000_000_000:.2f}B"
        if absolute >= 1_000_000:
            return f"{value / 1_000_000:.2f}M"
        if absolute >= 1_000:
            return f"{value / 1_000:.1f}K"
        return f"{value:,.0f}"

    def _active_source_sort_column(self) -> int:
        source = self.sourceModel()
        if source is None or source.columnCount() == 0:
            return -1
        sort_column_getter = getattr(source, "sortColumn", None)
        column = sort_column_getter() if callable(sort_column_getter) else -1
        if column < 0 or column >= source.columnCount():
            return 0
        return column

    def _bar_fraction(self, row: int) -> float:
        source = self.sourceModel()
        sort_column = self._active_source_sort_column()
        if source is None or sort_column < 0 or row < 0 or row >= source.rowCount():
            return 0.0

        values: list[float] = []
        row_value = 0.0
        for candidate_row in range(source.rowCount()):
            candidate = self._raw_value(source.index(candidate_row, sort_column))
            if not isinstance(candidate, Real):
                continue
            numeric = float(candidate)
            if not isfinite(numeric):
                continue
            numeric = max(0.0, numeric)
            values.append(numeric)
            if candidate_row == row:
                row_value = numeric
        maximum = max(values, default=0.0)
        if maximum <= 0.0:
            return 0.0
        return max(0.0, min(1.0, row_value / maximum))

    # -- Source signal propagation ---------------------------------------------

    def setSourceModel(self, source_model) -> None:
        if source_model is self.sourceModel():
            return
        self.beginResetModel()
        self._disconnect_source()
        super().setSourceModel(source_model)
        self._connect_source(source_model)
        self._clear_layout_tracking()
        self.endResetModel()

    def _connect(self, signal, slot) -> None:
        signal.connect(slot)
        self._source_connections.append((signal, slot))

    def _connect_source(self, source) -> None:
        if source is None:
            return
        connections = (
            (source.modelAboutToBeReset, self._source_model_about_to_reset),
            (source.modelReset, self._source_model_reset),
            (source.dataChanged, self._source_data_changed),
            (source.headerDataChanged, self._source_header_data_changed),
            (source.layoutAboutToBeChanged, self._source_layout_about_to_change),
            (source.layoutChanged, self._source_layout_changed),
            (source.rowsAboutToBeInserted, self._source_rows_about_to_be_inserted),
            (source.rowsInserted, self._source_rows_inserted),
            (source.rowsAboutToBeRemoved, self._source_rows_about_to_be_removed),
            (source.rowsRemoved, self._source_rows_removed),
            (source.columnsAboutToBeInserted, self._source_columns_about_to_be_inserted),
            (source.columnsInserted, self._source_columns_inserted),
            (source.columnsAboutToBeRemoved, self._source_columns_about_to_be_removed),
            (source.columnsRemoved, self._source_columns_removed),
            (source.rowsAboutToBeMoved, self._source_rows_about_to_be_moved),
            (source.rowsMoved, self._source_rows_moved),
            (source.columnsAboutToBeMoved, self._source_columns_about_to_be_moved),
            (source.columnsMoved, self._source_columns_moved),
        )
        for signal, slot in connections:
            self._connect(signal, slot)

    def _disconnect_source(self) -> None:
        for signal, slot in self._source_connections:
            try:
                signal.disconnect(slot)
            except (RuntimeError, TypeError):
                pass
        self._source_connections.clear()

    def _source_model_about_to_reset(self) -> None:
        self._clear_layout_tracking()
        self.beginResetModel()

    def _source_model_reset(self) -> None:
        self.endResetModel()

    def _source_data_changed(
            self, _top_left: QModelIndex, _bottom_right: QModelIndex,
            roles: list[int] | None = None) -> None:
        if self.rowCount() == 0 or self.columnCount() == 0:
            return
        changed_roles = list(roles or ())
        for role in self._DERIVED_ROLES:
            if role not in changed_roles:
                changed_roles.append(role)
        self.dataChanged.emit(
            self.index(0, 0),
            self.index(self.rowCount() - 1, self.columnCount() - 1),
            changed_roles,
        )

    def _source_header_data_changed(
            self, orientation: Qt.Orientation, first: int, last: int) -> None:
        if orientation == Qt.Orientation.Horizontal:
            self.headerDataChanged.emit(
                orientation,
                first + self.SOURCE_COLUMN_OFFSET,
                last + self.SOURCE_COLUMN_OFFSET,
            )
            return
        self.headerDataChanged.emit(orientation, first, last)
        if self.rowCount() > 0:
            first_row = max(0, min(first, self.rowCount() - 1))
            last_row = max(first_row, min(last, self.rowCount() - 1))
            self.dataChanged.emit(
                self.index(first_row, self.IDENTITY_COLUMN),
                self.index(last_row, self.IDENTITY_COLUMN),
                [
                    Qt.ItemDataRole.DisplayRole.value,
                    Qt.ItemDataRole.ToolTipRole.value,
                    self.IdentityRole,
                    self.RankRole,
                ],
            )

    def _source_layout_about_to_change(
            self, _parents=None,
            hint=QAbstractItemModel.LayoutChangeHint.NoLayoutChangeHint) -> None:
        self._layout_indexes = list(self.persistentIndexList())
        self._layout_anchors = []
        source = self.sourceModel()
        for proxy_index in self._layout_indexes:
            source_index = self.mapToSource(proxy_index)
            if not source_index.isValid() and source is not None and source.columnCount() > 0:
                source_index = source.index(proxy_index.row(), 0)
            self._layout_anchors.append(
                (QPersistentModelIndex(source_index), proxy_index.column()))
        self._layout_hint = hint
        # PySide exposes these inherited signals through their zero-argument
        # overload even though Qt's C++ API also carries parents and a hint.
        self.layoutAboutToBeChanged.emit()

    def _source_layout_changed(
            self, _parents=None,
            hint=QAbstractItemModel.LayoutChangeHint.NoLayoutChangeHint) -> None:
        new_indexes: list[QModelIndex] = []
        for source_anchor, proxy_column in self._layout_anchors:
            if source_anchor.isValid():
                new_indexes.append(self.index(source_anchor.row(), proxy_column))
            else:
                new_indexes.append(QModelIndex())
        if self._layout_indexes:
            self.changePersistentIndexList(self._layout_indexes, new_indexes)
        self.layoutChanged.emit()
        self._clear_layout_tracking()

    def _clear_layout_tracking(self) -> None:
        self._layout_indexes = []
        self._layout_anchors = []
        self._layout_hint = QAbstractItemModel.LayoutChangeHint.NoLayoutChangeHint

    def _source_rows_about_to_be_inserted(
            self, parent: QModelIndex, first: int, last: int) -> None:
        self.beginInsertRows(self.mapFromSource(parent), first, last)

    def _source_rows_inserted(self, _parent: QModelIndex, _first: int, _last: int) -> None:
        self.endInsertRows()

    def _source_rows_about_to_be_removed(
            self, parent: QModelIndex, first: int, last: int) -> None:
        self.beginRemoveRows(self.mapFromSource(parent), first, last)

    def _source_rows_removed(self, _parent: QModelIndex, _first: int, _last: int) -> None:
        self.endRemoveRows()

    def _source_columns_about_to_be_inserted(
            self, parent: QModelIndex, first: int, last: int) -> None:
        self.beginInsertColumns(
            self.mapFromSource(parent),
            first + self.SOURCE_COLUMN_OFFSET,
            last + self.SOURCE_COLUMN_OFFSET,
        )

    def _source_columns_inserted(self, _parent: QModelIndex, _first: int, _last: int) -> None:
        self.endInsertColumns()

    def _source_columns_about_to_be_removed(
            self, parent: QModelIndex, first: int, last: int) -> None:
        self.beginRemoveColumns(
            self.mapFromSource(parent),
            first + self.SOURCE_COLUMN_OFFSET,
            last + self.SOURCE_COLUMN_OFFSET,
        )

    def _source_columns_removed(self, _parent: QModelIndex, _first: int, _last: int) -> None:
        self.endRemoveColumns()

    def _source_rows_about_to_be_moved(
            self, source_parent: QModelIndex, source_start: int, source_end: int,
            destination_parent: QModelIndex, destination_row: int) -> None:
        self._row_move_active = self.beginMoveRows(
            self.mapFromSource(source_parent), source_start, source_end,
            self.mapFromSource(destination_parent), destination_row)

    def _source_rows_moved(self, *_args) -> None:
        if self._row_move_active:
            self.endMoveRows()
        self._row_move_active = False

    def _source_columns_about_to_be_moved(
            self, source_parent: QModelIndex, source_start: int, source_end: int,
            destination_parent: QModelIndex, destination_column: int) -> None:
        self._column_move_active = self.beginMoveColumns(
            self.mapFromSource(source_parent),
            source_start + self.SOURCE_COLUMN_OFFSET,
            source_end + self.SOURCE_COLUMN_OFFSET,
            self.mapFromSource(destination_parent),
            destination_column + self.SOURCE_COLUMN_OFFSET,
        )

    def _source_columns_moved(self, *_args) -> None:
        if self._column_move_active:
            self.endMoveColumns()
        self._column_move_active = False


class OverviewMeterDelegate(QStyledItemDelegate):
    """Paint Command Console rows using tokens and display-only model roles."""

    def __init__(self, tokens: ConsoleTokens, parent=None):
        super().__init__(parent)
        self._tokens = tokens
        self._meter_enabled = True
        self._compact_magnitudes = True

    @property
    def meter_enabled(self) -> bool:
        return self._meter_enabled

    def set_meter_enabled(self, enabled: bool) -> None:
        self._meter_enabled = bool(enabled)

    def set_compact_magnitudes(self, enabled: bool) -> None:
        self._compact_magnitudes = bool(enabled)

    def set_tokens(self, tokens: ConsoleTokens) -> None:
        self._tokens = tokens

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        hint = super().sizeHint(option, index)
        target = px(39 if self._meter_enabled else 28, self._tokens.scale)
        return QSize(hint.width(), max(hint.height(), target))

    def paint(
            self, painter: QPainter, option: QStyleOptionViewItem,
            index: QModelIndex) -> None:
        painter.save()
        painter.setClipRect(option.rect)

        rank = index.data(RankRole) or index.row() + 1
        accent_index = (int(rank) - 1) % len(self._tokens.accents)
        accent = QColor(self._tokens.accents[accent_index])
        selected = bool(option.state & QStyle.StateFlag.State_Selected)

        if self._meter_enabled:
            self._paint_meter_row(painter, option, index, accent_index, selected)
        else:
            self._paint_grid_row(painter, option, index, accent_index, selected)

        if index.column() == OverviewDisplayProxy.IDENTITY_COLUMN:
            self._paint_identity(painter, option, index, rank, accent)
        else:
            self._paint_metric(painter, option, index)

        if option.state & QStyle.StateFlag.State_HasFocus:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QColor(BORDERS["focus"]))
            painter.drawRect(option.rect.adjusted(1, 1, -2, -2))
        painter.restore()

    def _row_rect(self, option: QStyleOptionViewItem, gap: int) -> QRect:
        # Both the main and frozen delegates paint one logical row canvas.  The
        # frozen view clips that shared canvas instead of starting a second,
        # differently-scaled meter at the Operator-column boundary.
        owner = self.parent()
        if isinstance(owner, QTableView):
            widget_width = owner.viewport().width()
        else:
            widget_width = (
                option.widget.width()
                if option.widget is not None
                else option.rect.right() + 1
            )
        top = option.rect.top() + gap // 2
        return QRect(0, top, widget_width, max(1, option.rect.height() - gap))

    def _paint_meter_row(
            self, painter: QPainter, option: QStyleOptionViewItem,
            index: QModelIndex, accent_index: int, selected: bool) -> None:
        gap = px(5, self._tokens.scale)
        radius = px(12, self._tokens.scale)
        row_rect = self._row_rect(option, gap)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(SURFACES["overlay"]))
        painter.drawRoundedRect(row_rect, radius, radius)

        fraction = index.data(BarFractionRole)
        try:
            fraction = max(0.0, min(1.0, float(fraction)))
        except (TypeError, ValueError):
            fraction = 0.0
        if fraction > 0.0:
            fill = QRect(row_rect)
            fill.setWidth(max(1, round(row_rect.width() * fraction)))
            painter.setBrush(QColor(self._tokens.accent_tint(accent_index)))
            painter.drawRoundedRect(fill, radius, radius)

        spine_width = px(4, self._tokens.scale)
        painter.setBrush(QColor(self._tokens.accents[accent_index]))
        painter.drawRect(row_rect.left(), row_rect.top(), spine_width, row_rect.height())

        if selected:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QColor(self._tokens.accent_edge(accent_index)))
            painter.drawRoundedRect(row_rect.adjusted(1, 1, -2, -2), radius, radius)

    def _paint_grid_row(
            self, painter: QPainter, option: QStyleOptionViewItem,
            _index: QModelIndex, accent_index: int, selected: bool) -> None:
        background = self._grid_row_background(
            _index.row(), accent_index, selected)
        painter.fillRect(option.rect, QColor(background))
        if _index.column() == OverviewDisplayProxy.IDENTITY_COLUMN:
            painter.fillRect(
                option.rect.left(), option.rect.top(), px(3, self._tokens.scale),
                option.rect.height(), QColor(self._tokens.accents[accent_index]))

    def _grid_row_background(
            self, row: int, accent_index: int, selected: bool) -> str:
        """Keep operator colour identity in every numeric-grid table mode."""
        surface = SURFACES["raised"] if row % 2 else SURFACES["base"]
        accent_ratio = 0.26 if selected else (0.14 if row % 2 else 0.16)
        return blend(self._tokens.accents[accent_index], surface, accent_ratio)

    def _paint_identity(
            self, painter: QPainter, option: QStyleOptionViewItem,
            index: QModelIndex, rank: int, accent: QColor) -> None:
        scale = self._tokens.scale
        content = option.rect.adjusted(px(9, scale), 0, -px(8, scale), 0)
        rank_width = px(31, scale)
        rank_rect = QRect(content.left(), content.top(), rank_width, content.height())
        name_rect = QRect(
            rank_rect.right() + px(7, scale), content.top(),
            max(0, content.right() - rank_rect.right() - px(7, scale)), content.height())

        rank_font = QFont(option.font)
        rank_font.setFamily("Roboto Mono")
        rank_font.setPixelSize(px(11, scale))
        rank_font.setWeight(QFont.Weight.Bold)
        painter.setFont(rank_font)
        painter.setPen(accent)
        painter.drawText(
            rank_rect,
            int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
            f"{int(rank):02}",
        )

        name_font = QFont(option.font)
        name_font.setFamily("Overpass")
        name_font.setPixelSize(px(12 if self._meter_enabled else 11, scale))
        name_font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(name_font)
        painter.setPen(QColor(TEXT["primary"]))
        identity = str(index.data(IdentityRole) or "")
        identity = QFontMetrics(name_font).elidedText(
            identity, Qt.TextElideMode.ElideRight, name_rect.width())
        painter.drawText(
            name_rect,
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            identity,
        )

    def _paint_metric(
            self, painter: QPainter, option: QStyleOptionViewItem,
            index: QModelIndex) -> None:
        scale = self._tokens.scale
        content = option.rect.adjusted(px(8, scale), 0, -px(8, scale), 0)
        display_role = (
            FormattedMagnitudeRole
            if self._compact_magnitudes
            else Qt.ItemDataRole.DisplayRole
        )
        value = index.data(display_role)
        text = "" if value is None else str(value)

        font = QFont(option.font)
        font.setFamily("Roboto Mono")
        if self._meter_enabled and index.column() == OverviewDisplayProxy.SOURCE_COLUMN_OFFSET:
            font.setPixelSize(px(14, scale))
            font.setWeight(QFont.Weight.Bold)
            colour = TEXT["primary"]
        else:
            font.setPixelSize(px(11, scale))
            font.setWeight(QFont.Weight.Medium)
            colour = TEXT["secondary"]
        painter.setFont(font)
        painter.setPen(QColor(colour))
        painter.drawText(
            content,
            int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
            text,
        )


class OverviewTableView(QTableView):
    """Overview table with a synchronized frozen identity companion view."""

    def __init__(self, tokens: ConsoleTokens, parent: QWidget | None = None):
        super().__init__(parent)
        self._tokens = tokens
        self._visible_source_columns: set[int] | None = None
        self._model_connections: list[tuple[object, object]] = []

        self.setObjectName("overviewTelemetryTable")
        self.setProperty("consoleRole", "telemetryTable")
        self.setShowGrid(False)
        self.setAlternatingRowColors(False)
        self.setWordWrap(False)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.horizontalHeader().setSectionsClickable(True)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.horizontalHeader().setStretchLastSection(False)
        self.horizontalHeader().setSortIndicatorShown(True)
        self.verticalHeader().hide()
        self.setSortingEnabled(True)

        self._frozen_view = QTableView(self)
        self._frozen_view.setObjectName("overviewFrozenIdentityTable")
        self._frozen_view.setProperty("consoleRole", "frozenIdentityTable")
        self._frozen_view.setFrameShape(QFrame.Shape.NoFrame)
        self._frozen_view.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._frozen_view.setShowGrid(False)
        self._frozen_view.setAlternatingRowColors(False)
        self._frozen_view.setWordWrap(False)
        self._frozen_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._frozen_view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._frozen_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._frozen_view.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self._frozen_view.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self._frozen_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._frozen_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._frozen_view.horizontalHeader().setSectionsClickable(False)
        self._frozen_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self._frozen_view.horizontalHeader().setSortIndicatorShown(True)
        self._frozen_view.verticalHeader().hide()

        self._delegate = OverviewMeterDelegate(tokens, self)
        self.setItemDelegate(self._delegate)
        self._frozen_view.setItemDelegate(self._delegate)
        self.viewport().stackUnder(self._frozen_view)

        self.horizontalHeader().sectionResized.connect(self._main_section_resized)
        self.horizontalHeader().geometriesChanged.connect(self._queue_geometry_update)
        self.verticalHeader().sectionResized.connect(self._main_row_resized)
        self._frozen_view.verticalHeader().sectionResized.connect(self._frozen_row_resized)
        self.horizontalHeader().sortIndicatorChanged.connect(
            self._frozen_view.horizontalHeader().setSortIndicator)
        self.verticalScrollBar().valueChanged.connect(
            self._frozen_view.verticalScrollBar().setValue)
        self._frozen_view.verticalScrollBar().valueChanged.connect(
            self.verticalScrollBar().setValue)
        self._frozen_view.horizontalScrollBar().rangeChanged.connect(
            lambda _minimum, _maximum: self._frozen_view.horizontalScrollBar().setValue(0))

        self._frozen_view.show()

    @property
    def frozen_view(self) -> QTableView:
        return self._frozen_view

    @property
    def display_proxy(self) -> OverviewDisplayProxy | None:
        model = self.model()
        return model if isinstance(model, OverviewDisplayProxy) else None

    def setModel(self, model) -> None:
        self._disconnect_model()
        super().setModel(model)
        frozen = getattr(self, "_frozen_view", None)
        if frozen is None:
            return
        frozen.setModel(model)
        if self.selectionModel() is not None:
            frozen.setSelectionModel(self.selectionModel())
        self._connect_model(model)
        self._apply_column_visibility()
        self._configure_frozen_columns()
        self.resizeRowsToContents()
        self._queue_geometry_update()

    def set_tokens(self, tokens: ConsoleTokens) -> None:
        self._tokens = tokens
        self._delegate.set_tokens(tokens)
        self.viewport().update()
        self._frozen_view.viewport().update()

    def set_meter_mode(self, enabled: bool) -> None:
        self._delegate.set_meter_enabled(enabled)
        self.resizeRowsToContents()
        self.viewport().update()
        self._frozen_view.viewport().update()

    def set_compact_magnitudes(self, enabled: bool) -> None:
        self._delegate.set_compact_magnitudes(enabled)
        self.viewport().update()
        self._frozen_view.viewport().update()

    def set_visible_source_columns(self, columns: Iterable[int]) -> None:
        model = self.display_proxy
        selected = {int(column) for column in columns}
        if any(column < 0 for column in selected):
            raise ValueError("source columns must be non-negative")
        if model is not None:
            source_count = model.columnCount() - model.SOURCE_COLUMN_OFFSET
            # OverviewTableModel reports zero columns until its first data row.
            # Accept the stable TABLE_HEADER indexes while empty and validate as
            # soon as a populated model is available.
            invalid = sorted(
                column for column in selected
                if source_count > 0 and column >= source_count)
            if invalid:
                raise IndexError(f"source columns are out of range: {invalid}")
        self._visible_source_columns = selected
        self._apply_column_visibility()
        self.resizeColumnsToContents()

    def visible_source_columns(self) -> frozenset[int]:
        model = self.display_proxy
        if model is None:
            return frozenset()
        return frozenset(
            source_column
            for source_column in range(model.columnCount() - model.SOURCE_COLUMN_OFFSET)
            if not self.isColumnHidden(model.view_column_for_source(source_column))
        )

    def sort_by_source_column(
            self, source_column: int,
            order: Qt.SortOrder = Qt.SortOrder.AscendingOrder) -> None:
        model = self.display_proxy
        if model is None:
            raise TypeError("OverviewTableView requires OverviewDisplayProxy")
        self.sortByColumn(model.view_column_for_source(source_column), order)

    def resizeColumnsToContents(self) -> None:
        super().resizeColumnsToContents()
        self._sync_identity_width()
        self._queue_geometry_update()

    def resizeRowsToContents(self) -> None:
        super().resizeRowsToContents()
        for row in range(self.model().rowCount() if self.model() is not None else 0):
            self._sync_row_height(row, self.rowHeight(row), self._frozen_view)
        self._queue_geometry_update()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.update_frozen_geometry()

    def update_frozen_geometry(self) -> None:
        if self.model() is None or self.model().columnCount() == 0:
            self._frozen_view.hide()
            return
        identity_width = self.columnWidth(OverviewDisplayProxy.IDENTITY_COLUMN)
        main_header_height = self.horizontalHeader().height()
        frozen_header = self._frozen_view.horizontalHeader()
        if frozen_header.height() != main_header_height:
            frozen_header.setFixedHeight(main_header_height)
            self._frozen_view.updateGeometries()
        self._frozen_view.setGeometry(
            self.frameWidth(),
            self.frameWidth(),
            identity_width,
            self.viewport().height() + main_header_height,
        )
        self._frozen_view.show()

    # Qt-style aliases make integration at existing widget call sites concise.
    setVisibleSourceColumns = set_visible_source_columns
    sortBySourceColumn = sort_by_source_column
    updateFrozenGeometry = update_frozen_geometry

    def _connect_model(self, model) -> None:
        if model is None:
            return
        for signal in (model.modelReset, model.columnsInserted, model.columnsRemoved):
            slot = self._model_structure_changed
            signal.connect(slot)
            self._model_connections.append((signal, slot))
        model.layoutChanged.connect(self._model_layout_changed)
        self._model_connections.append((model.layoutChanged, self._model_layout_changed))

    def _disconnect_model(self) -> None:
        for signal, slot in self._model_connections:
            try:
                signal.disconnect(slot)
            except (RuntimeError, TypeError):
                pass
        self._model_connections.clear()

    def _model_structure_changed(self, *_args) -> None:
        self._apply_column_visibility()
        self._configure_frozen_columns()
        self.resizeRowsToContents()
        self._queue_geometry_update()

    def _model_layout_changed(self, *_args) -> None:
        self._configure_frozen_columns()
        self._queue_geometry_update()

    def _apply_column_visibility(self) -> None:
        model = self.display_proxy
        if model is None:
            return
        super().setColumnHidden(model.IDENTITY_COLUMN, False)
        source_count = model.columnCount() - model.SOURCE_COLUMN_OFFSET
        for source_column in range(source_count):
            hidden = (
                self._visible_source_columns is not None
                and source_column not in self._visible_source_columns
            )
            super().setColumnHidden(model.view_column_for_source(source_column), hidden)

    def _configure_frozen_columns(self) -> None:
        model = self.model()
        if model is None:
            return
        for column in range(model.columnCount()):
            self._frozen_view.setColumnHidden(
                column, column != OverviewDisplayProxy.IDENTITY_COLUMN)
        self._sync_identity_width()

    def _main_section_resized(self, logical_index: int, _old: int, new: int) -> None:
        if logical_index != OverviewDisplayProxy.IDENTITY_COLUMN:
            return
        if self._frozen_view.columnWidth(logical_index) != new:
            self._frozen_view.setColumnWidth(logical_index, new)
        self.update_frozen_geometry()

    def _sync_identity_width(self) -> None:
        if self.model() is None or self.model().columnCount() == 0:
            return
        width = self.columnWidth(OverviewDisplayProxy.IDENTITY_COLUMN)
        if self._frozen_view.columnWidth(OverviewDisplayProxy.IDENTITY_COLUMN) != width:
            self._frozen_view.setColumnWidth(OverviewDisplayProxy.IDENTITY_COLUMN, width)

    def _main_row_resized(self, row: int, _old: int, new: int) -> None:
        self._sync_row_height(row, new, self._frozen_view)

    def _frozen_row_resized(self, row: int, _old: int, new: int) -> None:
        self._sync_row_height(row, new, self)

    @staticmethod
    def _sync_row_height(row: int, height: int, target: QTableView) -> None:
        if target.rowHeight(row) != height:
            target.setRowHeight(row, height)

    def _queue_geometry_update(self) -> None:
        QTimer.singleShot(0, self.update_frozen_geometry)


class _AnalysisIdentityHeader(QHeaderView):
    """Paint the frozen identity caption without editing parser header data."""

    identity_label = "SOURCE"

    def paintSection(
            self, painter: QPainter, rect: QRect, logical_index: int) -> None:
        if logical_index != AnalysisTreeView.IDENTITY_COLUMN:
            super().paintSection(painter, rect, logical_index)
            return
        option = QStyleOptionHeader()
        self.initStyleOptionForIndex(option, logical_index)
        option.rect = rect
        option.text = self.identity_label
        painter.save()
        self.style().drawControl(
            QStyle.ControlElement.CE_Header,
            option,
            painter,
            self,
        )
        painter.restore()


class AnalysisTreeDelegate(QStyledItemDelegate):
    """Paint hierarchy as a quiet, scan-friendly telemetry surface.

    All styling is derived from existing indexes and the view's expansion
    state.  No roles are added to the parser model and no data is written back.
    """

    def __init__(self, owner: "AnalysisTreeView"):
        super().__init__(owner)
        self._owner = owner

    def sizeHint(
            self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        """Use one height for the identity pane and every metric cell in a logical row."""
        hint = super().sizeHint(option, index)
        model = index.model()
        if model is None or index.column() != AnalysisTreeView.IDENTITY_COLUMN:
            return hint
        height = hint.height()
        parent = index.parent()
        for column in range(model.columnCount(parent)):
            sibling = model.index(index.row(), column, parent)
            height = max(height, super().sizeHint(option, sibling).height())
        return QSize(hint.width(), height)

    def paint(
            self, painter: QPainter, option: QStyleOptionViewItem,
            index: QModelIndex) -> None:
        display_option = QStyleOptionViewItem(option)
        self.initStyleOption(display_option, index)

        selected = bool(
            display_option.state & QStyle.StateFlag.State_Selected)
        background = self._row_background(index, selected)
        brush = QBrush(background)
        display_option.backgroundBrush = brush
        for role in (
                QPalette.ColorRole.Base,
                QPalette.ColorRole.AlternateBase,
                QPalette.ColorRole.Highlight):
            display_option.palette.setBrush(role, brush)
        display_option.palette.setColor(
            QPalette.ColorRole.HighlightedText, QColor(TEXT["primary"]))
        actor_group_label = (
            self._actor_group_label(index)
            if index.column() == AnalysisTreeView.IDENTITY_COLUMN else None
        )
        if actor_group_label is not None:
            display_option.text = actor_group_label
            display_option.font.setBold(True)
            display_option.palette.setColor(
                QPalette.ColorRole.Text, self._owner.analysis_accent_color)
            display_option.palette.setColor(
                QPalette.ColorRole.WindowText, self._owner.analysis_accent_color)

        style = (
            display_option.widget.style()
            if display_option.widget is not None
            else QApplication.style()
        )
        style.drawControl(
            QStyle.ControlElement.CE_ItemViewItem,
            display_option,
            painter,
            display_option.widget,
        )

        if (
                index.column() == AnalysisTreeView.IDENTITY_COLUMN
                and self._is_expanded_parent(index)):
            painter.save()
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self._owner.analysis_accent_color)
            painter.drawRect(QRect(
                option.rect.left(), option.rect.top(),
                self._owner.analysis_spine_width, option.rect.height()))
            painter.restore()

    @staticmethod
    def _actor_group_label(index: QModelIndex) -> str | None:
        """Present parser actor buckets as useful group headers without editing them."""
        if index.parent().isValid():
            return None
        source = str(index.data(Qt.ItemDataRole.DisplayRole) or '').strip().lower()
        model = index.model()
        if model is None or model.rowCount(index) == 0:
            return None
        if source == 'player':
            label = 'PLAYER' if model.rowCount(index) == 1 else 'PLAYERS'
        elif source == 'npc':
            label = 'NPC'
        else:
            return None
        count = model.rowCount(index)
        return f'{label} // {count} SOURCE' + ('' if count == 1 else 'S')

    def _row_background(self, index: QModelIndex, selected: bool) -> QColor:
        depth = self._depth(index)
        surface = SURFACES["raised"] if depth == 0 else SURFACES["base"]
        ratio = max(0.035, 0.10 - depth * 0.025)
        if self._actor_group_label(index) is not None:
            ratio = max(ratio, 0.15)
        if self._is_expanded_parent(index):
            ratio += 0.09
        if selected:
            ratio = max(ratio, 0.22)
        return QColor(blend(
            self._owner.analysis_accent_color.name(), surface, ratio))

    @staticmethod
    def _depth(index: QModelIndex) -> int:
        depth = 0
        parent = index.parent()
        while parent.isValid():
            depth += 1
            parent = parent.parent()
        return depth

    def _is_expanded_parent(self, index: QModelIndex) -> bool:
        identity = index.sibling(index.row(), AnalysisTreeView.IDENTITY_COLUMN)
        model = identity.model()
        return (
            identity.isValid()
            and model is not None
            and model.rowCount(identity) > 0
            and self._owner.isExpanded(identity)
        )


class AnalysisTreeView(QTreeView):
    """Analysis tree with a view-only frozen identity column.

    The companion is deliberately another ``QTreeView`` over the *same* model
    and selection model.  It does not proxy, copy, or mutate parser data; it
    only keeps column zero visible while the metric columns scroll.  Expansion
    state and vertical position are view state, so those are mirrored in both
    directions as well.
    """

    IDENTITY_COLUMN = 0

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._model_connections: list[tuple[object, object]] = []
        self._syncing_expansion = False
        self._analysis_accent_color = QColor(TEXT["eyebrow"])
        self._analysis_spine_width = 3
        self._delegate = AnalysisTreeDelegate(self)
        self.setItemDelegate(self._delegate)

        frozen = QTreeView(self)
        frozen.setHeader(_AnalysisIdentityHeader(Qt.Orientation.Horizontal, frozen))
        self._frozen_view = frozen
        frozen.setObjectName("analysisFrozenIdentityTree")
        # Use the same role as the main tree so global Command Console rules
        # produce identical fonts, padding, and therefore row heights.
        frozen.setProperty("consoleRole", "analysisTree")
        frozen.setProperty("frozenIdentity", True)
        frozen.setItemDelegate(self._delegate)
        frozen.setFrameShape(QFrame.Shape.NoFrame)
        frozen.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        frozen.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        frozen.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        frozen.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        frozen.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        frozen.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        frozen.header().setSectionsClickable(True)
        frozen.header().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        frozen.header().setMinimumSectionSize(1)
        frozen.header().setStretchLastSection(False)
        frozen.header().setSortIndicatorShown(True)

        self.viewport().stackUnder(frozen)
        self.header().sectionResized.connect(self._main_section_resized)
        self.header().geometriesChanged.connect(self._queue_geometry_update)
        self.header().sortIndicatorChanged.connect(frozen.header().setSortIndicator)
        frozen.header().sectionClicked.connect(self._frozen_section_clicked)
        self.verticalScrollBar().valueChanged.connect(
            frozen.verticalScrollBar().setValue)
        frozen.verticalScrollBar().valueChanged.connect(
            self.verticalScrollBar().setValue)
        frozen.horizontalScrollBar().rangeChanged.connect(
            self._reset_frozen_horizontal_scroll)
        frozen.horizontalScrollBar().valueChanged.connect(
            self._reset_frozen_horizontal_value)

        self.expanded.connect(self._main_expanded)
        self.collapsed.connect(self._main_collapsed)
        frozen.expanded.connect(self._frozen_expanded)
        frozen.collapsed.connect(self._frozen_collapsed)
        frozen.show()

    def _get_analysis_accent_color(self) -> QColor:
        return QColor(self._analysis_accent_color)

    def _set_analysis_accent_color(self, colour: QColor) -> None:
        resolved = QColor(colour)
        if not resolved.isValid() or resolved == self._analysis_accent_color:
            return
        self._analysis_accent_color = resolved
        self.viewport().update()
        self._frozen_view.viewport().update()

    def _get_analysis_spine_width(self) -> int:
        return self._analysis_spine_width

    def _set_analysis_spine_width(self, width: int) -> None:
        resolved = max(1, int(width))
        if resolved == self._analysis_spine_width:
            return
        self._analysis_spine_width = resolved
        self.viewport().update()
        self._frozen_view.viewport().update()

    analysisAccentColor = Property(
        QColor, _get_analysis_accent_color, _set_analysis_accent_color)
    analysisSpineWidth = Property(
        int, _get_analysis_spine_width, _set_analysis_spine_width)

    @property
    def analysis_accent_color(self) -> QColor:
        return QColor(self._analysis_accent_color)

    @property
    def analysis_spine_width(self) -> int:
        return self._analysis_spine_width

    @property
    def frozen_view(self) -> QTreeView:
        return self._frozen_view

    def setModel(self, model) -> None:
        self._disconnect_model()
        super().setModel(model)
        self._frozen_view.setModel(model)
        selection_model = self.selectionModel()
        if selection_model is not None:
            self._frozen_view.setSelectionModel(selection_model)
        self._connect_model(model)
        self._configure_frozen_columns()
        self._queue_view_sync()

    def setSelectionModel(self, selection_model) -> None:
        """Keep the parser UI's exact ``TreeSelectionModel`` instance."""
        super().setSelectionModel(selection_model)
        frozen = getattr(self, "_frozen_view", None)
        if (
                frozen is not None
                and selection_model is not None
                and frozen.model() is selection_model.model()):
            frozen.setSelectionModel(selection_model)

    # Presentation properties set by AnalysisTables/AnalysisView must match on
    # both panes or Qt can calculate different row heights for the same index.
    def setStyleSheet(self, style_sheet: str) -> None:
        super().setStyleSheet(style_sheet)
        frozen = getattr(self, "_frozen_view", None)
        if frozen is not None:
            frozen.setStyleSheet(style_sheet)

    def setFont(self, font: QFont) -> None:
        super().setFont(font)
        frozen = getattr(self, "_frozen_view", None)
        if frozen is not None:
            frozen.setFont(font)

    def setAlternatingRowColors(self, enabled: bool) -> None:
        super().setAlternatingRowColors(enabled)
        frozen = getattr(self, "_frozen_view", None)
        if frozen is not None:
            frozen.setAlternatingRowColors(enabled)

    def setWordWrap(self, enabled: bool) -> None:
        super().setWordWrap(enabled)
        frozen = getattr(self, "_frozen_view", None)
        if frozen is not None:
            frozen.setWordWrap(enabled)

    def setUniformRowHeights(self, enabled: bool) -> None:
        super().setUniformRowHeights(enabled)
        frozen = getattr(self, "_frozen_view", None)
        if frozen is not None:
            frozen.setUniformRowHeights(enabled)

    def setIndentation(self, indentation: int) -> None:
        super().setIndentation(indentation)
        frozen = getattr(self, "_frozen_view", None)
        if frozen is not None:
            frozen.setIndentation(indentation)

    def setRootIsDecorated(self, enabled: bool) -> None:
        super().setRootIsDecorated(enabled)
        frozen = getattr(self, "_frozen_view", None)
        if frozen is not None:
            frozen.setRootIsDecorated(enabled)

    def setItemsExpandable(self, enabled: bool) -> None:
        super().setItemsExpandable(enabled)
        frozen = getattr(self, "_frozen_view", None)
        if frozen is not None:
            frozen.setItemsExpandable(enabled)

    def setExpandsOnDoubleClick(self, enabled: bool) -> None:
        super().setExpandsOnDoubleClick(enabled)
        frozen = getattr(self, "_frozen_view", None)
        if frozen is not None:
            frozen.setExpandsOnDoubleClick(enabled)

    def setAnimated(self, enabled: bool) -> None:
        super().setAnimated(enabled)
        frozen = getattr(self, "_frozen_view", None)
        if frozen is not None:
            frozen.setAnimated(enabled)

    def setSelectionMode(self, mode: QAbstractItemView.SelectionMode) -> None:
        super().setSelectionMode(mode)
        frozen = getattr(self, "_frozen_view", None)
        if frozen is not None:
            frozen.setSelectionMode(mode)

    def setSelectionBehavior(
            self, behavior: QAbstractItemView.SelectionBehavior) -> None:
        super().setSelectionBehavior(behavior)
        frozen = getattr(self, "_frozen_view", None)
        if frozen is not None:
            frozen.setSelectionBehavior(behavior)

    def setEditTriggers(self, triggers: QAbstractItemView.EditTrigger) -> None:
        super().setEditTriggers(triggers)
        frozen = getattr(self, "_frozen_view", None)
        if frozen is not None:
            frozen.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

    def setRootIndex(self, index: QModelIndex) -> None:
        super().setRootIndex(index)
        frozen = getattr(self, "_frozen_view", None)
        if frozen is not None and frozen.model() is self.model():
            frozen.setRootIndex(index)
            self._queue_view_sync()

    def resizeColumnToContents(self, column: int) -> None:
        super().resizeColumnToContents(column)
        if column == self.IDENTITY_COLUMN:
            self._sync_identity_width()
            self._queue_geometry_update()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.update_frozen_geometry()

    def update_frozen_geometry(self) -> None:
        model = self.model()
        if model is None or model.columnCount(self.rootIndex()) == 0:
            self._frozen_view.hide()
            return
        identity_width = self.columnWidth(self.IDENTITY_COLUMN)
        main_header_height = self.header().height()
        frozen_header = self._frozen_view.header()
        if frozen_header.height() != main_header_height:
            frozen_header.setFixedHeight(main_header_height)
            self._frozen_view.updateGeometries()
        self._frozen_view.setGeometry(
            self.frameWidth(),
            self.frameWidth(),
            identity_width,
            self.viewport().height() + main_header_height,
        )
        self._frozen_view.show()

    updateFrozenGeometry = update_frozen_geometry

    def _connect_model(self, model) -> None:
        if model is None:
            return
        for signal in (
                model.modelReset,
                model.columnsInserted,
                model.columnsRemoved,
                model.rowsInserted,
                model.rowsRemoved):
            slot = self._model_structure_changed
            signal.connect(slot)
            self._model_connections.append((signal, slot))
        model.layoutChanged.connect(self._model_layout_changed)
        self._model_connections.append((model.layoutChanged, self._model_layout_changed))

    def _disconnect_model(self) -> None:
        for signal, slot in self._model_connections:
            try:
                signal.disconnect(slot)
            except (RuntimeError, TypeError):
                pass
        self._model_connections.clear()

    def _model_structure_changed(self, *_args) -> None:
        self._configure_frozen_columns()
        self._queue_view_sync()

    def _model_layout_changed(self, *_args) -> None:
        self._configure_frozen_columns()
        self._queue_view_sync()

    def _configure_frozen_columns(self) -> None:
        model = self.model()
        if model is None:
            return
        column_count = model.columnCount(self.rootIndex())
        for column in range(column_count):
            self._frozen_view.setColumnHidden(
                column, column != self.IDENTITY_COLUMN)
        self._sync_identity_width()

    def _main_section_resized(self, logical_index: int, _old: int, new: int) -> None:
        if logical_index != self.IDENTITY_COLUMN:
            return
        if self._frozen_view.columnWidth(logical_index) != new:
            self._frozen_view.setColumnWidth(logical_index, new)
        self.update_frozen_geometry()

    def _sync_identity_width(self) -> None:
        model = self.model()
        if model is None or model.columnCount(self.rootIndex()) == 0:
            return
        width = self.columnWidth(self.IDENTITY_COLUMN)
        if self._frozen_view.columnWidth(self.IDENTITY_COLUMN) != width:
            self._frozen_view.setColumnWidth(self.IDENTITY_COLUMN, width)

    def _frozen_section_clicked(self, logical_index: int) -> None:
        """Forward identity-header sorting to the model-owning main view."""
        if logical_index != self.IDENTITY_COLUMN or not self.isSortingEnabled():
            return
        header = self.header()
        if header.sortIndicatorSection() == logical_index:
            current = header.sortIndicatorOrder()
            order = (
                Qt.SortOrder.DescendingOrder
                if current == Qt.SortOrder.AscendingOrder
                else Qt.SortOrder.AscendingOrder
            )
        else:
            order = Qt.SortOrder.AscendingOrder
        self.sortByColumn(logical_index, order)

    def _main_expanded(self, index: QModelIndex) -> None:
        self._mirror_expansion(self._frozen_view, index, True)

    def _main_collapsed(self, index: QModelIndex) -> None:
        self._mirror_expansion(self._frozen_view, index, False)

    def _frozen_expanded(self, index: QModelIndex) -> None:
        self._mirror_expansion(self, index, True)

    def _frozen_collapsed(self, index: QModelIndex) -> None:
        self._mirror_expansion(self, index, False)

    def _mirror_expansion(
            self, target: QTreeView, index: QModelIndex, expanded: bool) -> None:
        if self._syncing_expansion or not index.isValid():
            return
        self._syncing_expansion = True
        try:
            target.setExpanded(index, expanded)
        finally:
            self._syncing_expansion = False
        self._queue_geometry_update()

    def _synchronise_expansion_state(self) -> None:
        model = self.model()
        if model is None:
            return

        def visit(parent: QModelIndex) -> None:
            for row in range(model.rowCount(parent)):
                index = model.index(row, self.IDENTITY_COLUMN, parent)
                expanded = self.isExpanded(index)
                self._mirror_expansion(self._frozen_view, index, expanded)
                if expanded:
                    visit(index)

        visit(self.rootIndex())

    def _reset_frozen_horizontal_scroll(self, _minimum: int, _maximum: int) -> None:
        self._frozen_view.horizontalScrollBar().setValue(0)

    def _reset_frozen_horizontal_value(self, value: int) -> None:
        if value:
            self._frozen_view.horizontalScrollBar().setValue(0)

    def _queue_geometry_update(self) -> None:
        QTimer.singleShot(0, self.update_frozen_geometry)

    def _queue_view_sync(self) -> None:
        QTimer.singleShot(0, self._synchronise_expansion_state)
        self._queue_geometry_update()


class LeagueStandingsDelegate(QStyledItemDelegate):
    """Token-driven ranked ladder presentation over the existing League sorter."""

    def __init__(self, tokens: ConsoleTokens, owner: "LeagueStandingsTableView"):
        super().__init__(owner)
        self._tokens = tokens
        self._owner = owner
        self._meter_enabled = True

    def set_tokens(self, tokens: ConsoleTokens) -> None:
        self._tokens = tokens

    def set_meter_enabled(self, enabled: bool) -> None:
        self._meter_enabled = bool(enabled)

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        hint = super().sizeHint(option, index)
        target = px(34 if self._meter_enabled else 28, self._tokens.scale)
        return QSize(hint.width(), max(hint.height(), target))

    def paint(
            self, painter: QPainter, option: QStyleOptionViewItem,
            index: QModelIndex) -> None:
        display_option = QStyleOptionViewItem(option)
        self.initStyleOption(display_option, index)
        selected = bool(display_option.state & QStyle.StateFlag.State_Selected)
        base = SURFACES["raised"] if index.row() % 2 == 0 else SURFACES["base"]
        if selected:
            base = blend(self._tokens.accents[2], base, 0.20)
        display_option.backgroundBrush = QBrush(QColor(base))
        for role in (
                QPalette.ColorRole.Base,
                QPalette.ColorRole.AlternateBase,
                QPalette.ColorRole.Highlight):
            display_option.palette.setBrush(role, display_option.backgroundBrush)

        if self._meter_enabled and index.column() == LeagueStandingsTableView.DPS_COLUMN:
            fraction = self._dps_fraction(index)
            meter = QColor(blend(
                self._tokens.accents[2], base, 0.12 + (0.20 * fraction)))
            painter.save()
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(meter)
            painter.drawRect(QRect(
                option.rect.left(), option.rect.top(),
                round(option.rect.width() * fraction), option.rect.height()))
            painter.restore()

        if index.column() == LeagueStandingsTableView.NAME_COLUMN:
            display_option.font.setFamily("Overpass")
            display_option.font.setWeight(QFont.Weight.DemiBold)
            display_option.palette.setColor(QPalette.ColorRole.Text, QColor(TEXT["primary"]))
        elif index.column() == LeagueStandingsTableView.HANDLE_COLUMN:
            display_option.font.setFamily("Roboto Mono")
            display_option.palette.setColor(QPalette.ColorRole.Text, QColor(TEXT["muted"]))

        style = (
            display_option.widget.style()
            if display_option.widget is not None else QApplication.style())
        style.drawControl(
            QStyle.ControlElement.CE_ItemViewItem,
            display_option, painter, display_option.widget)

        if index.column() == LeagueStandingsTableView.NAME_COLUMN:
            painter.save()
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(self._tokens.accents[2]))
            painter.drawRect(QRect(
                option.rect.left(), option.rect.top(), px(3, self._tokens.scale),
                option.rect.height()))
            painter.restore()

    def _dps_fraction(self, index: QModelIndex) -> float:
        maximum = 0.0
        model = index.model()
        if model is None:
            return 0.0
        for row in range(model.rowCount()):
            maximum = max(maximum, self._raw_dps(model.index(row, index.column())))
        if maximum <= 0:
            return 0.0
        return min(1.0, self._raw_dps(index) / maximum)

    @staticmethod
    def _raw_dps(index: QModelIndex) -> float:
        model = index.model()
        if model is None:
            return 0.0
        try:
            source_index = model.mapToSource(index)
            source_model = model.sourceModel()
            return float(source_model._data[source_index.row()][index.column()])
        except (AttributeError, IndexError, TypeError, ValueError):
            return 0.0


class LeagueStandingsTableView(QTableView):
    """League grid with rank header and synchronized frozen Name/Handle identity."""

    NAME_COLUMN = 0
    HANDLE_COLUMN = 1
    DPS_COLUMN = 2
    IDENTITY_COLUMNS = (NAME_COLUMN, HANDLE_COLUMN)

    def __init__(self, tokens: ConsoleTokens, parent: QWidget | None = None):
        super().__init__(parent)
        self._tokens = tokens
        self._model_connections: list[tuple[object, object]] = []
        self._syncing_rows = False
        self._delegate = LeagueStandingsDelegate(tokens, self)
        self.setObjectName("leagueStandingsTable")
        self.setProperty("consoleRole", "leagueTable")
        self.setShowGrid(False)
        self.setAlternatingRowColors(False)
        self.setWordWrap(False)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.horizontalHeader().setSectionsClickable(True)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.horizontalHeader().setStretchLastSection(False)
        self.horizontalHeader().setSortIndicatorShown(True)
        self.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.verticalHeader().setDefaultSectionSize(px(34, tokens.scale))
        self.setSortingEnabled(True)
        self.setItemDelegate(self._delegate)

        frozen = QTableView(self)
        frozen.setObjectName("leagueFrozenIdentityTable")
        frozen.setProperty("consoleRole", "leagueTable")
        frozen.setProperty("frozenIdentity", True)
        frozen.setFrameShape(QFrame.Shape.NoFrame)
        frozen.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        frozen.setShowGrid(False)
        frozen.setAlternatingRowColors(False)
        frozen.setWordWrap(False)
        frozen.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        frozen.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        frozen.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        frozen.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        frozen.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        frozen.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        frozen.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        frozen.horizontalHeader().setSectionsClickable(True)
        frozen.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        frozen.horizontalHeader().setStretchLastSection(False)
        frozen.horizontalHeader().setSortIndicatorShown(True)
        frozen.verticalHeader().hide()
        frozen.setItemDelegate(self._delegate)
        self._frozen_view = frozen
        self.viewport().stackUnder(frozen)

        self.horizontalHeader().sectionResized.connect(self._main_section_resized)
        self.horizontalHeader().geometriesChanged.connect(self._queue_geometry_update)
        self.verticalHeader().geometriesChanged.connect(self._queue_geometry_update)
        self.verticalHeader().sectionResized.connect(self._main_row_resized)
        frozen.verticalHeader().sectionResized.connect(self._frozen_row_resized)
        self.horizontalHeader().sortIndicatorChanged.connect(
            frozen.horizontalHeader().setSortIndicator)
        frozen.horizontalHeader().sectionClicked.connect(self._frozen_section_clicked)
        self.verticalScrollBar().valueChanged.connect(frozen.verticalScrollBar().setValue)
        frozen.verticalScrollBar().valueChanged.connect(self.verticalScrollBar().setValue)
        frozen.show()

    @property
    def frozen_view(self) -> QTableView:
        return self._frozen_view

    def setModel(self, model) -> None:
        self._disconnect_model()
        super().setModel(model)
        self._frozen_view.setModel(model)
        if self.selectionModel() is not None:
            self._frozen_view.setSelectionModel(self.selectionModel())
        self._connect_model(model)
        self._configure_frozen_columns()
        self.resizeRowsToContents()
        self._queue_geometry_update()

    def setSelectionModel(self, selection_model) -> None:
        super().setSelectionModel(selection_model)
        frozen = getattr(self, "_frozen_view", None)
        if frozen is not None and selection_model is not None:
            frozen.setSelectionModel(selection_model)

    def set_tokens(self, tokens: ConsoleTokens) -> None:
        self._tokens = tokens
        self._delegate.set_tokens(tokens)
        self.verticalHeader().setDefaultSectionSize(px(34, tokens.scale))
        self.resizeRowsToContents()
        self.viewport().update()
        self._frozen_view.viewport().update()

    def set_meter_mode(self, enabled: bool) -> None:
        self._delegate.set_meter_enabled(enabled)
        self.resizeRowsToContents()
        self.viewport().update()
        self._frozen_view.viewport().update()

    def meter_mode(self) -> bool:
        return self._delegate._meter_enabled

    def resizeColumnsToContents(self) -> None:
        super().resizeColumnsToContents()
        self._sync_identity_widths()
        self._queue_geometry_update()

    def resizeRowsToContents(self) -> None:
        super().resizeRowsToContents()
        model = self.model()
        if model is not None:
            for row in range(model.rowCount()):
                self._sync_row_height(row, self.rowHeight(row), self._frozen_view)
        self._queue_geometry_update()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.update_frozen_geometry()

    def update_frozen_geometry(self) -> None:
        model = self.model()
        if model is None or model.columnCount() == 0:
            self._frozen_view.hide()
            return
        self._sync_identity_widths()
        header_height = self.horizontalHeader().height()
        frozen_header = self._frozen_view.horizontalHeader()
        if frozen_header.height() != header_height:
            frozen_header.setFixedHeight(header_height)
            self._frozen_view.updateGeometries()
        self._frozen_view.setGeometry(
            self.verticalHeader().width() + self.frameWidth(),
            self.frameWidth(),
            self._identity_width(),
            self.viewport().height() + header_height,
        )
        self._frozen_view.show()

    setTokens = set_tokens
    setMeterMode = set_meter_mode
    updateFrozenGeometry = update_frozen_geometry

    def _connect_model(self, model) -> None:
        if model is None:
            return
        for signal in (model.modelReset, model.columnsInserted, model.columnsRemoved):
            signal.connect(self._model_structure_changed)
            self._model_connections.append((signal, self._model_structure_changed))
        model.layoutChanged.connect(self._model_layout_changed)
        self._model_connections.append((model.layoutChanged, self._model_layout_changed))

    def _disconnect_model(self) -> None:
        for signal, slot in self._model_connections:
            try:
                signal.disconnect(slot)
            except (RuntimeError, TypeError):
                pass
        self._model_connections.clear()

    def _model_structure_changed(self, *_args) -> None:
        self._configure_frozen_columns()
        self.resizeRowsToContents()
        self._queue_geometry_update()

    def _model_layout_changed(self, *_args) -> None:
        self._configure_frozen_columns()
        self._queue_geometry_update()

    def _configure_frozen_columns(self) -> None:
        model = self.model()
        if model is None:
            return
        for column in range(model.columnCount()):
            self._frozen_view.setColumnHidden(column, column not in self.IDENTITY_COLUMNS)
        self._sync_identity_widths()

    def _main_section_resized(self, logical: int, _old: int, new: int) -> None:
        if logical not in self.IDENTITY_COLUMNS:
            return
        if self._frozen_view.columnWidth(logical) != new:
            self._frozen_view.setColumnWidth(logical, new)
        self.update_frozen_geometry()

    def _sync_identity_widths(self) -> None:
        model = self.model()
        if model is None:
            return
        for column in self.IDENTITY_COLUMNS:
            if column < model.columnCount() and (
                    self._frozen_view.columnWidth(column) != self.columnWidth(column)):
                self._frozen_view.setColumnWidth(column, self.columnWidth(column))

    def _identity_width(self) -> int:
        return sum(self.columnWidth(column) for column in self.IDENTITY_COLUMNS)

    def _main_row_resized(self, row: int, _old: int, new: int) -> None:
        self._sync_row_height(row, new, self._frozen_view)

    def _frozen_row_resized(self, row: int, _old: int, new: int) -> None:
        self._sync_row_height(row, new, self)

    def _sync_row_height(self, row: int, height: int, target: QTableView) -> None:
        if self._syncing_rows or target.rowHeight(row) == height:
            return
        self._syncing_rows = True
        try:
            target.setRowHeight(row, height)
        finally:
            self._syncing_rows = False

    def _frozen_section_clicked(self, logical: int) -> None:
        current = self.horizontalHeader().sortIndicatorSection()
        order = self.horizontalHeader().sortIndicatorOrder()
        if logical == current:
            order = (
                Qt.SortOrder.DescendingOrder
                if order == Qt.SortOrder.AscendingOrder else Qt.SortOrder.AscendingOrder)
        else:
            order = Qt.SortOrder.AscendingOrder
        self.sortByColumn(logical, order)

    def _queue_geometry_update(self) -> None:
        QTimer.singleShot(0, self.update_frozen_geometry)


__all__ = (
    "BarFractionRole",
    "FormattedMagnitudeRole",
    "IdentityRole",
    "AnalysisTreeView",
    "LeagueStandingsDelegate",
    "LeagueStandingsTableView",
    "OverviewDisplayProxy",
    "OverviewMeterDelegate",
    "OverviewTableView",
    "RankRole",
    "RawValueRole",
)
