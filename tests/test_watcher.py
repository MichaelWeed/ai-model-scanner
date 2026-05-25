"""Tests for watcher module."""

from pathlib import Path
from unittest.mock import MagicMock, patch
from datetime import datetime

import pytest

from ai_model_scanner.model_analyzer import ModelInfo


def _make_model(path: Path) -> ModelInfo:
    return ModelInfo(
        path=path,
        size=600 * 1024 * 1024,
        size_human="600.00 MB",
        modified_date=datetime.now(),
        extension=path.suffix,
        model_name=path.stem,
        tool="Test",
        hash="",
        is_recent=False,
    )


class TestSendNotification:
    def test_uses_plyer_when_available(self):
        mock_notification = MagicMock()
        with patch("ai_model_scanner.watcher.PLYER_AVAILABLE", True):
            with patch("ai_model_scanner.watcher.notification", mock_notification):
                from ai_model_scanner.watcher import send_notification
                send_notification("Title", "Message")
                mock_notification.notify.assert_called_once()

    def test_falls_back_to_print_when_plyer_unavailable(self, capsys):
        with patch("ai_model_scanner.watcher.PLYER_AVAILABLE", False):
            from ai_model_scanner.watcher import send_notification
            send_notification("New Model", "flux-dev 8GB")
            captured = capsys.readouterr()
            assert "New Model" in captured.out

    def test_falls_back_to_print_on_plyer_exception(self, capsys):
        mock_notification = MagicMock()
        mock_notification.notify.side_effect = Exception("plyer error")
        with patch("ai_model_scanner.watcher.PLYER_AVAILABLE", True):
            with patch("ai_model_scanner.watcher.notification", mock_notification):
                from ai_model_scanner.watcher import send_notification
                send_notification("Title", "Message")
                captured = capsys.readouterr()
                assert "Title" in captured.out


class TestModelFileHandler:
    """Tests for the filesystem event handler."""

    def test_ignores_directory_events(self, tmp_path):
        from ai_model_scanner.watcher import ModelFileHandler
        from ai_model_scanner.utils import get_model_extensions

        handler = ModelFileHandler(
            min_size_bytes=500 * 1024 * 1024,
            extensions=get_model_extensions(),
        )
        event = MagicMock()
        event.is_directory = True
        event.src_path = str(tmp_path)

        # Should return immediately without error
        handler.on_created(event)

    def test_ignores_non_model_files(self, tmp_path):
        from ai_model_scanner.watcher import ModelFileHandler
        from ai_model_scanner.utils import get_model_extensions

        callback = MagicMock()
        handler = ModelFileHandler(
            min_size_bytes=0,
            extensions=get_model_extensions(),
            callback=callback,
        )

        non_model = tmp_path / "document.txt"
        non_model.write_text("not a model")

        event = MagicMock()
        event.is_directory = False
        event.src_path = str(non_model)

        handler.on_created(event)
        callback.assert_not_called()

    def test_ignores_files_below_min_size(self, tmp_path):
        from ai_model_scanner.watcher import ModelFileHandler
        from ai_model_scanner.utils import get_model_extensions

        callback = MagicMock()
        # Require 1 GB minimum
        handler = ModelFileHandler(
            min_size_bytes=1024 * 1024 * 1024,
            extensions=get_model_extensions(),
            callback=callback,
        )

        small_model = tmp_path / "tiny.gguf"
        small_model.write_bytes(b"\x00" * 100)

        event = MagicMock()
        event.is_directory = False
        event.src_path = str(small_model)

        with patch("time.sleep"):
            handler.on_created(event)

        callback.assert_not_called()

    def test_calls_callback_for_valid_model(self, tmp_path):
        from ai_model_scanner.watcher import ModelFileHandler
        from ai_model_scanner.utils import get_model_extensions

        callback = MagicMock()
        handler = ModelFileHandler(
            min_size_bytes=0,  # Accept any size
            extensions=get_model_extensions(),
            callback=callback,
        )

        model_file = tmp_path / "llama-3-8b.gguf"
        model_file.write_bytes(b"\x00" * 1024)

        event = MagicMock()
        event.is_directory = False
        event.src_path = str(model_file)

        with patch("ai_model_scanner.watcher.send_notification"):
            with patch("time.sleep"):
                handler.on_created(event)

        callback.assert_called_once()
        called_model = callback.call_args[0][0]
        assert called_model.path == model_file


class TestModelWatcher:
    """Tests for ModelWatcher orchestration class."""

    def test_raises_on_missing_watchdog(self):
        with patch("ai_model_scanner.watcher.WATCHDOG_AVAILABLE", False):
            # Re-import to pick up the patched constant
            import importlib
            import ai_model_scanner.watcher as watcher_module
            # Temporarily patch WATCHDOG_AVAILABLE on the already-imported module
            with patch.object(watcher_module, "WATCHDOG_AVAILABLE", False):
                with patch.object(watcher_module, "Observer", None):
                    with pytest.raises(ImportError):
                        watcher_module.ModelWatcher()

    def test_watch_paths_raises_on_empty_paths(self, tmp_path):
        from ai_model_scanner.watcher import ModelWatcher

        with patch("ai_model_scanner.watcher.Observer") as MockObserver:
            MockObserver.return_value = MagicMock()
            with patch("ai_model_scanner.watcher.WATCHDOG_AVAILABLE", True):
                watcher = ModelWatcher.__new__(ModelWatcher)
                watcher.config = MagicMock()
                watcher.config.watcher_paths = []
                watcher.config.watcher_min_size_mb = 500
                watcher.observer = MagicMock()
                watcher.handlers = []
                watcher.min_size_bytes = 500 * 1024 * 1024
                from ai_model_scanner.utils import get_model_extensions
                watcher.extensions = get_model_extensions()

                with pytest.raises(ValueError, match="No paths"):
                    watcher.watch_paths(paths=[])

    def test_watch_paths_skips_nonexistent(self, tmp_path, capsys):
        from ai_model_scanner.watcher import ModelWatcher
        from ai_model_scanner.utils import get_model_extensions

        with patch("ai_model_scanner.watcher.Observer") as MockObserver:
            mock_obs = MagicMock()
            MockObserver.return_value = mock_obs
            with patch("ai_model_scanner.watcher.WATCHDOG_AVAILABLE", True):
                watcher = ModelWatcher.__new__(ModelWatcher)
                watcher.config = MagicMock()
                watcher.observer = mock_obs
                watcher.handlers = []
                watcher.min_size_bytes = 0
                watcher.extensions = get_model_extensions()

                # Nonexistent path should be warned but not raise
                watcher.watch_paths(paths=[str(tmp_path / "nonexistent")])
                captured = capsys.readouterr()
                assert "Warning" in captured.out or "does not exist" in captured.out
