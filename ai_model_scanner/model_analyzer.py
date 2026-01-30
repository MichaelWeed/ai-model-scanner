"""Model analyzer - extract metadata, compute hashes, parse model names."""

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from .utils import format_size, is_recent_file


@dataclass
class ModelInfo:
    """Information about a discovered model file."""
    
    path: Path
    size: int
    size_human: str
    modified_date: datetime
    extension: str
    model_name: str
    tool: str
    hash: str
    is_recent: bool = False
    
    def to_dict(self) -> dict:
        """Convert to dictionary for export."""
        return {
            'path': str(self.path),
            'size': self.size,
            'size_human': self.size_human,
            'modified_date': self.modified_date.isoformat(),
            'extension': self.extension,
            'model_name': self.model_name,
            'tool': self.tool,
            'hash': self.hash,
            'is_recent': self.is_recent,
        }


def compute_hash(filepath: Path, max_bytes: int = 1024 * 1024) -> str:
    """
    Compute SHA256 hash of file.
    
    For large files (>10MB), only hash the first max_bytes for performance.
    For smaller files, hash the entire file.
    
    Args:
        filepath: Path to file
        max_bytes: Maximum bytes to read for large files (default 1MB)
        
    Returns:
        SHA256 hash as hex string
    """
    sha256 = hashlib.sha256()
    
    try:
        file_size = filepath.stat().st_size
        
        with open(filepath, 'rb') as f:
            if file_size > 10 * 1024 * 1024:  # Files > 10MB
                # Only hash first max_bytes
                data = f.read(max_bytes)
            else:
                # Hash entire file for smaller files
                data = f.read()
            
            sha256.update(data)
        
        return sha256.hexdigest()
    except (OSError, IOError) as e:
        # Return empty hash on error
        return ""


def parse_model_name(filename: str) -> str:
    """
    Parse model name from filename using regex patterns.
    
    Args:
        filename: Filename to parse
        
    Returns:
        Extracted model name or filename without extension
    """
    # Remove extension
    name = Path(filename).stem.lower()
    
    # Model name patterns (order matters - more specific first)
    patterns = [
        (r'llama-?(\d+\.?\d*)?-?(\d+b?)', lambda m: f"llama-{m.group(1) or ''}-{m.group(2) or ''}".strip('-')),
        (r'qwen(\d+\.?\d*)?-?(\d+b?)', lambda m: f"qwen{m.group(1) or ''}-{m.group(2) or ''}".strip('-')),
        (r'mistral-?(\d+\.?\d*)?-?(\d+b?)', lambda m: f"mistral-{m.group(1) or ''}-{m.group(2) or ''}".strip('-')),
        (r'phi-?(\d+\.?\d*)?-?(\d+b?)', lambda m: f"phi-{m.group(1) or ''}-{m.group(2) or ''}".strip('-')),
        (r'gemma-?(\d+\.?\d*)?-?(\d+b?)', lambda m: f"gemma-{m.group(1) or ''}-{m.group(2) or ''}".strip('-')),
        (r'codellama-?(\d+\.?\d*)?-?(\d+b?)', lambda m: f"codellama-{m.group(1) or ''}-{m.group(2) or ''}".strip('-')),
        (r'falcon-?(\d+\.?\d*)?-?(\d+b?)', lambda m: f"falcon-{m.group(1) or ''}-{m.group(2) or ''}".strip('-')),
        (r'neural-?chat-?(\d+\.?\d*)?-?(\d+b?)', lambda m: f"neural-chat-{m.group(1) or ''}-{m.group(2) or ''}".strip('-')),
        (r'star(coder|code)-?(\d+\.?\d*)?-?(\d+b?)', lambda m: f"star{m.group(1)}-{m.group(2) or ''}-{m.group(3) or ''}".strip('-')),
        (r'sdxl|sd-xl', lambda m: "SDXL"),
        (r'sd-?(\d+\.?\d*)', lambda m: f"SD-{m.group(1)}"),
        (r'flux', lambda m: "Flux"),
        (r'stable-diffusion', lambda m: "Stable Diffusion"),
        (r'stable_diffusion', lambda m: "Stable Diffusion"),
        (r'stablediffusion', lambda m: "Stable Diffusion"),
        (r'clip', lambda m: "CLIP"),
        (r'vae', lambda m: "VAE"),
        (r'unet', lambda m: "UNet"),
        (r'loras?', lambda m: "LoRA"),
        (r'controlnet', lambda m: "ControlNet"),
    ]
    
    for pattern, formatter in patterns:
        match = re.search(pattern, name, re.IGNORECASE)
        if match:
            result = formatter(match)
            if result:
                return result
    
    # If no pattern matches, try to extract meaningful parts
    # Remove common suffixes/prefixes
    cleaned = re.sub(r'[-_]?(q\d|f16|f32|fp16|fp32|int8|int4|gguf|safetensors|pth|pt|bin|ckpt)', '', name)
    cleaned = re.sub(r'[-_]?(v\d+\.?\d*|version\d*)', '', cleaned)
    
    # If cleaned name is too short or just numbers, use original stem
    if len(cleaned) < 3 or cleaned.isdigit():
        return Path(filename).stem
    
    return cleaned.title() if cleaned != name else Path(filename).stem


def analyze_model_file(
    filepath: Path,
    min_size_bytes: int = 0,
    compute_hash_value: bool = True,
    detect_tool_func=None
) -> Optional[ModelInfo]:
    """
    Analyze a model file and extract all metadata.
    
    Args:
        filepath: Path to model file
        min_size_bytes: Minimum file size in bytes (skip if smaller)
        compute_hash_value: Whether to compute hash (can be slow)
        detect_tool_func: Function to detect tool (defaults to tool_detector.detect_tool)
        
    Returns:
        ModelInfo object or None if file should be skipped
    """
    try:
        stat = filepath.stat()
        file_size = stat.st_size
        
        # Skip if too small
        if file_size < min_size_bytes:
            return None
        
        # Get file metadata
        modified_date = datetime.fromtimestamp(stat.st_mtime)
        extension = filepath.suffix.lower()
        filename = filepath.name
        
        # Parse model name
        model_name = parse_model_name(filename)
        
        # Detect tool
        if detect_tool_func is None:
            from .tool_detector import detect_tool
            detect_tool_func = detect_tool
        
        tool = detect_tool_func(filepath)
        
        # Compute hash
        hash_value = ""
        if compute_hash_value:
            hash_value = compute_hash(filepath)
        
        # Check if recent
        is_recent = is_recent_file(filepath, days=30)
        
        return ModelInfo(
            path=filepath,
            size=file_size,
            size_human=format_size(file_size),
            modified_date=modified_date,
            extension=extension,
            model_name=model_name,
            tool=tool,
            hash=hash_value,
            is_recent=is_recent,
        )
    except (OSError, IOError) as e:
        # Skip files we can't access
        return None
