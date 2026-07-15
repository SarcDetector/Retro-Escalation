from argparse import ArgumentParser
from multiprocessing import freeze_support, set_start_method, get_start_method
import os
import sys

from re_oscr import REOSCRApplication


class Launcher():

    __version__ = '11.1.0.dev10+re.oscr'

    @staticmethod
    def base_path() -> str:
        """initialize the base path"""
        try:
            base_path = sys._MEIPASS
        except Exception:
            if getattr(sys, 'frozen', False):
                # The application is frozen
                base_path = os.path.dirname(sys.executable)
            else:
                base_path = os.path.abspath(os.path.dirname(__file__))
        return base_path

    @staticmethod
    def launch():
        argparser = ArgumentParser(
            prog='RE-OSCR',
            description='Retro Escalation frontend for the Open Source Combatlog Reader parser.')
        argparser.add_argument(
            '--config_dir', type=str, required=False,
            help='Change configuration directory (must be readable and writable)')
        args, _ = argparser.parse_known_args()
        exit_code = REOSCRApplication(
            args=args, app_dir_path=Launcher.base_path(), version=Launcher.__version__).run()
        sys.exit(exit_code)


if __name__ == '__main__':
    freeze_support()
    try:
        set_start_method('spawn')
    except RuntimeError:
        if get_start_method() != 'spawn':
            set_start_method('spawn', force=True)
    Launcher.launch()
