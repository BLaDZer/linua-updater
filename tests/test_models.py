import threading

from linua_updater.constants import MB
from linua_updater.core.models import CheckSums, DLCInfo, DownloadSource, InstallationStats


def test_summary_before_finish_is_none():
    stats = InstallationStats()
    stats.start()
    assert stats.get_summary() is None


def test_record_download_tracks_bytes_and_speed():
    stats = InstallationStats()
    stats.record_download("EP01", 10 * MB, 2)
    entry = stats.downloads["EP01"]
    assert entry["size_mb"] == 10
    assert entry["speed_mbps"] == 5
    assert stats.total_bytes == 10 * MB
    stats.record_download("EP02", MB, 1)
    assert stats.total_bytes == 11 * MB


def test_record_download_zero_duration_no_division_error():
    stats = InstallationStats()
    stats.record_download("EP01", 10 * MB, 0)
    assert stats.downloads["EP01"]["speed_mbps"] == 0


def test_record_error_accumulates():
    stats = InstallationStats()
    stats.record_error("EP01", "boom")
    stats.record_error("EP02", "bang")
    assert len(stats.errors) == 2
    assert stats.errors[0]["dlc_id"] == "EP01"
    assert stats.errors[1]["error"] == "bang"


def test_summary_aggregates():
    stats = InstallationStats()
    stats.start()
    stats.total_dlc = 3
    stats.record_download("EP01", 10 * MB, 2)
    stats.record_download("EP02", 20 * MB, 5)
    stats.record_error("EP03", "nope")
    stats.finish()
    summary = stats.get_summary()
    assert summary is not None
    assert summary["total_dlc"] == 3
    assert summary["successful"] == 2
    assert summary["failed"] == 1
    assert summary["total_size_mb"] == 30
    assert summary["avg_speed_mbps"] == 30 / 7
    assert summary["total_duration_sec"] >= 0
    assert summary["errors"] == stats.errors


def test_summary_thread_safety():
    stats = InstallationStats()
    stats.start()
    stats.total_dlc = 100

    def worker(i):
        stats.record_download(f"DLC{i}", MB, 1)
        stats.record_error(f"DLC{i}", f"error{i}")

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    stats.finish()
    summary = stats.get_summary()
    assert summary["total_dlc"] == 100
    assert summary["successful"] == 50
    assert summary["failed"] == 50
    assert len(stats.downloads) == 50
    assert len(stats.errors) == 50


def test_summary_cancelled_run_no_downloads():
    stats = InstallationStats()
    stats.start()
    stats.total_dlc = 3
    stats.record_error("EP01", "Cancelled")
    stats.record_error("EP02", "All download attempts failed")
    stats.finish()
    summary = stats.get_summary()
    assert summary["total_dlc"] == 3
    assert summary["successful"] == 0
    assert summary["failed"] == 3


def test_summary_failed_is_per_dlc_not_per_attempt():
    stats = InstallationStats()
    stats.start()
    stats.total_dlc = 3
    stats.record_download("EP01", 10 * MB, 2)
    stats.record_error("EP02", "All download attempts failed")
    stats.record_error("EP02", "aria2c not found")
    stats.record_error("EP02", "Part 5 failed: Cancelled")
    stats.record_download("EP03", 20 * MB, 5)
    stats.record_error("EP03", "checksum mismatch on second mirror")
    stats.finish()
    summary = stats.get_summary()
    assert summary["total_dlc"] == 3
    assert summary["successful"] == 2
    assert summary["failed"] == 1
    assert summary["successful"] + summary["failed"] == summary["total_dlc"]


def test_checksums_getters_and_get():
    cs = CheckSums("sha256-x", "sha1-x", "md5-x")
    assert cs.getSha256() == "sha256-x"
    assert cs.getSha1() == "sha1-x"
    assert cs.getMd5() == "md5-x"
    assert cs.get("sha256") == "sha256-x"
    assert cs.get("sha1") == "sha1-x"
    assert cs.get("md5") == "md5-x"
    assert cs.get("bogus") is None


def test_checksums_from_dict_skips_absent_and_empty():
    cs = CheckSums.from_dict({"sha256": "", "sha1": None, "md5": "abc"})
    assert cs.getSha256() is None
    assert cs.getSha1() is None
    assert cs.getMd5() == "abc"


def test_checksums_from_dict_none():
    assert CheckSums.from_dict(None) is None


