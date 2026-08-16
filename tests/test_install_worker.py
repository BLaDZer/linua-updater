import threading

import pytest

from linua_updater.workers.install_worker import InstallWorker, installer_kind


class FakeQueue:
    def __init__(self):
        self.calls = []

    def add(self, dlc_id, url, progress):
        self.calls.append((dlc_id, url, progress))


class FakeState:
    def __init__(self):
        self.calls = []

    def save_state(self, *args):
        self.calls.append(args)


class FakeDb:
    def __init__(self, data):
        self.data = data

    def all(self):
        return self.data


@pytest.fixture
def worker(tmp_path):
    worker = InstallWorker.__new__(InstallWorker)
    worker._active_downloaders_lock = threading.Lock()
    return worker


def test_install_single_unknown_dlc(worker, tmp_path):
    worker.db = FakeDb({})
    worker.logger = None
    worker.game_path = tmp_path
    worker.settings = {}
    worker.mirrors = {}
    dlc_id, ok, msg = worker._install_single("NOPE")
    assert not ok
    assert "DLC not found in database" in msg


def test_save_download_state_writes_queue_and_state(worker, tmp_path):
    queue = FakeQueue()
    state = FakeState()
    worker.db = FakeDb({"EP01": {"url": "https://example.com/EP01.zip"}})
    worker._download_queue = queue
    worker._download_state = state
    worker.dlc_ids = ["EP01", "GP01"]
    worker._completed_ids = ["EP01"]
    worker._failed_ids = []
    worker.game_path = tmp_path
    worker.download_progress = {"EP01": 42}
    worker._save_download_state()
    assert ("EP01", "https://example.com/EP01.zip", 42) in queue.calls
    assert state.calls == [(worker.dlc_ids, worker._completed_ids, worker._failed_ids, tmp_path)]


def test_pause_saves_state(worker):
    saved = []

    def fake_save():
        saved.append(True)

    worker._save_download_state = fake_save
    worker._active_downloaders = []
    worker.pause()
    assert saved == [True]


def test_installer_kind_magnet():
    info = {"magnet": "magnet:?xt=foo", "url": "http://example.com/a.zip"}
    assert installer_kind(info) == "magnet"


def test_installer_kind_parts():
    info = {"parts": ["http://example.com/1.7z.001"]}
    assert installer_kind(info) == "parts"


def test_installer_kind_url_only():
    info = {"url": "http://example.com/a.zip"}
    assert installer_kind(info) == "single"


def test_installer_kind_empty():
    assert installer_kind({}) == "single"


def test_installer_kind_none():
    assert installer_kind(None) == "single"


def test_installer_kind_magnet_over_parts():
    info = {"magnet": "magnet:?xt=foo", "parts": ["http://example.com/1.7z.001"], "url": "http://example.com/a.zip"}
    assert installer_kind(info) == "magnet"


def test_cancel_does_not_resume(worker):
    """cancel() should only call cancel() on downloaders, not resume()."""
    resume_called = []
    cancel_called = []

    class FakeDownloader:
        def cancel(self):
            cancel_called.append(True)
        def resume(self):
            resume_called.append(True)
        def pause(self):
            pass

    worker._active_downloaders = [FakeDownloader()]
    worker.parallel_manager = None
    worker.downloader = None
    worker.cancel()
    assert len(cancel_called) == 1
    assert len(resume_called) == 0
