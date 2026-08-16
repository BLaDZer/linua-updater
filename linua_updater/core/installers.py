import os
import tempfile
import threading
import time

from linua_updater.core.checksum import verify_file_checksums
from linua_updater.utils.sevenzip import SevenZipFinder


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
            ok, reason = self.dl.download(url, temp, dlc_name, resume=self.dl.resume_enabled, expected_size=expected_size)
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
            errors = verify_file_checksums(temp, self.info.get("checksum"))
            if errors:
                for error in errors:
                    self.log(error, "WARNING")
                if self.stats:
                    self.stats.record_error(self.dlc, "; ".join(errors))
                return False, "; ".join(errors)
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
                return False, "7-Zip not found"
            parts = self.info.get("parts", [])
            if not parts:
                return False, "No parts defined"
            total_parts = len(parts)
            self.log(f"Downloading {self.dlc}: {total_parts} parts")
            for i, url in enumerate(parts):
                name = f"{self.dlc}_{threading.get_ident()}.7z.{str(i+1).zfill(3)}"
                out = os.path.join(tempfile.gettempdir(), name)
                dlc_name = f"{self.dlc} Part {i+1}"
                part_weight = 100.0 / total_parts
                current_base = i * part_weight
                if self._progress_callback:
                    def part_progress(progress, downloaded, total, base=current_base, weight=part_weight):
                        total_progress = base + (progress * weight / 100)
                        self._progress_callback(total_progress, downloaded, total)
                    self.dl.set_progress_callback(part_progress)
                ok, reason = self.dl.download(url, out, dlc_name, resume=self.dl.resume_enabled)
                if not ok:
                    self.log(f"Part {i+1}/{total_parts} failed: {reason}", "WARNING")
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


class TorrentInstaller:
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
            magnet = self.info.get("magnet")
            if not magnet:
                return False, "Magnet missing"
            temp = tempfile.mkdtemp(prefix=f"{self.dlc}_torrent_")
            dlc_name = f"{self.dlc} - {self.info.get('name', 'Unknown')}"
            expected_size = self.info.get("size")
            if self._progress_callback:
                self.dl.set_progress_callback(lambda progress, downloaded, total: self._progress_callback(progress, downloaded, total))
            ok, result = self.dl.download(magnet, temp, dlc_name=dlc_name, expected_size=expected_size)
            if not ok:
                if self.stats:
                    self.stats.record_error(self.dlc, result)
                return False, result
            if not isinstance(result, list) or not result:
                return False, "No files downloaded from torrent"
            primary = None
            size_target = self.info.get("size")
            if size_target:
                candidates = [(f, os.path.getsize(f)) for f in result if os.path.isfile(f)]
                for f, sz in candidates:
                    if sz == size_target:
                        primary = f
                        break
            if not primary:
                candidates = [(f, os.path.getsize(f)) for f in result if os.path.isfile(f)]
                if candidates:
                    primary = max(candidates, key=lambda x: x[1])[0]
            if not primary or not os.path.isfile(primary):
                return False, "Primary archive not found"
            file_size = os.path.getsize(primary)
            if file_size == 0:
                return False, "Downloaded file is empty"
            errors = verify_file_checksums(primary, self.info.get("checksum"))
            if errors:
                for error in errors:
                    self.log(error, "WARNING")
                if self.stats:
                    self.stats.record_error(self.dlc, "; ".join(errors))
                return False, "; ".join(errors)
            self.log("Extracting...")
            name = os.path.basename(primary).lower()
            if name.endswith(".zip"):
                ok, reason = self.ex.extract_zip(primary, self.game)
            elif name.endswith((".7z", ".001")):
                seven_finder = SevenZipFinder(self.logger)
                seven_path = seven_finder.find()
                if not seven_path:
                    return False, "7-Zip not found"
                ok, reason = self.ex.extract_7z(seven_path, primary, self.game)
            else:
                return False, f"Unsupported torrent archive: {os.path.basename(primary)}"
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
            if temp and os.path.exists(temp):
                try:
                    import shutil
                    shutil.rmtree(temp)
                except:
                    pass