import os
import subprocess
import types

import pytest

import linua_updater.core.clients as clients_mod
from linua_updater.constants import MB
from linua_updater.core.clients import (
    Aria2TorrentClient,
    _popen_kwargs,
    create_torrent_client,
)


class FakeLogger:
    def log(self, text, level="INFO"):
        pass


class FakeProcess:
    def __init__(self, lines=None, exit_code=0):
        self.lines = lines or []
        self.exit_code = exit_code
        self._idx = 0
        self._terminated = False

    @property
    def stdout(self):
        return self

    def readline(self):
        if self._idx < len(self.lines):
            line = self.lines[self._idx]
            self._idx += 1
            return line
        return ""

    def poll(self):
        if self._idx >= len(self.lines):
            return self.exit_code
        return None

    def wait(self, timeout=None):
        return self.exit_code

    def terminate(self):
        self._terminated = True

    def kill(self):
        self._terminated = True


class RunningProcess(FakeProcess):
    def poll(self):
        return None  # always "running" regardless of buffered lines


def _stub_subprocess(monkeypatch, popen_fn=None, has_create_no_window=False):
    attrs = {"PIPE": object()}
    if popen_fn is not None:
        attrs["Popen"] = popen_fn
    if has_create_no_window:
        attrs["CREATE_NO_WINDOW"] = 0x08000000
    monkeypatch.setattr(clients_mod, "subprocess", types.SimpleNamespace(**attrs))


def test_is_available_with_real_path(tmp_path):
    aria2c = tmp_path / "aria2c"
    aria2c.write_text("")
    client = Aria2TorrentClient(FakeLogger(), aria2_path=str(aria2c))
    assert client.is_available() is True


def test_is_available_without_path(tmp_path):
    client = Aria2TorrentClient(FakeLogger(), aria2_path=str(tmp_path / "nope"))
    assert client.is_available() is False


def test_start_builds_command_with_aria2_flags(tmp_path, monkeypatch):
    aria2c = tmp_path / "aria2c"
    aria2c.write_text("")
    captured = {}

    def fake_popen(*a, **kw):
        captured["args"] = a
        captured["kwargs"] = kw
        return FakeProcess(lines=[], exit_code=0)

    _stub_subprocess(monkeypatch, popen_fn=fake_popen)
    monkeypatch.setattr(clients_mod, "_popen_kwargs", lambda: {})
    out_dir = str(tmp_path / "out")
    client = Aria2TorrentClient(FakeLogger(), aria2_path=str(aria2c))
    client.start("magnet:?xt=foo", out_dir)

    assert os.path.isdir(out_dir)  # start() makedirs
    cmd = list(captured["args"][0])
    assert cmd[0] == str(aria2c)
    assert cmd[1] == "magnet:?xt=foo"
    assert cmd[2] == "--dir=" + out_dir
    for flag in (
        clients_mod.ARIA2_FLAG_SEED_TIME,
        clients_mod.ARIA2_FLAG_CONTINUE,
        clients_mod.ARIA2_FLAG_ALLOW_OVERWRITE,
        clients_mod.ARIA2_FLAG_FILE_ALLOCATION,
        clients_mod.ARIA2_FLAG_SUMMARY_INTERVAL,
        clients_mod.ARIA2_FLAG_CHECK_INTEGRITY,
    ):
        assert flag in cmd
    assert f"{clients_mod.ARIA2_FLAG_BT_STOP_TIMEOUT}{clients_mod.TORRENT_STOP_TIMEOUT_SEC}" in cmd

    kw = captured["kwargs"]
    assert kw["text"] is True
    assert kw["bufsize"] == 1
    assert "stdout" in kw
    assert "stderr" in kw


def test_start_passes_create_no_window(tmp_path, monkeypatch):
    aria2c = tmp_path / "aria2c"
    aria2c.write_text("")
    captured = {}

    def fake_popen(*a, **kw):
        captured.update(kw)
        return FakeProcess(lines=[], exit_code=0)

    _stub_subprocess(monkeypatch, popen_fn=fake_popen, has_create_no_window=True)
    client = Aria2TorrentClient(FakeLogger(), aria2_path=str(aria2c))
    client.start("magnet:?xt=foo", str(tmp_path / "out"))
    assert captured.get("creationflags") == 0x08000000


def test_start_raises_on_popen_failure(tmp_path, monkeypatch):
    aria2c = tmp_path / "aria2c"
    aria2c.write_text("")

    def failing_popen(*a, **kw):
        raise OSError("boom")

    _stub_subprocess(monkeypatch, popen_fn=failing_popen)
    client = Aria2TorrentClient(FakeLogger(), aria2_path=str(aria2c))
    with pytest.raises(RuntimeError, match="boom"):
        client.start("magnet:?xt=foo", str(tmp_path / "out"))


