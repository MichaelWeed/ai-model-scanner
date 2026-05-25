"""Tests for reference_finder module."""

import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ai_model_scanner.model_analyzer import ModelInfo
from ai_model_scanner.reference_finder import (
    _MIN_TERM_LENGTH,
    _search_file_for_models,
    find_references,
)


def _make_model(path: Path, model_name: str = "", tool: str = "Test") -> ModelInfo:
    """Helper to create a minimal ModelInfo for tests."""
    from datetime import datetime
    return ModelInfo(
        path=path,
        size=1024 * 1024,
        size_human="1.00 MB",
        modified_date=datetime.now(),
        extension=path.suffix,
        model_name=model_name or path.stem,
        tool=tool,
        hash="abc123",
        is_recent=False,
    )


# ---------------------------------------------------------------------------
# _search_file_for_models
# ---------------------------------------------------------------------------

class TestSearchFileForModels:
    """Unit tests for the single-file search helper."""

    def _make_pattern_and_map(self, models):
        """Build the regex + term map the same way find_references does."""
        import re
        term_to_model_indices = {}
        for idx, model in enumerate(models):
            for term in (model.path.name.lower(), model.path.stem.lower(), model.model_name.lower()):
                if len(term) >= _MIN_TERM_LENGTH:
                    term_to_model_indices.setdefault(term, set()).add(idx)
        if not term_to_model_indices:
            return None, {}
        pattern = re.compile(
            "|".join(re.compile(r"").escape(t) if False else __import__("re").escape(t)
                     for t in term_to_model_indices),
            re.IGNORECASE,
        )
        return pattern, term_to_model_indices

    def test_finds_model_by_filename(self, tmp_path):
        model_file = tmp_path / "llama-3-8b.gguf"
        model_file.write_bytes(b"\x00" * 1024)
        model = _make_model(model_file, "llama-3-8b")

        code_file = tmp_path / "run.py"
        code_file.write_text('model_path = "/models/llama-3-8b.gguf"')

        pattern, term_map = self._make_pattern_and_map([model])
        result = _search_file_for_models(code_file, [model], pattern, term_map)
        assert model in result

    def test_case_insensitive_match(self, tmp_path):
        model_file = tmp_path / "Mistral-7B.safetensors"
        model_file.write_bytes(b"\x00" * 1024)
        model = _make_model(model_file, "Mistral-7B")

        code_file = tmp_path / "config.yaml"
        code_file.write_text("model: MISTRAL-7B.SAFETENSORS")

        pattern, term_map = self._make_pattern_and_map([model])
        result = _search_file_for_models(code_file, [model], pattern, term_map)
        assert model in result

    def test_no_false_positive_short_terms(self, tmp_path):
        """Terms shorter than _MIN_TERM_LENGTH should NOT be indexed."""
        model_file = tmp_path / "vae.gguf"
        model_file.write_bytes(b"\x00" * 1024)
        model = _make_model(model_file, "vae")  # 'vae' is only 3 chars

        code_file = tmp_path / "train.py"
        code_file.write_text("# This file trains various models using a vae architecture")

        pattern, term_map = self._make_pattern_and_map([model])
        if pattern is None:
            # No indexable terms — correct, no results expected
            return
        result = _search_file_for_models(code_file, [model], pattern, term_map)
        # Should NOT match purely on the 3-char stem
        assert model not in result

    def test_unreadable_file_returns_empty(self, tmp_path):
        model_file = tmp_path / "model12345.gguf"
        model_file.write_bytes(b"\x00" * 1024)
        model = _make_model(model_file, "model12345")

        missing_file = tmp_path / "nonexistent_code.py"
        pattern, term_map = self._make_pattern_and_map([model])
        result = _search_file_for_models(missing_file, [model], pattern, term_map)
        assert result == []

    def test_returns_empty_for_no_match(self, tmp_path):
        model_file = tmp_path / "stable-diffusion-xl.safetensors"
        model_file.write_bytes(b"\x00" * 1024)
        model = _make_model(model_file, "StableDiffusionXL")

        code_file = tmp_path / "unrelated.py"
        code_file.write_text("print('hello world')")

        pattern, term_map = self._make_pattern_and_map([model])
        result = _search_file_for_models(code_file, [model], pattern, term_map)
        assert result == []


# ---------------------------------------------------------------------------
# find_references
# ---------------------------------------------------------------------------

