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
    
    # Extract number and unit
    match = re.match(r'^(\d+(?:\.\d+)?)\s*([KMGT]?B?)$', size_str)
    if not match:
        raise ValueError(f"Invalid size format: {size_str}")
    
    number = float(match.group(1))
    unit = match.group(2) or 'B'
    
    # Normalize unit (remove B if present, handle M vs MB)
    if unit.endswith('B'):
        unit = unit[:-1]
    
    multipliers = {
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
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def expand_path(path: str) -> Path:
    """
    Expand user home directory and resolve to absolute path.
    
    Args:
        path: Path string (may contain ~)
        
    Returns:
        Expanded Path object
    """
    return Path(path).expanduser().resolve()


def is_model_extension(filename: str, extensions: Optional[list] = None) -> bool:
    """
    Check if file has a model extension.
    
    Args:
        filename: Filename to check
        extensions: List of extensions (defaults to common model extensions)
        
    Returns:
        True if file has a model extension
    """
    if extensions is None:
        extensions = [
            '.gguf', '.safetensors', '.pth', '.pt', '.bin',
            '.ckpt', '.ggml', '.mlmodel', '.tflite'
        ]
    
    filename_lower = filename.lower()
    return any(filename_lower.endswith(ext.lower()) for ext in extensions)


def get_model_extensions() -> list:
    """
    Get list of common model file extensions.
    
    Returns:
        List of model extensions
    """
    return [
        '.gguf', '.safetensors', '.pth', '.pt', '.bin',
        '.ckpt', '.ggml', '.mlmodel', '.tflite'
    ]


def is_recent_file(filepath: Path, days: int = 30) -> bool:
    """
    Check if file was accessed within the last N days.
    
    Args:
        filepath: Path to file
        days: Number of days to check
        
    Returns:
        True if file was accessed recently
    """
    try:
        stat = filepath.stat()
        import time
        current_time = time.time()
        access_time = stat.st_atime
        days_since_access = (current_time - access_time) / (24 * 60 * 60)
        return days_since_access <= days
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
