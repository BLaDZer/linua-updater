from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QProgressBar, QWidget

from linua_updater.constants import MB, PERCENT_MAX


class SimpleProgressBar(QProgressBar):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._last_percent = -1

    def setValue(self, value: int) -> None:
        value = max(0, min(PERCENT_MAX, int(value)))
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
            mb_downloaded = downloaded / MB
            mb_total = total / MB
            text = f"Downloading {dlc_id}: {int(percent)}% ({mb_downloaded:.1f}MB/{mb_total:.1f}MB)"
            self.setText(text)
            self.setVisible(True)
