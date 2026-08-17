from linua_updater.constants import GB, KB
from linua_updater.utils.disk_space import DEFAULT_DLC_SIZE_FALLBACK, SPACE_BUFFER_FACTOR, DiskSpaceChecker


def test_get_dlc_size_known():
    assert DiskSpaceChecker.get_dlc_size("EP01") == 1900000000
    assert DiskSpaceChecker.get_dlc_size("GP01") == 800000000


def test_get_dlc_size_default():
    assert DiskSpaceChecker.get_dlc_size("UNKNOWN") == DEFAULT_DLC_SIZE_FALLBACK


def test_required_space_adds_buffer():
    required = DiskSpaceChecker.calculate_required_space(["EP01", "EP02"])
    assert required == int((1900000000 + 2100000000) * SPACE_BUFFER_FACTOR)


def test_format_size():
    assert DiskSpaceChecker.format_size(KB) == "1.0 KB"
    assert DiskSpaceChecker.format_size(GB) == "1.0 GB"