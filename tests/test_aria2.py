import os
import sys
import types

import linua_updater.utils.aria2 as aria2_module
from linua_updater.utils.aria2 import Aria2Finder


class FakeLogger:
    def __init__(self):
        self.logs = []

    def log(self, text, level="INFO"):
        self.logs.append((text, level))


def _stub_shutil(monkeypatch, which_fn):
    monkeypatch.setattr(aria2_module, "shutil", types.SimpleNamespace(which=which_fn))


def test_executable_names_per_platform(monkeypatch):
    finder = Aria2Finder(FakeLogger())
    monkeypatch.setattr(sys, "platform", "win32")
    assert finder._executable_names() == ["aria2c.exe"]
    monkeypatch.setattr(sys, "platform", "linux")
    assert finder._executable_names() == ["aria2c"]
    monkeypatch.setattr(sys, "platform", "darwin")
    assert finder._executable_names() == ["aria2c"]


def test_finds_aria2c_via_which(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(sys, "argv", [str(tmp_path / "app")])
    _stub_shutil(monkeypatch, lambda name: "/usr/bin/aria2c" if name == "aria2c" else None)
    assert Aria2Finder(FakeLogger()).find() == "/usr/bin/aria2c"


def test_meipass_wins_over_path(tmp_path, monkeypatch):
    aria2c = tmp_path / "aria2c"
    aria2c.write_text("")
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(sys, "argv", [str(tmp_path / "app")])
    monkeypatch.setattr(Aria2Finder, "POSSIBLE_LOCATIONS", [])
    _stub_shutil(monkeypatch, lambda name: "/fake/from/path")
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert Aria2Finder(FakeLogger()).find() == str(aria2c)


def test_exe_dir_scan_wins_over_path(tmp_path, monkeypatch):
    aria2c = tmp_path / "aria2c"
    aria2c.write_text("")
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(sys, "argv", [str(tmp_path / "app")])
    monkeypatch.setattr(Aria2Finder, "POSSIBLE_LOCATIONS", [])
    _stub_shutil(monkeypatch, lambda name: "/fake/from/path")
    assert Aria2Finder(FakeLogger()).find() == str(aria2c)


def test_not_found_logs_once_and_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(sys, "argv", [str(tmp_path / "app")])
    monkeypatch.setattr(Aria2Finder, "POSSIBLE_LOCATIONS", [])
    _stub_shutil(monkeypatch, lambda name: None)
    monkeypatch.setattr(os, "environ", {"PATH": str(tmp_path / "empty")})
    logger = FakeLogger()
    assert Aria2Finder(logger).find() is None
    assert len(logger.logs) == 1
    assert "aria2c not found" in logger.logs[0][0]


def test_windows_exe_name(tmp_path, monkeypatch):
    aria2c = tmp_path / "aria2c.exe"
    aria2c.write_text("")
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(sys, "argv", [str(tmp_path / "app.exe")])
    monkeypatch.setattr(Aria2Finder, "POSSIBLE_LOCATIONS", [])
    _stub_shutil(monkeypatch, lambda name: None)
    assert Aria2Finder(FakeLogger()).find() == str(aria2c)


def test_possible_locations_win_over_which(tmp_path, monkeypatch):
    aria2c = tmp_path / "aria2c"
    aria2c.write_text("")
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(sys, "argv", [str(tmp_path / "app")])
    monkeypatch.setattr(Aria2Finder, "POSSIBLE_LOCATIONS", [str(aria2c)])
    _stub_shutil(monkeypatch, lambda name: "/fake/from/path")
    assert Aria2Finder(FakeLogger()).find() == str(aria2c)
