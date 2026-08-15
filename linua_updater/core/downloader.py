import os
import shutil
import threading
import time

import requests

from linua_updater.constants import APP_VERSION, DEFAULT_MIRRORS


class SmartDownloader:
    def __init__(self, logger, diagnostics=None, use_proxy=True, resume=True, cleanup=True, mirrors=None):
        self.logger = logger
        self.diagnostics = diagnostics
        self.mirrors = mirrors if mirrors else dict(DEFAULT_MIRRORS)
        self.use_proxy = use_proxy
        self.resume = resume
        self.cleanup = cleanup
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'Linua-Updater/' + APP_VERSION})
        self._cancelled = False
        self._paused = False
        self._pause_cond = threading.Condition()
        self._progress_callback = None
        self.min_speed_threshold = 50 * 1024  # 50 KB/s minimum speed
        self.speed_check_duration = 10  # Check speed after 10 seconds

    def set_progress_callback(self, callback):
        self._progress_callback = callback

    def set_proxy(self, proxy_dict):
        if proxy_dict:
            self.session.proxies = proxy_dict
        else:
            self.session.proxies = {}

    def cancel(self):
        self._cancelled = True
        with self._pause_cond:
            self._paused = False
            self._pause_cond.notify_all()

    def pause(self):
        with self._pause_cond:
            self._paused = True

    def resume(self):
        with self._pause_cond:
            self._paused = False
            self._pause_cond.notify_all()

    def download(self, url, out_path, dlc_name=None, resume=False, expected_size=None):
        display = dlc_name or url
        temp_path = out_path + ".part"
        downloaded = 0

        if resume and os.path.exists(temp_path):
            downloaded = os.path.getsize(temp_path)
            self.logger.log(f"Resuming download: {downloaded / (1024*1024):.1f}MB")

        success, msg = self._try_download_with_retry(url, out_path, temp_path, downloaded, expected_size)
        if success:
            return True, "OK"

        if self.diagnostics and self.diagnostics.working_proxies and self.use_proxy:
            for proxy in self.diagnostics.working_proxies:
                self.set_proxy(proxy)
                success, msg = self._try_download_with_retry(url, out_path, temp_path, downloaded, expected_size)
                if success:
                    return True, "Downloaded via proxy"

        mirrors = self.mirrors
        for domain, mirror in mirrors.items():
            if domain in url:
                mirror_url = url.replace(domain, mirror)
                self.set_proxy(None)
                success, msg = self._try_download_with_retry(mirror_url, out_path, temp_path, downloaded, expected_size)
                if success:
                    return True, "Downloaded via mirror"

        return False, "All download attempts failed"

    def _try_download_with_retry(self, url, out_path, temp_path, start_byte=0, expected_size=None, max_retries=3):
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    delay = min(2 ** attempt, 10)
                    time.sleep(delay)
                success, msg = self._try_download(url, out_path, temp_path, start_byte, expected_size)
                if success:
                    return True, "OK"
                if "corrupted" in msg.lower() or "invalid" in msg.lower():
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                    start_byte = 0
            except Exception as e:
                if attempt == max_retries - 1:
                    return False, str(e)
        return False, "Max retries exceeded"

    def _try_download(self, url, out_path, temp_path, start_byte=0, expected_size=None):
        try:
            os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
            headers = {}
            if start_byte > 0:
                headers['Range'] = f'bytes={start_byte}-'
            with self.session.get(url, stream=True, timeout=30, verify=True, headers=headers) as r:
                r.raise_for_status()

                # Use expected_size if Content-Length is not available
                total_size = int(r.headers.get('content-length', 0))
                if total_size == 0 and expected_size:
                    total_size = expected_size

                total_size += start_byte
                if total_size > 10 * 1024 * 1024 * 1024:
                    return False, "File too large (>10GB)"

                mode = 'ab' if start_byte > 0 else 'wb'
                with open(temp_path, mode) as f:
                    downloaded = start_byte
                    start_time = time.time()
                    last_check_time = start_time
                    last_check_bytes = downloaded

                    for chunk in r.iter_content(chunk_size=256*1024):
                        if self._cancelled:
                            return False, "Cancelled"
                        if self._paused:
                            with self._pause_cond:
                                while self._paused and not self._cancelled:
                                    self._pause_cond.wait(timeout=0.5)
                        if self._cancelled:
                            return False, "Cancelled"
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
                                        self.logger.log(f"Speed too slow: {current_speed/1024:.1f} KB/s (min: {self.min_speed_threshold/1024:.1f} KB/s)")
                                        return False, "Speed too slow, trying alternative"

                                last_check_time = current_time
                                last_check_bytes = downloaded

                            if total_size > 0 and self._progress_callback:
                                progress = (downloaded / total_size) * 100
                                self._progress_callback(progress, downloaded, total_size)

                if total_size > 0:
                    actual_size = os.path.getsize(temp_path)
                    # Only check size if we have Content-Length from server
                    if int(r.headers.get('content-length', 0)) > 0 and actual_size != total_size:
                        return False, f"Size mismatch: expected {total_size}, got {actual_size}"
                if os.path.exists(temp_path):
                    shutil.move(temp_path, out_path)
                if total_size > 0 and self._progress_callback:
                    self._progress_callback(100, downloaded, total_size)
                return True, "OK"
        except requests.exceptions.Timeout:
            return False, "Timeout"
        except requests.exceptions.ConnectionError:
            return False, "Connection error"
        except Exception as e:
            return False, str(e)