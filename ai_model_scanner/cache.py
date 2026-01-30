"""Cache management for scan results."""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from .model_analyzer import ModelInfo


def get_cache_path() -> Path:
    """Get platform-specific cache file path."""
    if sys.platform == "win32":
        appdata = os.getenv("APPDATA", "")
        if appdata:
            cache_dir = Path(appdata) / "ai-model-scanner"
        else:
            cache_dir = Path.home() / ".cache" / "ai-model-scanner"
    else:
        cache_dir = Path.home() / ".cache" / "ai-model-scanner"
    
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / "last_scan.json"


def save_scan_results(models: List[ModelInfo], scan_params: Optional[dict] = None) -> None:
    """
    Save scan results to cache file.
    
    Args:
        models: List of ModelInfo objects
        scan_params: Optional dictionary of scan parameters (root, min_size, etc.)
    """
    cache_path = get_cache_path()
    
    data = {
        'timestamp': datetime.now().isoformat(),
        'scan_params': scan_params or {},
        'models': [model.to_dict() for model in models],
        'total_models': len(models),
    }
    
    try:
        with open(cache_path, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception:
        # Silently fail - cache is optional
        pass


def load_scan_results(max_age_hours: int = 24) -> Optional[tuple[List[ModelInfo], dict]]:
    """
    Load scan results from cache if available and recent.
    
    Args:
        max_age_hours: Maximum age of cache in hours (default: 24)
        
    Returns:
        Tuple of (models list, scan_params dict) if cache is valid, None otherwise
    """
    cache_path = get_cache_path()
    
    if not cache_path.exists():
        return None
    
    try:
        # Check cache age
        cache_age = datetime.now() - datetime.fromtimestamp(cache_path.stat().st_mtime)
        if cache_age > timedelta(hours=max_age_hours):
            return None
        
        # Load cache
        with open(cache_path, 'r') as f:
            data = json.load(f)
        
        # Reconstruct ModelInfo objects
        models = []
        for model_dict in data.get('models', []):
            # Reconstruct ModelInfo from dict
            model = ModelInfo(
                path=Path(model_dict['path']),
                size=model_dict['size'],
                size_human=model_dict['size_human'],
                modified_date=datetime.fromisoformat(model_dict['modified_date']),
                extension=model_dict['extension'],
                model_name=model_dict['model_name'],
                tool=model_dict['tool'],
                hash=model_dict.get('hash', ''),
                is_recent=model_dict.get('is_recent', False),
            )
            models.append(model)
        
        scan_params = data.get('scan_params', {})
        return models, scan_params
    
    except Exception:
        # Cache is corrupted or invalid
        return None


def get_cache_info() -> Optional[dict]:
    """Get information about cached scan results."""
    cache_path = get_cache_path()
    
    if not cache_path.exists():
        return None
    
    try:
        cache_age = datetime.now() - datetime.fromtimestamp(cache_path.stat().st_mtime)
        
        with open(cache_path, 'r') as f:
            data = json.load(f)
        
        return {
            'timestamp': data.get('timestamp'),
            'age': cache_age,
            'age_human': _format_timedelta(cache_age),
            'total_models': data.get('total_models', 0),
            'scan_params': data.get('scan_params', {}),
        }
    except Exception:
        return None


def _format_timedelta(td: timedelta) -> str:
    """Format timedelta to human-readable string."""
    hours = td.total_seconds() / 3600
    if hours < 1:
        minutes = td.total_seconds() / 60
        return f"{int(minutes)} minute(s)"
    elif hours < 24:
        return f"{int(hours)} hour(s)"
    else:
        days = hours / 24
        return f"{int(days)} day(s)"


def get_directory_index_path() -> Path:
    """Get platform-specific directory index cache file path."""
    cache_dir = get_cache_path().parent
    return cache_dir / "directory_index.json"


def load_directory_index() -> Dict[str, dict]:
    """
    Load directory index from cache.
    
    Returns:
        Dictionary mapping directory path (str) to metadata dict with:
        - mtime: modification time (float)
        - model_count: number of models in directory (int)
        - model_hashes: list of model hashes (List[str])
    """
    index_path = get_directory_index_path()
    
    if not index_path.exists():
        return {}
    
    try:
        with open(index_path, 'r') as f:
            return json.load(f)
    except Exception:
        return {}


def save_directory_index(index: Dict[str, dict]) -> None:
    """
    Save directory index to cache.
    
    Args:
        index: Dictionary mapping directory path to metadata dict
    """
    index_path = get_directory_index_path()
    
    try:
        with open(index_path, 'w') as f:
            json.dump(index, f, indent=2)
    except Exception:
        # Silently fail - cache is optional
        pass


def update_directory_index(directory: Path, models: List[ModelInfo]) -> None:
    """
    Update directory index for a specific directory.
    
    Args:
        directory: Directory path
        models: List of ModelInfo objects found in that directory
    """
    try:
        # Get directory modification time
        mtime = directory.stat().st_mtime
        
        # Extract model hashes
        model_hashes = [m.hash for m in models if m.hash]
        
        # Load existing index
        index = load_directory_index()
        
        # Update entry
        dir_str = str(directory)
        index[dir_str] = {
            'mtime': mtime,
            'model_count': len(models),
            'model_hashes': model_hashes,
        }
        
        # Save updated index
        save_directory_index(index)
    except Exception:
        # Silently fail - cache is optional
        pass


def is_directory_unchanged(directory: Path, cached_entry: dict) -> bool:
    """
    Check if a directory is unchanged based on cached metadata.
    
    Args:
        directory: Directory path to check
        cached_entry: Cached metadata dict with 'mtime' key
        
    Returns:
        True if directory appears unchanged, False otherwise
    """
    try:
        if not directory.exists():
            return False
        
        current_mtime = directory.stat().st_mtime
        cached_mtime = cached_entry.get('mtime', 0)
        
        # Allow small tolerance for filesystem precision
        return abs(current_mtime - cached_mtime) < 1.0
    except Exception:
        return False
