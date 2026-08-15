import json
import time

import pytest

from linua_updater.paths import AppPaths
from linua_updater.persistence.download_queue import DownloadQueue
from linua_updater.persistence.download_state import DownloadState


@pytest.fixture
def isolated_app_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(AppPaths, "BASE_DIR", tmp_path)
    monkeypatch.setattr(AppPaths, "DOWNLOAD_QUEUE_FILE", tmp_path / "download_queue.json")
    monkeypatch.setattr(AppPaths, "DOWNLOAD_STATE_FILE", tmp_path / "download_state.json")
    return tmp_path


def test_download_queue_roundtrip(isolated_app_paths):
    queue = DownloadQueue()
    queue.add("EP01", "https://example.com/EP01.zip", progress=10)
    assert queue.get_incomplete() == {"EP01": queue.get_incomplete()["EP01"]}
    queue.update_progress("EP01", 100)
    assert not queue.get_incomplete()
    queue.remove("EP01")
    assert "EP01" not in queue.get_incomplete()
    queue.clear_all()
    assert queue.get_incomplete() == {}


def test_download_state_roundtrip(isolated_app_paths):
    state = DownloadState()
    assert state.save_state(["EP01", "GP01"], completed=["EP01"], failed=[], game_path="/game")
    loaded = state.load_state()
    assert loaded is not None
    assert loaded["remaining"] == ["GP01"]
    assert loaded["game_path"] == "/game"
    state.clear_state()
    assert DownloadState().load_state() is None


def test_download_queue_corrupted_file_returns_empty(isolated_app_paths):
    (isolated_app_paths / "download_queue.json").write_text("{not json", encoding="utf-8")
    queue = DownloadQueue()
    assert queue.queue == {}
    assert queue.get_incomplete() == {}


def test_download_queue_add_overwrites(isolated_app_paths):
    queue = DownloadQueue()
    queue.add("EP01", "https://example.com/old", progress=10)
    queue.add("EP01", "https://example.com/new", progress=55)
    entry = queue.queue["EP01"]
    assert entry["url"] == "https://example.com/new"
    assert entry["progress"] == 55


def test_download_queue_update_progress_unknown_is_noop(isolated_app_paths):
    queue = DownloadQueue()
    queue.update_progress("NOPE", 50)
    assert queue.queue == {}
    assert queue.get_incomplete() == {}


def test_download_state_expired_returns_none(isolated_app_paths):
    state = DownloadState()
    state.save_state(["EP01"], completed=[], failed=[])
    stale = {
        "timestamp": time.time() - AppPaths.DOWNLOAD_STATE_DURATION - 10,
        "total": ["EP01"],
        "completed": [],
        "failed": [],
        "remaining": ["EP01"],
    }
    (isolated_app_paths / "download_state.json").write_text(json.dumps(stale))
    assert DownloadState().load_state() is None


def test_download_state_corrupted_returns_none(isolated_app_paths):
    (isolated_app_paths / "download_state.json").write_text("{not json")
    assert DownloadState().load_state() is None


def test_download_state_missing_file_returns_none(isolated_app_paths):
    assert DownloadState().load_state() is None