import logging
from pathlib import Path

import pytest

from linua_updater import logging_util
from linua_updater.logging_util import ImprovedLogger
from linua_updater.paths import AppPaths


class FakeWidget:
    def __init__(self):
        self.lines = []

    def append(self, text):
        self.lines.append(text)

    def ensureCursorVisible(self):
        pass


@pytest.fixture
def isolated_app_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(AppPaths, "BASE_DIR", tmp_path)
    monkeypatch.setattr(AppPaths, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(AppPaths, "LOG_FILE", tmp_path / "logs" / "updater.log")
    logging.getLogger("LinuaUpdater").handlers.clear()
    return tmp_path


@pytest.fixture
def logger(isolated_app_paths):
    return ImprovedLogger()


def test_log_writes_to_file_logger(logger, isolated_app_paths):
    logger.log("x")
    assert AppPaths.LOG_FILE.exists()
    assert "x" in AppPaths.LOG_FILE.read_text()


def test_log_colorized_by_level(isolated_app_paths):
    widget = FakeWidget()
    logger = ImprovedLogger(widget)
    logger.log("Something ERROR happened")
    logger.log("OK")
    logger.log("Complete")
    assert '<font color="#ff6b6b">' in widget.lines[0]
    assert '<font color="#6bcf7f">' in widget.lines[1]
    assert '<font color="#6bcf7f">' in widget.lines[2]


def test_log_no_widget_still_logs_to_file(logger, isolated_app_paths):
    logger.log("no widget")
    assert AppPaths.LOG_FILE.exists()
    assert "no widget" in AppPaths.LOG_FILE.read_text()


def test_export_logs_missing_file(logger, isolated_app_paths):
    AppPaths.LOG_FILE.unlink(missing_ok=True)
    assert not AppPaths.LOG_FILE.exists()
    ok, msg = logger.export_logs()
    assert not ok
    assert "No log file found" in msg


def test_export_logs_copies_file(logger, isolated_app_paths, monkeypatch, tmp_path):
    monkeypatch.setattr(logging_util, "_reveal_in_explorer", lambda path: None)
    logger.log("export me")
    target = tmp_path / "sub" / "exported.txt"
    ok, path = logger.export_logs(target_path=target)
    assert ok
    assert Path(path).exists()
    assert "export me" in Path(path).read_text()