def test_read_progress_returns_parsed_ticks_and_skips_lines(tmp_path, monkeypatch):
    aria2c = tmp_path / "aria2c"
    aria2c.write_text("")
    lines = [
        "a non-progress log line",
        "[#hash123 10MiB/100MiB(10%) CN:1 DL:1.0MiB]",
        "another non-progress log line",
        "[#hash123 100MiB/100MiB(100%) CN:1 DL:0.0KiB]",
    ]
    _stub_subprocess(
        monkeypatch,
        popen_fn=lambda *a, **kw: FakeProcess(lines=lines, exit_code=0),
    )
    client = Aria2TorrentClient(FakeLogger(), aria2_path=str(aria2c))
    client.start("magnet:?xt=foo", str(tmp_path / "out"))

    tick1 = client.read_progress()
    assert tick1[0] == 10.0
    assert tick1[1] == pytest.approx(10 * MB)
    assert tick1[2] == 0

    tick2 = client.read_progress()
    assert tick2[0] == 100.0
    assert tick2[1] == pytest.approx(100 * MB)

    assert client.read_progress() is None  # EOF


def test_read_progress_missing_stdout_raises(tmp_path, monkeypatch):
    aria2c = tmp_path / "aria2c"
    aria2c.write_text("")

    class NoStdoutProcess(FakeProcess):
        @property
        def stdout(self):
            return None

    _stub_subprocess(
        monkeypatch,
        popen_fn=lambda *a, **kw: NoStdoutProcess(lines=[], exit_code=0),
    )
    client = Aria2TorrentClient(FakeLogger(), aria2_path=str(aria2c))
    client.start("magnet:?xt=foo", str(tmp_path / "out"))
    with pytest.raises(RuntimeError, match="aria2c did not provide stdout"):
        client.read_progress()


def test_parse_summary():
    line = "[#hash123 12.3MiB/123.4MiB(10%) CN:2 DL:1.2MiB]"
    progress, downloaded, total = Aria2TorrentClient._parse_summary(line)
    assert progress == 10.0
    assert downloaded == pytest.approx(12.3 * MB)
    assert total == 0


def test_parse_summary_100_percent():
    line = "[#hash123 100MiB/100MiB(100%) CN:2 DL:1.0MiB]"
    progress, downloaded, total = Aria2TorrentClient._parse_summary(line)
    assert progress == 100.0
    assert downloaded == pytest.approx(100 * MB)


def test_stop_terminates_running_process(tmp_path, monkeypatch):
    aria2c = tmp_path / "aria2c"
    aria2c.write_text("")
    proc = RunningProcess()
    _stub_subprocess(monkeypatch, popen_fn=lambda *a, **kw: proc)
    client = Aria2TorrentClient(FakeLogger(), aria2_path=str(aria2c))
    client.start("magnet:?xt=foo", str(tmp_path / "out"))
    client.stop()
    assert proc._terminated is True


def test_abort_kills_when_terminate_ignored(tmp_path, monkeypatch):
    class StubbornProcess(FakeProcess):
        def __init__(self):
            super().__init__(lines=[], exit_code=0)
            self.killed = False

        def poll(self):
            return None  # always "running"

        def wait(self, timeout=None):
            if timeout is not None:
                raise subprocess.TimeoutExpired(cmd="aria2c", timeout=timeout)
            return self.exit_code

        def kill(self):
            self.killed = True

    proc = StubbornProcess()
    _stub_subprocess(monkeypatch, popen_fn=lambda *a, **kw: proc)
    aria2c = tmp_path / "aria2c"
    aria2c.write_text("")
    client = Aria2TorrentClient(FakeLogger(), aria2_path=str(aria2c))
    client.start("magnet:?xt=foo", str(tmp_path / "out"))
    client.abort()
    assert proc.killed is True


def test_wait_exit_returns_exit_code(tmp_path, monkeypatch):
    aria2c = tmp_path / "aria2c"
    aria2c.write_text("")
    _stub_subprocess(
        monkeypatch,
        popen_fn=lambda *a, **kw: FakeProcess(lines=[], exit_code=3),
    )
    client = Aria2TorrentClient(FakeLogger(), aria2_path=str(aria2c))
    client.start("magnet:?xt=foo", str(tmp_path / "out"))
    assert client.wait_exit() == 3


def test_popen_kwargs_linux_no_creationflags(monkeypatch):
    monkeypatch.setattr(clients_mod, "subprocess", types.SimpleNamespace())
    assert _popen_kwargs() == {}


def test_popen_kwargs_windows_sets_creationflags(monkeypatch):
    monkeypatch.setattr(clients_mod, "subprocess", types.SimpleNamespace(CREATE_NO_WINDOW=0x08000000))
    assert _popen_kwargs() == {"creationflags": 0x08000000}


def test_create_torrent_client_returns_aria2(tmp_path, monkeypatch):
    class FakeFinder:
        def __init__(self, logger):
            self.logger = logger

        def find(self):
            return str(tmp_path / "aria2c")

    monkeypatch.setattr(clients_mod, "Aria2Finder", FakeFinder)
    client = create_torrent_client(FakeLogger())
    assert isinstance(client, Aria2TorrentClient)
    assert client.name == "aria2"


def test_create_torrent_client_unknown_raises():
    with pytest.raises(ValueError):
        create_torrent_client(FakeLogger(), client_name="libtorrent")