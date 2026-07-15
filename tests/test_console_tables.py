import os
import unittest
from copy import deepcopy

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QMimeData, QModelIndex, QPoint, QRect, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QStyleOptionViewItem

from re_oscr.console.tables import (
    BarFractionRole,
    FormattedMagnitudeRole,
    IdentityRole,
    OverviewDisplayProxy,
    OverviewTableView,
    RankRole,
    RawValueRole,
)
from re_oscr.console.tokens import SURFACES, ConsoleTokens
from re_oscr.datamodels import OverviewTableModel, SortingProxy


DEFAULT_ACCENTS = ("#FF8A2A", "#D4AD3F", "#9A6BC4", "#4FC3CC", "#D94B55")
HEADERS = ("DPS", "Combat Time", "DPS Share", "Total Damage")
ROWS = (
    [1_000_000.0, 12.5, 0.25, 2_500_000.0],
    [500.0, 8.0, 0.10, 4_000.0],
    [2_000_000.0, 20.0, 0.65, 5_000_000.0],
)
IDENTITIES = ("Beta@handle", "Gamma@handle", "Alpha@handle")


_APP = None


def setUpModule():
    global _APP
    _APP = QApplication.instance() or QApplication([])


def process_events():
    QApplication.instance().processEvents()
    QApplication.instance().processEvents()


def make_model_chain(rows=ROWS, identities=IDENTITIES):
    source = OverviewTableModel()
    source.init_fonts(QFont(), QFont())
    source.set_data([list(row) for row in rows], list(HEADERS), list(identities))
    sorter = SortingProxy()
    sorter.setSourceModel(source)
    display = OverviewDisplayProxy()
    display.setSourceModel(sorter)
    return source, sorter, display


