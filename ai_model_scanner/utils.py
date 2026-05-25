"""Utility functions for file size parsing, path expansion, and helper functions."""

import os
import re
from pathlib import Path
from typing import Optional


def parse_size(size_str: str) -> int:
    """
    Parse human-readable size string to bytes.
    
    Supports formats like: 500MB, 1GB, 500M, 1G, 500, etc.
    
    Args:
        size_str: Human-readable size string (e.g., "500MB", "1GB")
        
    Returns:
        Size in bytes
        
    Raises:
        ValueError: If size string cannot be parsed
    """
    size_str = size_str.strip().upper()

    # Accept bare integers (no unit) — treat as bytes
    if size_str.isdigit():
        return int(size_str)

    # Extract number and unit
    match = re.match(r'^(\d+(?:\.\d+)?)\s*([KMGT]?B?)$', size_str)
    if not match:
        raise ValueError(
            f"Invalid size format: {size_str!r}. "
            "Expected a value like '500MB', '1GB', '1024', etc."
        )

    number = float(match.group(1))
    unit = match.group(2) or 'B'

    # Normalise: strip trailing 'B' so 'MB' → 'M', 'GB' → 'G', etc.
    if unit.endswith('B') and unit != 'B':
        unit = unit[:-1]

    multipliers = {
        '': 1,   # empty string after strip means plain bytes
        'B': 1,
        'K': 1024,
        'M': 1024 ** 2,
        'G': 1024 ** 3,
        'T': 1024 ** 4,
    }

    multiplier = multipliers.get(unit, 1)
    return int(number * multiplier)


def format_size(size_bytes: int) -> str:
    """
    Format bytes to human-readable size string.

    Args:
        size_bytes: Size in bytes

    Returns:
        Human-readable size string (e.g., "1.5 GB")
    """
    value = float(size_bytes)
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if value < 1024.0:
            return f"{value:.2f} {unit}"
        value /= 1024.0
    return f"{value:.2f} PB"


def expand_path(path: str) -> Path:
    """
    Expand user home directory and resolve to absolute path.
    
    Args:
        path: Path string (may contain ~)
        
    Returns:
        Expanded Path object
    """
    return Path(path).expanduser().resolve()


def is_model_extension(
    filename: str,
    extensions: Optional[list] = None,
    filepath: Optional[Path] = None,
) -> bool:
    """
    Check if a file has a recognised model extension.

    For the ambiguous ``.bin`` extension a path-context guard is applied:
    the file is only accepted if its path contains a directory segment that
    strongly suggests a model artefact (e.g. ``models``, ``weights``,
    ``snapshots``, ``onnx_models``, ``transformers``, etc.).  This avoids
    false positives from compiled binaries, git object files, and other
    non-model ``.bin`` files that happen to be large.

    Args:
        filename: Filename (basename) to check.
        extensions: List of extensions to match (defaults to
                    ``get_model_extensions()``).
        filepath: Full path used for the ``.bin`` context guard.
                  If *None* the guard is skipped (accepts all ``.bin`` files
                  that pass the size threshold).

    Returns:
        ``True`` if the file should be treated as a model file.
    """
    if extensions is None:
        extensions = get_model_extensions()

    filename_lower = filename.lower()

    if not any(filename_lower.endswith(e.lower()) for e in extensions):
        return False

    # .bin path-context guard
    if filename_lower.endswith('.bin') and filepath is not None:
        _BIN_MODEL_MARKERS = {
            'models', 'weights', 'checkpoints', 'snapshots',
            'onnx_models', 'transformers', 'diffusers', 'loras',
            'embeddings', 'adapters', 'unet', 'vae', 'clip',
            'text_encoders', 'controlnet', 'ipadapter', 'huggingface',
            'lmstudio', 'ollama', 'comfyui', 'mlx-community',
            'sentence-transformers',
        }
        path_parts = set(str(filepath).lower().replace('\\', '/').split('/'))
        # Also accept pytorch_model*.bin (HuggingFace shard naming convention)
        if (path_parts & _BIN_MODEL_MARKERS) or 'pytorch_model' in filename_lower:
            return True
        return False

    return True


def get_model_extensions() -> list:
    """
    Get list of common model file extensions.

    Covers:
      - .safetensors  modern standard (HuggingFace, LoRA, VAE, ControlNet)
      - .gguf         llama.cpp / GGML quantised LLMs
      - .ggml         older GGML format
      - .pt / .pth    PyTorch weights, checkpoints, textual inversions
      - .ckpt         legacy Stable Diffusion checkpoints
      - .bin          older PyTorch exports, HF model shards, LoRA adapters
                      (filtered by path context in is_model_extension to
                      avoid matching compiled binaries and git objects)
      - .onnx         ONNX Runtime / interoperability (embedding models,
                      Whisper, sentence-transformers via Chroma, etc.)
      - .h5           Keras / TensorFlow HDF5
      - .pb           TensorFlow SavedModel (frozen graph)
      - .tflite       TensorFlow Lite
      - .mlmodel      Core ML (Apple)

    Returns:
        List of model extensions
    """
    return [
        '.gguf', '.safetensors', '.pth', '.pt', '.bin',
        '.ckpt', '.ggml', '.mlmodel', '.tflite',
        '.onnx', '.h5', '.pb',
    ]


def is_recent_file(filepath: Path, days: int = 30) -> bool:
    """
    Check if a file was *modified* within the last N days.

    Uses modification time (``st_mtime``) rather than access time
    (``st_atime``) because many file systems update atime on every read,
    making it an unreliable indicator of "recently used".

    Args:
        filepath: Path to file
        days: Number of days to check

    Returns:
        True if file was modified recently
    """
    try:
        import time
        stat = filepath.stat()
        days_since_modified = (time.time() - stat.st_mtime) / (24 * 60 * 60)
        return days_since_modified <= days
    except (OSError, AttributeError):
        return False


def check_command_available(command: str) -> bool:
    """
    Check if a command is available in PATH.
    
    Args:
        command: Command name to check
        
    Returns:
        True if command is available
    """
    import shutil
    return shutil.which(command) is not None
