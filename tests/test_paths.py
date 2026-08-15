"""Cross-platform tests for AppPaths base directory resolution.

The module recomputes ``AppPaths.BASE_DIR`` at import time from the current
``os.environ`` / ``Path.home()`` state, so these tests control those values and
reload ``linua_updater.paths`` to make the class attributes recompute.
"""

import importlib
import sys

import pytest

import linua_updater.paths as paths_module
from linua_updater.paths import AppPaths, _default_base_dir


@pytest.fixture(autouse=True)
def fresh_paths_module():
    """Ensure paths_module carries fresh, environment-correct values around each test."""
    importlib.reload(paths_module)
    yield
    importlib.reload(paths_module)


def _is_relative_to(path, base):
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


def test_derived_attributes_under_base_dir():
    base = AppPaths.BASE_DIR
    managed = [
        AppPaths.LOG_DIR,
        AppPaths.CONFIG_FILE,
        AppPaths.UPDATE_CACHE_FILE,
        AppPaths.DIAG_CACHE_FILE,
        AppPaths.DOWNLOAD_QUEUE_FILE,
        AppPaths.DOWNLOAD_STATE_FILE,
        AppPaths.LOG_FILE,
    ]
    for p in managed:
        assert _is_relative_to(p, base)
    assert AppPaths.LOG_DIR == AppPaths.BASE_DIR / "logs"
    assert AppPaths.LOG_FILE == AppPaths.LOG_DIR / "updater.log"


def test_default_base_dir_windows_helper(monkeypatch, tmp_path):
    """The win32 branch honors LOCALAPPDATA — verifiable deterministically on any host."""
    monkeypatch.setattr(paths_module.sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert _default_base_dir() == tmp_path / "LinuaUpdater"


def test_linux_xdg_data_home(monkeypatch, tmp_path):
    if sys.platform in ("win32", "darwin"):
        pytest.skip("XDG layout only applies on Linux/other POSIX")
    xdg = tmp_path / "xdg-data"
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(xdg))
    monkeypatch.setattr(paths_module.Path, "home", lambda: tmp_path / "home-fallback")
    importlib.reload(paths_module)
    assert paths_module.AppPaths.BASE_DIR == xdg / "linua-updater"


def test_linux_default_fallback(monkeypatch, tmp_path):
    if sys.platform in ("win32", "darwin"):
        pytest.skip("XDG layout only applies on Linux/other POSIX")
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setattr(paths_module.Path, "home", lambda: tmp_path)
    importlib.reload(paths_module)
    assert paths_module.AppPaths.BASE_DIR == tmp_path / ".local" / "share" / "linua-updater"


def test_macos_default(monkeypatch, tmp_path):
    if sys.platform != "darwin":
        pytest.skip("macOS layout only applies on darwin")
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setattr(paths_module.Path, "home", lambda: tmp_path)
    importlib.reload(paths_module)
    assert paths_module.AppPaths.BASE_DIR == tmp_path / "Library" / "Application Support" / "LinuaUpdater"


def test_windows_localappdata(monkeypatch, tmp_path):
    if sys.platform != "win32":
        pytest.skip("Windows layout only applies on win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    importlib.reload(paths_module)
    assert paths_module.AppPaths.BASE_DIR == tmp_path / "LinuaUpdater"


def test_windows_fallback_home(monkeypatch, tmp_path):
    if sys.platform != "win32":
        pytest.skip("Windows layout only applies on win32")
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setattr(paths_module.Path, "home", lambda: tmp_path)
    importlib.reload(paths_module)
    assert paths_module.AppPaths.BASE_DIR == tmp_path / "AppData" / "Local" / "LinuaUpdater"