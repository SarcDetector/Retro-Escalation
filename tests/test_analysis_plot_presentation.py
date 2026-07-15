import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pyqtgraph import BarGraphItem
from PySide6.QtWidgets import QApplication

from re_oscr.themes.command_console import create_command_console_theme
from re_oscr.widgets import AnalysisPlot


class _SeriesItem:
    def __init__(self, name: str, values: tuple[float, ...]):
        self._name = name
        self.graph_data = values

    def get_data(self, _column: int):
        return self._name


class AnalysisPlotPresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.theme = create_command_console_theme(1.0)
        cls.colours = cls.theme["plot"]["color_cycler"]

    def make_plot(self, presentation: str):
        plot = AnalysisPlot(self.theme, self.colours, presentation=presentation)
        self.addCleanup(plot.close)
        return plot

    def test_command_plot_defaults_to_live_weighted_lines(self):
        plot = self.make_plot("instrument")
        first = _SeriesItem("First", (0.0, 10.0, 3.0, 8.0))
        second = _SeriesItem("Second", (1.0, 3.0, 12.0, 4.0))

        self.assertEqual(plot.display_mode, "line")
        self.assertFalse(plot.frozen)
        plot.add_bar(first)
        plot.add_bar(second)

        self.assertEqual(len(plot._bar_queue), 2)
        self.assertGreater(
            plot._bar_queue[-1].opts["pen"].widthF(),
            plot._bar_queue[0].opts["pen"].widthF(),
        )
        self.assertEqual(plot._bar_queue[0].opts["pen"].color().alpha(), 155)
        self.assertEqual(plot._bar_queue[-1].opts["pen"].color().alpha(), 255)

    def test_plot_preserves_detailed_bars_as_an_explicit_mode(self):
        plot = self.make_plot("instrument")
        plot.add_bar(_SeriesItem("Selected", (1.0, 2.0, 3.0)))
        plot.set_display_mode("bar")

        self.assertEqual(plot.display_mode, "bar")
        self.assertIsInstance(plot._bar_queue[0], BarGraphItem)

        plot.set_display_mode("line")
        self.assertEqual(plot.display_mode, "line")
        self.assertNotIsInstance(plot._bar_queue[0], BarGraphItem)

    def test_legacy_manual_capture_stays_unchanged(self):
        plot = self.make_plot("legacy")
        item = _SeriesItem("Legacy", (1.0, 2.0, 3.0))

        self.assertEqual(plot.display_mode, "bar")
        self.assertTrue(plot.frozen)
        self.assertIsNone(plot.add_bar(item))
        self.assertEqual(plot._bar_queue, [])

        plot.toggle_freeze(False)
        plot.add_bar(item)
        self.assertIsInstance(plot._bar_queue[0], BarGraphItem)


if __name__ == "__main__":
    unittest.main()
