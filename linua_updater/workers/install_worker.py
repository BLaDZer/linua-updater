import threading
from concurrent.futures import CancelledError, as_completed
from typing import Any, Dict, List, Optional, Tuple, Union, cast

from PyQt6.QtCore import QObject, pyqtSignal

from linua_updater.constants import DEFAULT_MIRRORS, PERCENT_MAX, RESULT_CANCELLED
from linua_updater.core.clients import create_torrent_client
from linua_updater.core.database import DLCDatabase
from linua_updater.core.downloader import SmartDownloader
from linua_updater.core.extractor import Extractor
from linua_updater.core.installers import MultiPartInstaller, SingleDLCInstaller, TorrentInstaller
from linua_updater.core.models import (
    SOURCE_TYPE_MAGNET,
    SOURCE_TYPE_PARTS,
    DLCInfo,
    DownloadSource,
    InstallationStats,
)
from linua_updater.core.parallel import ParallelInstallManager
from linua_updater.core.torrent_downloader import TorrentDownloader
from linua_updater.logging_util import SignalLogger
from linua_updater.persistence.download_queue import DownloadQueue
from linua_updater.persistence.download_state import DownloadState
from linua_updater.utils.config import DEFAULT_SETTINGS
from linua_updater.utils.sevenzip import SevenZipFinder

INSTALLER_TYPE_SINGLE_FILE = "single"
INSTALLER_TYPE_MAGNET = "magnet"
INSTALLER_TYPE_PARTS = "parts"


def get_installer_type(source: Optional[DownloadSource]) -> str:
    if source is None:
        return INSTALLER_TYPE_SINGLE_FILE
    if source.getType() == SOURCE_TYPE_MAGNET:
        return INSTALLER_TYPE_MAGNET
    if source.getType() == SOURCE_TYPE_PARTS:
        return INSTALLER_TYPE_PARTS

    return INSTALLER_TYPE_SINGLE_FILE


