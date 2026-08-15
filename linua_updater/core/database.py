import copy
import json
import time

import requests

from linua_updater.constants import DEFAULT_DATABASE_FALLBACK, DEFAULT_DATABASE_URL, SIZE_ESTIMATES
from linua_updater.paths import AppPaths


class DLCDatabase:
    """DLC catalog backed by the remote ``database.json`` payload.

    The remote file is treated as a generic database: the whole payload (any
    keys such as ``version``, ``updatedAt``, ``dlc``, ...) is cached verbatim
    under the app state folder. Today only the ``dlc`` key is consumed, but
    future keys can be read straight from :attr:`data` without restructuring.

    Resolution order:

    1. a fresh cache file (younger than ``cache_duration``) is used as-is;
    2. otherwise the remote URL is fetched and, if valid, stored to cache;
    3. otherwise a stale but parseable cache is reused;
    4. finally the hardcoded :data:`~linua_updater.constants.DEFAULT_DATABASE_FALLBACK`.
    """

    def __init__(self, db_url=None, cache_file=None, cache_duration=None):
        self.db_url = db_url or DEFAULT_DATABASE_URL
        self.cache_file = cache_file or AppPaths.DATABASE_CACHE_FILE
        self.cache_duration = cache_duration if cache_duration is not None else AppPaths.DATABASE_CACHE_DURATION
        self.data = self._load()
        self.dlc = self.data.get("dlc", {})
        self._apply_sizes()

    def refresh(self):
        """Invalidate the cache file and reload, re-running the resolution order.
        Returns True when the payload came from the remote server."""
        try:
            if self.cache_file.exists():
                self.cache_file.unlink()
        except OSError:
            pass
        self.data = self._load()
        self.dlc = self.data.get("dlc", {})
        self._apply_sizes()
        return self.source == "remote"

    def _apply_sizes(self):
        for dlc_id, info in self.dlc.items():
            if dlc_id in SIZE_ESTIMATES:
                info['size'] = SIZE_ESTIMATES[dlc_id]

    def _load(self):
        fresh = self._load_cache(fresh_only=True)
        if fresh is not None:
            self.source = "cache"
            return fresh
        downloaded = self._download()
        if downloaded is not None:
            self._save_cache(downloaded)
            self.source = "remote"
            return downloaded
        stale = self._load_cache(fresh_only=False)
        if stale is not None:
            self.source = "stale_cache"
            return stale
        self.source = "fallback"
        return copy.deepcopy(DEFAULT_DATABASE_FALLBACK)

    def _load_cache(self, fresh_only=True):
        """Return the cached payload, or ``None`` when missing/invalid/stale."""
        try:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._cache_age_h = int((time.time() - data.get("timestamp", 0)) / 3600)
            if fresh_only and time.time() - data.get("timestamp", 0) >= self.cache_duration:
                return None
            payload = data.get("database")
            return payload if self._is_valid(payload) else None
        except Exception:
            return None

    def _download(self):
        try:
            response = requests.get(self.db_url, timeout=10)
            if response.status_code == 200:
                payload = response.json()
                if self._is_valid(payload):
                    return payload
        except Exception:
            pass
        return None

    def _save_cache(self, payload):
        try:
            AppPaths.ensure()
            cache = {"timestamp": time.time(), "database": payload}
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False)
        except Exception:
            pass

    @staticmethod
    def _is_valid(payload):
        if not isinstance(payload, dict):
            return False
        dlc = payload.get("dlc")
        return isinstance(dlc, dict) and len(dlc) > 0

    def all(self):
        return self.dlc

    def get(self, dlc_id):
        return self.dlc.get(dlc_id)

    def get_key(self, key, default=None):
        """Return any top-level key of the remote database payload (e.g. ``version``)."""
        return self.data.get(key, default)

    def source_description(self):
        """One ready-to-log sentence naming which branch produced the payload."""
        if self.source == "remote":
            return f"DLC database: refreshed from remote ({self.db_url})"
        if self.source == "stale_cache":
            return f"DLC database: loaded from stale cache ({self.cache_file}, ~{self._cache_age_h} h old)"
        if self.source == "fallback":
            return "DLC database: using built-in fallback data"
        return f"DLC database: loaded from cache ({self.cache_file})"