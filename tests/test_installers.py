import os

import pytest

from linua_updater.core import installers
from linua_updater.core.installers import MultiPartInstaller, SingleDLCInstaller
from linua_updater.core.models import InstallationStats


class FakeLogger:
    def log(self, *args, **kwargs):
        pass


class RecordingLogger:
    def __init__(self):
        self.records = []

    def log(self, text, level="INFO"):
        self.records.append((text, level))


class StubDownloader:
    def __init__(self, results, cleanup=True, resume=False):
        self.results = list(results)
        self.cleanup = cleanup
        self.resume_enabled = resume
        self.calls = []
        self.out_paths = []

    def set_progress_callback(self, callback):
        pass

    def download(self, url, out_path, dlc_name=None, resume=False, expected_size=None):
        self.calls.append((url, out_path, dlc_name, resume, expected_size))
        self.out_paths.append(out_path)
        ok, payload = self.results.pop(0)
        if ok:
            with open(out_path, "wb") as f:
                f.write(payload)
        return ok, "OK" if ok else payload


class StubExtractor:
    def __init__(self, zip_result=(True, "OK"), seven_result=(True, "OK")):
        self.zip_result = zip_result
        self.seven_result = seven_result
        self.extract_zip_calls = []
        self.extract_7z_calls = []

    def extract_zip(self, src, dst):
        self.extract_zip_calls.append((src, dst))
        return self.zip_result

    def extract_7z(self, seven, archive, dst):
        self.extract_7z_calls.append((seven, archive, dst))
        return self.seven_result


class FakeTempfile:
    def __init__(self, path):
        self._path = path

    def gettempdir(self):
        return self._path

    def mkdtemp(self, prefix=None):
        import tempfile as _tempfile

        return _tempfile.mkdtemp(prefix=prefix)


@pytest.fixture
def temp_download_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(installers, "tempfile", FakeTempfile(str(tmp_path)))
    return tmp_path


def _single(dlc_id, info, game_path, downloader, extractor, stats):
    return SingleDLCInstaller(dlc_id, info, game_path, downloader, extractor, FakeLogger(), stats)


def test_single_missing_url(tmp_path):
    dl = StubDownloader([])
    ex = StubExtractor()
    stats = InstallationStats()
    installer = _single("EP01", {}, str(tmp_path), dl, ex, stats)
    ok, msg = installer.run()
    assert ok is False
    assert msg == "URL missing"
    assert dl.calls == []
    assert stats.errors == []


def test_single_empty_download(temp_download_dir):
    dl = StubDownloader([(True, b"")])
    ex = StubExtractor()
    installer = _single("EP01", {"url": "http://example.com/a.zip"}, str(temp_download_dir), dl, ex, InstallationStats())
    ok, msg = installer.run()
    assert ok is False
    assert msg == "Downloaded file is empty"
    assert len(dl.out_paths) == 1
    assert os.path.exists(dl.out_paths[0]) is False


def test_single_too_small_download(temp_download_dir):
    dl = StubDownloader([(True, b"x" * 512)])
    ex = StubExtractor()
    installer = _single("EP01", {"url": "http://example.com/a.zip"}, str(temp_download_dir), dl, ex, InstallationStats())
    ok, msg = installer.run()
    assert ok is False
    assert msg == "Downloaded file too small (corrupted?)"


def test_single_extract_failure_records_error(temp_download_dir):
    dl = StubDownloader([(True, b"x" * 2048)])
    ex = StubExtractor(zip_result=(False, "boom"))
    stats = InstallationStats()
    installer = _single("EP01", {"url": "http://example.com/a.zip"}, str(temp_download_dir), dl, ex, stats)
    ok, msg = installer.run()
    assert ok is False
    assert msg == "boom"
    assert len(stats.errors) == 1
    assert stats.errors[0]["dlc_id"] == "EP01"
    assert stats.errors[0]["error"] == "boom"


def test_single_success_records_download(temp_download_dir):
    dl = StubDownloader([(True, b"x" * 2048)])
    ex = StubExtractor()
    stats = InstallationStats()
    installer = _single("EP01", {"url": "http://example.com/a.zip"}, str(temp_download_dir), dl, ex, stats)
    ok, msg = installer.run()
    assert ok is True
    assert msg == "OK"
    assert "EP01" in stats.downloads
    assert stats.downloads["EP01"]["size_mb"] == pytest.approx(2048 / (1024 * 1024))
    assert stats.errors == []
    assert ex.extract_zip_calls == [(dl.out_paths[0], str(temp_download_dir))]


