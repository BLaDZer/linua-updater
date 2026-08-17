import os
import time
from typing import Callable, List, Optional, Tuple, Union

from linua_updater.constants import (
    RESULT_CANCELLED,
)
from linua_updater.core.clients import TorrentClient
from linua_updater.logging_util import ImprovedLogger

PAUSE_POLL_INTERVAL_SEC = 0.1

TORRENT_EXTENSIONS = (".aria2", ".torrent")


class TorrentDownloader:
    """Service orchestrating a single injected :class:`TorrentClient`.

    Owns the pause/resume restart loop, progress-callback dedupe, artifact
    cleanup and lifecycle logging; all engine-specific mechanics are delegated
    to the client.
    """

    def __init__(self, logger: ImprovedLogger, client: TorrentClient, cleanup: bool = True) -> None:
        self.logger = logger
        self.cleanup = cleanup
        self._client = client
        self._cancelled = False
        self._paused = False
        self._active = False
        self._display: Optional[str] = None
        self._source: Optional[str] = None
        self._progress_callback: Optional[Callable[[float, float, float], None]] = None

    def set_progress_callback(self, callback: Optional[Callable[[float, float, float], None]]) -> None:
        self._progress_callback = callback

    def cancel(self) -> None:
        self._cancelled = True
        self._client.abort()

    def pause(self) -> None:
        self._paused = True
        self._client.stop()
        if self._active:
            self.logger.log(f"Paused torrent download: {self._display}", "WARNING")

    def resume(self) -> None:
        self._paused = False
        if self._active:
            self.logger.log(f"Resumed torrent download: {self._display}")

    def _wait_for_resume(self) -> None:
        """Block until resume() or cancel(). Yields the GIL via sleep."""
        while self._paused and not self._cancelled:
            time.sleep(PAUSE_POLL_INTERVAL_SEC)

    def download(
        self,
        magnet: str,
        out_dir: str,
        dlc_name: Optional[str] = None,
        expected_size: Optional[int] = None,
    ) -> Tuple[bool, Union[str, List[str]]]:
        self._active = True
        self._display = dlc_name or magnet
        self._source = magnet
        display = self._display
        self.logger.log(f"Starting torrent download: {display} ({self._source})")
        if not self._client.is_available():
            self._active = False
            self.logger.log("Torrent download: no available torrent client found. Torrent downloads will be skipped", "WARNING")

            return False, "no available torrent client found"

        try:
            if self._cancelled:  # cancel() beat download() to the start → no download
                return False, RESULT_CANCELLED
            self._cancelled = False
            total_bytes: float = 0
            last_progress: float = 0

            while True:  # outer restart loop — pause terminates, resume restarts
                if self._cancelled:  # never re-launch after a cancel (also after resume/pause)
                    return False, RESULT_CANCELLED
                try:
                    self._client.start(magnet, out_dir)
                except Exception as e:
                    return False, str(e)

                restart = False
                try:
                    while True:
                        try:
                            tick = self._client.read_progress()
                        except Exception as e:
                            return False, str(e)
                        if tick is None:  # stream end → exit this inner loop
                            break
                        if self._cancelled:
                            self.logger.log(f"Torrent download cancelled: {display}", "WARNING")  # type: ignore[unreachable]  # cancel() may run in another thread
                            return False, RESULT_CANCELLED
                        if self._paused:
                            restart = True  # halt; restart below once resumed
                            break
                        progress, downloaded, total = tick
                        if total == 0 and expected_size:
                            total = expected_size
                        total_bytes = max(total_bytes, downloaded)
                        if progress != last_progress and self._progress_callback:
                            self._progress_callback(progress, downloaded, total)
                            last_progress = progress
                except Exception:
                    pass

                if restart:
                    # loop hit a progress tick while paused → wait, then restart
                    self._wait_for_resume()
                    if self._cancelled:
                        self.logger.log(f"Torrent download cancelled: {display}", "WARNING")  # type: ignore[unreachable]  # cancel() may run in another thread
                        return False, RESULT_CANCELLED
                    self._client.wait_exit()  # reap the terminated child
                    continue  # re-run the command; --continue=true resumes from .aria2

                exit_code = self._client.wait_exit()
                if self._cancelled:
                    self.logger.log(f"Torrent download cancelled: {display}", "WARNING")  # type: ignore[unreachable]  # cancel() may run in another thread
                    return False, RESULT_CANCELLED
                if self._paused:
                    # read_progress hit EOF because pause() terminated the process → wait, then restart
                    self._wait_for_resume()
                    if self._cancelled:
                        self.logger.log(f"Torrent download cancelled: {display}", "WARNING")  # type: ignore[unreachable]  # cancel() may run in another thread
                        return False, RESULT_CANCELLED
                    continue
                if exit_code != 0:
                    self.logger.log(f"aria2c exit code {exit_code}", "ERROR")
                    return False, f"aria2c exit code {exit_code}"
                break  # completed normally

            completed_files = []
            try:
                for f in os.listdir(out_dir):
                    if f.endswith(TORRENT_EXTENSIONS):
                        try:
                            os.remove(os.path.join(out_dir, f))
                        except Exception:
                            pass
                    else:
                        fp = os.path.join(out_dir, f)
                        if os.path.isfile(fp):
                            completed_files.append(fp)
            except Exception:
                pass

            completed_files.sort()
            self.logger.log(f"Torrent download complete: {display}")
            return True, completed_files
        finally:
            self._active = False
