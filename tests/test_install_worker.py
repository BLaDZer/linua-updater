import threading

import pytest

from linua_updater.logging_util import SignalLogger
from linua_updater.paths import AppPaths
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


class FakeStats:
    def record_error(self, dlc_id, reason):
        pass


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


def test_install_single_cancelled_returns_cancelled(worker, tmp_path):
    worker.db = FakeDb({"EP01": {"magnet": "magnet:?xt=foo", "url": "http://example.com/EP01.zip"}})
    worker.logger = None
    worker.game_path = tmp_path
    worker.settings = {}
    worker.mirrors = {}
    worker._cancelled = True
    worker._active_downloaders = []
    dlc_id, ok, msg = worker._install_single("EP01")
    assert dlc_id == "EP01"
    assert ok is False
    assert msg == "Cancelled"
    assert worker._active_downloaders == []


def test_install_single_torrent_cancelled_no_fallback(worker, tmp_path, monkeypatch):
    worker.db = FakeDb({"EP01": {"magnet": "magnet:?xt=foo", "url": "http://example.com/EP01.zip"}})
    worker.logger = None
    worker.game_path = tmp_path
    worker.settings = {}
    worker.mirrors = {}
    worker._cancelled = False
    worker.stats = FakeStats()
    worker.extractor = None
    worker._active_downloaders = []

    direct_downloads = []

    class FakeTorrentDownloader:
        def __init__(self, logger):
            self.logger = logger

        def cancel(self):
            pass

        def set_progress_callback(self, callback):
            pass

        def download(self, magnet, temp, dlc_name=None, expected_size=None):
            return False, "Cancelled"

    class FakeSmartDownloader:
        def __init__(self, *args, **kwargs):
            pass

        def download(self, url, out_path, **kwargs):
            direct_downloads.append(url)
            return True, "OK"

    monkeypatch.setattr(
        "linua_updater.workers.install_worker.TorrentDownloader",
        FakeTorrentDownloader,
    )
    monkeypatch.setattr(
        "linua_updater.workers.install_worker.SmartDownloader",
        FakeSmartDownloader,
    )

    dlc_id, ok, msg = worker._install_single("EP01")
    assert dlc_id == "EP01"
    assert ok is False
    assert msg == "Cancelled"
    assert direct_downloads == []


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


def test_worker_logger_is_signal_logger(worker, tmp_path, monkeypatch):
    """The worker's logger is a SignalLogger forwarding to log_updated."""
    from PyQt6.QtCore import QObject

    QObject.__init__(worker)
    monkeypatch.setattr(AppPaths, "BASE_DIR", tmp_path)
    monkeypatch.setattr(AppPaths, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(AppPaths, "LOG_FILE", tmp_path / "logs" / "updater.log")
    received = []
    worker.log_updated.connect(lambda text, level: received.append((text, level)))
    worker.logger = SignalLogger(worker.log_updated.emit)
    worker.logger.log("hello", "WARNING")
    assert isinstance(worker.logger, SignalLogger)
    assert ("hello", "WARNING") in received
