import threading

import pytest

from linua_updater.workers.install_worker import InstallWorker


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
