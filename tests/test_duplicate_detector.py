"""Tests for duplicate_detector module."""

from datetime import datetime
from pathlib import Path

from ai_model_scanner.duplicate_detector import find_duplicates, get_duplicate_stats
from ai_model_scanner.model_analyzer import ModelInfo


def test_find_duplicates():
    """Test duplicate detection."""
    # Create test models
    models = [
        ModelInfo(
            path=Path("/test/model1.gguf"),
            size=1000,
            size_human="1 KB",
            modified_date=datetime.now(),
            extension=".gguf",
            model_name="test-model",
            tool="Ollama",
            hash="abc123",
        ),
        ModelInfo(
            path=Path("/test/model2.gguf"),
            size=1000,
            size_human="1 KB",
            modified_date=datetime.now(),
            extension=".gguf",
            model_name="test-model",
            tool="Ollama",
            hash="abc123",  # Same hash = duplicate
        ),
        ModelInfo(
            path=Path("/test/model3.gguf"),
            size=1000,
            size_human="1 KB",
            modified_date=datetime.now(),
            extension=".gguf",
            model_name="test-model",
            tool="Ollama",
            hash="def456",  # Different hash
        ),
    ]
    
    duplicates = find_duplicates(models)
    
    # Should find one duplicate group
    assert len(duplicates) == 1
    assert "abc123" in duplicates
    assert len(duplicates["abc123"]) == 2


def test_get_duplicate_stats():
    """Test duplicate statistics."""
    models = [
        ModelInfo(
            path=Path("/test/model1.gguf"),
            size=1000,
            size_human="1 KB",
            modified_date=datetime.now(),
            extension=".gguf",
            model_name="test-model",
            tool="Ollama",
            hash="abc123",
        ),
        ModelInfo(
            path=Path("/test/model2.gguf"),
            size=1000,
            size_human="1 KB",
            modified_date=datetime.now(),
            extension=".gguf",
            model_name="test-model",
            tool="Ollama",
            hash="abc123",
        ),
    ]
    
    duplicates = find_duplicates(models)
    stats = get_duplicate_stats(duplicates)
    
    assert stats["duplicate_groups"] == 1
    assert stats["duplicate_files"] == 2
    assert stats["wasted_space"] == 1000  # One duplicate copy
