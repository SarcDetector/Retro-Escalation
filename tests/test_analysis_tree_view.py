import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QItemSelection, QItemSelectionModel, QModelIndex, QSize, Qt
from PySide6.QtGui import QColor, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QApplication

from re_oscr.console.tables import AnalysisTreeView
from re_oscr.console.tokens import ConsoleTokens
from re_oscr.datamodels import TreeSelectionModel


_APP = None


def setUpModule():
    global _APP
    _APP = QApplication.instance() or QApplication([])


def process_events():
    QApplication.instance().processEvents()
    QApplication.instance().processEvents()


def row_items(label: str, columns: int = 5, height: int | None = None):
    items = [QStandardItem(label)]
    items.extend(QStandardItem(f"{label} metric {column}") for column in range(1, columns))
    if height is not None:
        for item in items:
            item.setSizeHint(QSize(180, height))
    return items


def make_tree_model(rows: int = 3, columns: int = 5) -> QStandardItemModel:
    model = QStandardItemModel()
    model.setHorizontalHeaderLabels(["Identity", "DPS", "Damage", "Hits", "Time"][:columns])
    for row in range(rows):
        top = row_items(f"Operator {row:02}", columns)
        top[0].appendRow(row_items(f"Ability {row:02}.1", columns))
        top[0].appendRow(row_items(f"Ability {row:02}.2", columns))
        model.appendRow(top)
    return model


