import json
from datetime import datetime
from typing import Any, Dict

from linua_updater.constants import JSON_INDENT, PERCENT_MAX
from linua_updater.paths import AppPaths


class DownloadQueue:
    def __init__(self) -> None:
        AppPaths.ensure()
        self.queue_file = AppPaths.DOWNLOAD_QUEUE_FILE
        self.queue = self._load()

    def _load(self) -> Dict[str, Any]:
        if self.queue_file.exists():
            try:
                with open(self.queue_file, encoding="utf-8") as f:
                    payload = json.load(f)
                return payload if isinstance(payload, dict) else {}
            except:
                return {}
        return {}

    def add(self, dlc_id: str, url: str, progress: float = 0) -> None:
        self.queue[dlc_id] = {"url": url, "progress": progress, "added": datetime.now().isoformat()}
        self._save()

    def update_progress(self, dlc_id: str, progress: float) -> None:
        if dlc_id in self.queue:
            self.queue[dlc_id]["progress"] = progress
            self._save()

    def remove(self, dlc_id: str) -> None:
        if dlc_id in self.queue:
            del self.queue[dlc_id]
            self._save()

    def get_incomplete(self) -> Dict[str, Any]:
        return {k: v for k, v in self.queue.items() if v.get("progress", 0) < PERCENT_MAX}

    def clear_all(self) -> None:
        self.queue = {}
        self._save()

    def _save(self) -> None:
        try:
            with open(self.queue_file, "w", encoding="utf-8") as f:
                json.dump(self.queue, f, indent=JSON_INDENT, ensure_ascii=False)
        except Exception as e:
            print(f"Queue save error: {e}")
