import threading
from concurrent.futures import ThreadPoolExecutor


class ParallelInstallManager:
    def __init__(self, max_workers=5):
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self._cancelled = False
        self._download_progress = {}
        self._overall_progress_callback = None
        self._lock = threading.Lock()
        self.total_count = 0

    def initialize(self, dlc_ids):
        with self._lock:
            self._download_progress = {dlc_id: {"progress": 0.0, "downloaded": 0, "total": 0} for dlc_id in dlc_ids}
            self.total_count = len(dlc_ids)

    def set_overall_progress_callback(self, callback):
        self._overall_progress_callback = callback

    def update_download_progress(self, dlc_id, progress, downloaded, total):
        with self._lock:
            self._download_progress[dlc_id] = {"progress": progress, "downloaded": downloaded, "total": total}
            total_progress = self._calculate_overall_progress()
        if self._overall_progress_callback:
            self._overall_progress_callback(total_progress)

    def _calculate_overall_progress(self):
        if not self._download_progress:
            return 0
        total_progress = sum(d["progress"] for d in self._download_progress.values())
        count = self.total_count if self.total_count > 0 else len(self._download_progress)
        return total_progress / count if count > 0 else 0

    def cancel_all(self):
        self._cancelled = True
        self.executor.shutdown(wait=False, cancel_futures=True)
