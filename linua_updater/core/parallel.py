import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Dict, List, Optional


class ParallelInstallManager:
    def __init__(self, max_workers: int = 5) -> None:
        self.max_workers: int = max_workers
        self.executor: ThreadPoolExecutor = ThreadPoolExecutor(max_workers=max_workers)
        self._cancelled: bool = False
        self._download_progress: Dict[str, Dict[str, float]] = {}
        self._overall_progress_callback: Optional[Callable[[float], None]] = None
        self._lock = threading.Lock()
        self.total_count: int = 0

    def initialize(self, dlc_ids: List[str]) -> None:
        with self._lock:
            self._download_progress = {dlc_id: {"progress": 0.0, "downloaded": 0, "total": 0} for dlc_id in dlc_ids}
            self.total_count = len(dlc_ids)

    def set_overall_progress_callback(self, callback: Optional[Callable[[float], None]]) -> None:
        self._overall_progress_callback = callback

    def update_download_progress(self, dlc_id: str, progress: float, downloaded: int, total: int) -> None:
        with self._lock:
            self._download_progress[dlc_id] = {"progress": progress, "downloaded": downloaded, "total": total}
            total_progress = self._calculate_overall_progress()
        if self._overall_progress_callback:
            self._overall_progress_callback(total_progress)

    def _calculate_overall_progress(self) -> float:
        if not self._download_progress:
            return 0
        total_progress = sum(d["progress"] for d in self._download_progress.values())
        count = self.total_count if self.total_count > 0 else len(self._download_progress)
        return total_progress / count if count > 0 else 0

    def cancel_all(self) -> None:
        self._cancelled = True
        self.executor.shutdown(wait=False, cancel_futures=True)
