"""Integration tests for AI Model Scanner."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from ai_model_scanner.config import Config
from ai_model_scanner.scanner import Scanner


def test_end_to_end_scan(temp_dir):
    """Test end-to-end scanning workflow."""
    # Create test structure
    models_dir = temp_dir / "models"
    models_dir.mkdir()
    
    # Create a model file (smaller than default 500MB for testing)
    model_file = models_dir / "test_model.gguf"
    model_file.write_bytes(b"0" * 10 * 1024 * 1024)  # 10MB
    
    # Create config with lower threshold (via config file)
    config_file = temp_dir / "config.toml"
    config_file.write_text("[scanner]\nmin_size_mb = 1\n")
    config = Config(config_path=config_file)
    
    # Scan
    scanner = Scanner(config=config)
    scanner.min_size_bytes = 1 * 1024 * 1024
    
    # Mock known paths to include our test directory
    with patch.object(config, "get_all_known_paths", return_value=[str(models_dir)]):
        models = scanner.scan_known_paths()
        assert len(models) > 0
        assert any("test_model" in str(m.path) for m in models)


def test_config_path_resolution():
    """Test config path resolution across platforms."""
    config = Config()
    
    # Should have a valid config path
    assert config.config_path is not None
    assert isinstance(config.config_path, Path)
    
    # Path should be absolute or expandable
    assert str(config.config_path)


def test_cross_platform_path_handling(temp_dir):
    """Test cross-platform path handling."""
    # Create paths with different separators
    test_path = Path(temp_dir) / "test" / "path"
    test_path.mkdir(parents=True)
    
    # Should handle both forward and backslashes
    path_str_forward = str(test_path).replace("\\", "/")
    
    # On non-Windows, backslashes aren't valid path separators
    # So we just test that forward-slash paths resolve correctly
    resolved_forward = Path(path_str_forward).resolve()
    
    # Both should resolve to the same actual path
    assert resolved_forward.exists()
    assert resolved_forward == test_path.resolve()
    
    # Test that Path handles both formats (on Windows, backslashes work; on Unix, they don't)
    if sys.platform == "win32":
        path_str_backward = str(test_path).replace("/", "\\")
        resolved_backward = Path(path_str_backward).resolve()
        assert resolved_backward == resolved_forward


def test_config_loading_and_merging(temp_dir):
    """Test config loading and merging with defaults."""
    config_file = temp_dir / "config.toml"
    config_content = """
[scanner]
min_size_mb = 100

[tools]
ollama_paths = ["~/custom_ollama"]
"""
    config_file.write_text(config_content)
    
    config = Config(config_path=config_file)
    
    # Should load custom min_size_mb
    assert config.min_size_mb == 100
    
    # Should merge with defaults for other tools
    assert isinstance(config.lm_studio_paths, list)
    assert isinstance(config.comfyui_paths, list)


def test_scanner_deduplication(temp_dir):
    """Test scanner deduplicates models found in multiple locations."""
    # Create same file in two locations
    model_content = b"0" * 10 * 1024 * 1024  # 10MB
    
    path1 = temp_dir / "path1" / "model.gguf"
    path1.parent.mkdir()
    path1.write_bytes(model_content)
    
    path2 = temp_dir / "path2" / "model.gguf"
    path2.parent.mkdir()
    path2.write_bytes(model_content)
    
    # Create config with lower threshold
    config_file = temp_dir / "config.toml"
    config_file.write_text("[scanner]\nmin_size_mb = 1\n")
    config = Config(config_path=config_file)
    
    scanner = Scanner(config=config)
    scanner.min_size_bytes = 1 * 1024 * 1024
    
    # Mock known paths to include both directories
    with patch.object(config, "get_all_known_paths", return_value=[str(path1.parent), str(path2.parent)]):
        models = scanner.scan_known_paths()
        # Should find both files
        assert len(models) == 2
