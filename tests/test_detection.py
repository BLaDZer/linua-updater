import os
import re
import sys
from pathlib import Path

import pytest

from linua_updater.core.detection import GameDetector


@pytest.fixture
def linux_env(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    yield


def _write_vdf(vdf_path, path_entries):
    lines = [b'"libraryfolders"', b'{']
    default = path_entries[0][1]
    lines.append(b'    "path" "%b"' % os.fspath(default).encode())
    for key, value in path_entries:
        lines.append(b'    "%b"' % key.encode())
        lines.append(b'    {')
        lines.append(b'        "path" "%b"' % os.fspath(value).encode())
        lines.append(b'    }')
    lines.append(b'}')
    vdf_path.write_bytes(b"\n".join(lines) + b"\n")


def _make_game_tree(base, with_exe=True):
    game_folder = base / "steamapps" / "common" / "The Sims 4"
    if with_exe:
        bin_dir = game_folder / "Game" / "Bin"
        bin_dir.mkdir(parents=True)
        (bin_dir / "TS4_x64.exe").write_bytes(b"MZ")
    else:
        game_folder.mkdir(parents=True)
    return game_folder


def test_find_from_registry_returns_empty_off_win32(linux_env, monkeypatch):
    monkeypatch.delitem(sys.modules, "winreg", raising=False)
    assert GameDetector.find_from_registry() == []
    assert sys.modules.get("winreg") is None


def test_find_from_steam_parses_vdf_with_default_and_custom_libraries(linux_env, tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    default_lib = tmp_path / "default-steam"
    default_lib.mkdir()
    custom_lib = tmp_path / "custom"
    valid_game = _make_game_tree(custom_lib)
    _make_game_tree(default_lib, with_exe=False)

    vdf = tmp_path / ".local" / "share" / "Steam" / "steamapps" / "libraryfolders.vdf"
    vdf.parent.mkdir(parents=True)
    _write_vdf(vdf, [("1", default_lib), ("2", custom_lib)])

    found = GameDetector.find_from_steam()
    assert str(valid_game) in found
    assert len(found) == 1


def test_find_from_steam_resolves_proton_compatdata(linux_env, tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    custom_lib = tmp_path / "custom"
    game_folder = _make_game_tree(custom_lib, with_exe=False)
    (game_folder / "Game").mkdir()
    proton_exe = (
        custom_lib
        / "steamapps"
        / "compatdata"
        / "313340"
        / "pfx"
        / "drive_c"
        / "Program Files (x86)"
        / "The Sims 4"
        / "Game"
        / "Bin"
        / "TS4_x64.exe"
    )
    proton_exe.parent.mkdir(parents=True)
    proton_exe.write_bytes(b"MZ")

    vdf = tmp_path / ".local" / "share" / "Steam" / "steamapps" / "libraryfolders.vdf"
    vdf.parent.mkdir(parents=True)
    _write_vdf(vdf, [("1", custom_lib)])

    found = GameDetector.find_from_steam()
    assert str(game_folder) in found
    assert len(found) == 1


def test_find_game_skips_drive_scan_off_win32(linux_env, monkeypatch):
    monkeypatch.setattr(GameDetector, "find_from_registry", list)
    monkeypatch.setattr(GameDetector, "find_from_steam", list)

    real_exists = os.path.exists
    drive_style_calls = []

    def recording_exists(path):
        text = str(path)
        if re.match(r"^[A-Za-z]:", text):
            drive_style_calls.append(text)
        return real_exists(path)

    monkeypatch.setattr("linua_updater.core.detection.os.path.exists", recording_exists)

    assert GameDetector.find_game() is None
    assert drive_style_calls == []


def test_find_game_first_wins_order(linux_env, tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    registry_game = tmp_path / "registry-game"
    bin_dir = registry_game / "Game" / "Bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "TS4_x64.exe").write_bytes(b"MZ")

    steam_lib = tmp_path / "steam-lib"
    _make_game_tree(steam_lib, with_exe=True)

    vdf = tmp_path / ".local" / "share" / "Steam" / "steamapps" / "libraryfolders.vdf"
    vdf.parent.mkdir(parents=True)
    _write_vdf(vdf, [("1", steam_lib)])

    monkeypatch.setattr(GameDetector, "find_from_registry", lambda: [str(registry_game)])

    assert GameDetector.find_game() == str(registry_game)


def test_has_valid_exe_missing_path():
    assert GameDetector._has_valid_exe("/no/such") is False


def test_parse_steam_library_paths_missing_vdf(tmp_path):
    assert GameDetector._parse_steam_library_paths(tmp_path / "nope.vdf") == []


def test_parse_steam_library_paths_malformed(tmp_path):
    vdf = tmp_path / "garbage.vdf"
    vdf.write_bytes(b"\xff\xfe\x00\x01\x02\x03")
    assert GameDetector._parse_steam_library_paths(vdf) == []


def test_steam_vdf_candidates_darwin(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "darwin")
    assert GameDetector._steam_vdf_candidates(tmp_path) == [
        tmp_path / "Library" / "Application Support" / "Steam" / "steamapps" / "libraryfolders.vdf"
    ]


def test_find_game_returns_none_when_nothing_found(linux_env, monkeypatch):
    monkeypatch.setattr(GameDetector, "find_from_registry", list)
    monkeypatch.setattr(GameDetector, "find_from_steam", list)

    assert GameDetector.find_game() is None