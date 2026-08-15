import ctypes
import pathlib
import shutil
import sys

import pytest

from linua_updater.utils.admin import AdminElevator


def test_is_admin_returns_bool():
    assert isinstance(AdminElevator.is_admin(), bool)


def test_requires_admin_writable(tmp_path):
    assert AdminElevator.requires_admin(str(tmp_path)) is False


def test_requires_admin_protected_when_write_fails(tmp_path, monkeypatch):
    def boom(self, *args, **kwargs):
        raise OSError("permission denied")

    monkeypatch.setattr(pathlib.Path, "touch", boom)
    assert AdminElevator.requires_admin(str(tmp_path)) is True


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX prefix fast-path only")
def test_requires_admin_posix_protected_prefix():
    assert AdminElevator.requires_admin("/usr/local") is True
    assert AdminElevator.requires_admin("/opt/linua") is True


def test_matches_win32_protected():
    assert AdminElevator._matches_win32_protected(r"C:\Program Files\Steam\whatever") is True
    assert AdminElevator._matches_win32_protected(r"C:\program files_whatever") is False
    assert AdminElevator._matches_win32_protected(r"C:\Games\The Sims 4") is False


def test_matches_win32_protected_boundaries():
    assert AdminElevator._matches_win32_protected(r"C:\Program Files") is True
    assert AdminElevator._matches_win32_protected(r"C:\Program Files\Steam") is True
    assert AdminElevator._matches_win32_protected("C:\\Program Files\\Steam\\") is True
    assert AdminElevator._matches_win32_protected(r"C:\program files\x") is True


def test_elevate_never_raises_and_falls_back(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: None)
    if sys.platform == "win32":
        monkeypatch.setattr(ctypes, "windll", None, raising=False)
    try:
        result = AdminElevator.elevate()
    except Exception:
        pytest.fail("elevate() raised")
    assert isinstance(result, bool)