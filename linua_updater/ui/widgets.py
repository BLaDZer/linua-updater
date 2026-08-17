from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QProgressBar, QWidget


class SimpleProgressBar(QProgressBar):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._last_percent = -1

    def setValue(self, value: int) -> None:
        value = max(0, min(100, int(value)))
        if value != self._last_percent:
            self._last_percent = value
            super().setValue(value)
            self.setFormat(f"{value}%")


class SimpleDetailWidget(QLabel):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setStyleSheet("QLabel { color: #cccccc; font-size: 11px; padding: 2px; text-align: center; }")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setVisible(False)

    def update_progress(self, dlc_id: str, percent: float, downloaded: int, total: int) -> None:
        if total > 0:
            mb_downloaded = downloaded / (1024 * 1024)
            mb_total = total / (1024 * 1024)
            text = f"Downloading {dlc_id}: {int(percent)}% ({mb_downloaded:.1f}MB/{mb_total:.1f}MB)"
            self.setText(text)
            self.setVisible(True)
