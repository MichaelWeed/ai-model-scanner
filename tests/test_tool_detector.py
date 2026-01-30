"""Tests for tool_detector module."""

from pathlib import Path

from ai_model_scanner.tool_detector import detect_tool


def test_detect_tool_ollama():
    """Test Ollama detection."""
    assert "Ollama" in detect_tool(Path("/home/user/ollama/models/test.gguf"))
    assert "Ollama" in detect_tool(Path("/usr/local/var/ollama/models/test.gguf"))


def test_detect_tool_lm_studio():
    """Test LM Studio detection."""
    assert "LM Studio" in detect_tool(Path("/Users/user/Library/Application Support/LMStudio/models/test.gguf"))
    assert "LM Studio" in detect_tool(Path("/Users/user/Library/Application Support/com.lmstudio.LMStudio/models/test.gguf"))


def test_detect_tool_comfyui():
    """Test ComfyUI detection."""
    assert "ComfyUI" in detect_tool(Path("/Users/user/ComfyUI/models/checkpoints/test.safetensors"))
    assert "ComfyUI" in detect_tool(Path("/Users/user/ComfyUI/models/loras/test.safetensors"))


def test_detect_tool_huggingface():
    """Test Hugging Face detection."""
    assert "Hugging Face" in detect_tool(Path("/Users/user/.cache/huggingface/hub/test.bin"))


def test_detect_tool_unknown():
    """Test unknown tool detection."""
    result = detect_tool(Path("/some/random/path/model.gguf"))
    # Should return "Unknown" or try to infer from path
    assert isinstance(result, str)


def test_detect_tool_windows_paths():
    """Test tool detection with Windows-style paths."""
    # Test with backslashes (Windows paths)
    assert "Ollama" in detect_tool(Path("C:\\Users\\user\\ollama\\models\\test.gguf"))
    assert "LM Studio" in detect_tool(Path("C:\\Users\\user\\AppData\\Local\\LMStudio\\models\\test.gguf"))
    assert "ComfyUI" in detect_tool(Path("C:\\Users\\user\\ComfyUI\\models\\checkpoints\\test.safetensors"))
    assert "Hugging Face" in detect_tool(Path("C:\\Users\\user\\.cache\\huggingface\\hub\\test.bin"))


def test_detect_tool_cross_platform():
    """Test tool detection handles both path separators."""
    # Unix-style path
    unix_path = Path("/home/user/ollama/models/test.gguf")
    unix_result = detect_tool(unix_path)
    
    # Windows-style path (same logical path)
    windows_path = Path("C:\\home\\user\\ollama\\models\\test.gguf")
    windows_result = detect_tool(windows_path)
    
    # Both should detect Ollama
    assert "Ollama" in unix_result
    assert "Ollama" in windows_result
