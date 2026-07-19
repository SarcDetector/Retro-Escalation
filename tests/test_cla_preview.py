"""Qt presentation checks for the dev15 CLA Damage Out technical preview."""

import json
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from re_oscr.clacoprocessor import analyze_damage_out_preview
from re_oscr.clapreview import ClaDamageOutPreviewDialog, HEADERS
from re_oscr.workbench import CombatEventIndex
from tests.test_workbench import make_combat, make_line


class ClaDamageOutPreviewDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_preview_is_dedicated_honest_and_copies_raw_provenance(self):
        index = CombatEventIndex(make_combat([
            make_line(
                1, owner_name="Alice", owner_id="P[1@10 Alice@handle]",
                magnitude=125, magnitude2=100),
        ]))
        result = analyze_damage_out_preview(
            index.snapshot_json,
            index.snapshot_id,
            product_version="11.1.0.dev15",
        )
        dialog = ClaDamageOutPreviewDialog(result)
        self.addCleanup(dialog.close)

        self.assertEqual(dialog.objectName(), "claDamageOutPreviewDialog")
        self.assertEqual(dialog.model.columnCount(), len(HEADERS))
        self.assertEqual(dialog.model.rowCount(), 1)
        self.assertEqual(
            dialog.model.index(0, 0).data(Qt.ItemDataRole.DisplayRole),
            "Alice@handle",
        )
        warning = dialog.findChild(QLabel, "claDamageOutPreviewWarning")
        self.assertIn("GOLDEN VERIFICATION PENDING", warning.text())
        self.assertIn("aggregation traversal", warning.text())
        self.assertNotIn("MATHCO", warning.text().upper())

        copy_table = dialog.findChild(QPushButton, "claDamageOutPreviewCopyTable")
        self.assertEqual(copy_table.text(), "COPY ROUNDED TABLE")
        dialog.copy_table()
        rounded = QApplication.clipboard().text()
        self.assertIn("ROUNDED DISPLAY VALUES, NOT AN ORACLE", rounded)
        self.assertIn(result.provenance.snapshot_id, rounded)

        dialog.copy_raw_report()
        copied = json.loads(QApplication.clipboard().text())
        self.assertEqual(copied["rows"][0]["player"], "Alice@handle")
        self.assertFalse(copied["provenance"]["league_eligible"])


if __name__ == "__main__":
    unittest.main()
