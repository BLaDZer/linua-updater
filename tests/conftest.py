import pytest

from linua_updater.paths import AppPaths


class FakeResponse:
    def __init__(self, status_code=404):
        self.status_code = status_code
        self._data = ""

    def json(self):
        raise ValueError("no body")


@pytest.fixture(autouse=True)
def offline_database(tmp_path, monkeypatch):
    """Keep every test deterministic and offline.

    `DLCDatabase` performs a network fetch only when its cache is missing or
    expired, so isolate its cache path and stub the network to fail. Tests that
    exercise download behavior override the stub per-test via monkeypatch (see
    ``tests/test_database.py``).
    """
    monkeypatch.setattr(AppPaths, "DATABASE_CACHE_FILE", tmp_path / "database_cache.json")
    monkeypatch.setattr(
        "linua_updater.core.database.requests.get",
        lambda url, timeout=10: FakeResponse(404),
    )