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