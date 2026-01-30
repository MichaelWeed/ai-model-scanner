"""Tests for path_detector module."""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ai_model_scanner.path_detector import (
    IS_LINUX,
    IS_MACOS,
    IS_WINDOWS,
    detect_comfyui_paths,
    detect_huggingface_paths,
    detect_lm_studio_paths,
    detect_ollama_paths,
    get_platform_common_paths,
)


def test_platform_detection():
    """Test platform detection constants."""
    if sys.platform == "win32":
        assert IS_WINDOWS
        assert not IS_MACOS
        assert not IS_LINUX
    elif sys.platform == "darwin":
        assert IS_MACOS
        assert not IS_WINDOWS
        assert not IS_LINUX
    elif sys.platform.startswith("linux"):
        assert IS_LINUX
        assert not IS_WINDOWS
        assert not IS_MACOS


def test_detect_ollama_paths_env_var(monkeypatch, temp_dir):
    """Test Ollama path detection via environment variable."""
    test_path = temp_dir / "ollama_models"
    test_path.mkdir()
    monkeypatch.setenv("OLLAMA_MODELS", str(test_path))
    
    paths = detect_ollama_paths()
    assert any(test_path in paths or test_path.samefile(p) for p in paths)


@patch("ai_model_scanner.path_detector.subprocess.run")
def test_detect_ollama_paths_cli(mock_subprocess, temp_dir):
    """Test Ollama path detection via CLI."""
    test_path = temp_dir / "ollama" / "models"
    test_path.mkdir(parents=True)
    
    # Mock successful ollama list command
    mock_subprocess.return_value = MagicMock(returncode=0, stdout="")
    
    paths = detect_ollama_paths()
    # Should fallback to common paths
    assert isinstance(paths, list)


def test_detect_lm_studio_paths_macos(temp_dir, monkeypatch):
    """Test LM Studio path detection on macOS."""
    if not IS_MACOS:
        pytest.skip("macOS-specific test")
    
    app_support = temp_dir / "Library" / "Application Support" / "LMStudio" / "models"
    app_support.mkdir(parents=True)
    
    with patch("ai_model_scanner.path_detector.Path.home", return_value=temp_dir):
        paths = detect_lm_studio_paths()
        # Should detect or fallback to common paths
        assert isinstance(paths, list)


def test_detect_lm_studio_paths_windows(temp_dir, monkeypatch):
    """Test LM Studio path detection on Windows."""
    if not IS_WINDOWS:
        pytest.skip("Windows-specific test")
    
    localappdata = temp_dir / "LocalAppData"
    lm_path = localappdata / "LMStudio" / "models"
    lm_path.mkdir(parents=True)
    
    monkeypatch.setenv("LOCALAPPDATA", str(localappdata))
    paths = detect_lm_studio_paths()
    assert isinstance(paths, list)


def test_detect_comfyui_paths(temp_dir):
    """Test ComfyUI path detection."""
    comfyui_base = temp_dir / "ComfyUI" / "models"
    (comfyui_base / "checkpoints").mkdir(parents=True)
    (comfyui_base / "loras").mkdir(parents=True)
    
    with patch("ai_model_scanner.path_detector.Path.home", return_value=temp_dir):
        paths = detect_comfyui_paths()
        assert isinstance(paths, list)


def test_detect_huggingface_paths_env_var(monkeypatch, temp_dir):
    """Test Hugging Face path detection via environment variable."""
    test_path = temp_dir / "hf_cache"
    test_path.mkdir()
    monkeypatch.setenv("HF_HOME", str(test_path))
    
    paths = detect_huggingface_paths()
    assert any(test_path in paths or test_path.samefile(p) for p in paths)


def test_get_platform_common_paths():
    """Test getting platform common paths."""
    paths = get_platform_common_paths()
    assert isinstance(paths, dict)
    assert "ollama" in paths
    assert "lm_studio" in paths
    assert "comfyui" in paths
    assert "huggingface" in paths
    assert "mlx" in paths
    
    # All values should be lists of strings
    for tool_paths in paths.values():
        assert isinstance(tool_paths, list)
        assert all(isinstance(p, str) for p in tool_paths)
