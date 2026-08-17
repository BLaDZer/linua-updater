import json
from datetime import datetime

from linua_updater.paths import AppPaths


class DownloadQueue:
    def __init__(self):
        AppPaths.ensure()
        self.queue_file = AppPaths.DOWNLOAD_QUEUE_FILE
        self.queue = self._load()

    def _load(self):
        if self.queue_file.exists():
            try:
                with open(self.queue_file, encoding="utf-8") as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def add(self, dlc_id, url, progress=0):
        self.queue[dlc_id] = {"url": url, "progress": progress, "added": datetime.now().isoformat()}
        self._save()

    def update_progress(self, dlc_id, progress):
        if dlc_id in self.queue:
            self.queue[dlc_id]["progress"] = progress
            self._save()

    def remove(self, dlc_id):
        if dlc_id in self.queue:
            del self.queue[dlc_id]
            self._save()

    def get_incomplete(self):
        return {k: v for k, v in self.queue.items() if v.get("progress", 0) < 100}

    def clear_all(self):
        self.queue = {}
        self._save()

    def _save(self):
        try:
            with open(self.queue_file, "w", encoding="utf-8") as f:
                json.dump(self.queue, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Queue save error: {e}")
