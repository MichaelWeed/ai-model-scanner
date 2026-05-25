"""Model analyzer - extract metadata, compute hashes, parse model names."""

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

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


def compute_hash(filepath: Path, sample_bytes: int = 1024 * 1024) -> str:
    """
    Compute a fast, reliable file fingerprint using a head+tail+size strategy.

    For large files (>10MB):
      - Reads the first ``sample_bytes`` (default 1 MB)
      - Reads the last ``sample_bytes``
      - Encodes the exact file size

    This prevents false-positive duplicate detection between models that share
    the same first megabyte (common with quantised GGUF variants of the same
    base model) while remaining far faster than a full-file SHA-256.

    For small files (<=10MB) the entire file is hashed.

    Args:
        filepath: Path to file
        sample_bytes: Bytes to read from head and tail for large files (default 1 MB)

    Returns:
        SHA256 hex-digest fingerprint string, or empty string on error
    """
    sha256 = hashlib.sha256()

    try:
        file_size = filepath.stat().st_size
        # Encode the size so two files that happen to share head+tail bytes
        # but differ in length are never considered equal.
        sha256.update(file_size.to_bytes(8, byteorder='little'))

        with open(filepath, 'rb') as f:
            if file_size > 10 * 1024 * 1024:  # > 10 MB: sample head + tail
                head = f.read(sample_bytes)
                sha256.update(head)
                # Seek to last sample_bytes (or start of file if smaller)
                tail_offset = max(file_size - sample_bytes, len(head))
                if tail_offset > len(head):
                    f.seek(tail_offset)
                    tail = f.read(sample_bytes)
                    sha256.update(tail)
            else:
                # Small file: hash everything
                sha256.update(f.read())

        return sha256.hexdigest()
    except (OSError, IOError):
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
            # Strip leading/trailing hyphens that arise from empty capture groups
            if result:
                result = result.strip('-')
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
    detect_tool_func: Optional[Callable[[Path], str]] = None
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
        
        # Resolve to canonical path — prevents the same file appearing twice
        # when reached via different scan paths (symlinks, extra_model_paths, etc.)
        canonical_path = filepath.resolve()

        return ModelInfo(
            path=canonical_path,
            size=file_size,
            size_human=format_size(file_size),
            modified_date=modified_date,
            extension=extension,
            model_name=model_name,
            tool=tool,
            hash=hash_value,
            is_recent=is_recent,
        )
    except (OSError, IOError):
        # Skip files we can't access
        return None


def verify_files_identical(
    path_a: Path,
    path_b: Path,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    chunk_size: int = 8 * 1024 * 1024,
) -> bool:
    """
    Definitively confirm two files are byte-for-byte identical via streaming SHA-256.

    Unlike ``compute_hash`` (which samples only the head, tail, and size for
    speed), this function reads every byte of both files simultaneously,
    bailing out at the first difference. It is intentionally slower — use it
    only when you need a guarantee before a destructive action.

    Size is checked first as a fast-reject: files of different sizes are
    never identical.

    Args:
        path_a: First file path.
        path_b: Second file path.
        progress_callback: Optional ``(bytes_read, total_bytes)`` callable
            called after each chunk, suitable for driving a progress bar.
        chunk_size: Read chunk size in bytes (default 8 MB).

    Returns:
        ``True`` if files are identical, ``False`` otherwise.

    Raises:
        OSError: If either file cannot be opened or read.
    """
    stat_a = path_a.stat()
    stat_b = path_b.stat()

    # Fast reject: different sizes → cannot be identical
    if stat_a.st_size != stat_b.st_size:
        return False

    total = stat_a.st_size
    bytes_read = 0
    sha_a = hashlib.sha256()
    sha_b = hashlib.sha256()

    with open(path_a, 'rb') as fa, open(path_b, 'rb') as fb:
        while True:
            chunk_a = fa.read(chunk_size)
            chunk_b = fb.read(chunk_size)

            # Bail at first difference — no need to finish the hash
            if chunk_a != chunk_b:
                return False

            if not chunk_a:
                # Both EOF simultaneously (guaranteed by size equality)
                break

            sha_a.update(chunk_a)
            sha_b.update(chunk_b)
            bytes_read += len(chunk_a)

            if progress_callback is not None:
                progress_callback(bytes_read, total)

    return sha_a.hexdigest() == sha_b.hexdigest()
