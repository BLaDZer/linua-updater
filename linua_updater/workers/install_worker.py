import threading
from concurrent.futures import CancelledError, as_completed

from PyQt6.QtCore import QObject, pyqtSignal

from linua_updater.constants import DEFAULT_MIRRORS
from linua_updater.core.database import DLCDatabase
from linua_updater.core.downloader import SmartDownloader
from linua_updater.core.extractor import Extractor
from linua_updater.core.installers import MultiPartInstaller, SingleDLCInstaller, TorrentInstaller
from linua_updater.core.models import InstallationStats
from linua_updater.core.parallel import ParallelInstallManager
from linua_updater.core.torrent_downloader import TorrentDownloader
from linua_updater.logging_util import SignalLogger
from linua_updater.persistence.download_queue import DownloadQueue
from linua_updater.persistence.download_state import DownloadState
from linua_updater.utils.sevenzip import SevenZipFinder


def installer_kind(source):
    if source is None:
        return "single"
    if source.getType() == "magnet":
        return "magnet"
    if source.getType() == "parts":
        return "parts"
    return "single"


class InstallWorker(QObject):
    progress_updated = pyqtSignal(str, float, int, int)
    overall_progress_updated = pyqtSignal(float)
    started = pyqtSignal()
    finished = pyqtSignal()
    result_ready = pyqtSignal(str, bool, str)
    stats_ready = pyqtSignal(dict)
    log_updated = pyqtSignal(str, str)
    
    def __init__(self, dlc_ids, game_path, settings=None, mirrors=None):
        super().__init__()
        self.dlc_ids = dlc_ids
        self.game_path = game_path
        self.settings = settings or {}
        self.mirrors = mirrors if mirrors else dict(DEFAULT_MIRRORS)
        self.max_workers = self.settings.get('max_threads', 3)
        self._cancelled = False
        self.parallel_manager = None
        self.logger = SignalLogger(self.log_updated.emit)
        self.db = DLCDatabase()
        self.logger.log(self.db.source_description(), "INFO")
        self.downloader = SmartDownloader(self.logger)
        self.extractor = Extractor(self.logger)
        self.stats = InstallationStats()
        self.download_progress = {}
        self._paused = False
        self._completed_ids = []
        self._failed_ids = []
        self._download_queue = DownloadQueue()
        self._download_state = DownloadState()
        self._active_downloaders = []
        self._active_downloaders_lock = threading.Lock()
    
    def cancel(self):
        self._cancelled = True
        if self.parallel_manager:
            self.parallel_manager.cancel_all()
        if self.downloader:
            self.downloader.cancel()
        with self._active_downloaders_lock:
            active = list(self._active_downloaders)
        for downloader in active:
            downloader.cancel()
    
    def pause(self):
        self._paused = True
        with self._active_downloaders_lock:
            active = list(self._active_downloaders)
        for downloader in active:
            downloader.pause()
        self._save_download_state()
    
    def resume(self):
        self._paused = False
        with self._active_downloaders_lock:
            active = list(self._active_downloaders)
        for downloader in active:
            downloader.resume()
    
    def _save_download_state(self):
        try:
            for dlc_id in self.dlc_ids:
                info = self.db.all().get(dlc_id)
                main = info.getMainDownloadSource() if info else None
                if main and main.getSource():
                    self._download_queue.add(dlc_id, main.getSource(), self.download_progress.get(dlc_id, 0))
            self._download_state.save_state(self.dlc_ids, self._completed_ids, self._failed_ids, self.game_path)
        except Exception as e:
            self.logger.log(f"Failed to save download state: {e}", "ERROR")

    def _build_installer(self, dlc_id, info, source, downloader):
        kind = installer_kind(source)
        if kind == "magnet":
            return TorrentInstaller(dlc_id, info, source, self.game_path, downloader, self.extractor, self.logger, self.stats)
        if kind == "parts":
            seven_finder = SevenZipFinder(self.logger)
            seven_path = seven_finder.find()
            if not seven_path:
                return None
            return MultiPartInstaller(dlc_id, info, source, self.game_path, downloader, self.extractor, seven_path, self.logger, self.stats)
        return SingleDLCInstaller(dlc_id, info, source, self.game_path, downloader, self.extractor, self.logger, self.stats)

    def _install_single(self, dlc_id):
        info = self.db.all().get(dlc_id)
        if not info:
            return dlc_id, False, "DLC not found in database"
        if self._cancelled:
            return dlc_id, False, "Cancelled"
        try:
            sources = []
            main = info.getMainDownloadSource()
            if main is not None:
                sources.append(main)
            sources.extend(info.getMirrors())
            last_message = None
            for source in sources:
                if self._cancelled:
                    return dlc_id, False, "Cancelled"
                if source.getType() == "magnet":
                    downloader = TorrentDownloader(self.logger)
                else:
                    downloader = SmartDownloader(self.logger, use_proxy=self.settings.get('use_proxy', True), resume=self.settings.get('resume_downloads', True), cleanup=self.settings.get('cleanup_temp', True), mirrors=self.mirrors)
                with self._active_downloaders_lock:
                    self._active_downloaders.append(downloader)
                try:
                    installer = self._build_installer(dlc_id, info, source, downloader)
                    if installer is None:
                        self.logger.log(f"{dlc_id}: parts source skipped (7-Zip not found)", "WARNING")
                        last_message = "7-zip not found"
                        continue
                    installer.set_progress_callback(lambda progress, downloaded, total: self._handle_progress(dlc_id, progress, downloaded, total))
                    success, message = installer.run()
                    if not success:
                        if self._cancelled or message == "Cancelled":
                            return dlc_id, False, "Cancelled"
                        self.logger.log(f"{dlc_id}: {source.getType()} source failed ({message}), trying next source", "WARNING")
                        last_message = message
                        continue
                    return dlc_id, True, message
                finally:
                    with self._active_downloaders_lock:
                        try:
                            self._active_downloaders.remove(downloader)
                        except ValueError:
                            pass
            return dlc_id, False, last_message or "No download sources available"
        except Exception as e:
            self.logger.log(f"{dlc_id}: ERROR - {e!s}", "ERROR")
            return dlc_id, False, f"Error: {e!s}"
    
    def run(self):
        try:
            self.started.emit()
            self.stats.start()
            total_dlc = len(self.dlc_ids)
            self.overall_progress_updated.emit(0)
            self.parallel_manager = ParallelInstallManager(max_workers=self.max_workers)
            self.parallel_manager.initialize(self.dlc_ids)
            self.parallel_manager.set_overall_progress_callback(lambda progress: self.overall_progress_updated.emit(progress))
            futures = {}
            for dlc_id in self.dlc_ids:
                if self._cancelled:
                    break
                try:
                    future = self.parallel_manager.executor.submit(self._install_single, dlc_id)
                except RuntimeError:
                    if self._cancelled:
                        break
                    raise
                futures[future] = dlc_id
            for future in as_completed(futures):
                dlc_id = futures[future]
                try:
                    _, success, message = future.result()
                except CancelledError:
                    success, message = False, "Cancelled"
                except Exception as e:
                    self.logger.log(f"{dlc_id}: ERROR - {e!s}", "ERROR")
                    success, message = False, f"Error: {e!s}"
                if success:
                    self._completed_ids.append(dlc_id)
                else:
                    self._failed_ids.append(dlc_id)
                self.result_ready.emit(dlc_id, success, message)
            self.stats.finish()
            summary = self.stats.get_summary()
            if summary:
                self.stats_ready.emit(summary)
            if not self._cancelled:
                self.overall_progress_updated.emit(100)
            self._download_state.clear_state()
            self._download_queue.clear_all()
            self.finished.emit()
        except Exception as e:
            self.logger.log(f"CRITICAL ERROR: {e!s}", "ERROR")
            self.result_ready.emit("SYSTEM", False, f"Worker error: {e!s}")
            self.finished.emit()
    
    def _handle_progress(self, dlc_id, progress, downloaded, total):
        if self.parallel_manager:
            self.parallel_manager.update_download_progress(dlc_id, progress, downloaded, total)
        self.download_progress[dlc_id] = progress
        self.progress_updated.emit(dlc_id, progress, downloaded, total)