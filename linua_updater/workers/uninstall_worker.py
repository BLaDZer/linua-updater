import os
import shutil

from PyQt6.QtCore import QObject, pyqtSignal


class UninstallWorker(QObject):
    """Worker thread for uninstalling DLC"""

    progress_updated = pyqtSignal(int, int)  # current, total
    dlc_removed = pyqtSignal(str, bool, str)  # dlc_id, success, message
    finished = pyqtSignal()

    def __init__(self, dlc_ids, game_path, logger):
        super().__init__()
        self.dlc_ids = dlc_ids
        self.game_path = game_path
        self.logger = logger
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        """Uninstall selected DLC"""
        total = len(self.dlc_ids)
        for i, dlc_id in enumerate(self.dlc_ids):
            if self._cancelled:
                break
            self.progress_updated.emit(i + 1, total)
            success, message = self.uninstall_dlc(dlc_id)
            self.dlc_removed.emit(dlc_id, success, message)
        self.finished.emit()

    def uninstall_dlc(self, dlc_id):
        """Uninstall a single DLC by deleting its folder"""
        try:
            dlc_path = os.path.join(self.game_path, dlc_id)
            if not os.path.exists(dlc_path):
                return False, f"DLC folder not found: {dlc_path}"
            if not os.path.isdir(dlc_path):
                return False, f"Not a directory: {dlc_path}"
            # Delete the DLC folder
            self.logger.log(f"Uninstalling {dlc_id}...", "INFO")
            shutil.rmtree(dlc_path)
            self.logger.log(f"{dlc_id}: Removed successfully", "INFO")
            return True, "OK"
        except PermissionError:
            return False, "Permission denied - try running as administrator"
        except Exception as e:
            return False, str(e)
