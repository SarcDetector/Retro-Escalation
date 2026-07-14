import os
from types import SimpleNamespace
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from re_oscr.analysistables import AnalysisTables
from re_oscr.translation import tr


class EmptyAnalysisTable:
    def __init__(self):
        self._model = SimpleNamespace(_player=SimpleNamespace(_children=[]))

    def model(self):
        return self._model

    def selectedIndexes(self):
        return []


class AnalysisModifiedCopyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tables = AnalysisTables.__new__(AnalysisTables)
        self.tables._analysis_modified = False
        self.tables.damage_out_table = EmptyAnalysisTable()
        self.tables.damage_in_table = EmptyAnalysisTable()
        self.tables.heal_out_table = EmptyAnalysisTable()
        self.tables.heal_in_table = EmptyAnalysisTable()

    def test_parser_truth_copy_is_unchanged(self):
        output = self.tables._copy_output("{ OSCR } parser truth")

        self.assertEqual(output, "{ OSCR } parser truth")
        self.assertEqual(QApplication.clipboard().text(), output)

    def test_modified_copy_has_unambiguous_workbench_label(self):
        self.tables.set_analysis_modified(True)

        output = self.tables._copy_output("{ OSCR } filtered result")

        self.assertEqual(
            output,
            "{ RE-OSCR MODIFIED VIEW }\n{ OSCR } filtered result",
        )
        self.assertEqual(QApplication.clipboard().text(), output)

    def test_empty_models_are_safe_for_every_aggregate_copy_mode(self):
        QApplication.clipboard().setText("unchanged")

        for tab in range(4):
            with self.subTest(tab=tab, mode="Global Max"):
                self.assertIsNone(self.tables.copy_analysis_data(
                    tab, tr("Global Max One Hit")))
            with self.subTest(tab=tab, mode="Magnitude"):
                self.assertIsNone(self.tables.copy_analysis_data(
                    tab, tr("Magnitude")))
            with self.subTest(tab=tab, mode="Magnitude / s"):
                self.assertIsNone(self.tables.copy_analysis_data(
                    tab, tr("Magnitude / s")))
            with self.subTest(tab=tab, mode="Max selected"):
                self.assertIsNone(self.tables.copy_analysis_data(
                    tab, tr("Max One Hit")))

        self.assertEqual(QApplication.clipboard().text(), "unchanged")


if __name__ == "__main__":
    unittest.main()
