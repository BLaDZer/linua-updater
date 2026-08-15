import os
import tempfile
import threading
import time


class SingleDLCInstaller:
    def __init__(self, dlc_id, info, game_path, downloader, extractor, logger, stats=None):
        self.dlc = dlc_id
        self.info = info
        self.game = game_path
        self.dl = downloader
        self.ex = extractor
        self.logger = logger
        self.stats = stats
        self._progress_callback = None
        self._start_time = None

    def set_progress_callback(self, callback):
        self._progress_callback = callback

    def log(self, text, level="INFO"):
        if self.logger:
            self.logger.log(f"{self.dlc}: {text}", level)

    def run(self):
        temp = None
        try:
            self._start_time = time.time()
            url = self.info.get("url")
            if not url:
                return False, "URL missing"

            expected_size = self.info.get("size")  # Get size from database if available

            temp = os.path.join(tempfile.gettempdir(), f"{self.dlc}_{int(time.time())}_{threading.get_ident()}.zip")
            self.log("Starting download...")
            dlc_name = f"{self.dlc} - {self.info.get('name', 'Unknown')}"
            if self._progress_callback:
                self.dl.set_progress_callback(self._progress_callback)
            ok, reason = self.dl.download(url, temp, dlc_name, resume=self.dl.resume, expected_size=expected_size)
            if not ok:
                if self.stats:
                    self.stats.record_error(self.dlc, reason)
                return False, reason
            if not os.path.exists(temp):
                return False, "Downloaded file not found"
            file_size = os.path.getsize(temp)
            if file_size == 0:
                return False, "Downloaded file is empty"
            if file_size < 1024:
                return False, "Downloaded file too small (corrupted?)"
            self.log("Extracting...")
            ok, reason = self.ex.extract_zip(temp, self.game)
            if not ok:
                if self.stats:
                    self.stats.record_error(self.dlc, reason)
                return False, reason
            if self.stats:
                duration = time.time() - self._start_time
                self.stats.record_download(self.dlc, file_size, duration)
            self.log("Complete")
            return True, "OK"
        except Exception as e:
            if self.stats:
                self.stats.record_error(self.dlc, str(e))
            return False, str(e)
        finally:
            if temp and os.path.exists(temp) and self.dl.cleanup:
                try:
                    os.remove(temp)
                except:
                    pass


class MultiPartInstaller:
    def __init__(self, dlc_id, info, game_path, downloader, extractor, seven_path, logger, stats=None):
        self.dlc = dlc_id
        self.info = info
        self.game = game_path
        self.dl = downloader
        self.ex = extractor
        self.seven = seven_path
        self.logger = logger
        self.stats = stats
        self._progress_callback = None
        self._start_time = None

    def set_progress_callback(self, callback):
        self._progress_callback = callback

    def log(self, text, level="INFO"):
        if self.logger:
            self.logger.log(f"{self.dlc}: {text}", level)

    def run(self):
        downloaded_files = []
        total_size = 0
        try:
            self._start_time = time.time()
            if not self.seven or not os.path.exists(self.seven):
                return False, "7z.exe not found"
            parts = self.info.get("parts", [])
            if not parts:
                return False, "No parts defined"
            total_parts = len(parts)
            for i, url in enumerate(parts):
                name = f"{self.dlc}_{threading.get_ident()}.7z.{str(i+1).zfill(3)}"
                out = os.path.join(tempfile.gettempdir(), name)
                self.log(f"Downloading part {i+1}/{total_parts}...")
                dlc_name = f"{self.dlc} Part {i+1}"
                part_weight = 100.0 / total_parts
                current_base = i * part_weight
                if self._progress_callback:
                    def part_progress(progress, downloaded, total, base=current_base, weight=part_weight):
                        total_progress = base + (progress * weight / 100)
                        self._progress_callback(total_progress, downloaded, total)
                    self.dl.set_progress_callback(part_progress)
                ok, reason = self.dl.download(url, out, dlc_name, resume=self.dl.resume)
                if not ok:
                    for f in downloaded_files:
                        try:
                            os.remove(f)
                        except:
                            pass
                    if self.stats:
                        self.stats.record_error(self.dlc, f"Part {i+1} failed: {reason}")
                    return False, f"Part {i+1} failed: {reason}"
                if not os.path.exists(out):
                    return False, f"Part {i+1} not found after download"
                part_size = os.path.getsize(out)
                if part_size == 0:
                    return False, f"Part {i+1} is empty"
                total_size += part_size
                downloaded_files.append(out)
            part1 = downloaded_files[0]
            self.log("Extracting multipart archive...")
            ok, reason = self.ex.extract_7z(self.seven, part1, self.game)
            if not ok:
                if self.stats:
                    self.stats.record_error(self.dlc, reason)
                return False, reason
            if self.stats:
                duration = time.time() - self._start_time
                self.stats.record_download(self.dlc, total_size, duration)
            self.log("Complete")
            return True, "OK"
        except Exception as e:
            if self.stats:
                self.stats.record_error(self.dlc, str(e))
            return False, str(e)
        finally:
            for f in downloaded_files:
                try:
                    if os.path.exists(f) and self.dl.cleanup:
                        os.remove(f)
                except:
                    pass