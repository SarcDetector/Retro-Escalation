"""Portable entry point for experimental Retro Escalation builds."""

from argparse import ArgumentParser
from multiprocessing import freeze_support, get_start_method, set_start_method
import os
from pathlib import Path
from shutil import copytree
import sys

from PySide6.QtCore import QTimer

from re_oscr import REOSCRApplication
from main import Launcher


class RetroEscalationLauncher:
    __version__ = '11.1.0.dev12'

    @staticmethod
    def installed_config_dir() -> Path:
        """Return the durable per-user settings location for wheel installs."""
        if sys.platform == 'win32':
            root = Path(os.environ.get(
                'APPDATA', Path.home() / 'AppData' / 'Roaming'))
        elif sys.platform == 'darwin':
            root = Path.home() / 'Library' / 'Application Support'
        else:
            root = Path(os.environ.get(
                'XDG_CONFIG_HOME', Path.home() / '.config'))
        return root / 'RE-OSCR'

    @staticmethod
    def default_config_dir() -> str:
        """Keep fork settings separate from an installed OSCR configuration."""
        if getattr(sys, 'frozen', False):
            app_dir = Path(sys.executable).resolve().parent
            config_dir = app_dir / 'settings'
            legacy_dirs = (app_dir.parent / 'Retro-Escalation' / 'settings',)
        else:
            app_dir = Path(Launcher.base_path())
            if (app_dir / 'pyproject.toml').is_file():
                config_dir = app_dir / '.re-oscr-settings'
                legacy_dirs = (app_dir / '.retro-escalation-settings',)
            else:
                config_dir = RetroEscalationLauncher.installed_config_dir()
                legacy_dirs = ()
        RetroEscalationLauncher.migrate_legacy_config_dir(config_dir, legacy_dirs)
        return str(config_dir)

    @staticmethod
    def migrate_legacy_config_dir(config_dir: Path, legacy_dirs: tuple[Path, ...]) -> None:
        """Copy a previous Retro Escalation settings directory once, without touching OSCR."""
        if config_dir.exists():
            return
        for legacy_dir in legacy_dirs:
            if not legacy_dir.is_dir():
                continue
            try:
                copytree(legacy_dir, config_dir)
            except OSError:
                pass
            return

    @staticmethod
    def launch():
        argparser = ArgumentParser(
            prog='RE-OSCR',
            description='Retro Escalation frontend for the Open Source Combatlog Reader parser.')
        argparser.add_argument(
            '--config_dir', type=str, required=False,
            default=RetroEscalationLauncher.default_config_dir(),
            help='Change configuration directory (must be readable and writable)')
        argparser.add_argument(
            '--startup-check', action='store_true',
            help='Create the application and exit automatically (used by package validation)')
        args, _ = argparser.parse_known_args()
        application = REOSCRApplication(
            args=args,
            app_dir_path=Launcher.base_path(),
            version=RetroEscalationLauncher.__version__,
        )
        if args.startup_check:
            QTimer.singleShot(250, application.app.quit)
        exit_code = application.run()
        sys.exit(exit_code)


if __name__ == '__main__':
    freeze_support()
    try:
        set_start_method('spawn')
    except RuntimeError:
        if get_start_method() != 'spawn':
            set_start_method('spawn', force=True)
    RetroEscalationLauncher.launch()
