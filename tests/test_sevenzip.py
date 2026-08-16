import os
import sys
import types

import linua_updater.utils.sevenzip as sevenzip_module
from linua_updater.utils.sevenzip import SevenZipFinder


class FakeLogger:
    def __init__(self):
        self.logs = []

    def log(self, text, level="INFO"):
        self.logs.append((text, level))


def _stub_shutil(monkeypatch, which_fn):
    monkeypatch.setattr(sevenzip_module, "shutil", types.SimpleNamespace(which=which_fn))


def _no_local_7z(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "argv", [str(tmp_path / "app")])
    monkeypatch.setattr(SevenZipFinder, "POSSIBLE_LOCATIONS", [])
    _stub_shutil(monkeypatch, lambda name: None)
    monkeypatch.setattr(os, "environ", {"PATH": str(tmp_path / "empty")})


def test_executable_names_per_platform(monkeypatch):
    finder = SevenZipFinder(FakeLogger())
    monkeypatch.setattr(sys, "platform", "win32")
    assert finder._executable_names() == ["7z.exe", "7za.exe"]
    monkeypatch.setattr(sys, "platform", "linux")
    assert finder._executable_names() == ["7z", "7za", "7zz"]
    monkeypatch.setattr(sys, "platform", "darwin")
    assert finder._executable_names() == ["7z", "7za", "7zz"]


def test_finds_7z_exe_on_win32_via_which(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(sys, "argv", [str(tmp_path / "app")])
    monkeypatch.setattr(SevenZipFinder, "POSSIBLE_LOCATIONS", [])
    _stub_shutil(monkeypatch, lambda name: "/fake/7z.exe" if name == "7z.exe" else None)

    assert SevenZipFinder(FakeLogger()).find() == "/fake/7z.exe"


def test_finds_7zz_on_posix_via_which(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(sys, "argv", [str(tmp_path / "app")])
    monkeypatch.setattr(SevenZipFinder, "POSSIBLE_LOCATIONS", [])
    _stub_shutil(monkeypatch, lambda name: "/usr/local/7zz" if name == "7zz" else None)

    assert SevenZipFinder(FakeLogger()).find() == "/usr/local/7zz"


def test_possible_locations_win_over_path(tmp_path, monkeypatch):
    seven = tmp_path / "7z"
    seven.write_text("")
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(sys, "argv", [str(tmp_path / "app")])
    monkeypatch.setattr(SevenZipFinder, "POSSIBLE_LOCATIONS", [str(seven)])
    _stub_shutil(monkeypatch, lambda name: "/fake/from/path")

    assert SevenZipFinder(FakeLogger()).find() == str(seven)


def test_exe_dir_scan_wins_over_path(tmp_path, monkeypatch):
    sevenzz = tmp_path / "7zz"
    sevenzz.write_text("")
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(sys, "argv", [str(tmp_path / "app")])
    monkeypatch.setattr(SevenZipFinder, "POSSIBLE_LOCATIONS", [])
    _stub_shutil(monkeypatch, lambda name: "/fake/from/path")

    assert SevenZipFinder(FakeLogger()).find() == str(sevenzz)


def test_not_found_logs_once_and_returns_none(tmp_path, monkeypatch):
    _no_local_7z(monkeypatch, tmp_path)
    logger = FakeLogger()

    assert SevenZipFinder(logger).find() is None
    assert len(logger.logs) == 1
    assert "7-Zip not found" in logger.logs[0][0]


def test_manual_path_walk_finds_posix_binary(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    seven = bin_dir / "7zz"
    seven.write_text("")
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(sys, "argv", [str(tmp_path / "app")])
    monkeypatch.setattr(SevenZipFinder, "POSSIBLE_LOCATIONS", [])
    _stub_shutil(monkeypatch, lambda name: None)
    monkeypatch.setattr(os, "environ", {"PATH": str(bin_dir)})

    assert SevenZipFinder(FakeLogger()).find() == str(seven)


def test_meipass_wins_over_path(tmp_path, monkeypatch):
    sevenzz = tmp_path / "7zz"
    sevenzz.write_text("")
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(sys, "argv", [str(tmp_path / "app")])
    monkeypatch.setattr(SevenZipFinder, "POSSIBLE_LOCATIONS", [])
    _stub_shutil(monkeypatch, lambda name: "/fake/from/path")
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert SevenZipFinder(FakeLogger()).find() == str(sevenzz)