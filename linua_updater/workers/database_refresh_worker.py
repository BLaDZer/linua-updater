from PyQt6.QtCore import QObject, pyqtSignal

from linua_updater.core.database import DLCDatabase


class DatabaseRefreshWorker(QObject):
    result_ready = pyqtSignal(bool)

    def __init__(self, db: DLCDatabase) -> None:
        super().__init__()
        self.db = db

    def run(self) -> None:
        self.result_ready.emit(self.db.refresh())
