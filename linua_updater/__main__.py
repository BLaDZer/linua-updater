"""Linua Updater entry point. Run with ``python -m linua_updater``."""

import sys

if sys.platform != "win32":
    import signal
    signal.signal(signal.SIGINT, signal.SIG_DFL)

try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except ImportError:
    pass

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QMessageBox

from linua_updater.constants import APP_VERSION
from linua_updater.core.database import DLCDatabase
from linua_updater.ui.main_window import LinuaUI
from linua_updater.ui.theme import apply_dark_palette
from linua_updater.utils.config import ConfigManager
from linua_updater.utils.single_instance import SingleInstanceLock


def main():
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
    if SingleInstanceLock.is_already_running():
        QMessageBox.critical(None, "Already Running", "Linua Updater is already running.\nCheck your system tray / notification area.")
        sys.exit(1)
    instance_lock = SingleInstanceLock()
    if not instance_lock.acquire():
        QMessageBox.critical(None, "Already Running", "Linua Updater is already running.\nCheck your system tray / notification area.")
        sys.exit(1)
    app = QApplication(sys.argv)
    app.setApplicationName("Linua Updater")
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("l1ntol")
    apply_dark_palette(app)
    config = ConfigManager()
    db = DLCDatabase()
    window = LinuaUI(config, db)
    window.show()
    exit_code = app.exec()
    instance_lock.release()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()