class TestFindReferences:
    """Integration tests for the find_references function."""

    def _make_code_dir(self, tmp_path: Path, content: str, filename: str = "run.py") -> Path:
        code_dir = tmp_path / "code"
        code_dir.mkdir(exist_ok=True)
        (code_dir / filename).write_text(content)
        return code_dir

    def test_finds_reference_by_filename(self, tmp_path):
        model_file = tmp_path / "llama-3-8b-q4.gguf"
        model_file.write_bytes(b"\x00" * 1024)
        model = _make_model(model_file, "llama-3-8b-q4")

        code_dir = self._make_code_dir(
            tmp_path, 'MODEL = "/models/llama-3-8b-q4.gguf"'
        )

        refs = find_references([model], code_folders=[str(code_dir)])
        assert any(model in v for v in refs.values()), "Expected to find model reference"

    def test_skip_dirs_are_pruned(self, tmp_path):
        """Files inside skip_dirs should not be searched."""
        model_file = tmp_path / "qwen25-7b.safetensors"
        model_file.write_bytes(b"\x00" * 1024)
        model = _make_model(model_file, "qwen25-7b")

        # Put a reference inside a node_modules dir (should be skipped)
        skip_dir = tmp_path / "project" / "node_modules"
        skip_dir.mkdir(parents=True)
        (skip_dir / "index.js").write_text("const model = 'qwen25-7b.safetensors'")

        # Also put one in a normal dir
        normal_dir = tmp_path / "project" / "src"
        normal_dir.mkdir(parents=True)
        (normal_dir / "main.py").write_text('path = "qwen25-7b.safetensors"')

        refs = find_references([model], code_folders=[str(tmp_path / "project")])
        found_files = set(refs.keys())

        # node_modules file should NOT be in results
        skip_file = skip_dir / "index.js"
        assert skip_file not in found_files, "node_modules should be skipped"

    def test_max_files_limit_respected(self, tmp_path):
        model_file = tmp_path / "gemma-7b-it.gguf"
        model_file.write_bytes(b"\x00" * 1024)
        model = _make_model(model_file, "gemma-7b-it")

        code_dir = tmp_path / "big_project"
        code_dir.mkdir()
        # Create 20 Python files
        for i in range(20):
            (code_dir / f"module_{i:02d}.py").write_text(
                f"# module {i}\npath = 'gemma-7b-it.gguf'"
            )

        # Limit to 5 files
        refs = find_references([model], code_folders=[str(code_dir)], max_files=5)
        # Should find references but only in up to 5 files
        assert len(refs) <= 5

    def test_empty_models_returns_empty(self, tmp_path):
        code_dir = self._make_code_dir(tmp_path, "print('nothing')")
        refs = find_references([], code_folders=[str(code_dir)])
        assert refs == {}

    def test_nonexistent_folder_skipped_gracefully(self, tmp_path):
        model_file = tmp_path / "flux-dev.safetensors"
        model_file.write_bytes(b"\x00" * 1024)
        model = _make_model(model_file, "flux-dev")

        refs = find_references(
            [model],
            code_folders=[str(tmp_path / "does_not_exist")],
        )
        assert refs == {}

    def test_found_callback_is_called(self, tmp_path):
        model_file = tmp_path / "mistral-7b-v03.gguf"
        model_file.write_bytes(b"\x00" * 1024)
        model = _make_model(model_file, "mistral-7b-v03")

        code_dir = self._make_code_dir(
            tmp_path, 'MODEL = "mistral-7b-v03.gguf"'
        )

        calls = []
        find_references(
            [model],
            code_folders=[str(code_dir)],
            found_callback=lambda f, m: calls.append((f, m)),
        )
        assert len(calls) > 0, "found_callback should be called at least once"

    def test_multiple_models_found_in_same_file(self, tmp_path):
        model1 = _make_model(tmp_path / "llama-3-8b-v2.gguf", "llama-3-8b-v2")
        model2 = _make_model(tmp_path / "mistral-7b-v03.safetensors", "mistral-7b-v03")
        for m in (model1, model2):
            m.path.write_bytes(b"\x00" * 1024)

        code_dir = self._make_code_dir(
            tmp_path,
            'paths = ["llama-3-8b-v2.gguf", "mistral-7b-v03.safetensors"]',
        )

        refs = find_references([model1, model2], code_folders=[str(code_dir)])
        found = [m for v in refs.values() for m in v]
        assert model1 in found
        assert model2 in found
