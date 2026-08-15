"""Centralized application data paths.

Every class that used to hardcode ``Path.home() / "AppData" / "Local" / "LinuaUpdater"``
now resolves its files through :class:`AppPaths`.

The base directory resolves per platform:

* **Windows:** ``%LOCALAPPDATA%\\LinuaUpdater`` (honoring the ``LOCALAPPDATA`` env var,
  falling back to ``Path.home() / "AppData" / "Local"``). Windows keeps the legacy
  title-case ``LinuaUpdater`` folder for backward compatibility.
* **macOS:** ``~/Library/Application Support/LinuaUpdater``.
* **Linux/other POSIX:** ``$XDG_DATA_HOME/linua-updater``, falling back to
  ``~/.local/share/linua-updater`` when ``XDG_DATA_HOME`` is unset (XDG Base Directory spec).

Resolution goes through :func:`_default_base_dir` so tests can monkeypatch
``os.environ`` / ``Path.home()`` and re-derive the same logic.
"""

import os
import sys
from pathlib import Path


def _default_base_dir() -> Path:
    """Resolve the platform-appropriate application data directory."""
    if sys.platform == "win32":
        local_appdata = os.environ.get("LOCALAPPDATA")
        if local_appdata:
            return Path(local_appdata) / "LinuaUpdater"
        return Path.home() / "AppData" / "Local" / "LinuaUpdater"

    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "LinuaUpdater"

    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    if xdg_data_home:
        return Path(xdg_data_home) / "linua-updater"
    return Path.home() / ".local" / "share" / "linua-updater"


class AppPaths:
    """Resolved locations of all persistent files under the platform base dir.

    Windows uses the legacy ``%LOCALAPPDATA%\\LinuaUpdater``, macOS uses
    ``~/Library/Application Support/LinuaUpdater`` and Linux uses the XDG
    ``linua-updater`` data directory.
    """

    BASE_DIR = _default_base_dir()
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