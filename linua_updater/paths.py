"""Centralized application data paths.

Every class that used to hardcode ``Path.home() / "AppData" / "Local" / "LinuaUpdater"``
now resolves its files through :class:`AppPaths`.
"""

from pathlib import Path


class AppPaths:
    """Resolved locations of all persistent files under ``%LOCALAPPDATA%\\LinuaUpdater``."""

    BASE_DIR = Path.home() / "AppData" / "Local" / "LinuaUpdater"
    LOG_DIR = BASE_DIR / "logs"

    CONFIG_FILE = BASE_DIR / "config.json"
    UPDATE_CACHE_FILE = BASE_DIR / "update_cache.json"
    DIAG_CACHE_FILE = BASE_DIR / "diag_cache.json"
    DOWNLOAD_QUEUE_FILE = BASE_DIR / "download_queue.json"
    DOWNLOAD_STATE_FILE = BASE_DIR / "download_state.json"

    LOG_FILE = LOG_DIR / "updater.log"

    # Cache lifetimes (seconds).
    UPDATE_CACHE_DURATION = 129600      # 36 hours
    DIAG_CACHE_DURATION = 10800         # 3 hours
    DOWNLOAD_STATE_DURATION = 86400     # 24 hours

    @classmethod
    def ensure(cls) -> None:
        """Create the base and log directories if they do not exist."""
        cls.BASE_DIR.mkdir(parents=True, exist_ok=True)
        cls.LOG_DIR.mkdir(parents=True, exist_ok=True)