import hashlib

from linua_updater.core.checksum import verify_file_checksums


def _write_payload(path, size=4096):
    payload = b"checksum-payload-" * (size // 17 + 1)
    payload = payload[:size]
    path.write_bytes(payload)
    return payload


def test_none_checksums_ok(tmp_path):
    f = tmp_path / "data.bin"
    payload = _write_payload(f)
    assert verify_file_checksums(str(f), None) == []
    assert payload


def test_empty_checksums_ok(tmp_path):
    f = tmp_path / "data.bin"
    _write_payload(f)
    assert verify_file_checksums(str(f), {}) == []


def test_one_correct_checksum_ok(tmp_path):
    f = tmp_path / "data.bin"
    payload = _write_payload(f)
    sha256 = hashlib.sha256(payload).hexdigest()
    assert verify_file_checksums(str(f), {"sha256": sha256}) == []


def test_one_wrong_checksum_reports_error(tmp_path):
    f = tmp_path / "data.bin"
    payload = _write_payload(f)
    expected = "0" * 64
    errors = verify_file_checksums(str(f), {"sha256": expected})
    assert len(errors) == 1
    assert "sha256" in errors[0]
    assert expected in errors[0]
    actual = hashlib.sha256(payload).hexdigest()
    assert actual in errors[0]


def test_all_three_correct_ok(tmp_path):
    f = tmp_path / "data.bin"
    payload = _write_payload(f)
    checksums = {
        "sha256": hashlib.sha256(payload).hexdigest(),
        "sha1": hashlib.sha1(payload).hexdigest(),
        "md5": hashlib.md5(payload).hexdigest(),
    }
    assert verify_file_checksums(str(f), checksums) == []


def test_only_wrong_variant_reported(tmp_path):
    f = tmp_path / "data.bin"
    payload = _write_payload(f)
    checksums = {
        "sha256": "0" * 64,
        "sha1": hashlib.sha1(payload).hexdigest(),
        "md5": hashlib.md5(payload).hexdigest(),
    }
    errors = verify_file_checksums(str(f), checksums)
    assert len(errors) == 1
    assert "sha256" in errors[0]


def test_empty_value_skipped(tmp_path):
    f = tmp_path / "data.bin"
    _write_payload(f)
    assert verify_file_checksums(str(f), {"md5": "   "}) == []


def test_unknown_algorithm_skipped(tmp_path):
    f = tmp_path / "data.bin"
    _write_payload(f)
    assert verify_file_checksums(str(f), {"crc32": "deadbeef"}) == []


def test_missing_file_returns_error(tmp_path):
    missing = tmp_path / "nope.bin"
    errors = verify_file_checksums(str(missing), {"sha256": "0" * 64})
    assert len(errors) == 1
    assert "Checksum verification failed" in errors[0]
