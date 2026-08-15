from linua_updater.workers.update_checker import UpdateChecker


def test_compare_versions():
    checker = UpdateChecker()
    assert checker._compare_versions("4.4.0", "4.3.0")
    assert checker._compare_versions("4.3.1", "4.3.0")
    assert checker._compare_versions("4.3.0.1", "4.3.0")
    assert not checker._compare_versions("4.3.0", "4.3.0")
    assert not checker._compare_versions("4.2.0", "4.3.0")