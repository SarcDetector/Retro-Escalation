"""Product identity checks for the frontend/parser boundary."""

from pathlib import Path
import hashlib
import struct
import tempfile
import tomllib
import unittest
from unittest.mock import patch

from main import Launcher
from re_oscr.app import REOSCRApplication
from retro_escalation import RetroEscalationLauncher


class ProductIdentityTests(unittest.TestCase):
    @staticmethod
    def _sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    @staticmethod
    def _png_size(path: Path) -> tuple[int, int]:
        payload = path.read_bytes()
        if payload[:8] != b"\x89PNG\r\n\x1a\n":
            raise AssertionError(f"Not a PNG file: {path}")
        return struct.unpack(">II", payload[16:24])

    def test_re_oscr_is_the_frontend_and_oscr_remains_the_parser(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        with (project_root / "pyproject.toml").open("rb") as project_file:
            pyproject = tomllib.load(project_file)

        project = pyproject["project"]
        self.assertEqual(project["name"], "RE-OSCR")
        self.assertIn("STO-OSCR==11.0.0", project["dependencies"])
        self.assertEqual(
            project["scripts"],
            {"re-oscr": "retro_escalation:RetroEscalationLauncher.launch"},
        )
        self.assertEqual(RetroEscalationLauncher.__version__, "11.1.0.dev15")
        self.assertEqual(Launcher.__version__, RetroEscalationLauncher.__version__)
        self.assertNotIn("+", RetroEscalationLauncher.__version__)

    def test_cla_credit_uses_an_original_logo_safe_badge(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        badge_path = project_root / "assets" / "cla_credit.svg"

        self.assertTrue(badge_path.is_file())
        badge = badge_path.read_text(encoding="utf-8")
        self.assertIn(">CLA</text>", badge)
        self.assertNotIn("STO_CombatLogAnalyzer-master", badge)

    def test_re_branding_assets_replace_affiliation_artwork(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        asset_dir = project_root / "assets"
        expected_hashes = {
            "oscr_icon_small.ico":
                "4e5cd2d2c4a2b10cd419711b32d84c81cf55feeac922dc4e5d25cce484197562",
            "oscr_icon_small.png":
                "e9cb40853c662c9f319199f2386b45e7e7e72bde1104a1ddf21e3de76760c914",
            "oscrbanner-slim-dark-label.png":
                "e3c00c01afd5050f43654dd352a1ead75fa7faf3f813a223d6e6a589a3c6e7ed",
            "re_icon_master.png":
                "23f020d1a8cb95c81867ea2bed4e25013dd2ad239a8e8c6b2de1464c3cf69985",
        }

        for filename, expected_hash in expected_hashes.items():
            with self.subTest(filename=filename):
                path = asset_dir / filename
                self.assertTrue(path.is_file())
                self.assertEqual(self._sha256(path), expected_hash)

        self.assertEqual(self._png_size(asset_dir / "oscr_icon_small.png"), (593, 593))
        self.assertEqual(
            self._png_size(asset_dir / "oscrbanner-slim-dark-label.png"), (2880, 126))
        self.assertEqual(self._png_size(asset_dir / "re_icon_master.png"), (1024, 1024))
        removed_assets = (
            "section" + "31badge.png",
            "sto" + "buildslogo.png",
        )
        for filename in removed_assets:
            self.assertFalse((asset_dir / filename).exists())

    def test_source_build_revision_reads_explicit_root_file_with_bom(self) -> None:
        commit = "A" * 40
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "BUILD_INFO.txt").write_text(
                f"Commit: {commit}\r\nWorking tree: clean\r\n",
                encoding="utf-8-sig",
            )

            with patch("re_oscr.app.sys.frozen", False, create=True):
                revision = REOSCRApplication.read_build_revision(root)

        self.assertEqual(revision, commit.lower())

    def test_frozen_build_revision_reads_executable_sibling_and_marks_dirty(self) -> None:
        commit = "A" * 40
        with tempfile.TemporaryDirectory() as temp_dir:
            portable_root = Path(temp_dir)
            internal = portable_root / "_internal"
            internal.mkdir()
            (portable_root / "BUILD_INFO.txt").write_text(
                "\n".join((
                    "RE-OSCR - Retro Escalation 11.1.0.dev15",
                    f"Commit: {commit}",
                    "Working tree: uncommitted changes included",
                )),
                encoding="utf-8",
            )

            with (
                    patch("re_oscr.app.sys.frozen", True, create=True),
                    patch("re_oscr.app.sys.executable", str(portable_root / "RE-OSCR.exe"))):
                revision = REOSCRApplication.read_build_revision(internal)

        self.assertEqual(revision, commit.lower() + "+dirty")

    def test_nonfrozen_parent_build_info_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            child = root / "package"
            child.mkdir()
            (root / "BUILD_INFO.txt").write_text(
                f"Commit: {'a' * 40}\nWorking tree: clean\n",
                encoding="utf-8",
            )
            with patch("re_oscr.app.sys.frozen", False, create=True):
                revision = REOSCRApplication.read_build_revision(child)

        self.assertIsNone(revision)

    def test_build_revision_fails_closed_for_bad_metadata(self) -> None:
        invalid_build_info = (
            "Commit: short\nWorking tree: clean\n",
            f"Commit: {'a' * 40}\n",
            f"Commit: {'a' * 40}\nWorking tree: unknown\n",
        )
        for build_info in invalid_build_info:
            with self.subTest(build_info=build_info), tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                (root / "BUILD_INFO.txt").write_text(build_info, encoding="utf-8")
                with patch("re_oscr.app.sys.frozen", False, create=True):
                    revision = REOSCRApplication.read_build_revision(root)
                self.assertIsNone(revision)


if __name__ == "__main__":
    unittest.main()
