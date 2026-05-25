"""Reference finder - search code files for model references."""

import os
import re
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set

from .config import Config
from .model_analyzer import ModelInfo

# Minimum character length for a search term to be used.
# Short terms like "vae", "clip", "bin" produce too many false positives.
_MIN_TERM_LENGTH = 5


def find_references(
    models: List[ModelInfo],
    code_folders: Optional[List[str]] = None,
    config: Optional[Config] = None,
    progress_callback: Optional[Callable[[Path, int, int], None]] = None,
    found_callback: Optional[Callable[[Path, List[ModelInfo]], None]] = None,
    max_files: int = 10000
) -> Dict[Path, List[ModelInfo]]:
    """
    Search code files for references to model files.

    Uses a single compiled regex per file (instead of iterating over every
    model for every file) to keep time complexity at O(files) rather than
    O(models × files).

    Args:
        models: List of ModelInfo objects to search for
        code_folders: List of folders to search (defaults to config)
        config: Configuration object
        progress_callback: Optional callback function(folder, files_searched, files_found)
        found_callback: Optional callback function(code_file, found_models) called when
            references are found
        max_files: Maximum number of files to search per folder (default: 10000)

    Returns:
        Dictionary mapping code file path to list of referenced models
    """
    if config is None:
        config = Config()

    if code_folders is None:
        code_folders = config.code_folders

    # -----------------------------------------------------------------------
    # Build the lookup structures once, before the file-scan loop.
    # -----------------------------------------------------------------------

    # Map each search term → set of model indices that match it.
    # We only keep terms long enough to avoid generic false positives.
    term_to_model_indices: Dict[str, Set[int]] = {}

    for idx, model in enumerate(models):
        candidates: Set[str] = set()
        # Full filename (e.g. "llama-3-8b-q4_k_m.gguf")
        candidates.add(model.path.name.lower())
        # Stem (e.g. "llama-3-8b-q4_k_m")
        candidates.add(model.path.stem.lower())
        # Parsed model name if meaningfully different
        mn = model.model_name.lower()
        if mn != model.path.stem.lower():
            candidates.add(mn)

        for term in candidates:
            if len(term) >= _MIN_TERM_LENGTH:
                term_to_model_indices.setdefault(term, set()).add(idx)

    if not term_to_model_indices:
        return {}

    # Compile a single regex that matches any of the search terms.
    # re.escape ensures filenames with dots/hyphens don't break the pattern.
    pattern = re.compile(
        "|".join(re.escape(t) for t in term_to_model_indices),
        re.IGNORECASE,
    )

    # File extensions to search
    code_extensions = frozenset({'.py', '.yml', '.yaml', '.json', '.toml', '.txt', '.md'})

    # Directories to skip (common non-code directories)
    skip_dirs = {
        '.git', '.svn', '.hg', '.bzr',
        '__pycache__', '.pytest_cache', '.mypy_cache',
        'node_modules', '.next', '.nuxt',
        '.venv', 'venv', 'env', '.env',
        '.idea', '.vscode', '.vs',
        'build', 'dist', '.build', '.dist',
        '.cache', 'cache',
        'target',
        '.gradle',
    }

    # Results: code file → list of models referenced
    references: Dict[Path, List[ModelInfo]] = {}

    for folder_str in code_folders:
        try:
            folder = Path(folder_str).expanduser().resolve()
            if not folder.exists() or not folder.is_dir():
                continue

            files_searched = 0
            files_found = 0

            # os.walk with in-place dirnames pruning is the correct way to
            # prevent descent into skipped directories (rglob cannot do this).
            for dirpath, dirnames, filenames in os.walk(folder):
                # Prune skipped directories in-place so os.walk won't recurse
                dirnames[:] = [
                    d for d in dirnames
                    if d not in skip_dirs and not d.startswith('.')
                ]

                for filename in filenames:
                    if files_searched >= max_files:
                        break

                    if Path(filename).suffix.lower() not in code_extensions:
                        continue

                    code_file = Path(dirpath) / filename

                    # Skip large files (likely not code)
                    try:
                        if code_file.stat().st_size > 10 * 1024 * 1024:  # 10 MB
                            continue
                    except OSError:
                        continue

                    files_searched += 1

                    found_models = _search_file_for_models(
                        code_file, models, pattern, term_to_model_indices
                    )
                    if found_models:
                        references[code_file] = found_models
                        files_found += 1
                        if found_callback:
                            found_callback(code_file, found_models)

                    if progress_callback and files_searched % 100 == 0:
                        progress_callback(folder, files_searched, files_found)

                if files_searched >= max_files:
                    break

            if progress_callback:
                progress_callback(folder, files_searched, files_found)

        except (OSError, PermissionError):
            continue

    return references


def _search_file_for_models(
    code_file: Path,
    models: List[ModelInfo],
    pattern: re.Pattern,
    term_to_model_indices: Dict[str, Set[int]],
) -> List[ModelInfo]:
    """
    Search a single file for model references using a pre-compiled regex.

    The file is read once; the regex finds all matching terms in a single
    pass, then we resolve which models each match belongs to.

    Args:
        code_file: Path to code file
        models: Master list of models (indexed)
        pattern: Pre-compiled regex covering all search terms
        term_to_model_indices: Map from lower-cased search term to model indices

    Returns:
        Deduplicated list of models referenced in the file
    """
    try:
        content = code_file.read_text(encoding='utf-8', errors='ignore').lower()
    except OSError:
        return []

    matched_indices: Set[int] = set()
    for match in pattern.finditer(content):
        term = match.group(0)
        indices = term_to_model_indices.get(term, set())
        matched_indices.update(indices)

    return [models[i] for i in sorted(matched_indices)]
