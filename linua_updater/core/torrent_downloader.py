import os
import re
import subprocess
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from linua_updater.logging_util import ImprovedLogger
from linua_updater.utils.aria2 import Aria2Finder


def _popen_kwargs() -> Dict[str, Any]:
    """Popen kwargs hiding the console window on Windows. No-op elsewhere."""
    kwargs: Dict[str, Any] = {}
    flag = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    if flag:
        kwargs["creationflags"] = flag
    return kwargs


class TorrentDownloader:
    def __init__(self, logger: ImprovedLogger, aria2_path: Optional[str] = None, cleanup: bool = True) -> None:
        self.logger = logger
        self.cleanup = cleanup
        self._aria2_path = aria2_path or Aria2Finder(logger).find()
        self._cancelled = False
        self._paused = False
        self._active = False
        self._display: Optional[str] = None
        self._source: Optional[str] = None
        self._progress_callback: Optional[Callable[[float, float, float], None]] = None
        self._process: Optional[subprocess.Popen[str]] = None
        self._command: Optional[List[str]] = None
        self._out_dir: Optional[str] = None
        self._lock = threading.Lock()

    def set_progress_callback(self, callback: Optional[Callable[[float, float, float], None]]) -> None:
        self._progress_callback = callback

    def cancel(self) -> None:
        self._cancelled = True
        with self._lock:
            if self._process and self._process.poll() is None:
                try:
                    self._process.terminate()
                    try:
                        self._process.wait(timeout=2)
                    except Exception:
                        try:
                            self._process.kill()
                        except Exception:
                            pass
                        try:
                            self._process.wait()
                        except Exception:
                            pass
                except Exception:
                    pass

    def pause(self) -> None:
        with self._lock:
            self._paused = True
            if self._process and self._process.poll() is None:
                try:
                    self._process.terminate()
                except Exception:
                    pass
        if self._active:
            self.logger.log(f"Paused torrent download: {self._display}", "WARNING")

    def resume(self) -> None:
        with self._lock:
            self._paused = False
        if self._active:
            self.logger.log(f"Resumed torrent download: {self._display}")

    def _wait_for_resume(self) -> None:
        """Block until resume() or cancel(). Yields the GIL via sleep."""
        while self._paused and not self._cancelled:
            time.sleep(0.1)

    def _build_command(self, magnet: str, out_dir: str) -> List[str]:
        assert self._aria2_path is not None  # guaranteed by download() before calling
        cmd = [
            self._aria2_path,
            magnet,
            "--dir=" + out_dir,
            "--seed-time=0",
            "--bt-stop-timeout=600",
            "--continue=true",
            "--allow-overwrite=true",
            "--file-allocation=none",
            "--summary-interval=1",
            "--check-integrity=true",
        ]
        return cmd

    @staticmethod
    def _parse_size(s: str) -> float:
        s = s.strip()
        multipliers = {
            "KiB": 1024,
            "MiB": 1024 * 1024,
            "GiB": 1024 * 1024 * 1024,
            "B": 1,
        }
        for unit, mult in multipliers.items():
            if s.endswith(unit):
                try:
                    return float(s[: -len(unit)].strip()) * mult
                except ValueError:
                    return 0
        try:
            return float(s)
        except ValueError:
            return 0

    @staticmethod
    def _parse_summary(line: str) -> Tuple[Optional[float], float, float]:
        m = re.search(r"\[(\S+?)\s+(\S+?)/(\S+?)\((\d+)%\)", line)
        if not m:
            return None, 0, 0
        progress = float(m.group(4))
        downloaded = TorrentDownloader._parse_size(m.group(2))
        return progress, downloaded, 0

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
        if not self._aria2_path or not os.path.exists(self._aria2_path):
            self._active = False
            self.logger.log("Torrent download: aria2c not found", "WARNING")
            return False, "aria2c not found"

        try:
            if self._cancelled:  # cancel() beat download() to the start → no download
                return False, "Cancelled"
            self._cancelled = False
            self._out_dir = out_dir
            os.makedirs(out_dir, exist_ok=True)
            cmd = self._build_command(magnet, out_dir)
            total_bytes: float = 0
            last_progress: float = 0

            while True:  # outer restart loop — pause terminates, resume restarts
                if self._cancelled:  # never re-launch aria2c after a cancel (also after resume/pause)
                    return False, "Cancelled"
                try:
                    self._process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        bufsize=1,
                        **_popen_kwargs(),
                    )
                except Exception as e:
                    return False, str(e)

                if self._process.stdout is None:
                    return False, "aria2c did not provide stdout"

                restart = False
                try:
                    while True:
                        line = self._process.stdout.readline()
                        if not line:
                            break
                        if self._cancelled:
                            self.logger.log(f"Torrent download cancelled: {display}", "WARNING")  # type: ignore[unreachable]  # cancel() may run in another thread
                            return False, "Cancelled"
                        if self._paused:
                            restart = True  # halt; restart below once resumed
                            break
                        parsed = self._parse_summary(line)
                        if parsed and parsed[0] is not None:
                            progress: float = parsed[0]
                            downloaded: float = parsed[1]
                            total: float = parsed[2]
                            if total == 0 and expected_size:
                                total = expected_size
                            total_bytes = max(total_bytes, downloaded)
                            if progress != last_progress and self._progress_callback:
                                self._progress_callback(progress, downloaded, total)
                                last_progress = progress
                except Exception:
                    pass

                if restart:
                    # loop hit a summary line while paused → wait, then restart
                    self._wait_for_resume()
                    if self._cancelled:
                        self.logger.log(f"Torrent download cancelled: {display}", "WARNING")  # type: ignore[unreachable]  # cancel() may run in another thread
                        return False, "Cancelled"
                    self._process.wait()  # reap the terminated child
                    self._process = None
                    continue  # re-run the command; --continue=true resumes from .aria2

                exit_code = self._process.wait()
                self._process = None
                if self._cancelled:
                    self.logger.log(f"Torrent download cancelled: {display}", "WARNING")  # type: ignore[unreachable]  # cancel() may run in another thread
                    return False, "Cancelled"
                if self._paused:
                    # readline hit EOF because pause() terminated the process → wait, then restart
                    self._wait_for_resume()
                    if self._cancelled:
                        self.logger.log(f"Torrent download cancelled: {display}", "WARNING")  # type: ignore[unreachable]  # cancel() may run in another thread
                        return False, "Cancelled"
                    continue
                if exit_code != 0:
                    self.logger.log(f"aria2c exit code {exit_code}", "ERROR")
                    return False, f"aria2c exit code {exit_code}"
                break  # completed normally

            completed_files = []
            try:
                for f in os.listdir(out_dir):
                    if f.endswith((".aria2", ".torrent")):
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
