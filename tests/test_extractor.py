import io
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