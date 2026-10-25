"""Log directory selection, retention and the file-logging fallback."""

import logging
import os
from pathlib import Path
import time
from unittest.mock import patch

import structlog

from backend import logging as app_logging


def test_production_and_development_log_dirs():
    assert app_logging.get_log_dir("production") == Path(app_logging.PROD_LOG_DIR)
    assert app_logging.get_log_dir("development") == Path(app_logging.DEV_LOG_DIR)


class TestCleanupOldLogFiles:
    def test_removes_only_old_rotated_files(self, tmp_path):
        old_rotated = tmp_path / "app.log.2020-01-01"
        new_rotated = tmp_path / "app.log.2099-01-01"
        active = tmp_path / "app.log"
        unrelated = tmp_path / "other.txt"
        for f in (old_rotated, new_rotated, active, unrelated):
            f.write_text("x")
        past = time.time() - 40 * 86400
        for f in (old_rotated, active, unrelated):
            os.utime(f, (past, past))

        removed = app_logging.cleanup_old_log_files(tmp_path, max_age_days=30)

        assert removed == 1
        assert not old_rotated.exists()
        # The live log and files that aren't ours are never touched, however old.
        assert active.exists()
        assert unrelated.exists()
        assert new_rotated.exists()

    def test_missing_dir_is_fine(self, tmp_path):
        assert app_logging.cleanup_old_log_files(tmp_path / "nope") == 0


def test_unwritable_log_dir_falls_back_to_console(tmp_path, capsys):
    """A container that can't create the log dir must still start and log."""
    blocker = tmp_path / "file-not-dir"
    blocker.write_text("x")
    root = logging.getLogger()
    handlers_before = list(root.handlers)
    try:
        with patch.object(app_logging, "get_log_dir", return_value=blocker / "logs"):
            app_logging.setup_logging()
    finally:
        for handler in root.handlers:
            if handler not in handlers_before:
                root.removeHandler(handler)
                handler.close()

    assert "Falling back to console-only logging" in capsys.readouterr().err


def test_file_logging_writes_json_lines(tmp_path):
    root = logging.getLogger()
    handlers_before = list(root.handlers)
    try:
        with patch.object(app_logging, "get_log_dir", return_value=tmp_path):
            app_logging.setup_logging()
        # warning: under pytest the root logger level stays at WARNING
        structlog.get_logger("test").warning("hello_event", answer=42)
    finally:
        for handler in root.handlers:
            if handler not in handlers_before:
                root.removeHandler(handler)
                handler.close()

    line = (tmp_path / "app.log").read_text(encoding="utf-8").strip().splitlines()[-1]
    assert '"event": "hello_event"' in line
    assert '"answer": 42' in line