class InstallWorker(QObject):
    progress_updated = pyqtSignal(str, float, "long long", "long long")
    overall_progress_updated = pyqtSignal(float)
    started = pyqtSignal()
    finished = pyqtSignal()
    result_ready = pyqtSignal(str, bool, str)
    stats_ready = pyqtSignal(dict)
    log_updated = pyqtSignal(str, str)

    def __init__(
        self,
        dlc_ids: List[str],
        game_path: str,
        settings: Optional[Dict[str, Any]] = None,
        mirrors: Optional[Dict[str, str]] = None,
    ) -> None:
        super().__init__()
        self.dlc_ids = dlc_ids
        self.game_path = game_path
        self.settings = settings or {}
        self.mirrors = mirrors if mirrors else dict(DEFAULT_MIRRORS)
        self.max_workers = self.settings.get("max_threads", DEFAULT_SETTINGS["max_threads"])
        self._cancelled = False
        self.parallel_manager: Optional[ParallelInstallManager] = None
        self.logger = SignalLogger(self.log_updated.emit)
        self.db = DLCDatabase()
        self.logger.log(self.db.source_description(), "INFO")
        self.downloader = SmartDownloader(self.logger)
        self.extractor = Extractor(self.logger)
        self.stats = InstallationStats()
        self.stats.total_dlc = len(self.dlc_ids)
        self.download_progress: Dict[str, float] = {}
        self._paused = False
        self._completed_ids: List[str] = []
        self._failed_ids: List[str] = []
        self._download_queue = DownloadQueue()
        self._download_state = DownloadState()
        self._active_downloaders: List[Union[TorrentDownloader, SmartDownloader]] = []
        self._active_downloaders_lock = threading.Lock()

    def cancel(self) -> None:
        self._cancelled = True
        if self.parallel_manager:
            self.parallel_manager.cancel_all()

        if self.downloader:
            self.downloader.cancel()

        with self._active_downloaders_lock:
            active = list(self._active_downloaders)

        for downloader in active:
            downloader.cancel()

    def pause(self) -> None:
        self._paused = True
        with self._active_downloaders_lock:
            active = list(self._active_downloaders)

        for downloader in active:
            downloader.pause()

        self._save_download_state()

    def resume(self) -> None:
        self._paused = False

        with self._active_downloaders_lock:
            active = list(self._active_downloaders)

        for downloader in active:
            downloader.resume()

    def _save_download_state(self) -> None:
        try:
            for dlc_id in self.dlc_ids:
                info = self.db.all().get(dlc_id)
                main = info.getMainDownloadSource() if info else None

                if main:
                    source = main.getSource()

                    if source:
                        self._download_queue.add(dlc_id, source, self.download_progress.get(dlc_id, 0))

            self._download_state.save_state(self.dlc_ids, self._completed_ids, self._failed_ids, self.game_path)
        except Exception as e:
            self.logger.log(f"Failed to save download state: {e}", "ERROR")

    def _build_installer(
        self,
        dlc_id: str,
        info: DLCInfo,
        source: DownloadSource,
        downloader: Union[TorrentDownloader, SmartDownloader],
    ) -> Optional[Union[SingleDLCInstaller, MultiPartInstaller, TorrentInstaller]]:
        installer_type = get_installer_type(source)

        if installer_type == INSTALLER_TYPE_MAGNET:
            return TorrentInstaller(
                dlc_id, info, source, self.game_path, cast(TorrentDownloader, downloader), self.extractor, self.logger, self.stats
            )

        if installer_type == INSTALLER_TYPE_PARTS:
            seven_finder = SevenZipFinder(self.logger)
            seven_path = seven_finder.find()

            if not seven_path:
                return None

            return MultiPartInstaller(
                dlc_id, info, source, self.game_path, cast(SmartDownloader, downloader), self.extractor, seven_path, self.logger, self.stats
            )

        return SingleDLCInstaller(
            dlc_id, info, source, self.game_path, cast(SmartDownloader, downloader), self.extractor, self.logger, self.stats
        )

    def _install_single(self, dlc_id: str) -> Tuple[str, bool, str]:
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

            self.logger.log(f"{dlc_id}: found {len(sources)} of sources for this DLC", "INFO")

            last_message = None
            for source in sources:
                if self._cancelled:
                    return dlc_id, False, "Cancelled"  # type: ignore[unreachable]  # cancel() may run on another thread

                downloader: Union[TorrentDownloader, SmartDownloader]

                if source.getType() == SOURCE_TYPE_MAGNET:
                    downloader = TorrentDownloader(self.logger, create_torrent_client(self.logger))
                else:
                    downloader = SmartDownloader(
                        self.logger,
                        use_proxy=self.settings.get("use_proxy", True),
                        resume=self.settings.get("resume_downloads", True),
                        cleanup=self.settings.get("cleanup_temp", True),
                        mirrors=self.mirrors,
                    )

                with self._active_downloaders_lock:
                    self._active_downloaders.append(downloader)

                try:
                    installer = self._build_installer(dlc_id, info, source, downloader)
                    if installer is None:
                        self.logger.log(f"{dlc_id}: parts source skipped (7-Zip not found)", "WARNING")
                        last_message = "7-zip not found"
                        continue

                    installer.set_progress_callback(
                        lambda progress, downloaded, total: self._handle_progress(
                            dlc_id, progress, cast(int, downloaded), cast(int, total)
                        )
                    )

                    success, message = installer.run()
                    message = cast(str, message)

                    if not success:
                        if self._cancelled or message == RESULT_CANCELLED:
                            return dlc_id, False, RESULT_CANCELLED

                        self.logger.log(
                            f"{dlc_id}: {source.getType()} source failed ({message}), trying next source", "WARNING"
                        )
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

    def run(self) -> None:
        try:
            self.started.emit()
            self.stats.start()
            self.overall_progress_updated.emit(0)
            self.parallel_manager = ParallelInstallManager(max_workers=self.max_workers)
            self.parallel_manager.initialize(self.dlc_ids)
            self.parallel_manager.set_overall_progress_callback(
                lambda progress: self.overall_progress_updated.emit(progress)
            )

            futures = {}
            for dlc_id in self.dlc_ids:
                if self._cancelled:
                    break

                try:
                    future = self.parallel_manager.executor.submit(self._install_single, dlc_id)
                except RuntimeError:
                    if self._cancelled:
                        break  # type: ignore[unreachable]  # cancel() may run on another thread
                    raise

                futures[future] = dlc_id

            for future in as_completed(futures):
                dlc_id = futures[future]

                try:
                    _, success, message = future.result()
                except CancelledError:
                    success, message = False, RESULT_CANCELLED
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
                self.overall_progress_updated.emit(PERCENT_MAX)

            self._download_state.clear_state()
            self._download_queue.clear_all()
            self.finished.emit()
        except Exception as e:
            self.logger.log(f"CRITICAL ERROR: {e!s}", "ERROR")
            self.result_ready.emit("SYSTEM", False, f"Worker error: {e!s}")
            self.finished.emit()

    def _handle_progress(self, dlc_id: str, progress: float, downloaded: int, total: int) -> None:
        if self.parallel_manager:
            self.parallel_manager.update_download_progress(dlc_id, progress, downloaded, total)

        self.download_progress[dlc_id] = progress
        self.progress_updated.emit(dlc_id, progress, downloaded, total)
