import unittest

from OSCRUI.theme import AppTheme


class DefaultThemeTests(unittest.TestCase):
    def setUp(self):
        self.theme = AppTheme(1.0)

    def test_default_palette_matches_oscr_11_1(self):
        self.assertEqual(self.theme["app"]["bg"], "#1a1a1a")
        self.assertEqual(self.theme["app"]["fg"], "#eeeeee")
        self.assertEqual(self.theme["app"]["oscr"], "#c82934")
        self.assertEqual(self.theme["defaults"]["mbg"], "#242424")
        self.assertEqual(self.theme["defaults"]["lbg"], "#404040")

    def test_default_plot_palette_remains_readable_and_complete(self):
        self.assertEqual(
            self.theme["plot"]["color_cycler"],
            (
                "#8f54b4", "#B14D54", "#89B177", "#545DB4", "#C8B74E",
                "#B45492", "#A27534", "#54A9B4", "#E47B1C", "#BCBCBC",
            ),
        )

    def test_stylesheet_generation_resolves_shortcuts_and_scale(self):
        scaled_theme = AppTheme(1.5)

        stylesheet = scaled_theme.get_style("frame")
        button_stylesheet = scaled_theme.get_style_class("QPushButton", "button")

        self.assertIn("background-color:#1a1a1a", stylesheet)
        self.assertIn("QPushButton", button_stylesheet)
        self.assertIn("border-color:#c82934", button_stylesheet)
        self.assertIn("margin:4.5px 4.5px 4.5px 4.5px", button_stylesheet)


if __name__ == "__main__":
    unittest.main()
