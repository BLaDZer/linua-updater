from pathlib import Path

from linua_updater.ui.main_window import _browse_default_dir, _game_placeholder, _ui_font_family


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