def test_single_checksum_failure_records_error(temp_download_dir):
    import hashlib

    payload = b"x" * 2048
    dl = StubDownloader([(True, payload)])
    ex = StubExtractor()
    stats = InstallationStats()
    info = {
        "url": "http://example.com/a.zip",
        "checksum": {"sha256": "0" * 64},
    }
    installer = _single("EP01", info, str(temp_download_dir), dl, ex, stats)
    ok, msg = installer.run()
    assert ok is False
    assert "Checksum mismatch" in msg
    assert len(stats.errors) == 1
    assert stats.errors[0]["dlc_id"] == "EP01"
    assert "Checksum mismatch" in stats.errors[0]["error"]
    assert ex.extract_zip_calls == []
    assert hashlib.sha256(payload).hexdigest() != "0" * 64


def test_single_checksum_success(temp_download_dir):
    import hashlib

    payload = b"x" * 2048
    dl = StubDownloader([(True, payload)])
    ex = StubExtractor()
    stats = InstallationStats()
    info = {
        "url": "http://example.com/a.zip",
        "checksum": {"sha256": hashlib.sha256(payload).hexdigest()},
    }
    installer = _single("EP01", info, str(temp_download_dir), dl, ex, stats)
    ok, msg = installer.run()
    assert ok is True
    assert msg == "OK"
    assert stats.errors == []
    assert ex.extract_zip_calls == [(dl.out_paths[0], str(temp_download_dir))]


def test_single_cleanup_removes_temp(temp_download_dir):
    dl = StubDownloader([(True, b"x" * 2048)], cleanup=True)
    ex = StubExtractor()
    installer = _single("EP01", {"url": "http://example.com/a.zip"}, str(temp_download_dir), dl, ex, InstallationStats())
    ok, msg = installer.run()
    assert ok is True
    assert len(dl.out_paths) == 1
    assert os.path.exists(dl.out_paths[0]) is False


def test_single_cleanup_false_keeps_temp(temp_download_dir):
    dl = StubDownloader([(True, b"x" * 2048)], cleanup=False)
    ex = StubExtractor()
    installer = _single("EP01", {"url": "http://example.com/a.zip"}, str(temp_download_dir), dl, ex, InstallationStats())
    ok, msg = installer.run()
    assert ok is True
    assert len(dl.out_paths) == 1
    assert os.path.exists(dl.out_paths[0]) is True


def _multipart(dlc_id, info, game_path, downloader, extractor, seven_path, stats):
    return MultiPartInstaller(dlc_id, info, game_path, downloader, extractor, seven_path, FakeLogger(), stats)


def test_multipart_missing_7z(temp_download_dir):
    dl = StubDownloader([])
    ex = StubExtractor()
    installer = _multipart("MP01", {"parts": ["http://example.com/1.7z.001"]}, str(temp_download_dir), dl, ex, "/no/such/7z", InstallationStats())
    ok, msg = installer.run()
    assert ok is False
    assert msg == "7-Zip not found"
    assert dl.calls == []


def test_multipart_no_parts(temp_download_dir):
    seven = temp_download_dir / "7z"
    seven.write_bytes(b"x")
    dl = StubDownloader([])
    ex = StubExtractor()
    installer = _multipart("MP01", {}, str(temp_download_dir), dl, ex, str(seven), InstallationStats())
    ok, msg = installer.run()
    assert ok is False
    assert msg == "No parts defined"
    assert dl.calls == []


def test_multipart_part_failure_cleans_up(temp_download_dir):
    seven = temp_download_dir / "7z"
    seven.write_bytes(b"x")
    dl = StubDownloader([(True, b"x" * 2048), (False, "boom")])
    ex = StubExtractor()
    stats = InstallationStats()
    installer = _multipart("MP01", {"parts": ["http://example.com/1.7z.001", "http://example.com/1.7z.002"]}, str(temp_download_dir), dl, ex, str(seven), stats)
    ok, msg = installer.run()
    assert ok is False
    assert msg == "Part 2 failed: boom"
    assert len(dl.out_paths) == 2
    assert os.path.exists(dl.out_paths[0]) is False
    assert os.path.exists(dl.out_paths[1]) is False
    assert len(stats.errors) == 1
    assert stats.errors[0]["dlc_id"] == "MP01"
    assert stats.errors[0]["error"] == "Part 2 failed: boom"


def test_multipart_logs_source_and_part_progress(temp_download_dir):
    seven = temp_download_dir / "7z"
    seven.write_bytes(b"x")
    dl = StubDownloader([(True, b"x" * 2048), (True, b"y" * 1024)])
    ex = StubExtractor()
    stats = InstallationStats()
    parts = ["http://example.com/1.7z.001", "http://example.com/1.7z.002"]
    logger = RecordingLogger()
    installer = MultiPartInstaller("MP01", {"parts": parts}, str(temp_download_dir), dl, ex, str(seven), logger, stats)
    ok, msg = installer.run()
    assert ok is True
    texts = [t for t, _ in logger.records]
    assert any(all(part in t for part in parts) and "parts from" in t for t in texts)
    assert any("Part 1/2 downloaded" in t for t in texts)
    assert any("Part 2/2 downloaded" in t for t in texts)


