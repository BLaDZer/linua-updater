import os
import re
import subprocess
import threading
import time

from linua_updater.utils.aria2 import Aria2Finder


class TorrentDownloader:
    def __init__(self, logger, aria2_path=None, cleanup=True):
        self.logger = logger
        self.cleanup = cleanup
        self._aria2_path = aria2_path or Aria2Finder(logger).find()
        self._cancelled = False
        self._paused = False
        self._progress_callback = None
        self._process = None
        self._command = None
        self._out_dir = None
        self._lock = threading.Lock()

    def set_progress_callback(self, callback):
        self._progress_callback = callback

    def cancel(self):
        self._cancelled = True
        with self._lock:
            if self._process and self._process.poll() is None:
                try:
                    self._process.terminate()
                except Exception:
                    pass

    def pause(self):
        with self._lock:
            self._paused = True
            if self._process and self._process.poll() is None:
                try:
                    self._process.terminate()
                except Exception:
                    pass

    def resume(self):
        with self._lock:
            self._paused = False

    def _wait_for_resume(self):
        """Block until resume() or cancel(). Yields the GIL via sleep."""
        while self._paused and not self._cancelled:
            time.sleep(0.1)

    def _build_command(self, magnet, out_dir):
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
    def _parse_size(s):
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
    def _parse_summary(line):
        m = re.search(r"\[(\S+?)\s+(\S+?)/(\S+?)\((\d+)%\)", line)
        if not m:
            return None, 0, 0
        progress = float(m.group(4))
        downloaded = TorrentDownloader._parse_size(m.group(2))
        return progress, downloaded, 0

    def download(self, magnet, out_dir, dlc_name=None, expected_size=None):
        if not self._aria2_path or not os.path.exists(self._aria2_path):
            return False, "aria2c not found"

        self._cancelled = False
        self._out_dir = out_dir
        os.makedirs(out_dir, exist_ok=True)
        cmd = self._build_command(magnet, out_dir)
        total_bytes = 0
        last_progress = 0

        while True:  # outer restart loop — pause terminates, resume restarts
            try:
                self._process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                )
            except Exception as e:
                return False, str(e)

            restart = False
            try:
                while True:
                    line = self._process.stdout.readline()
                    if not line:
                        break
                    if self._cancelled:
                        return False, "Cancelled"
                    if self._paused:
                        restart = True  # halt; restart below once resumed
                        break
                    parsed = self._parse_summary(line)
                    if parsed and parsed[0] is not None:
                        progress, downloaded, total = parsed
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
                    return False, "Cancelled"
                self._process.wait()  # reap the terminated child
                self._process = None
                continue  # re-run the command; --continue=true resumes from .aria2

            exit_code = self._process.wait()
            self._process = None
            if self._cancelled:
                return False, "Cancelled"
            if self._paused:
                # readline hit EOF because pause() terminated the process → wait, then restart
                self._wait_for_resume()
                if self._cancelled:
                    return False, "Cancelled"
                continue
            if exit_code != 0:
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
        return True, completed_files
