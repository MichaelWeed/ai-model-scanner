"""Tests for config module."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from ai_model_scanner.config import Config


def test_config_default_path_windows(monkeypatch, temp_dir):
    """Test default config path on Windows."""
    if sys.platform != "win32":
        pytest.skip("Windows-specific test")
    
    monkeypatch.setenv("APPDATA", str(temp_dir))
    config = Config()
    
    expected_path = temp_dir / "ai-model-scanner" / "config.toml"
    assert config.config_path == expected_path


def test_config_default_path_unix(temp_dir):
    """Test default config path on Unix systems."""
    if sys.platform == "win32":
        pytest.skip("Unix-specific test")
    
    with patch("ai_model_scanner.config.Path.home", return_value=temp_dir):
        config = Config()
        
        expected_path = temp_dir / ".config" / "ai-model-scanner" / "config.toml"
        assert config.config_path == expected_path


def test_config_custom_path(temp_dir):
    """Test config with custom path."""
    custom_path = temp_dir / "custom_config.toml"
    config = Config(config_path=custom_path)
    assert config.config_path == custom_path


def test_config_loads_from_file(mock_config_file):
    """Test config loads from file."""
    config = Config(config_path=mock_config_file)
    assert config.min_size_mb == 1
    assert config.known_paths_only is False


def test_config_defaults():
    """Test config defaults."""
    config = Config()
    assert config.min_size_mb == 500
    assert config.known_paths_only is False
    assert config.default_format == "table"
    assert config.group_by_tool is True
    assert config.show_duplicates is True


def test_config_path_properties():
    """Test config path properties."""
    config = Config()
    
    # These should return lists
    assert isinstance(config.ollama_paths, list)
    assert isinstance(config.lm_studio_paths, list)
    assert isinstance(config.comfyui_paths, list)
    assert isinstance(config.huggingface_paths, list)
    assert isinstance(config.mlx_paths, list)
    assert isinstance(config.code_folders, list)


def test_config_get_all_known_paths():
    """Test getting all known paths."""
    config = Config()
    all_paths = config.get_all_known_paths()
    
    assert isinstance(all_paths, list)
    assert len(all_paths) > 0


def test_config_watcher_paths():
    """Test watcher paths."""
    config = Config()
    watcher_paths = config.watcher_paths
    
    assert isinstance(watcher_paths, list)
    # Should default to all known paths if not specified
    assert len(watcher_paths) > 0