class OverviewDisplayProxyTests(unittest.TestCase):
    def test_shape_headers_and_bidirectional_mapping(self):
        source, sorter, display = make_model_chain()

        self.assertIs(display.sourceModel(), sorter)
        self.assertIs(sorter.sourceModel(), source)
        self.assertEqual(display.rowCount(), 3)
        self.assertEqual(display.columnCount(), source.columnCount(QModelIndex()) + 1)
        self.assertEqual(
            display.headerData(0, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole),
            "Operator",
        )
        self.assertEqual(
            display.headerData(1, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole),
            HEADERS[0],
        )

        identity = display.index(0, OverviewDisplayProxy.IDENTITY_COLUMN)
        metric = display.index(0, OverviewDisplayProxy.view_column_for_source(2))
        self.assertFalse(display.mapToSource(identity).isValid())
        self.assertEqual(display.mapToSource(metric), sorter.index(0, 2))
        self.assertEqual(display.mapFromSource(sorter.index(0, 2)), metric)
        self.assertEqual(OverviewDisplayProxy.source_column_for_view(0), None)
        self.assertEqual(OverviewDisplayProxy.source_column_for_view(3), 2)
        self.assertEqual(OverviewDisplayProxy.view_column_for_source(2), 3)
        with self.assertRaises(ValueError):
            OverviewDisplayProxy.view_column_for_source(-1)
        with self.assertRaises(ValueError):
            OverviewDisplayProxy.source_column_for_view(-1)

    def test_identity_rank_raw_formatted_and_bar_roles(self):
        _source, _sorter, display = make_model_chain()
        identity = display.index(0, 0)
        magnitude = display.index(0, 1)
        duration = display.index(0, 2)

        self.assertEqual(identity.data(Qt.ItemDataRole.DisplayRole), IDENTITIES[0])
        self.assertEqual(identity.data(Qt.ItemDataRole.ToolTipRole), IDENTITIES[0])
        self.assertEqual(identity.data(IdentityRole), IDENTITIES[0])
        self.assertEqual(identity.data(RankRole), 1)
        self.assertIsNone(identity.data(RawValueRole))
        self.assertEqual(identity.data(FormattedMagnitudeRole), IDENTITIES[0])

        self.assertEqual(magnitude.data(Qt.ItemDataRole.DisplayRole), "1,000,000.00")
        self.assertEqual(magnitude.data(RawValueRole), 1_000_000.0)
        self.assertEqual(magnitude.data(FormattedMagnitudeRole), "1.00M")
        self.assertEqual(duration.data(RawValueRole), 12.5)
        self.assertEqual(duration.data(FormattedMagnitudeRole), "12.5s")
        self.assertEqual(magnitude.data(IdentityRole), IDENTITIES[0])
        self.assertEqual(magnitude.data(RankRole), 1)

        self.assertAlmostEqual(display.index(0, 0).data(BarFractionRole), 0.5)
        self.assertAlmostEqual(display.index(1, 0).data(BarFractionRole), 0.00025)
        self.assertAlmostEqual(display.index(2, 0).data(BarFractionRole), 1.0)
        role_names = display.roleNames()
        self.assertEqual(role_names[RankRole], b"rank")
        self.assertEqual(role_names[IdentityRole], b"identity")
        self.assertEqual(role_names[BarFractionRole], b"barFraction")
        self.assertEqual(role_names[FormattedMagnitudeRole], b"formattedMagnitude")
        self.assertEqual(role_names[RawValueRole], b"rawValue")
        item_roles = display.itemData(magnitude)
        self.assertEqual(item_roles[RawValueRole], 1_000_000.0)
        self.assertEqual(item_roles[FormattedMagnitudeRole], "1.00M")
        self.assertEqual(item_roles[IdentityRole], IDENTITIES[0])

    def test_all_writable_model_routes_are_rejected(self):
        source, _sorter, display = make_model_chain()
        original_rows = deepcopy(source._data)
        original_row_object = source._data
        index = display.index(0, 1)
        root = QModelIndex()

        rejected = (
            display.setData(index, 9_999),
            display.setItemData(index, {Qt.ItemDataRole.DisplayRole.value: 9_999}),
            display.clearItemData(index),
            display.setHeaderData(0, Qt.Orientation.Horizontal, "Changed"),
            display.insertRows(0, 1, root),
            display.insertColumns(0, 1, root),
            display.removeRows(0, 1, root),
            display.removeColumns(0, 1, root),
            display.moveRows(root, 0, 0, root, 1),
            display.moveColumns(root, 0, 0, root, 1),
            display.dropMimeData(
                QMimeData(), Qt.DropAction.CopyAction, 0, 0, root
            ),
        )

        self.assertEqual(rejected, (False,) * len(rejected))
        self.assertEqual(display.supportedDropActions(), Qt.DropAction.IgnoreAction)
        self.assertEqual(display.supportedDragActions(), Qt.DropAction.IgnoreAction)
        self.assertIs(source._data, original_row_object)
        self.assertEqual(source._data, original_rows)
        for model_index in (display.index(0, 0), index):
            flags = display.flags(model_index)
            self.assertFalse(flags & Qt.ItemFlag.ItemIsEditable)
            self.assertFalse(flags & Qt.ItemFlag.ItemIsDragEnabled)
            self.assertFalse(flags & Qt.ItemFlag.ItemIsDropEnabled)

    def test_sorting_maps_to_the_legacy_sorter_without_mutating_source_rows(self):
        source, sorter, display = make_model_chain()
        original_rows = deepcopy(source._data)

        display.sort_source_column(0, Qt.SortOrder.AscendingOrder)
        self.assertEqual(sorter.sortColumn(), 0)
        self.assertEqual(
            [display.index(row, 0).data(IdentityRole) for row in range(3)],
            ["Alpha@handle", "Beta@handle", "Gamma@handle"],
        )
        self.assertEqual(display.index(0, 1).data(RawValueRole), 2_000_000.0)

        display.sort(
            OverviewDisplayProxy.view_column_for_source(0),
            Qt.SortOrder.DescendingOrder,
        )
        self.assertEqual(
            [display.index(row, 0).data(IdentityRole) for row in range(3)],
            ["Gamma@handle", "Beta@handle", "Alpha@handle"],
        )
        active_sort = (sorter.sortColumn(), sorter.sortOrder())
        display.sort(OverviewDisplayProxy.IDENTITY_COLUMN, Qt.SortOrder.AscendingOrder)
        self.assertEqual((sorter.sortColumn(), sorter.sortOrder()), active_sort)
        with self.assertRaises(IndexError):
            display.sort_source_column(source.columnCount(QModelIndex()))
        self.assertEqual(source._data, original_rows)

    def test_source_model_reset_replaces_shape_and_derived_data(self):
        source, sorter, display = make_model_chain()
        resets = []
        display.modelReset.connect(lambda: resets.append(True))

        replacement = [[3_500_000.0, 33.0, 1.0, 9_000_000.0]]
        source.set_data(replacement, list(HEADERS), ["Reset@handle"])
        process_events()

        self.assertTrue(resets)
        self.assertIs(display.sourceModel(), sorter)
        self.assertEqual(display.rowCount(), 1)
        self.assertEqual(display.columnCount(), len(replacement[0]) + 1)
        self.assertEqual(display.index(0, 0).data(IdentityRole), "Reset@handle")
        self.assertEqual(display.index(0, 1).data(RawValueRole), 3_500_000.0)
        self.assertEqual(display.index(0, 1).data(FormattedMagnitudeRole), "3.50M")
        self.assertEqual(display.index(0, 0).data(BarFractionRole), 1.0)

        source.clear()
        process_events()
        self.assertEqual(display.rowCount(), 0)
        self.assertEqual(display.columnCount(), 1)


