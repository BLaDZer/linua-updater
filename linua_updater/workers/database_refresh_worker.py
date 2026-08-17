from PyQt6.QtCore import QObject, pyqtSignal


class DatabaseRefreshWorker(QObject):
    result_ready = pyqtSignal(bool)

    def __init__(self, db):
        super().__init__()
        self.db = db

    def run(self):
        self.result_ready.emit(self.db.refresh())
