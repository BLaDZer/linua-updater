import os
import types
from pathlib import Path

from linua_updater.core.detection import GameDetector
from linua_updater.ui.main_window import (
    LinuaUI,
    _browse_default_dir,
    _changed_valid_path,
    _game_folder_state,
    _game_placeholder,
    _persistable_game_path,
    _resolve_detected_path,
    _startup_detect_message,
    _ui_font_family,
)


class _FakeConfig:
    def __init__(self):
        self.calls = []

    def set(self, key, value):
        self.calls.append((key, value))


def test_browse_default_dir_empty_uses_home():
    assert _browse_default_dir("") == str(Path.home())


def test_browse_default_dir_keeps_given_path():
    assert _browse_default_dir("/some/game") == "/some/game"


def test_game_placeholder_windows_example():
    placeholder = _game_placeholder("win32")
    assert "Steam" in placeholder
    assert "The Sims 4" in placeholder


def test_game_placeholder_linux_is_generic():
    placeholder = _game_placeholder("linux")
    assert "C:" not in placeholder
    assert "Program Files" not in placeholder


def test_game_placeholder_darwin_is_generic():
    placeholder = _game_placeholder("darwin")
    assert "C:" not in placeholder
    assert "Program Files" not in placeholder


def test_ui_font_family_has_generic_fallbacks():
    family = _ui_font_family()
    assert "sans-serif" in family
    assert "Noto Sans" in family


def test_persistable_game_path_empty_is_none():
    assert _persistable_game_path("") is None


def test_persistable_game_path_nonexistent_is_none():
    assert _persistable_game_path("/no/such/game/folder") is None


def test_persistable_game_path_dir_without_exe_is_none(tmp_path):
    assert _persistable_game_path(str(tmp_path)) is None


def test_persistable_game_path_valid_returns_stripped(tmp_path):
    (tmp_path / "Game" / "Bin").mkdir(parents=True)
    (tmp_path / "Game" / "Bin" / "TS4_x64.exe").touch()
    assert _persistable_game_path(f"  {tmp_path}  ") == str(tmp_path)


def test_game_folder_state_empty_is_false():
    assert _game_folder_state("") is False


def test_game_folder_state_whitespace_is_false():
    assert _game_folder_state("   ") is False


def test_game_folder_state_dir_without_exe_is_false(tmp_path):
    assert _game_folder_state(str(tmp_path)) is False


def test_game_folder_state_nonexistent_is_false():
    assert _game_folder_state("/no/such/game/folder") is False


def test_game_folder_state_valid_is_true(tmp_path):
    (tmp_path / "Game" / "Bin").mkdir(parents=True)
    (tmp_path / "Game" / "Bin" / "TS4_x64.exe").touch()
    assert _game_folder_state(str(tmp_path)) is True


def test_changed_valid_path_empty_text_is_none():
    assert _changed_valid_path("", "") is None


def test_changed_valid_path_unchanged_stored_is_none(tmp_path):
    (tmp_path / "Game" / "Bin").mkdir(parents=True)
    (tmp_path / "Game" / "Bin" / "TS4_x64.exe").touch()
    assert _changed_valid_path(str(tmp_path), str(tmp_path)) is None


def test_changed_valid_path_different_stored_returns_path(tmp_path):
    (tmp_path / "Game" / "Bin").mkdir(parents=True)
    (tmp_path / "Game" / "Bin" / "TS4_x64.exe").touch()
    assert _changed_valid_path(str(tmp_path), "some/unrelated/value") == str(tmp_path)


def test_changed_valid_path_empty_stored_returns_path(tmp_path):
    (tmp_path / "Game" / "Bin").mkdir(parents=True)
    (tmp_path / "Game" / "Bin" / "TS4_x64.exe").touch()
    assert _changed_valid_path(str(tmp_path), "") == str(tmp_path)


def test_changed_valid_path_strips_whitespace_before_comparing(tmp_path):
    (tmp_path / "Game" / "Bin").mkdir(parents=True)
    (tmp_path / "Game" / "Bin" / "TS4_x64.exe").touch()
    path = str(tmp_path)
    padding = "  \t"
    assert _changed_valid_path(f"{padding}{path}{padding}", f"{padding}{path}{padding}") is None


def test_resolve_detected_path_valid_saved_skips_scan(tmp_path, monkeypatch):
    (tmp_path / "Game" / "Bin").mkdir(parents=True)
    (tmp_path / "Game" / "Bin" / "TS4_x64.exe").touch()

    def fail_find_game():
        raise AssertionError("GameDetector.find_game() should not be called")

    monkeypatch.setattr(GameDetector, "find_game", fail_find_game)
    assert _resolve_detected_path(str(tmp_path)) == str(tmp_path)


def test_resolve_detected_path_empty_delegates_to_scan(monkeypatch):
    monkeypatch.setattr(GameDetector, "find_game", lambda: "/fake/game")
    assert _resolve_detected_path("") == "/fake/game"


def test_resolve_detected_path_empty_scan_none_is_none(monkeypatch):
    monkeypatch.setattr(GameDetector, "find_game", lambda: None)
    assert _resolve_detected_path("") is None


def test_resolve_detected_path_dir_without_exe_delegates_to_scan(tmp_path, monkeypatch):
    calls = []

    def fake_find_game():
        calls.append(True)
        return "/fake/game"

    monkeypatch.setattr(GameDetector, "find_game", fake_find_game)
    assert _resolve_detected_path(str(tmp_path)) == "/fake/game"
    assert calls == [True]


def test_startup_detect_message_valid_folder(tmp_path):
    (tmp_path / "Game" / "Bin").mkdir(parents=True)
    (tmp_path / "Game" / "Bin" / "TS4_x64.exe").touch()
    assert _startup_detect_message(str(tmp_path)) == f"Using saved game folder: {tmp_path}"


def test_startup_detect_message_empty_states_no_saved():
    assert _startup_detect_message("") != ""
    assert _startup_detect_message("   ") != ""
    for message in (_startup_detect_message(""), _startup_detect_message("   ")):
        assert "Auto Detect" in message
        assert "manually" in message


def test_startup_detect_message_invalid_folder():
    message = _startup_detect_message("/no/such/game/folder")
    assert message != ""
    assert "not a valid game path" in message
    assert "Auto Detect" in message


def test_startup_detect_message_whitespace_only():
    message = _startup_detect_message("  \t  ")
    assert "No game folder saved" in message
    assert "Auto Detect" in message


def test_game_folder_state_dir_with_trailing_slash(tmp_path):
    (tmp_path / "Game" / "Bin").mkdir(parents=True)
    (tmp_path / "Game" / "Bin" / "TS4_x64.exe").touch()
    assert _game_folder_state(str(tmp_path) + os.sep) is True


def test_persist_valid_path_returns_none_for_invalid():
    fake_config = _FakeConfig()
    obj = types.SimpleNamespace(config=fake_config)
    assert LinuaUI._persist_valid_path(obj, "/no/such/game") is None
    assert fake_config.calls == []


def test_persist_valid_path_persists_and_returns(tmp_path):
    (tmp_path / "Game" / "Bin").mkdir(parents=True)
    (tmp_path / "Game" / "Bin" / "TS4_x64.exe").touch()
    fake_config = _FakeConfig()
    obj = types.SimpleNamespace(config=fake_config)
    path = LinuaUI._persist_valid_path(obj, str(tmp_path))
    assert path == str(tmp_path)
    assert fake_config.calls == [("game_path", str(tmp_path))]