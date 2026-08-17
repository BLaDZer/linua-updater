import os
import shutil
import threading
import time
from typing import Callable, Dict, Optional, Tuple

import requests

from linua_updater.constants import (
    DEFAULT_MIRRORS,
    GB,
    KB,
    MB,
    PERCENT_MAX,
    RESULT_CANCELLED,
    RESULT_OK,
)
from linua_updater.core.clients import HTTPClient
from linua_updater.core.diagnostics import NetworkDiagnostics
from linua_updater.logging_util import ImprovedLogger

# Downloader tuning
DOWNLOAD_CHUNK_SIZE = 256 * KB
MIN_SPEED_THRESHOLD = 50 * KB
MAX_FILE_SIZE = 10 * GB
MAX_RETRIES = 3

MAX_RETRY_BACKOFF_SEC = 10
SPEED_CHECK_DURATION_SEC = 10
PAUSE_WAIT_TIMEOUT_SEC = 0.5


class SmartDownloader:
    def __init__(
        self,
        logger: ImprovedLogger,
        diagnostics: Optional[NetworkDiagnostics] = None,
        use_proxy: bool = True,
        resume: bool = True,
        cleanup: bool = True,
        mirrors: Optional[Dict[str, str]] = None,
        client: Optional[HTTPClient] = None,
    ) -> None:
        self.logger = logger
        self.diagnostics = diagnostics
        self.mirrors = mirrors if mirrors else dict(DEFAULT_MIRRORS)
        self.use_proxy = use_proxy
        self.resume_enabled = resume
        self.cleanup = cleanup
        self.client = client or HTTPClient()
        self._cancelled = False
        self._paused = False
        self._active = False
        self._display: Optional[str] = None
        self._source: Optional[str] = None
        self._pause_cond = threading.Condition()
        self._progress_callback: Optional[Callable[[float, float, float], None]] = None
        self.min_speed_threshold = MIN_SPEED_THRESHOLD  # 50 KB/s minimum speed
        self.speed_check_duration = SPEED_CHECK_DURATION_SEC  # Check speed after 10 seconds

    def set_progress_callback(self, callback: Optional[Callable[[float, float, float], None]]) -> None:
        self._progress_callback = callback

    def set_proxy(self, proxy_dict: Optional[Dict[str, str]]) -> None:
        self.client.set_proxy(proxy_dict)

    def cancel(self) -> None:
        self._cancelled = True
        with self._pause_cond:
            self._paused = False
            self._pause_cond.notify_all()

    def pause(self) -> None:
        with self._pause_cond:
            self._paused = True
        if self._active:
            self.logger.log(f"Paused {self._display} from {self._source}", "WARNING")

    def resume(self) -> None:
        with self._pause_cond:
            self._paused = False
            self._pause_cond.notify_all()
        if self._active:
            self.logger.log(f"Resumed {self._display} from {self._source}")

    def _log_downloaded(self, out_path: str) -> None:
        try:
            size = os.path.getsize(out_path)
        except OSError:
            size = 0
        self.logger.log(f"Downloaded {self._display} ({size / MB:.1f} MB)")

    def download(
        self,
        url: str,
        out_path: str,
        dlc_name: Optional[str] = None,
        resume: bool = False,
        expected_size: Optional[int] = None,
    ) -> Tuple[bool, str]:
        self._active = True
        self._display = dlc_name or url
        self._source = url
        self.logger.log(f"Downloading {self._display} from {self._source}")
        temp_path = out_path + ".part"
        downloaded = 0

        if self._cancelled:
            self._active = False
            return False, RESULT_CANCELLED

        if resume and os.path.exists(temp_path):
            downloaded = os.path.getsize(temp_path)
            self.logger.log(f"Resuming download: {downloaded / MB:.1f}MB")

        success, msg = self._try_download_with_retry(url, out_path, temp_path, downloaded, expected_size)
        if success:
            self._log_downloaded(out_path)
            self._active = False
            return True, RESULT_OK

        if self._cancelled:
            self._active = False  # type: ignore[unreachable]  # may flip to True (cancel) from another thread
            return False, RESULT_CANCELLED

        if self.diagnostics and self.diagnostics.working_proxies and self.use_proxy:
            for proxy in self.diagnostics.working_proxies:
                if self._cancelled:
                    self._active = False  # type: ignore[unreachable]  # may flip to True (cancel) from another thread
                    return False, RESULT_CANCELLED
                self.set_proxy(proxy)
                success, msg = self._try_download_with_retry(url, out_path, temp_path, downloaded, expected_size)
                if success:
                    self._log_downloaded(out_path)
                    self._active = False
                    return True, "Downloaded via proxy"

        if self._cancelled:
            self._active = False  # type: ignore[unreachable]  # may flip to True (cancel) from another thread
            return False, RESULT_CANCELLED

        mirrors = self.mirrors
        for domain, mirror in mirrors.items():
            if domain in url:
                if self._cancelled:
                    self._active = False  # type: ignore[unreachable]  # may flip to True (cancel) from another thread
                    return False, RESULT_CANCELLED
                mirror_url = url.replace(domain, mirror)
                self.set_proxy(None)
                success, msg = self._try_download_with_retry(mirror_url, out_path, temp_path, downloaded, expected_size)
                if success:
                    self._log_downloaded(out_path)
                    self._active = False
                    return True, "Downloaded via mirror"

        self._active = False
        self.logger.log(f"All download attempts failed: {self._display} from {self._source}", "WARNING")
        return False, "All download attempts failed"

    def _try_download_with_retry(
        self,
        url: str,
        out_path: str,
        temp_path: str,
        start_byte: int = 0,
        expected_size: Optional[int] = None,
        max_retries: int = MAX_RETRIES,
    ) -> Tuple[bool, str]:
        for attempt in range(max_retries):
            if self._cancelled:
                return False, RESULT_CANCELLED
            try:
                if attempt > 0:
                    delay = min(2**attempt, MAX_RETRY_BACKOFF_SEC)
                    time.sleep(delay)
                success, msg = self._try_download(url, out_path, temp_path, start_byte, expected_size)
                if success:
                    return True, RESULT_OK
                if "corrupted" in msg.lower() or "invalid" in msg.lower():
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                    start_byte = 0
            except Exception as e:
                if attempt == max_retries - 1:
                    return False, str(e)
        return False, "Max retries exceeded"

    def _try_download(
        self,
        url: str,
        out_path: str,
        temp_path: str,
        start_byte: int = 0,
        expected_size: Optional[int] = None,
    ) -> Tuple[bool, str]:
        try:
            os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
            with self.client.get_stream(url, start_byte=start_byte) as response:
                response.raise_for_status()

                # Use expected_size if Content-Length is not available
                total_size = int(response.headers.get("content-length", 0))
                if total_size == 0 and expected_size:
                    total_size = expected_size

                total_size += start_byte
                if total_size > MAX_FILE_SIZE:
                    return False, "File too large (>10GB)"

                mode = "ab" if start_byte > 0 else "wb"
                with open(temp_path, mode) as f:
                    downloaded = start_byte
                    start_time = time.time()
                    last_check_time = start_time
                    last_check_bytes = downloaded

                    for chunk in response.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
                        if self._cancelled:
                            return False, RESULT_CANCELLED
                        if self._paused:
                            with self._pause_cond:
                                while self._paused and not self._cancelled:
                                    self._pause_cond.wait(timeout=PAUSE_WAIT_TIMEOUT_SEC)
                        if self._cancelled:
                            return False, RESULT_CANCELLED  # type: ignore[unreachable]  # may flip to True (cancel) from another thread
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)

                            # Calculate current speed
                            current_time = time.time()
                            elapsed = current_time - last_check_time

                            # Check speed every second
                            if elapsed >= 1.0:
                                bytes_since_check = downloaded - last_check_bytes
                                current_speed = bytes_since_check / elapsed

                                # If speed is too slow for more than speed_check_duration seconds, abort
                                if current_time - start_time > self.speed_check_duration:
                                    if current_speed < self.min_speed_threshold:
                                        self.logger.log(
                                            f"Speed too slow: {current_speed / KB:.1f} KB/s (min: {self.min_speed_threshold / KB:.1f} KB/s)"
                                        )
                                        return False, "Speed too slow, trying alternative"

                                last_check_time = current_time
                                last_check_bytes = downloaded

                            if total_size > 0 and self._progress_callback:
                                progress = (downloaded / total_size) * PERCENT_MAX
                                self._progress_callback(progress, downloaded, total_size)

                if total_size > 0:
                    actual_size = os.path.getsize(temp_path)
                    # Only check size if we have Content-Length from server
                    if int(response.headers.get("content-length", 0)) > 0 and actual_size != total_size:
                        return False, f"Size mismatch: expected {total_size}, got {actual_size}"
                if os.path.exists(temp_path):
                    shutil.move(temp_path, out_path)
                if total_size > 0 and self._progress_callback:
                    self._progress_callback(PERCENT_MAX, downloaded, total_size)
                return True, RESULT_OK
        except requests.exceptions.Timeout:
            return False, "Timeout"
        except requests.exceptions.ConnectionError:
            return False, "Connection error"
        except Exception as e:
            return False, str(e)
