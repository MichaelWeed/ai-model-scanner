"""Tests for Formatter export methods (JSON, CSV, TXT)."""

import csv
import json
from datetime import datetime
from pathlib import Path

import pytest

from ai_model_scanner.formatters import Formatter
from ai_model_scanner.model_analyzer import ModelInfo


def _make_model(name: str, size_mb: int = 100, tool: str = "Test", tmp_path: Path = None) -> ModelInfo:
    path = (tmp_path or Path("/tmp")) / f"{name}.gguf"
    size = size_mb * 1024 * 1024
    return ModelInfo(
        path=path,
        size=size,
        size_human=f"{size_mb:.2f} MB",
        modified_date=datetime(2024, 6, 1),
        extension=".gguf",
        model_name=name,
        tool=tool,
        hash=f"hash_{name}",
        is_recent=False,
    )


@pytest.fixture
def models(tmp_path):
    return [
        _make_model("llama-3-8b", size_mb=4096, tool="Ollama", tmp_path=tmp_path),
        _make_model("mistral-7b", size_mb=3900, tool="LM Studio", tmp_path=tmp_path),
        _make_model("phi-3-mini", size_mb=1800, tool="Ollama", tmp_path=tmp_path),
    ]


@pytest.fixture
def formatter():
    from rich.console import Console
    return Formatter(Console(width=120))


class TestExportJson:
    def test_creates_valid_json(self, formatter, models, tmp_path):
        out = tmp_path / "models.json"
        formatter.export_json(models, out)

        assert out.exists()
        data = json.loads(out.read_text())
        assert "models" in data
        assert "summary" in data
        assert data["summary"]["total_models"] == len(models)

    def test_json_model_count(self, formatter, models, tmp_path):
        out = tmp_path / "models.json"
        formatter.export_json(models, out)
        data = json.loads(out.read_text())
        assert len(data["models"]) == len(models)

    def test_json_model_fields(self, formatter, models, tmp_path):
        out = tmp_path / "models.json"
        formatter.export_json(models, out)
        data = json.loads(out.read_text())
        first = data["models"][0]
        for field in ("path", "size", "size_human", "extension", "model_name", "tool", "hash"):
            assert field in first, f"Field '{field}' missing from JSON model"

    def test_json_includes_duplicate_stats_when_present(self, formatter, tmp_path):
        """When duplicates exist, JSON should include duplicate_stats."""
        model_a = _make_model("sdxl-base", size_mb=6000, tmp_path=tmp_path)
        model_b = _make_model("sdxl-base-copy", size_mb=6000, tmp_path=tmp_path)
        # Give them the same hash to simulate duplicates
        model_a.hash = model_b.hash = "deadbeef" * 8

        out = tmp_path / "dup_models.json"
        formatter.export_json([model_a, model_b], out)
        data = json.loads(out.read_text())
        assert "duplicate_stats" in data
        assert data["duplicate_stats"]["duplicate_groups"] >= 1

    def test_json_empty_models(self, formatter, tmp_path):
        out = tmp_path / "empty.json"
        formatter.export_json([], out)
        data = json.loads(out.read_text())
        assert data["summary"]["total_models"] == 0
        assert data["models"] == []


class TestExportCsv:
    def test_creates_csv_with_headers(self, formatter, models, tmp_path):
        out = tmp_path / "models.csv"
        formatter.export_csv(models, out)

        assert out.exists()
        with open(out, newline='') as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames
        expected_headers = {
            "Path", "Size", "Size (Human)", "Modified Date",
            "Extension", "Model Name", "Tool", "Hash", "Is Recent",
        }
        assert expected_headers == set(headers)

    def test_csv_row_count_matches_models(self, formatter, models, tmp_path):
        out = tmp_path / "models.csv"
        formatter.export_csv(models, out)

        with open(out, newline='') as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == len(models)

    def test_csv_sorted_by_size_descending(self, formatter, models, tmp_path):
        out = tmp_path / "models.csv"
        formatter.export_csv(models, out)

        with open(out, newline='') as f:
            rows = list(csv.DictReader(f))
        sizes = [int(r["Size"]) for r in rows]
        assert sizes == sorted(sizes, reverse=True)

    def test_csv_empty_models(self, formatter, tmp_path):
        out = tmp_path / "empty.csv"
        formatter.export_csv([], out)
        with open(out, newline='') as f:
            rows = list(csv.DictReader(f))
        assert rows == []


class TestExportTxt:
    def test_creates_txt_file(self, formatter, models, tmp_path):
        out = tmp_path / "models.txt"
        formatter.export_txt(models, out)
        assert out.exists()

    def test_txt_contains_summary_section(self, formatter, models, tmp_path):
        out = tmp_path / "models.txt"
        formatter.export_txt(models, out)
        content = out.read_text()
        assert "Summary" in content
        assert "Total models" in content

    def test_txt_contains_model_names(self, formatter, models, tmp_path):
        out = tmp_path / "models.txt"
        formatter.export_txt(models, out)
        content = out.read_text()
        for model in models:
            assert model.model_name in content

    def test_txt_groups_by_tool(self, formatter, models, tmp_path):
        out = tmp_path / "models.txt"
        formatter.export_txt(models, out)
        content = out.read_text()
        # Both tools should appear as section headers
        assert "Ollama" in content
        assert "LM Studio" in content

    def test_txt_empty_models(self, formatter, tmp_path):
        out = tmp_path / "empty.txt"
        formatter.export_txt([], out)
        content = out.read_text()
        assert "Summary" in content


class TestFormatSize:
    """Tests for the internal _format_size static method."""

    def test_bytes(self):
        assert Formatter._format_size(512) == "512.00 B"

    def test_kilobytes(self):
        result = Formatter._format_size(2048)
        assert "KB" in result

    def test_megabytes(self):
        result = Formatter._format_size(5 * 1024 * 1024)
        assert "MB" in result

    def test_gigabytes(self):
        result = Formatter._format_size(4 * 1024 ** 3)
        assert "GB" in result

    def test_zero_bytes(self):
        result = Formatter._format_size(0)
        assert "0.00 B" == result

    def test_does_not_mutate_input(self):
        """format_size should not modify its input parameter."""
        size = 1024 * 1024 * 1024
        original = size
        Formatter._format_size(size)
        assert size == original
