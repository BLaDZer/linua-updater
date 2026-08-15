from linua_updater.utils.disk_space import DiskSpaceChecker


def test_get_dlc_size_known():
    assert DiskSpaceChecker.get_dlc_size("EP01") == 1900000000
    assert DiskSpaceChecker.get_dlc_size("GP01") == 800000000


def test_get_dlc_size_default():
    assert DiskSpaceChecker.get_dlc_size("UNKNOWN") == 500000000


def test_required_space_adds_buffer():
    required = DiskSpaceChecker.calculate_required_space(["EP01", "EP02"])
    assert required == int((1900000000 + 2100000000) * 1.1)


def test_format_size():
    assert DiskSpaceChecker.format_size(1024) == "1.0 KB"
    assert DiskSpaceChecker.format_size(1024**3) == "1.0 GB"