class OverviewTableViewTests(unittest.TestCase):
    def setUp(self):
        self.tokens = ConsoleTokens(1.0, DEFAULT_ACCENTS)

    def make_view(self, rows=ROWS, identities=IDENTITIES):
        source, sorter, display = make_model_chain(rows, identities)
        view = OverviewTableView(self.tokens)
        view.setModel(display)
        self.addCleanup(view.close)
        return source, sorter, display, view

    def test_frozen_view_shares_model_selection_and_only_shows_identity(self):
        _source, _sorter, display, view = self.make_view()
        frozen = view.frozen_view

        self.assertIs(view.model(), display)
        self.assertIs(frozen.model(), display)
        self.assertIs(frozen.selectionModel(), view.selectionModel())
        self.assertFalse(frozen.isColumnHidden(OverviewDisplayProxy.IDENTITY_COLUMN))
        for column in range(1, display.columnCount()):
            self.assertTrue(frozen.isColumnHidden(column))

        view.selectRow(1)
        process_events()
        self.assertTrue(
            frozen.selectionModel().isRowSelected(1, QModelIndex())
        )

    def test_visible_source_columns_use_stable_source_indexes_and_survive_reset(self):
        source, _sorter, display, view = self.make_view(rows=(), identities=())

        view.set_visible_source_columns({0, 2})
        source.set_data([list(ROWS[0])], list(HEADERS), [IDENTITIES[0]])
        process_events()

        self.assertFalse(view.isColumnHidden(display.IDENTITY_COLUMN))
        self.assertFalse(view.isColumnHidden(display.view_column_for_source(0)))
        self.assertTrue(view.isColumnHidden(display.view_column_for_source(1)))
        self.assertFalse(view.isColumnHidden(display.view_column_for_source(2)))
        self.assertTrue(view.isColumnHidden(display.view_column_for_source(3)))
        self.assertEqual(view.visible_source_columns(), frozenset({0, 2}))
        with self.assertRaises(ValueError):
            view.set_visible_source_columns({-1})
        with self.assertRaises(IndexError):
            view.set_visible_source_columns({source.columnCount(QModelIndex())})

    def test_vertical_scroll_row_height_identity_width_and_sort_indicator_sync(self):
        rows = [
            [float(100_000 - index), 10.0 + index, 0.1, float(200_000 - index)]
            for index in range(30)
        ]
        identities = [f"Operator {index:02}" for index in range(30)]
        _source, _sorter, display, view = self.make_view(rows, identities)
        frozen = view.frozen_view
        view.resize(420, 180)
        view.show()
        process_events()

        # Native styles may give the sortable main header a taller size hint
        # than the frozen identity header.  Their viewport and row origins
        # must still remain identical.
        frozen.horizontalHeader().setFixedHeight(
            max(1, view.horizontalHeader().height() - 5))
        view.update_frozen_geometry()
        process_events()
        self.assertEqual(
            frozen.horizontalHeader().height(), view.horizontalHeader().height())
        self.assertEqual(
            frozen.viewport().mapToGlobal(QPoint(0, 0)).y(),
            view.viewport().mapToGlobal(QPoint(0, 0)).y(),
            (
                view.frameWidth(), frozen.frameWidth(),
                view.horizontalHeader().geometry().getRect(),
                frozen.horizontalHeader().geometry().getRect(),
                view.viewport().geometry().getRect(),
                frozen.viewport().geometry().getRect(),
            ),
        )
        self.assertEqual(
            frozen.visualRect(display.index(0, display.IDENTITY_COLUMN)).top(),
            view.visualRect(display.index(0, display.SOURCE_COLUMN_OFFSET)).top(),
        )
        self.assertEqual(
            frozen.visualRect(display.index(0, display.IDENTITY_COLUMN)).height(),
            view.visualRect(display.index(0, display.SOURCE_COLUMN_OFFSET)).height(),
        )

        self.assertGreater(view.verticalScrollBar().maximum(), 0)
        scroll_value = min(
            view.verticalScrollBar().maximum(),
            frozen.verticalScrollBar().maximum(),
        ) // 2
        self.assertGreater(scroll_value, 0)
        view.verticalScrollBar().setValue(scroll_value)
        self.assertEqual(frozen.verticalScrollBar().value(), scroll_value)
        frozen.verticalScrollBar().setValue(scroll_value - 1)
        self.assertEqual(view.verticalScrollBar().value(), scroll_value - 1)

        view.setRowHeight(0, 47)
        self.assertEqual(frozen.rowHeight(0), 47)
        frozen.setRowHeight(1, 53)
        self.assertEqual(view.rowHeight(1), 53)
        view.setColumnWidth(display.IDENTITY_COLUMN, 211)
        self.assertEqual(frozen.columnWidth(display.IDENTITY_COLUMN), 211)
        view.resizeColumnsToContents()
        self.assertEqual(
            frozen.columnWidth(display.IDENTITY_COLUMN),
            view.columnWidth(display.IDENTITY_COLUMN),
        )

        view.sort_by_source_column(2, Qt.SortOrder.DescendingOrder)
        process_events()
        self.assertEqual(
            frozen.horizontalHeader().sortIndicatorSection(),
            display.view_column_for_source(2),
        )
        self.assertEqual(
            frozen.horizontalHeader().sortIndicatorOrder(),
            Qt.SortOrder.DescendingOrder,
        )

    def test_frozen_and_main_delegate_share_one_meter_canvas_width(self):
        _source, _sorter, _display, view = self.make_view()
        view.resize(560, 220)
        view.show()
        process_events()

        option = QStyleOptionViewItem()
        option.widget = view.frozen_view.viewport()
        option.rect = QRect(0, 0, view.frozen_view.viewport().width(), 39)
        row_rect = view.itemDelegate()._row_rect(option, 5)

        self.assertEqual(row_rect.left(), 0)
        self.assertEqual(row_rect.width(), view.viewport().width())

    def test_numeric_grid_rows_keep_distinct_operator_accents(self):
        _source, _sorter, _display, view = self.make_view()
        delegate = view.itemDelegate()

        row_colours = [
            delegate._grid_row_background(0, index, False)
            for index in range(len(self.tokens.accents))
        ]

        self.assertEqual(len(set(row_colours)), len(self.tokens.accents))
        self.assertNotIn(SURFACES["base"], row_colours)
        self.assertNotEqual(
            delegate._grid_row_background(0, 0, False),
            delegate._grid_row_background(0, 0, True),
        )

    def test_frozen_identity_ignores_horizontal_scrolling(self):
        _source, _sorter, display, view = self.make_view()
        frozen = view.frozen_view
        view.resize(320, 180)
        for column in range(display.columnCount()):
            view.setColumnWidth(column, 180)
        view.show()
        process_events()

        self.assertGreater(view.horizontalScrollBar().maximum(), 0)
        view.horizontalScrollBar().setValue(view.horizontalScrollBar().maximum())
        process_events()
        self.assertGreater(view.horizontalScrollBar().value(), 0)
        self.assertEqual(frozen.horizontalScrollBar().value(), 0)
        self.assertEqual(
            frozen.horizontalScrollBarPolicy(),
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
        )
        self.assertEqual(frozen.x(), view.frameWidth())
        self.assertEqual(
            frozen.width(), view.columnWidth(OverviewDisplayProxy.IDENTITY_COLUMN)
        )


if __name__ == "__main__":
    unittest.main()
