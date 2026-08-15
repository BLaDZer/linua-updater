import shutil

import pytest

from linua_updater.workers.uninstall_worker import UninstallWorker


class FakeLogger:
    def log(self, *args, **kwargs):
        pass


@pytest.fixture
def worker(tmp_path):
    return UninstallWorker(["EP01", "EP02"], tmp_path, FakeLogger())


def test_uninstall_missing_folder(worker):
    ok, msg = worker.uninstall_dlc("NOPE")
    assert not ok
    assert "DLC folder not found" in msg


def test_uninstall_file_not_directory(tmp_path):
    (tmp_path / "EP01").write_text("not a dir")
    worker = UninstallWorker(["EP01"], tmp_path, FakeLogger())
    ok, msg = worker.uninstall_dlc("EP01")
    assert not ok
    assert "Not a directory" in msg


def test_uninstall_success_deletes_folder(tmp_path):
    game = tmp_path / "game"
    folder = game / "EP01"
    folder.mkdir(parents=True)
    (folder / "file.bin").write_bytes(b"data")
    worker = UninstallWorker(["EP01"], game, FakeLogger())
    ok, msg = worker.uninstall_dlc("EP01")
    assert ok
    assert msg == "OK"
    assert not folder.exists()


def test_uninstall_permission_error(tmp_path, monkeypatch):
    (tmp_path / "EP01").mkdir()
    worker = UninstallWorker(["EP01"], tmp_path, FakeLogger())

    def raise_permission(*args, **kwargs):
        raise PermissionError("nope")

    monkeypatch.setattr(shutil, "rmtree", raise_permission)
    ok, msg = worker.uninstall_dlc("EP01")
    assert not ok
    assert "Permission denied" in msg


def test_run_cancelled_skips_remaining(worker):
    calls = []

    def fake_uninstall(dlc_id):
        calls.append(dlc_id)
        worker._cancelled = True
        return True, "OK"

    worker.uninstall_dlc = fake_uninstall
    worker.run()
    assert calls == ["EP01"]
