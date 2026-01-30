"""Duplicate detection - hash-based grouping and duplicate identification."""

from collections import defaultdict
from typing import Dict, List

from .model_analyzer import ModelInfo
from .utils import format_size


def find_duplicates(models: List[ModelInfo]) -> Dict[str, List[ModelInfo]]:
    """
    Group models by hash to find duplicates.
    
    Args:
        models: List of ModelInfo objects
        
    Returns:
        Dictionary mapping hash to list of ModelInfo objects with that hash
    """
    # First, deduplicate by path to avoid phantom duplicates
    # (in case the same file appears multiple times in the models list)
    seen_paths: Dict[Path, ModelInfo] = {}
    for model in models:
        if model.path not in seen_paths:
            seen_paths[model.path] = model
        # If we see the same path again, keep the one with a hash if available
        elif model.hash and not seen_paths[model.path].hash:
            seen_paths[model.path] = model
    
    # Now group by hash
    hash_groups: Dict[str, List[ModelInfo]] = defaultdict(list)
    
    for model in seen_paths.values():
        if model.hash:  # Only group models with computed hashes
            hash_groups[model.hash].append(model)
    
    # Filter to only return groups with duplicates (more than one file)
    # Also deduplicate within each group by path (in case same path appears in same hash group)
    duplicates = {}
    for h, models_list in hash_groups.items():
        if len(models_list) > 1:
            # Deduplicate by path within this hash group
            unique_models = []
            seen_in_group = set()
            for model in models_list:
                if model.path not in seen_in_group:
                    unique_models.append(model)
                    seen_in_group.add(model.path)
            
            # Only add if we still have duplicates after deduplication
            if len(unique_models) > 1:
                duplicates[h] = unique_models
    
    return duplicates


def get_duplicate_stats(duplicates: Dict[str, List[ModelInfo]]) -> Dict:
    """
    Get statistics about duplicates.
    
    Args:
        duplicates: Dictionary of hash -> list of ModelInfo objects
        
    Returns:
        Dictionary with duplicate statistics
    """
    total_duplicate_groups = len(duplicates)
    total_duplicate_files = sum(len(files) for files in duplicates.values())
    total_wasted_space = 0
    
    for files in duplicates.values():
        if len(files) > 1:
            # Calculate wasted space (all copies except one)
            file_size = files[0].size
            wasted = file_size * (len(files) - 1)
            total_wasted_space += wasted
    
    return {
        'duplicate_groups': total_duplicate_groups,
        'duplicate_files': total_duplicate_files,
        'wasted_space': total_wasted_space,
        'wasted_space_human': format_size(total_wasted_space) if total_wasted_space > 0 else "0 B"
    }