def test_multipart_logs_failure_reason(temp_download_dir):
    seven = temp_download_dir / "7z"
    seven.write_bytes(b"x")
    dl = StubDownloader([(True, b"x" * 2048), (False, "boom")])
    ex = StubExtractor()
    stats = InstallationStats()
    parts = ["http://example.com/1.7z.001", "http://example.com/1.7z.002"]
    logger = RecordingLogger()
    installer = MultiPartInstaller("MP01", {"parts": parts}, str(temp_download_dir), dl, ex, str(seven), logger, stats)
    ok, msg = installer.run()
    assert ok is False
    assert any(
        "Part 2/2 failed" in t and "boom" in t
        for t, lv in logger.records
        if lv == "WARNING"
    )


class StubTorrentDownloader:
    def __init__(self, results, cleanup=True):
        self.results = list(results)
        self.cleanup = cleanup
        self.calls = []
        self._progress_callback = None

    def set_progress_callback(self, callback):
        self._progress_callback = callback

    def download(self, magnet, out_dir, dlc_name=None, expected_size=None):
        self.calls.append((magnet, out_dir, dlc_name, expected_size))
        ok, payload = self.results.pop(0)
        if ok and isinstance(payload, list):
            for f in payload:
                if os.path.isfile(f):
                    pass
        return ok, payload


def _torrent(dlc_id, info, game_path, downloader, extractor, stats):
    from linua_updater.core.installers import TorrentInstaller
    return TorrentInstaller(dlc_id, info, game_path, downloader, extractor, FakeLogger(), stats)


def test_torrent_missing_magnet(temp_download_dir):
    dl = StubTorrentDownloader([])
    ex = StubExtractor()
    installer = _torrent("EP01", {}, str(temp_download_dir), dl, ex, InstallationStats())
    ok, msg = installer.run()
    assert ok is False
    assert msg == "Magnet missing"


def test_torrent_download_failure(temp_download_dir):
    dl = StubTorrentDownloader([(False, "no seeders")])
    ex = StubExtractor()
    stats = InstallationStats()
    installer = _torrent("EP01", {"magnet": "magnet:?xt=foo"}, str(temp_download_dir), dl, ex, stats)
    ok, msg = installer.run()
    assert ok is False
    assert msg == "no seeders"
    assert len(stats.errors) == 1


def test_torrent_success(temp_download_dir, monkeypatch):
    import hashlib
    import zipfile

    archive = temp_download_dir / "EP01.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("test.dat", b"x" * 2048)

    sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    dl = StubTorrentDownloader([(True, [str(archive)])])
    ex = StubExtractor()
    stats = InstallationStats()
    info = {
        "magnet": "magnet:?xt=foo",
        "checksum": {"sha256": sha},
        "size": archive.stat().st_size,
    }
    installer = _torrent("EP01", info, str(temp_download_dir), dl, ex, stats)
    ok, msg = installer.run()
    assert ok is True
    assert msg == "OK"
    assert "EP01" in stats.downloads


def test_torrent_checksum_failure(temp_download_dir):
    import zipfile

    archive = temp_download_dir / "EP01.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("test.dat", b"x" * 2048)

    dl = StubTorrentDownloader([(True, [str(archive)])])
    ex = StubExtractor()
    stats = InstallationStats()
    info = {
        "magnet": "magnet:?xt=foo",
        "checksum": {"sha256": "0" * 64},
    }
    installer = _torrent("EP01", info, str(temp_download_dir), dl, ex, stats)
    ok, msg = installer.run()
    assert ok is False
    assert "Checksum mismatch" in msg
    assert len(stats.errors) == 1


def test_torrent_unsupported_archive(temp_download_dir):
    exe = temp_download_dir / "setup.exe"
    exe.write_bytes(b"x" * 2048)
    dl = StubTorrentDownloader([(True, [str(exe)])])
    ex = StubExtractor()
    installer = _torrent("EP01", {"magnet": "magnet:?xt=foo"}, str(temp_download_dir), dl, ex, InstallationStats())
    ok, msg = installer.run()
    assert ok is False
    assert "Unsupported torrent archive" in msg


def test_torrent_no_files(temp_download_dir):
    dl = StubTorrentDownloader([(True, [])])
    ex = StubExtractor()
    installer = _torrent("EP01", {"magnet": "magnet:?xt=foo"}, str(temp_download_dir), dl, ex, InstallationStats())
    ok, msg = installer.run()
    assert ok is False
    assert "No files downloaded" in msg
