import json
import time

import pytest
import requests

from linua_updater.constants import APP_VERSION
from linua_updater.paths import AppPaths
from linua_updater.workers.update_checker import UpdateChecker


def _newer_version():
    parts = [int(x) for x in APP_VERSION.split(".")]
    parts[0] += 1
    return ".".join(str(x) for x in parts)


@pytest.fixture
def isolated_update_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(AppPaths, "BASE_DIR", tmp_path)
    monkeypatch.setattr(AppPaths, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(AppPaths, "UPDATE_CACHE_FILE", tmp_path / "update_cache.json")
    monkeypatch.setattr(AppPaths, "UPDATE_CACHE_DURATION", 3600)
    return tmp_path


class FakeResponse:
    def __init__(self, status_code, data=None):
        self.status_code = status_code
        self._data = data or {}

    def json(self):
        return self._data


class FakeHTTPClient:
    def __init__(self, response=None, exc=None):
        self._response = response
        self._exc = exc
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(url)
        if self._exc is not None:
            raise self._exc
        return self._response


def test_compare_versions():
    checker = UpdateChecker()
    assert checker._compare_versions("4.4.0", "4.3.0")
    assert checker._compare_versions("4.3.1", "4.3.0")
    assert checker._compare_versions("4.3.0.1", "4.3.0")
    assert not checker._compare_versions("4.3.0", "4.3.0")
    assert not checker._compare_versions("4.2.0", "4.3.0")


def test_compare_versions_invalid_tokens():
    checker = UpdateChecker()
    assert not checker._compare_versions("4.3.a", "4.3.0")
    assert not checker._compare_versions("4.3.0", "4.3.b")


def test_compare_versions_shorter_major_wins_rule():
    checker = UpdateChecker()
    assert checker._compare_versions("10.0", "9.9.9")
    assert not checker._compare_versions("9.9.9", "10.0")


def test_check_update_available_emits_signal(isolated_update_cache):
    client = FakeHTTPClient(FakeResponse(200, {"version": "v" + _newer_version(), "download_url": "https://example.com/dl"}))
    checker = UpdateChecker(client=client)
    emitted = []
    checker.update_available.connect(lambda *a: emitted.append(a))
    checker.check_for_updates()
    assert emitted == [(_newer_version(), "https://example.com/dl")]


def test_check_no_update_emits(isolated_update_cache):
    client = FakeHTTPClient(FakeResponse(200, {"version": "4.3.0", "download_url": "https://example.com/dl"}))
    checker = UpdateChecker(client=client)
    emitted = []
    checker.no_update.connect(lambda *a: emitted.append(a))
    checker.check_for_updates()
    assert emitted == [()]


def test_check_http_error_emits_failed(isolated_update_cache):
    client = FakeHTTPClient(FakeResponse(500, {}))
    checker = UpdateChecker(client=client)
    emitted = []
    checker.check_failed.connect(lambda *a: emitted.append(a))
    checker.check_for_updates()
    assert emitted == [("HTTP 500",)]


def test_check_timeout_emits_failed(isolated_update_cache):
    client = FakeHTTPClient(exc=requests.exceptions.Timeout())
    checker = UpdateChecker(client=client)
    emitted = []
    checker.check_failed.connect(lambda *a: emitted.append(a))
    checker.check_for_updates()
    assert emitted == [("Timeout",)]


def test_check_connection_error_emits_failed(isolated_update_cache):
    client = FakeHTTPClient(exc=requests.exceptions.ConnectionError())
    checker = UpdateChecker(client=client)
    emitted = []
    checker.check_failed.connect(lambda *a: emitted.append(a))
    checker.check_for_updates()
    assert emitted == [("Connection error",)]


def test_check_uses_fresh_cache(isolated_update_cache):
    (isolated_update_cache / "update_cache.json").write_text(json.dumps({
        "timestamp": time.time(),
        "latest_version": _newer_version(),
        "download_url": "https://example.com/dl",
    }))
    client = FakeHTTPClient(exc=AssertionError("network must not be called for fresh cache"))
    checker = UpdateChecker(client=client)
    emitted = []
    checker.update_available.connect(lambda *a: emitted.append(a))
    checker.check_for_updates()
    assert emitted == [(_newer_version(), "https://example.com/dl")]
    assert client.calls == []


def test_check_expired_cache_ignored(isolated_update_cache):
    (isolated_update_cache / "update_cache.json").write_text(json.dumps({
        "timestamp": time.time() - 7200,
        "latest_version": APP_VERSION,
        "download_url": "https://example.com/dl",
    }))
    client = FakeHTTPClient(FakeResponse(200, {"version": _newer_version(), "download_url": "https://example.com/new"}))
    checker = UpdateChecker(client=client)
    emitted = []
    checker.update_available.connect(lambda *a: emitted.append(a))
    checker.check_for_updates()
    assert client.calls == [checker.version_url]
    assert emitted == [(_newer_version(), "https://example.com/new")]


def test_save_cache_writes_file(isolated_update_cache):
    checker = UpdateChecker()
    checker._save_cache("4.4.0", "https://example.com/dl")
    cache = json.loads((isolated_update_cache / "update_cache.json").read_text())
    assert cache["latest_version"] == "4.4.0"
    assert cache["download_url"] == "https://example.com/dl"
    assert cache["timestamp"] <= time.time()