class AnalysisTreeViewTests(unittest.TestCase):
    def make_view(self, rows: int = 3):
        model = make_tree_model(rows)
        view = AnalysisTreeView()
        view.setObjectName("analysisTestTree")
        view.setProperty("consoleRole", "analysisTree")
        view.setSelectionMode(AnalysisTreeView.SelectionMode.ExtendedSelection)
        view.setSelectionBehavior(AnalysisTreeView.SelectionBehavior.SelectItems)
        view.setHorizontalScrollMode(AnalysisTreeView.ScrollMode.ScrollPerPixel)
        view.setVerticalScrollMode(AnalysisTreeView.ScrollMode.ScrollPerPixel)
        view.setModel(model)
        selection = TreeSelectionModel(model)
        view.setSelectionModel(selection)
        self.addCleanup(view.close)
        return model, selection, view

    def test_companion_shares_exact_model_and_tree_selection_model(self):
        model, selection, view = self.make_view()
        frozen = view.frozen_view

        self.assertIs(view.model(), model)
        self.assertIs(frozen.model(), model)
        self.assertIs(view.selectionModel(), selection)
        self.assertIs(frozen.selectionModel(), selection)
        self.assertIsInstance(selection, TreeSelectionModel)
        self.assertFalse(frozen.isColumnHidden(AnalysisTreeView.IDENTITY_COLUMN))
        for column in range(1, model.columnCount(QModelIndex())):
            self.assertTrue(frozen.isColumnHidden(column))

        first = model.index(0, 0, QModelIndex())
        selection.select(
            QItemSelection(first, first),
            QItemSelectionModel.SelectionFlag.ClearAndSelect,
        )
        process_events()
        self.assertEqual(
            frozen.selectionModel().selectedRows(), selection.selectedRows())

    def test_expansion_and_collapse_are_synchronised_both_directions(self):
        model, _selection, view = self.make_view()
        frozen = view.frozen_view
        parent = model.index(0, 0, QModelIndex())
        child = model.index(0, 0, parent)

        view.expand(parent)
        view.expand(child)
        process_events()
        self.assertTrue(frozen.isExpanded(parent))
        self.assertTrue(frozen.isExpanded(child))

        frozen.collapse(child)
        frozen.collapse(parent)
        process_events()
        self.assertFalse(view.isExpanded(child))
        self.assertFalse(view.isExpanded(parent))

        frozen.expand(parent)
        process_events()
        self.assertTrue(view.isExpanded(parent))

    def test_delegate_derives_hierarchy_tint_and_expanded_parent_spine(self):
        model, _selection, view = self.make_view()
        parent = model.index(0, 0, QModelIndex())
        child = model.index(0, 0, parent)
        delegate = view.itemDelegate()

        self.assertIs(delegate, view.frozen_view.itemDelegate())
        self.assertEqual(delegate._depth(parent), 0)
        self.assertEqual(delegate._depth(child), 1)
        self.assertFalse(delegate._is_expanded_parent(parent))
        self.assertNotEqual(
            delegate._row_background(parent, False),
            delegate._row_background(child, False),
        )

        view.expand(parent)
        process_events()
        self.assertTrue(delegate._is_expanded_parent(parent))
        self.assertEqual(view.analysis_spine_width, 3)
        self.assertNotEqual(
            delegate._row_background(parent, False),
            delegate._row_background(child, False),
        )

    def test_analysis_accent_updates_the_shared_delegate_palette(self):
        _model, _selection, view = self.make_view()
        colour = QColor("#A65FD4")

        view.analysisAccentColor = colour
        process_events()

        self.assertEqual(view.analysis_accent_color, colour)
        self.assertIs(view.itemDelegate(), view.frozen_view.itemDelegate())

    def test_console_stylesheet_supplies_live_analysis_accent_and_scale(self):
        _model, _selection, view = self.make_view()
        app = QApplication.instance()
        previous_stylesheet = app.styleSheet()
        self.addCleanup(app.setStyleSheet, previous_stylesheet)
        tokens = ConsoleTokens(
            scale=2.0,
            accents=("#35A67A", "#A65FD4", "#40B8C5", "#D6A946", "#D55757"),
        )

        app.setStyleSheet(tokens.stylesheet())
        view.show()
        process_events()

        self.assertEqual(view.analysis_accent_color, QColor(tokens.accents[1]))
        self.assertEqual(view.analysis_spine_width, 6)

    def test_frozen_source_header_does_not_mutate_model_header_data(self):
        model, _selection, view = self.make_view()
        model.setHeaderData(
            AnalysisTreeView.IDENTITY_COLUMN,
            Qt.Orientation.Horizontal,
            "",
            Qt.ItemDataRole.DisplayRole,
        )
        process_events()

        self.assertEqual(
            model.headerData(
                AnalysisTreeView.IDENTITY_COLUMN,
                Qt.Orientation.Horizontal,
                Qt.ItemDataRole.DisplayRole,
            ),
            "",
        )
        self.assertEqual(view.frozen_view.header().identity_label, "SOURCE")

    def test_vertical_scroll_and_model_driven_row_heights_match(self):
        model, _selection, view = self.make_view(rows=60)
        frozen = view.frozen_view
        tall_top = model.item(0, 0)
        for column in range(model.columnCount()):
            model.item(0, column).setSizeHint(QSize(180, 47))
        for column in range(model.columnCount()):
            tall_top.child(0, column).setSizeHint(QSize(180, 53))

        parent = model.index(0, 0, QModelIndex())
        child = model.index(0, 0, parent)
        view.expand(parent)
        view.resize(420, 190)
        view.show()
        process_events()

        self.assertEqual(view.visualRect(parent).height(), 47)
        self.assertEqual(frozen.visualRect(parent).height(), 47)
        self.assertEqual(view.visualRect(child).height(), 53)
        self.assertEqual(frozen.visualRect(child).height(), 53)
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

    def test_identity_width_and_sort_indicator_follow_main_header(self):
        model, _selection, view = self.make_view()
        frozen = view.frozen_view

        view.setColumnWidth(AnalysisTreeView.IDENTITY_COLUMN, 211)
        self.assertEqual(frozen.columnWidth(AnalysisTreeView.IDENTITY_COLUMN), 211)
        view.resizeColumnToContents(AnalysisTreeView.IDENTITY_COLUMN)
        self.assertEqual(
            frozen.columnWidth(AnalysisTreeView.IDENTITY_COLUMN),
            view.columnWidth(AnalysisTreeView.IDENTITY_COLUMN),
        )

        view.setSortingEnabled(True)
        view.sortByColumn(2, Qt.SortOrder.DescendingOrder)
        process_events()
        self.assertEqual(frozen.header().sortIndicatorSection(), 2)
        self.assertEqual(
            frozen.header().sortIndicatorOrder(), Qt.SortOrder.DescendingOrder)
        self.assertIs(frozen.model(), model)

        view.resize(420, 220)
        view.show()
        process_events()
        view.header().setFixedHeight(41)
        process_events()
        self.assertEqual(frozen.header().height(), 41)

    def test_frozen_identity_header_forwards_sort_and_toggles_order(self):
        model, _selection, view = self.make_view()
        frozen = view.frozen_view
        view.setSortingEnabled(True)
        view.sortByColumn(2, Qt.SortOrder.DescendingOrder)

        frozen.header().sectionClicked.emit(AnalysisTreeView.IDENTITY_COLUMN)
        process_events()
        self.assertEqual(
            view.header().sortIndicatorSection(), AnalysisTreeView.IDENTITY_COLUMN)
        self.assertEqual(
            view.header().sortIndicatorOrder(), Qt.SortOrder.AscendingOrder)

        frozen.header().sectionClicked.emit(AnalysisTreeView.IDENTITY_COLUMN)
        process_events()
        self.assertEqual(
            view.header().sortIndicatorOrder(), Qt.SortOrder.DescendingOrder)
        self.assertIs(frozen.model(), model)

    def test_model_reset_keeps_shared_view_state_and_frozen_column_contract(self):
        model, selection, view = self.make_view()
        frozen = view.frozen_view
        view.expand(model.index(0, 0, QModelIndex()))

        model.clear()
        model.setHorizontalHeaderLabels(["Identity", "DPS", "Damage", "Hits", "Time"])
        replacement = row_items("Replacement", 5)
        replacement[0].appendRow(row_items("Replacement ability", 5))
        model.appendRow(replacement)
        process_events()

        self.assertIs(view.model(), model)
        self.assertIs(frozen.model(), model)
        self.assertIs(view.selectionModel(), selection)
        self.assertIs(frozen.selectionModel(), selection)
        self.assertEqual(
            model.index(0, 0, QModelIndex()).data(Qt.ItemDataRole.DisplayRole),
            "Replacement",
        )
        self.assertFalse(frozen.isColumnHidden(AnalysisTreeView.IDENTITY_COLUMN))
        for column in range(1, model.columnCount(QModelIndex())):
            self.assertTrue(frozen.isColumnHidden(column))
        self.assertEqual(
            frozen.columnWidth(AnalysisTreeView.IDENTITY_COLUMN),
            view.columnWidth(AnalysisTreeView.IDENTITY_COLUMN),
        )

    def test_frozen_identity_ignores_horizontal_scrolling(self):
        model, _selection, view = self.make_view()
        frozen = view.frozen_view
        view.resize(320, 180)
        for column in range(model.columnCount(QModelIndex())):
            view.setColumnWidth(column, 180)
        view.show()
        process_events()

        self.assertGreater(view.horizontalScrollBar().maximum(), 0)
        view.horizontalScrollBar().setValue(view.horizontalScrollBar().maximum())
        # Even an explicit attempt to move the companion is corrected.
        frozen.horizontalScrollBar().setValue(frozen.horizontalScrollBar().maximum())
        process_events()
        self.assertGreater(view.horizontalScrollBar().value(), 0)
        self.assertEqual(frozen.horizontalScrollBar().value(), 0)
        self.assertEqual(
            frozen.horizontalScrollBarPolicy(), Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.assertEqual(frozen.x(), view.frameWidth())
        self.assertEqual(
            frozen.width(), view.columnWidth(AnalysisTreeView.IDENTITY_COLUMN))


if __name__ == "__main__":
    unittest.main()
