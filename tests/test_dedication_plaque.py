import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QFrame, QLabel, QPushButton

from re_oscr.dedicationplaque import DedicationPlaqueDialog


DEFAULT_ACCENTS = ("#FF8A2A", "#D4AD3F", "#9A6BC4", "#4FC3CC", "#D94B55")


class _ThemeFixture:
    scale = 1.0

    def __getitem__(self, key):
        if key == "plot":
            return {"color_cycler": DEFAULT_ACCENTS}
        raise KeyError(key)


class DedicationPlaqueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_plaque_uses_semantic_console_roles_and_credits_sarc(self):
        dialog = DedicationPlaqueDialog(_ThemeFixture())
        self.addCleanup(dialog.deleteLater)

        self.assertEqual(dialog.property("consoleRole"), "dedicationPlaqueDialog")
        self.assertEqual(dialog.windowTitle(), "RE-OSCR — Dedication Plaque")
        self.assertEqual(
            dialog.findChild(QPushButton, "dedicationPlaqueDismiss").property("consoleRole"),
            "actionButton",
        )
        plaque_text = " ".join(label.text() for label in dialog.findChildren(QLabel))
        self.assertIn("SARC", plaque_text)
        self.assertIn("ANOTHERNATHAN / CLA", plaque_text)
        rails = [
            frame for frame in dialog.findChildren(QFrame)
            if frame.property("consoleRole") == "dedicationPlaqueRailSegment"
        ]
        self.assertEqual(len(rails), 5)
        self.assertEqual(
            [frame.property("accentIndex") for frame in rails],
            ["0", "1", "2", "3", "4"],
        )


if __name__ == "__main__":
    unittest.main()
