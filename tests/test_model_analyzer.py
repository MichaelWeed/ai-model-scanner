"""Tests for model_analyzer module."""

import tempfile
from pathlib import Path

import pytest

from ai_model_scanner.model_analyzer import ModelInfo, compute_hash, parse_model_name


def test_parse_model_name():
    """Test model name parsing."""
    # Test various model name patterns
    assert "llama-3.1-8b" in parse_model_name("llama-3.1-8b-instruct.gguf").lower()
    assert "qwen" in parse_model_name("qwen2.5-72b.gguf").lower()
    assert "mistral" in parse_model_name("mistral-7b.gguf").lower()
    assert "sdxl" in parse_model_name("sdxl-base.safetensors").lower()
    assert "flux" in parse_model_name("flux-dev.safetensors").lower()
    assert "phi" in parse_model_name("phi-3-mini.gguf").lower()
    assert "gemma" in parse_model_name("gemma-7b.gguf").lower()


def test_compute_hash():
    """Test hash computation."""
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(b"test content for hashing")
        temp_path = Path(f.name)
    
    try:
        hash1 = compute_hash(temp_path)
        hash2 = compute_hash(temp_path)
        
        # Same file should produce same hash
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex string length
    finally:
        temp_path.unlink()


def test_model_info_to_dict():
    """Test ModelInfo to_dict conversion."""
    from datetime import datetime
    
    model = ModelInfo(
        path=Path("/test/model.gguf"),
        size=1024 * 1024 * 500,  # 500MB
        size_human="500.00 MB",
        modified_date=datetime.now(),
        extension=".gguf",
        model_name="test-model",
        tool="Ollama",
        hash="abc123",
        is_recent=False,
    )
    
    data = model.to_dict()
    assert data["path"] == "/test/model.gguf"
    assert data["size"] == 1024 * 1024 * 500
    assert data["model_name"] == "test-model"
    assert data["tool"] == "Ollama"
