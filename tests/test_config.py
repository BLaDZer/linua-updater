import pytest

from linua_updater.paths import AppPaths
from linua_updater.utils.config import ConfigManager


@pytest.fixture
def isolated_app_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(AppPaths, "BASE_DIR", tmp_path)
    monkeypatch.setattr(AppPaths, "CONFIG_FILE", tmp_path / "config.json")
    return tmp_path


def test_defaults_created(isolated_app_paths):
    c = ConfigManager()
    assert c.get("game_path") == ""
    assert c.get_settings()["max_threads"] == 3


def test_roundtrip(isolated_app_paths):
    c = ConfigManager()
    c.set("game_path", "/some/game")
    c.set("settings", {"max_threads": 5, "use_proxy": False})
    c2 = ConfigManager()
    assert c2.get("game_path") == "/some/game"
    assert c2.get_settings() == {"max_threads": 5, "use_proxy": False}


def test_get_network_defaults(isolated_app_paths):
    net = ConfigManager().get_network()
    assert net["version_check_url"].startswith("https://")
    assert isinstance(net["proxy_ports"], list)
    assert isinstance(net["mirrors"], dict)