"""Portable Windows entry point for experimental Retro Escalation builds."""

from argparse import ArgumentParser
from multiprocessing import freeze_support, get_start_method, set_start_method
from pathlib import Path
import sys

from OSCRUI import OSCRUI
from main import Launcher


class RetroEscalationLauncher:
    __version__ = '11.1.0-re.2-dev'

    @staticmethod
    def default_config_dir() -> str:
        """Keep fork settings separate from an installed OSCR configuration."""
        if getattr(sys, 'frozen', False):
            return str(Path(sys.executable).resolve().parent / 'settings')
        return str(Path(Launcher.base_path()) / '.retro-escalation-settings')

    @staticmethod
    def launch():
        argparser = ArgumentParser(
            prog='Retro Escalation',
            description='Experimental themed build of the Open Source Combatlog Reader.')
        argparser.add_argument(
            '--config_dir', type=str, required=False,
            default=RetroEscalationLauncher.default_config_dir(),
            help='Change configuration directory (must be readable and writable)')
        args, _ = argparser.parse_known_args()
        exit_code = OSCRUI(
            args=args,
            app_dir_path=Launcher.base_path(),
            version=RetroEscalationLauncher.__version__,
        ).run()
        sys.exit(exit_code)


if __name__ == '__main__':
    freeze_support()
    try:
        set_start_method('spawn')
    except RuntimeError:
        if get_start_method() != 'spawn':
            set_start_method('spawn', force=True)
    RetroEscalationLauncher.launch()
