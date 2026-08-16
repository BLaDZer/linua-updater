import io
import subprocess
import zipfile

from linua_updater.core.extractor import Extractor


class FakeLogger:
    def log(self, *args, **kwargs):
        pass


def _zip_with(members):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, content in members:
            z.writestr(zipfile.ZipInfo(name), content)
    return buf


def test_rejects_path_traversal(tmp_path):
    archive = _zip_with([("../../evil.txt", "oops")])
    ok, msg = Extractor(FakeLogger()).extract_zip(archive, str(tmp_path))
    assert not ok
    assert "Unsafe path" in msg


def test_rejects_nested_path_traversal(tmp_path):
    archive = _zip_with([("EP/../../evil.txt", "oops")])
    ok, msg = Extractor(FakeLogger()).extract_zip(archive, str(tmp_path))
    assert not ok
    assert "Unsafe path" in msg


def test_posix_absolute_path_is_contained(tmp_path):
    archive = _zip_with([("/tmp/evil.txt", "oops")])
    ok, msg = Extractor(FakeLogger()).extract_zip(archive, str(tmp_path))
    assert ok
    assert (tmp_path / "tmp" / "evil.txt").read_text() == "oops"


def test_extracts_normal_archive(tmp_path):
    archive = _zip_with([("Game/EP01/file.txt", "hello")])
    ok, msg = Extractor(FakeLogger()).extract_zip(archive, str(tmp_path))
    assert ok
    assert (tmp_path / "Game" / "EP01" / "file.txt").read_text() == "hello"


def test_rejects_corrupted_zip(tmp_path):
    archive = io.BytesIO(b"not a real zip archive at all")
    ok, msg = Extractor(FakeLogger()).extract_zip(archive, str(tmp_path))
    assert not ok
    assert "ZIP" in msg or "zip" in msg


def _seven_and_archive(tmp_path):
    seven = tmp_path / "7z"
    seven.touch()
    archive = tmp_path / "archive.7z"
    archive.touch()
    return str(seven), str(archive)


def test_extract_7z_missing_binary(tmp_path):
    _, archive = _seven_and_archive(tmp_path)
    ok, msg = Extractor(FakeLogger()).extract_7z("/no/7z", archive, str(tmp_path / "out"))
    assert not ok
    assert msg == "7-Zip not found"


def test_extract_7z_missing_archive(tmp_path):
    seven, _ = _seven_and_archive(tmp_path)
    ok, msg = Extractor(FakeLogger()).extract_7z(seven, "/no/archive", str(tmp_path / "out"))
    assert not ok
    assert msg == "Archive not found"


def test_extract_7z_subprocess_error(tmp_path, monkeypatch):
    seven, archive = _seven_and_archive(tmp_path)

    def fake_run(cmd, **kwargs):
        raise subprocess.CalledProcessError(returncode=1, cmd=cmd, stderr="boom")

    monkeypatch.setattr("linua_updater.core.extractor.subprocess.run", fake_run)
    ok, msg = Extractor(FakeLogger()).extract_7z(seven, archive, str(tmp_path / "out"))
    assert not ok
    assert msg == "7z error: boom"


def test_extract_7z_timeout(tmp_path, monkeypatch):
    seven, archive = _seven_and_archive(tmp_path)

    def fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=300)

    monkeypatch.setattr("linua_updater.core.extractor.subprocess.run", fake_run)
    ok, msg = Extractor(FakeLogger()).extract_7z(seven, archive, str(tmp_path / "out"))
    assert not ok
    assert msg == "7z timeout (5 minutes)"


def test_extract_7z_success(tmp_path, monkeypatch):
    seven, archive = _seven_and_archive(tmp_path)

    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(args=cmd, returncode=0)

    monkeypatch.setattr("linua_updater.core.extractor.subprocess.run", fake_run)
    ok, msg = Extractor(FakeLogger()).extract_7z(seven, archive, str(tmp_path / "out"))
    assert ok
    assert msg == "OK"


def test_extract_7z_passes_no_window_flag(tmp_path, monkeypatch):
    seven, archive = _seven_and_archive(tmp_path)
    captured = {}

    def fake_run(cmd, **kwargs):
        captured.update(kwargs)
        return subprocess.CompletedProcess(args=cmd, returncode=0)

    monkeypatch.setattr("linua_updater.core.extractor.subprocess.run", fake_run)
    ok, msg = Extractor(FakeLogger()).extract_7z(seven, archive, str(tmp_path / "out"))
    assert ok
    assert msg == "OK"
    assert captured.get("creationflags") == getattr(subprocess, "CREATE_NO_WINDOW", 0)


def test_rejects_windows_drive_absolute_path(tmp_path):
    archive = _zip_with([("CC:/evil.txt", "oops")])
    ok, msg = Extractor(FakeLogger()).extract_zip(archive, str(tmp_path))
    assert not ok
    assert "Unsafe path" in msg