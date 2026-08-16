import json
import time

import pytest

from linua_updater.constants import DEFAULT_DATABASE_FALLBACK
from linua_updater.core.database import DLCDatabase
from linua_updater.paths import AppPaths


def _sample_payload():
    return {
        "version": "1.2.3",
        "updatedAt": "2026-08-15T00:00:00Z",
        "dlc": {
            "EP01": {"name": "Get to Work", "url": "https://example.com/EP01.zip"},
        },
    }


class FakeResponse:
    def __init__(self, status_code=200, data=None, raise_on_json=False):
        self.status_code = status_code
        self._data = data
        self._raise = raise_on_json

    def json(self):
        if self._raise:
            raise ValueError("invalid json")
        return self._data


@pytest.fixture
def isolated_db_env(tmp_path, monkeypatch):
    monkeypatch.setattr(AppPaths, "BASE_DIR", tmp_path)
    monkeypatch.setattr(AppPaths, "DATABASE_CACHE_FILE", tmp_path / "database_cache.json")
    monkeypatch.setattr(AppPaths, "DATABASE_CACHE_DURATION", 3600)

    def offline(url, timeout=10):
        return FakeResponse(404)

    monkeypatch.setattr("linua_updater.core.database.requests.get", offline)
    return tmp_path


@pytest.fixture
def cache_file(isolated_db_env):
    return AppPaths.DATABASE_CACHE_FILE


def _write_cache(path, payload, timestamp=None):
    path.write_text(
        json.dumps({"timestamp": timestamp if timestamp is not None else time.time(), "database": payload}),
        encoding="utf-8",
    )


def test_catalog_has_109_entries(isolated_db_env):
    db = DLCDatabase()
    assert len(db.all()) == 109


def test_size_enrichment_from_estimates(isolated_db_env):
    db = DLCDatabase()
    assert db.all()["EP01"].getSize() == 1900000000
    assert db.all()["EP21"].getSize() == 2553349168
    assert db.all()["SP70"].getSize() is None


def test_get(isolated_db_env):
    db = DLCDatabase()
    assert db.get("EP01").getName() == "Get to Work"
    assert db.get("DOES_NOT_EXIST") is None


def test_main_source_routing(isolated_db_env):
    db = DLCDatabase()
    ep01 = db.get("EP01")
    main = ep01.getMainDownloadSource()
    assert main is not None
    assert main.getType() == "url"
    assert main.getSource() == "https://raw.githubusercontent.com/BLaDZer/linua-updater/refs/heads/main/EP01.zip"
    assert ep01.getMirrors() == []


def test_fallback_ep06_parts_mirror(isolated_db_env):
    db = DLCDatabase()
    ep06 = db.get("EP06")
    main = ep06.getMainDownloadSource()
    assert main is not None
    assert main.getType() == "url"
    parts_mirrors = [m for m in ep06.getMirrors() if m.getType() == "parts"]
    assert len(parts_mirrors) == 1
    parts_mirror = parts_mirrors[0]
    assert parts_mirror.getPriority() == 0
    parts = parts_mirror.getParts()
    assert len(parts) == 7
    assert all(p.getType() == "url" for p in parts)


def test_fresh_cache_used_without_download(cache_file, monkeypatch):
    _write_cache(cache_file, _sample_payload())
    calls = []

    def fake_get(url, timeout=10):
        calls.append(url)
        return FakeResponse(404)

    monkeypatch.setattr("linua_updater.core.database.requests.get", fake_get)
    db = DLCDatabase()
    assert calls == []
    assert db.all()["EP01"].getName() == "Get to Work"
    assert db.data["version"] == "1.2.3"
    assert db.get_key("updatedAt") == "2026-08-15T00:00:00Z"
    assert db.source == "cache"
    message = db.source_description()
    assert str(db.cache_file) in message
    assert "loaded from cache" in message


def test_size_enrichment_applied_to_cached_data(cache_file):
    _write_cache(cache_file, {"dlc": {"EP01": {"name": "Get to Work", "url": "x"}}})
    db = DLCDatabase()
    assert db.all()["EP01"].getSize() == 1900000000


def test_expired_cache_triggers_download(cache_file, monkeypatch):
    _write_cache(cache_file, {"dlc": {"EP01": {"name": "old", "url": "x"}}}, timestamp=time.time() - 7200)
    calls = []

    def fake_get(url, timeout=10):
        calls.append(url)
        return FakeResponse(200, _sample_payload())

    monkeypatch.setattr("linua_updater.core.database.requests.get", fake_get)
    db = DLCDatabase()
    assert calls == [db.db_url]
    assert db.all()["EP01"].getName() == "Get to Work"
    saved = json.loads(cache_file.read_text(encoding="utf-8"))
    assert saved["database"]["version"] == "1.2.3"
    assert db.source == "remote"
    assert db.db_url in db.source_description()


