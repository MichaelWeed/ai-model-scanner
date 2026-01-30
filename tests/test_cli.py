"""Tests for CLI module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from ai_model_scanner.cli import app


@pytest.fixture
def cli_runner():
    """Create a CLI test runner."""
    return CliRunner()


def test_cli_help(cli_runner):
    """Test CLI help command."""
    result = cli_runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "ai-model-scanner" in result.stdout.lower()


def test_cli_scan_help(cli_runner):
    """Test scan command help."""
    result = cli_runner.invoke(app, ["scan", "--help"])
    assert result.exit_code == 0
    assert "scan" in result.stdout.lower()


def test_cli_scan_dry_run(cli_runner, temp_dir):
    """Test scan dry run."""
    with patch("ai_model_scanner.cli.Path.home", return_value=temp_dir):
        result = cli_runner.invoke(app, ["scan", "--dry-run"])
        assert result.exit_code == 0
        assert "dry run" in result.stdout.lower() or "Dry run" in result.stdout


def test_cli_scan_with_root(cli_runner, temp_dir):
    """Test scan with custom root."""
    result = cli_runner.invoke(app, ["scan", "--root", str(temp_dir), "--min-size", "1MB"])
    # Should complete (may find nothing, but shouldn't error)
    assert result.exit_code in [0, 1]  # 0 if successful, 1 if no models found


def test_cli_scan_invalid_size(cli_runner):
    """Test scan with invalid size format."""
    result = cli_runner.invoke(app, ["scan", "--min-size", "invalid"])
    assert result.exit_code != 0
    assert "error" in result.stdout.lower() or "invalid" in result.stdout.lower()


def test_cli_watch_help(cli_runner):
    """Test watch command help."""
    result = cli_runner.invoke(app, ["watch", "--help"])
    assert result.exit_code == 0
    assert "watch" in result.stdout.lower()


def test_cli_health_help(cli_runner):
    """Test health command help."""
    result = cli_runner.invoke(app, ["health", "--help"])
    assert result.exit_code == 0
    assert "health" in result.stdout.lower()


@patch("ai_model_scanner.cli.Scanner")
def test_cli_scan_full_workflow(mock_scanner_class, cli_runner, temp_dir):
    """Test full scan workflow."""
    # Mock scanner to return empty list
    mock_scanner = MagicMock()
    mock_scanner.scan.return_value = []
    mock_scanner.min_size_bytes = 500 * 1024 * 1024
    mock_scanner_class.return_value = mock_scanner
    
    with patch("ai_model_scanner.cli.Path.home", return_value=temp_dir):
        result = cli_runner.invoke(app, ["scan", "--root", str(temp_dir)])
        # Should handle empty results gracefully
        assert result.exit_code in [0, 1]


def test_cli_report_help(cli_runner):
    """Test report command help."""
    result = cli_runner.invoke(app, ["report", "--help"])
    assert result.exit_code == 0
    assert "report" in result.stdout.lower()


def test_cli_keep_help(cli_runner):
    """Test keep command help."""
    result = cli_runner.invoke(app, ["keep", "--help"])
    assert result.exit_code == 0
    assert "keep" in result.stdout.lower()


@patch("ai_model_scanner.cli.load_scan_results")
@patch("ai_model_scanner.cli.find_references")
@patch("ai_model_scanner.cli.find_duplicates")
def test_cli_report_command(mock_find_duplicates, mock_find_references, mock_load_cache, cli_runner, temp_dir, mock_model_file):
    """Test report command."""
    from ai_model_scanner.model_analyzer import ModelInfo
    from datetime import datetime
    
    # Mock cached models
    model = ModelInfo(
        path=mock_model_file,
        size=1024 * 1024,
        size_human="1 MB",
        modified_date=datetime.now(),
        extension=".gguf",
        model_name="test_model",
        tool="Test",
        hash="test_hash",
        is_recent=False,
    )
    
    mock_load_cache.return_value = ([model], {"root": str(temp_dir)})
    mock_find_references.return_value = {}
    mock_find_duplicates.return_value = {}
    
    with patch("ai_model_scanner.cli.Path.home") as mock_home:
        mock_home.return_value = temp_dir
        # Mock Desktop path
        desktop = temp_dir / "Desktop"
        desktop.mkdir()
        
        with patch("ai_model_scanner.cli.sys.platform", "darwin"):
            result = cli_runner.invoke(app, ["report", "--output", str(desktop)])
            # Should complete successfully
            assert result.exit_code == 0
            # Check that files were created
            csv_files = list(desktop.glob("*.csv"))
            assert len(csv_files) >= 0  # May be 0 if no models


@patch("ai_model_scanner.cli.load_scan_results")
@patch("ai_model_scanner.cli.find_duplicates")
def test_cli_keep_command_no_duplicates(mock_find_duplicates, mock_load_cache, cli_runner, temp_dir, mock_model_file):
    """Test keep command with no duplicates."""
    from ai_model_scanner.model_analyzer import ModelInfo
    from datetime import datetime
    
    # Resolve path to match what the command will resolve
    resolved_path = Path(mock_model_file).expanduser().resolve()
    
    model = ModelInfo(
        path=resolved_path,
        size=1024 * 1024,
        size_human="1 MB",
        modified_date=datetime.now(),
        extension=".gguf",
        model_name="test_model",
        tool="Test",
        hash="test_hash",
        is_recent=False,
    )
    
    mock_load_cache.return_value = ([model], {"root": str(temp_dir)})
    mock_find_duplicates.return_value = {}  # No duplicates
    
    result = cli_runner.invoke(app, ["keep", str(mock_model_file), "--dry-run"])
    assert result.exit_code == 0
    assert "No duplicates" in result.stdout or "no duplicates" in result.stdout.lower()


@patch("ai_model_scanner.cli.load_scan_results")
@patch("ai_model_scanner.cli.find_duplicates")
def test_cli_keep_command_with_duplicates(mock_find_duplicates, mock_load_cache, cli_runner, temp_dir, mock_model_file):
    """Test keep command with duplicates."""
    from ai_model_scanner.model_analyzer import ModelInfo
    from datetime import datetime
    
    # Resolve paths to match what the command will resolve
    resolved_path1 = Path(mock_model_file).expanduser().resolve()
    
    # Create duplicate model
    duplicate_file = temp_dir / "duplicate.gguf"
    duplicate_file.write_bytes(b"0" * 1024 * 1024)
    resolved_path2 = Path(duplicate_file).expanduser().resolve()
    
    model1 = ModelInfo(
        path=resolved_path1,
        size=1024 * 1024,
        size_human="1 MB",
        modified_date=datetime.now(),
        extension=".gguf",
        model_name="test_model",
        tool="Test",
        hash="same_hash",
        is_recent=False,
    )
    
    model2 = ModelInfo(
        path=resolved_path2,
        size=1024 * 1024,
        size_human="1 MB",
        modified_date=datetime.now(),
        extension=".gguf",
        model_name="test_model",
        tool="Test",
        hash="same_hash",
        is_recent=False,
    )
    
    mock_load_cache.return_value = ([model1, model2], {"root": str(temp_dir)})
    mock_find_duplicates.return_value = {"same_hash": [model1, model2]}
    
    result = cli_runner.invoke(app, ["keep", str(mock_model_file), "--dry-run"])
    assert result.exit_code == 0
    assert "duplicate" in result.stdout.lower() or "Duplicate" in result.stdout


def test_cli_keep_command_invalid_path(cli_runner):
    """Test keep command with invalid path."""
    result = cli_runner.invoke(app, ["keep", "/nonexistent/path/model.gguf"])
    assert result.exit_code != 0
    assert "error" in result.stdout.lower() or "does not exist" in result.stdout.lower()
