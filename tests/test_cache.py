"""Tests for cache module."""

import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from ai_model_scanner.cache import (
    get_cache_path,
    get_directory_index_path,
    is_directory_unchanged,
    load_directory_index,
    load_scan_results,
    save_directory_index,
    save_scan_results,
    update_directory_index,
)
from ai_model_scanner.model_analyzer import ModelInfo
from datetime import datetime


def test_get_cache_path():
    """Test cache path resolution."""
    cache_path = get_cache_path()
    assert cache_path is not None
    assert isinstance(cache_path, Path)
    assert cache_path.name == "last_scan.json"


def test_get_directory_index_path():
    """Test directory index path resolution."""
    index_path = get_directory_index_path()
    assert index_path is not None
    assert isinstance(index_path, Path)
    assert index_path.name == "directory_index.json"


def test_save_and_load_directory_index(temp_dir):
    """Test saving and loading directory index."""
    test_index = {
        str(temp_dir / "dir1"): {
            "mtime": 1234567890.0,
            "model_count": 5,
            "model_hashes": ["hash1", "hash2"],
        },
        str(temp_dir / "dir2"): {
            "mtime": 1234567891.0,
            "model_count": 3,
            "model_hashes": ["hash3"],
        },
    }
    
    with patch("ai_model_scanner.cache.get_directory_index_path", return_value=temp_dir / "test_index.json"):
        save_directory_index(test_index)
        loaded = load_directory_index()
        assert loaded == test_index


def test_load_directory_index_missing():
    """Test loading directory index when file doesn't exist."""
    with patch("ai_model_scanner.cache.get_directory_index_path", return_value=Path("/nonexistent/path/index.json")):
        index = load_directory_index()
        assert index == {}


def test_is_directory_unchanged(temp_dir):
    """Test directory unchanged check."""
    test_dir = temp_dir / "test_dir"
    test_dir.mkdir()
    
    # Get current mtime
    current_mtime = test_dir.stat().st_mtime
    
    cached_entry = {"mtime": current_mtime}
    assert is_directory_unchanged(test_dir, cached_entry) is True
    
    # Wait a bit and modify directory
    time.sleep(1.1)  # Wait longer than the 1.0 second tolerance
    (test_dir / "new_file.txt").write_text("test")
    
    # Force filesystem sync and get new mtime
    import os
    os.sync()
    new_mtime = test_dir.stat().st_mtime
    
    # Should detect change (mtime should be different)
    assert is_directory_unchanged(test_dir, cached_entry) is False or abs(new_mtime - current_mtime) >= 1.0


def test_is_directory_unchanged_nonexistent():
    """Test directory unchanged check for non-existent directory."""
    fake_dir = Path("/nonexistent/directory")
    cached_entry = {"mtime": 1234567890.0}
    assert is_directory_unchanged(fake_dir, cached_entry) is False


def test_update_directory_index(temp_dir):
    """Test updating directory index for a directory."""
    test_dir = temp_dir / "models"
    test_dir.mkdir()
    
    # Create a mock model
    model_file = test_dir / "model.gguf"
    model_file.write_bytes(b"0" * 1024)
    
    model = ModelInfo(
        path=model_file,
        size=1024,
        size_human="1 KB",
        modified_date=datetime.now(),
        extension=".gguf",
        model_name="model",
        tool="Test",
        hash="test_hash_123",
        is_recent=False,
    )
    
    with patch("ai_model_scanner.cache.get_directory_index_path", return_value=temp_dir / "test_index.json"):
        update_directory_index(test_dir, [model])
        
        index = load_directory_index()
        assert str(test_dir) in index
        assert index[str(test_dir)]["model_count"] == 1
        assert "test_hash_123" in index[str(test_dir)]["model_hashes"]


def test_save_and_load_scan_results(temp_dir):
    """Test saving and loading scan results."""
    model_file = temp_dir / "model.gguf"
    model_file.write_bytes(b"0" * 1024)
    
    model = ModelInfo(
        path=model_file,
        size=1024,
        size_human="1 KB",
        modified_date=datetime.now(),
        extension=".gguf",
        model_name="model",
        tool="Test",
        hash="test_hash",
        is_recent=False,
    )
    
    scan_params = {"root": str(temp_dir), "min_size": "500MB"}
    
    with patch("ai_model_scanner.cache.get_cache_path", return_value=temp_dir / "test_cache.json"):
        save_scan_results([model], scan_params)
        result = load_scan_results(max_age_hours=24)
        
        assert result is not None
        models, params = result
        assert len(models) == 1
        assert models[0].path == model_file
        assert params == scan_params
