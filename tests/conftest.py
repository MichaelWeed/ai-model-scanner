"""Pytest configuration and fixtures."""

import tempfile
from pathlib import Path
from typing import Generator

import pytest

from ai_model_scanner.config import Config


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_model_file(temp_dir: Path) -> Path:
    """Create a mock model file for testing."""
    model_file = temp_dir / "test_model.gguf"
    # Create a file larger than default min size (500MB)
    # For testing, we'll create a smaller file and adjust min_size
    model_file.write_bytes(b"0" * 1024 * 1024)  # 1MB file
    return model_file


@pytest.fixture
def mock_config_file(temp_dir: Path) -> Path:
    """Create a mock config file for testing."""
    config_file = temp_dir / "config.toml"
    config_content = """
[scanner]
min_size_mb = 1
known_paths_only = false
scan_roots = ["~/"]
"""
    config_file.write_text(config_content)
    return config_file


@pytest.fixture
def config_with_custom_path(temp_dir: Path) -> Config:
    """Create a Config instance with a custom config path."""
    config_file = temp_dir / "config.toml"
    config_content = """
[scanner]
min_size_mb = 1
known_paths_only = false

[tools]
ollama_paths = ["~/test_ollama"]
"""
    config_file.write_text(config_content)
    return Config(config_path=config_file)


@pytest.fixture
def default_config() -> Config:
    """Create a default Config instance."""
    return Config()


@pytest.fixture
def mock_ollama_path(temp_dir: Path) -> Path:
    """Create a mock Ollama models directory."""
    ollama_dir = temp_dir / "ollama" / "models"
    ollama_dir.mkdir(parents=True)
    return ollama_dir


@pytest.fixture
def mock_lm_studio_path(temp_dir: Path) -> Path:
    """Create a mock LM Studio models directory."""
    lm_dir = temp_dir / "lmstudio" / "models"
    lm_dir.mkdir(parents=True)
    return lm_dir


@pytest.fixture
def mock_comfyui_path(temp_dir: Path) -> Path:
    """Create a mock ComfyUI models directory structure."""
    base = temp_dir / "ComfyUI" / "models"
    (base / "checkpoints").mkdir(parents=True)
    (base / "loras").mkdir(parents=True)
    return base


@pytest.fixture
def mock_huggingface_path(temp_dir: Path) -> Path:
    """Create a mock Hugging Face cache directory."""
    hf_dir = temp_dir / ".cache" / "huggingface" / "hub"
    hf_dir.mkdir(parents=True)
    return hf_dir
