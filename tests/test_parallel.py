from linua_updater.core.parallel import ParallelInstallManager


def test_initialize_sets_progress_map():
    manager = ParallelInstallManager()
    manager.initialize(["EP01", "GP01"])
    assert set(manager._download_progress) == {"EP01", "GP01"}
    assert manager.total_count == 2
    assert all(d["progress"] == 0.0 for d in manager._download_progress.values())
    manager.cancel_all()


def test_overall_progress_average():
    manager = ParallelInstallManager()
    manager.initialize(["EP01", "GP01"])
    manager.update_download_progress("EP01", 100, 100, 100)
    manager.update_download_progress("GP01", 50, 50, 100)
    assert manager._calculate_overall_progress() == 75
    manager.cancel_all()


def test_overall_progress_empty_is_zero():
    manager = ParallelInstallManager()
    assert manager._calculate_overall_progress() == 0
    manager.cancel_all()


def test_cancel_all_shuts_down_executor():
    manager = ParallelInstallManager()
    manager.cancel_all()
    assert manager._cancelled is True
    manager.cancel_all()
