import threading

from linua_updater.core.models import InstallationStats


def test_summary_before_finish_is_none():
    stats = InstallationStats()
    stats.start()
    assert stats.get_summary() is None


def test_record_download_tracks_bytes_and_speed():
    stats = InstallationStats()
    stats.record_download("EP01", 10 * 1024 * 1024, 2)
    entry = stats.downloads["EP01"]
    assert entry["size_mb"] == 10
    assert entry["speed_mbps"] == 5
    assert stats.total_bytes == 10 * 1024 * 1024
    stats.record_download("EP02", 1024 * 1024, 1)
    assert stats.total_bytes == 11 * 1024 * 1024


def test_record_download_zero_duration_no_division_error():
    stats = InstallationStats()
    stats.record_download("EP01", 10 * 1024 * 1024, 0)
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
    stats.record_download("EP01", 10 * 1024 * 1024, 2)
    stats.record_download("EP02", 20 * 1024 * 1024, 5)
    stats.record_error("EP03", "nope")
    stats.finish()
    summary = stats.get_summary()
    assert summary is not None
    assert summary["total_dlc"] == 2
    assert summary["successful"] == 2
    assert summary["failed"] == 1
    assert summary["total_size_mb"] == 30
    assert summary["avg_speed_mbps"] == 30 / 7
    assert summary["total_duration_sec"] >= 0
    assert summary["errors"] == stats.errors


def test_summary_thread_safety():
    stats = InstallationStats()
    stats.start()

    def worker(i):
        stats.record_download(f"DLC{i}", 1024 * 1024, 1)
        stats.record_error(f"DLC{i}", f"error{i}")

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    stats.finish()
    summary = stats.get_summary()
    assert summary["successful"] == 50
    assert summary["failed"] == 50
    assert len(stats.downloads) == 50
    assert len(stats.errors) == 50
