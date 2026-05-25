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


# ---------------------------------------------------------------------------
# verify_files_identical
# ---------------------------------------------------------------------------

from ai_model_scanner.model_analyzer import verify_files_identical


class TestVerifyFilesIdentical:
    def test_identical_files_return_true(self, tmp_path):
        content = b"\x00" * (2 * 1024 * 1024)  # 2 MB
        a = tmp_path / "model_a.gguf"
        b = tmp_path / "model_b.gguf"
        a.write_bytes(content)
        b.write_bytes(content)
        assert verify_files_identical(a, b) is True

    def test_different_content_returns_false(self, tmp_path):
        a = tmp_path / "model_a.gguf"
        b = tmp_path / "model_b.gguf"
        a.write_bytes(b"\x00" * 1024)
        b.write_bytes(b"\xff" * 1024)
        assert verify_files_identical(a, b) is False

    def test_different_size_returns_false_fast(self, tmp_path):
        a = tmp_path / "model_a.gguf"
        b = tmp_path / "model_b.gguf"
        a.write_bytes(b"\x00" * 1024)
        b.write_bytes(b"\x00" * 2048)
        assert verify_files_identical(a, b) is False

    def test_empty_files_are_identical(self, tmp_path):
        a = tmp_path / "a.gguf"
        b = tmp_path / "b.gguf"
        a.write_bytes(b"")
        b.write_bytes(b"")
        assert verify_files_identical(a, b) is True

    def test_progress_callback_is_called(self, tmp_path):
        content = b"\xAB" * (10 * 1024 * 1024)  # 10 MB — crosses chunk boundary
        a = tmp_path / "a.gguf"
        b = tmp_path / "b.gguf"
        a.write_bytes(content)
        b.write_bytes(content)

        calls = []
        verify_files_identical(a, b, progress_callback=lambda done, total: calls.append((done, total)))
        assert len(calls) > 0
        # Last call should report full size
        assert calls[-1][0] == len(content)
        assert calls[-1][1] == len(content)

    def test_raises_on_missing_file(self, tmp_path):
        a = tmp_path / "exists.gguf"
        a.write_bytes(b"\x00" * 512)
        b = tmp_path / "nonexistent.gguf"
        with pytest.raises(OSError):
            verify_files_identical(a, b)

    def test_files_differing_only_at_tail(self, tmp_path):
        """Files that share the first 1 MB but differ in the last byte."""
        shared = b"\x42" * (1024 * 1024)  # 1 MB identical head
        a = tmp_path / "a.gguf"
        b = tmp_path / "b.gguf"
        a.write_bytes(shared + b"\x00")
        b.write_bytes(shared + b"\xFF")
        assert verify_files_identical(a, b) is False


# ---------------------------------------------------------------------------
# analyze_model_file — path canonicalization
# ---------------------------------------------------------------------------

class TestAnalyzeModelFilePathCanonicalization:
    def test_stores_resolved_path(self, tmp_path):
        """analyze_model_file must store the resolved (canonical) path."""
        from ai_model_scanner.model_analyzer import analyze_model_file

        model_file = tmp_path / "llama-3-8b.gguf"
        model_file.write_bytes(b"\x00" * (600 * 1024 * 1024))  # 600 MB

        result = analyze_model_file(model_file, min_size_bytes=0)
        assert result is not None
        assert result.path == model_file.resolve()

    def test_symlink_resolves_to_real_path(self, tmp_path):
        """A symlink to a model file should be stored as the real path."""
        from ai_model_scanner.model_analyzer import analyze_model_file

        real_file = tmp_path / "real_model.gguf"
        real_file.write_bytes(b"\x00" * (600 * 1024 * 1024))

        link = tmp_path / "link_model.gguf"
        link.symlink_to(real_file)

        result = analyze_model_file(link, min_size_bytes=0)
        assert result is not None
        # Path should resolve to the real file, not the symlink
        assert result.path == real_file.resolve()

