"""Tests for utils module."""

import pytest

from ai_model_scanner.utils import (
    check_command_available,
    format_size,
    is_model_extension,
    parse_size,
)


def test_parse_size():
    """Test size parsing."""
    assert parse_size("500MB") == 500 * 1024 * 1024
    assert parse_size("1GB") == 1024 * 1024 * 1024
    assert parse_size("500M") == 500 * 1024 * 1024
    assert parse_size("1G") == 1024 * 1024 * 1024
    assert parse_size("500") == 500
    assert parse_size("2TB") == 2 * 1024 * 1024 * 1024 * 1024
    
    with pytest.raises(ValueError):
        parse_size("invalid")


def test_format_size():
    """Test size formatting."""
    assert "500.00 MB" in format_size(500 * 1024 * 1024)
    assert "1.00 GB" in format_size(1024 * 1024 * 1024)
    assert "1.00 KB" in format_size(1024)
    assert "1.00 B" in format_size(1)


def test_is_model_extension():
    """Test model extension detection."""
    assert is_model_extension("model.gguf")
    assert is_model_extension("model.GGUF")  # Case insensitive
    assert is_model_extension("model.safetensors")
    assert is_model_extension("model.pth")
    assert is_model_extension("model.pt")
    assert is_model_extension("model.bin")
    assert is_model_extension("model.ckpt")
    assert is_model_extension("model.mlmodel")
    assert is_model_extension("model.tflite")
    assert not is_model_extension("model.txt")
    assert not is_model_extension("model.py")


def test_check_command_available():
    """Test command availability check."""
    # Should return True for common commands
    assert check_command_available("python") or check_command_available("python3")
    # Should return False for non-existent commands
    assert not check_command_available("nonexistent-command-xyz123")
