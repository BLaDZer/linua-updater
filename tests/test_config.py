import json

import pytest

from linua_updater.constants import DEFAULT_REGION_API, DEFAULT_VERSION_CHECK_URL
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


def test_corrupted_config_recovered_with_defaults(isolated_app_paths):
    (isolated_app_paths / "config.json").write_text("{not valid json", encoding="utf-8")
    c = ConfigManager()
    assert c.get("game_path") == ""
    assert c.get_settings()["max_threads"] == 3
    saved = json.loads((isolated_app_paths / "config.json").read_text(encoding="utf-8"))
    assert saved["game_path"] == ""


def test_get_network_merges_only_falsy(isolated_app_paths):
    c = ConfigManager()
    c.set("network", {"version_check_url": "", "region_api": ""})
    net = c.get_network()
    assert net["version_check_url"] == DEFAULT_VERSION_CHECK_URL
    assert net["region_api"] == DEFAULT_REGION_API


def test_get_network_keeps_custom_values(isolated_app_paths):
    c = ConfigManager()
    c.set("network", {
        "version_check_url": "https://custom.example.com/v.json",
        "region_api": "https://custom.example.com/geo",
        "proxy_ports": [1, 2],
        "mirrors": {"a": "b"},
    })
    net = c.get_network()
    assert net["version_check_url"] == "https://custom.example.com/v.json"
    assert net["region_api"] == "https://custom.example.com/geo"
    assert net["proxy_ports"] == [1, 2]
    assert net["mirrors"] == {"a": "b"}


def test_set_overwrites_and_persists(isolated_app_paths):
    c = ConfigManager()
    c.set("game_path", "/first")
    c.set("game_path", "/second")
    c2 = ConfigManager()
    assert c2.get("game_path") == "/second"