def test_dlc_info_url_only_entry():
    info = DLCInfo.from_entry("EP01", {"name": "Get to Work", "url": "https://example.com/EP01.zip"})
    assert info.getId() == "EP01"
    assert info.getName() == "Get to Work"
    assert info.getSize() is None
    main = info.getMainDownloadSource()
    assert main is not None
    assert main.getType() == "url"
    assert main.getSource() == "https://example.com/EP01.zip"
    assert info.getMirrors() == []


def test_dlc_info_legacy_magnet_and_parts_mirrors():
    info = DLCInfo.from_entry(
        "EP01",
        {
            "name": "Get Famous",
            "url": "https://example.com/EP01.zip",
            "magnet": "magnet:?xt=foo",
            "parts": ["https://example.com/1.7z.001", "https://example.com/1.7z.002"],
            "checksum": {"sha256": "c0ffee"},
        },
    )
    assert info.getName() == "Get Famous"
    main = info.getMainDownloadSource()
    assert main.getSource() == "https://example.com/EP01.zip"
    mirrors = info.getMirrors()
    assert len(mirrors) == 2
    assert mirrors[0].getType() == "magnet"
    assert mirrors[0].getSource() == "magnet:?xt=foo"
    assert mirrors[0].getPriority() == 0
    assert mirrors[0].getCheckSums().get("sha256") == "c0ffee"
    assert mirrors[1].getType() == "parts"
    assert mirrors[1].getPriority() == 0
    parts = mirrors[1].getParts()
    assert len(parts) == 2
    assert parts[0].getType() == "url"
    assert parts[0].getSource() == "https://example.com/1.7z.001"
    assert parts[1].getSource() == "https://example.com/1.7z.002"


def test_dlc_info_mirror_sort_by_priority_desc():
    info = DLCInfo.from_entry(
        "EP06",
        {
            "name": "Get Famous",
            "url": "https://example.com/EP06.zip",
            "mirrors": [
                {
                    "type": "parts",
                    "parts": [
                        {"type": "url", "url": "https://example.com/1.7z.001"},
                        {"type": "url", "url": "https://example.com/1.7z.002"},
                    ],
                },
                {"type": "magnet", "magnet": "magnet:?xt=foo", "priority": 20},
            ],
        },
    )
    mirrors = info.getMirrors()
    assert len(mirrors) == 2
    assert [m.getType() for m in mirrors] == ["magnet", "parts"]
    assert mirrors[0].getPriority() == 20
    assert mirrors[1].getPriority() == 0
    parts = mirrors[1].getParts()
    assert len(parts) == 2
    assert [p.getSource() for p in parts] == ["https://example.com/1.7z.001", "https://example.com/1.7z.002"]


def test_dlc_info_mirror_inherits_entry_checksum():
    entry = {
        "name": "Get Famous",
        "url": "https://example.com/EP06.zip",
        "checksum": {"sha256": "abc123"},
        "mirrors": [{"type": "magnet", "magnet": "magnet:?xt=foo"}],
    }
    info = DLCInfo.from_entry("EP06", entry)
    mirror = info.getMirrors()[0]
    assert mirror.getCheckSums().get("sha256") == "abc123"


def test_dlc_info_mirror_keeps_own_checksum():
    entry = {
        "name": "Get Famous",
        "url": "https://example.com/EP06.zip",
        "checksum": {"sha256": "abc123"},
        "mirrors": [{"type": "magnet", "magnet": "magnet:?xt=foo", "checksum": {"sha256": "own123"}}],
    }
    info = DLCInfo.from_entry("EP06", entry)
    mirror = info.getMirrors()[0]
    assert mirror.getCheckSums().get("sha256") == "own123"


def test_dlc_info_get_size():
    info = DLCInfo.from_entry("EP01", {"name": "x", "url": "u", "size": 12345})
    assert info.getSize() == 12345


def test_dlc_info_no_main_source_without_url():
    info = DLCInfo.from_entry("EP01", {"name": "x", "magnet": "magnet:?xt=foo"})
    assert info.getMainDownloadSource() is None
    assert len(info.getMirrors()) == 1
    assert info.getMirrors()[0].getType() == "magnet"


def test_download_source_from_dict_infers_type():
    src = DownloadSource.from_dict({"url": "https://example.com/a.zip"})
    assert src.getType() == "url"
    assert src.getSource() == "https://example.com/a.zip"
    assert src.getPriority() == 0
    src2 = DownloadSource.from_dict({"parts": [{"url": "u1"}]})
    assert src2.getType() == "parts"
    assert len(src2.getParts()) == 1
    assert src2.getParts()[0].getType() == "url"
