import json
import time
from typing import Any, Dict, Optional

import requests
from PyQt6.QtCore import QObject, pyqtSignal

from linua_updater.constants import APP_VERSION, DEFAULT_VERSION_CHECK_URL
from linua_updater.logging_util import ImprovedLogger
from linua_updater.paths import AppPaths


class UpdateChecker(QObject):
    update_available = pyqtSignal(str, str)
    no_update = pyqtSignal()
    check_failed = pyqtSignal(str)

    def __init__(self, logger: Optional[ImprovedLogger] = None, version_url: Optional[str] = None) -> None:
        super().__init__()
        self.logger = logger
        self.version_url = version_url or DEFAULT_VERSION_CHECK_URL
        self.cache_file = AppPaths.UPDATE_CACHE_FILE
        self.cache_duration = AppPaths.UPDATE_CACHE_DURATION

    def log(self, text: str, level: str = "INFO") -> None:
        if self.logger:
            self.logger.log(text, level)

    def _load_cache(self) -> Optional[Dict[str, Any]]:
        """Load cached update check result"""
        try:
            if self.cache_file.exists():
                with open(self.cache_file) as f:
                    cache: Dict[str, Any] = json.load(f)
                    cached_time = cache.get("timestamp", 0)
                    current_time = time.time()

                    # Check if cache is still valid
                    if current_time - cached_time < self.cache_duration:
                        return cache
        except:
            pass
        return None

    def _save_cache(self, latest_version: str, download_url: str) -> None:
        """Save update check result to cache"""
        try:
            AppPaths.ensure()
            cache = {"timestamp": time.time(), "latest_version": latest_version, "download_url": download_url}
            with open(self.cache_file, "w") as f:
                json.dump(cache, f)
        except Exception as e:
            self.log(f"Failed to save update cache: {e}", "DEBUG")

    def check_for_updates(self) -> None:
        """Check for updates using version.json (no API rate limits)"""
        try:
            # Try to use cached result first
            cache = self._load_cache()
            if cache:
                latest_version = cache.get("latest_version", "")
                download_url = cache.get("download_url", "")
                self.log(f"Using cached update info (age: {int((time.time() - cache['timestamp']) / 60)} min)", "DEBUG")

                if latest_version and self._compare_versions(latest_version, APP_VERSION):
                    self.update_available.emit(latest_version, download_url)
                else:
                    self.no_update.emit()
                return

            # Perform actual check
            self.log("Checking for updates...", "INFO")
            response = requests.get(self.version_url, timeout=10)

            if response.status_code == 200:
                data = response.json()
                latest_version = data.get("version", "").replace("v", "")
                download_url = data.get("download_url", "")

                self.log(f"Latest version: {latest_version}, Current: {APP_VERSION}", "DEBUG")

                # Save to cache
                self._save_cache(latest_version, download_url)

                if latest_version and self._compare_versions(latest_version, APP_VERSION):
                    self.update_available.emit(latest_version, download_url)
                else:
                    self.no_update.emit()
            else:
                self.check_failed.emit(f"HTTP {response.status_code}")

        except requests.exceptions.Timeout:
            self.check_failed.emit("Timeout")
        except requests.exceptions.ConnectionError:
            self.check_failed.emit("Connection error")
        except Exception as e:
            self.check_failed.emit(str(e))

    def _compare_versions(self, latest: str, current: str) -> bool:
        """Compare version strings (returns True if latest > current)"""
        try:
            latest_parts = [int(x) for x in latest.split(".")]
            current_parts = [int(x) for x in current.split(".")]

            for number_from_latest, number_from_current in zip(latest_parts, current_parts):
                if number_from_latest > number_from_current:
                    return True
                elif number_from_latest < number_from_current:
                    return False

            return len(latest_parts) > len(current_parts)
        except:
            return False