def test_missing_cache_successful_download_writes_cache(cache_file, monkeypatch):
    monkeypatch.setattr(
        "linua_updater.core.database.requests.get",
        lambda url, timeout=10: FakeResponse(200, _sample_payload()),
    )
    db = DLCDatabase()
    assert db.all()["EP01"].getName() == "Get to Work"
    assert db.get_key("version") == "1.2.3"
    saved = json.loads(cache_file.read_text(encoding="utf-8"))
    assert saved["database"] == _sample_payload()
    assert saved["timestamp"] <= time.time()


def test_download_failure_stale_cache_used(cache_file):
    _write_cache(cache_file, {"dlc": {"EP01": {"name": "stale", "url": "x"}}}, timestamp=time.time() - 7200)
    db = DLCDatabase()
    assert db.all()["EP01"].getName() == "stale"
    assert db.source == "stale_cache"
    message = db.source_description()
    assert str(db.cache_file) in message
    assert "~2 h old" in message


def test_download_failure_no_cache_fallback(cache_file):
    db = DLCDatabase()
    assert set(db.all().keys()) == set(DEFAULT_DATABASE_FALLBACK["dlc"].keys())
    fallback_ep01 = DEFAULT_DATABASE_FALLBACK["dlc"]["EP01"]
    assert db.all()["EP01"].getName() == fallback_ep01["name"]
    assert db.all()["EP01"].getMainDownloadSource().getSource() == fallback_ep01["url"]
    assert not cache_file.exists()
    assert db.source == "fallback"
    assert "built-in fallback data" in db.source_description()


def test_broken_remote_missing_dlc_uses_fallback(cache_file):
    db = DLCDatabase()
    assert db.all()["EP01"].getName() == "Get to Work"


def test_broken_remote_invalid_json_uses_fallback(cache_file, monkeypatch):
    monkeypatch.setattr(
        "linua_updater.core.database.requests.get",
        lambda url, timeout=10: FakeResponse(200, None, raise_on_json=True),
    )
    db = DLCDatabase()
    assert len(db.all()) == 109


def test_broken_cache_file_ignored(cache_file):
    cache_file.write_text("{not valid json", encoding="utf-8")
    db = DLCDatabase()
    assert len(db.all()) == 109


def test_cache_without_dlc_key_falls_back(cache_file):
    _write_cache(cache_file, {"version": "1.0"})
    db = DLCDatabase()
    assert len(db.all()) == 109


def test_refresh_with_fresh_cache_replaces_it_from_remote(cache_file, monkeypatch):
    _write_cache(cache_file, _sample_payload())
    expected = {
        "version": "9.9.9",
        "updatedAt": "2026-08-16T00:00:00Z",
        "dlc": {"EP01": {"name": "Get to Work 2", "url": "https://example.com/EP01_v2.zip"}},
    }
    monkeypatch.setattr(
        "linua_updater.core.database.requests.get",
        lambda url, timeout=10: FakeResponse(200, json.loads(json.dumps(expected))),
    )
    db = DLCDatabase()
    assert db.source == "cache"
    assert db.refresh() is True
    assert db.source == "remote"
    assert db.all()["EP01"].getName() == "Get to Work 2"
    assert db.get_key("version") == "9.9.9"
    saved = json.loads(cache_file.read_text(encoding="utf-8"))
    assert saved["database"] == expected
    assert db.db_url in db.source_description()


def test_refresh_failure_removes_cache_and_falls_back(cache_file):
    _write_cache(cache_file, _sample_payload())
    db = DLCDatabase()
    assert db.source == "cache"
    assert db.refresh() is False
    assert db.source == "fallback"
    assert not cache_file.exists()
    assert len(db.all()) == 109
    assert "built-in fallback data" in db.source_description()


def test_refresh_reapplies_size_enrichment(cache_file, monkeypatch):
    _write_cache(cache_file, _sample_payload())
    monkeypatch.setattr(
        "linua_updater.core.database.requests.get",
        lambda url, timeout=10: FakeResponse(200, _sample_payload()),
    )
    db = DLCDatabase()
    assert db.refresh() is True
    assert db.all()["EP01"].getSize() == 1900000000