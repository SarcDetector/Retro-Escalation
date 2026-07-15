import unittest
from types import SimpleNamespace

from re_oscr.analysistables import ANALYSIS_DISPLAY_LENSES, AnalysisTables


class _Tree:
    def __init__(self):
        self.hidden = set()

    def showColumn(self, column):
        self.hidden.discard(column)

    def hideColumn(self, column):
        self.hidden.add(column)


class AnalysisDisplayLensTests(unittest.TestCase):
    def setUp(self):
        settings = SimpleNamespace(
            dmg_columns=[True] * 21,
            heal_columns=[True] * 13,
        )
        self.tables = AnalysisTables(None, settings)
        self.tables.damage_out_table = _Tree()
        self.tables.damage_in_table = _Tree()
        self.tables.heal_out_table = _Tree()
        self.tables.heal_in_table = _Tree()

    def test_lenses_are_display_only_intersections_with_settings(self):
        self.tables.set_analysis_display_lens('CORE')

        self.assertEqual(self.tables.analysis_display_lens, 'CORE')
        self.assertEqual(
            self.tables.damage_out_table.hidden,
            set(range(1, 22)) - {1, 2, 3, 4, 5, 6, 8, 19},
        )
        self.assertEqual(
            self.tables.heal_out_table.hidden,
            set(range(1, 14)) - {1, 2, 3, 5, 7, 8, 11},
        )

        self.tables._settings.dmg_columns[1] = False
        self.tables.set_analysis_display_lens('ALL')

        self.assertEqual(self.tables.damage_out_table.hidden, {2})
        self.assertEqual(self.tables.damage_in_table.hidden, {2})
        self.assertEqual(self.tables.heal_out_table.hidden, set())

    def test_lens_names_are_strict(self):
        self.assertEqual(ANALYSIS_DISPLAY_LENSES, ('CORE', 'EVENTS', 'DETAIL', 'ALL'))
        with self.assertRaises(ValueError):
            self.tables.set_analysis_display_lens('overview')
