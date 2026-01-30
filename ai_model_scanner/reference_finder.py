"""Reference finder - search code files for model references."""

from pathlib import Path
from typing import Callable, Dict, List, Optional, Set

from .config import Config
from .model_analyzer import ModelInfo


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
    
    Args:
        models: List of ModelInfo objects to search for
        code_folders: List of folders to search (defaults to config)
        config: Configuration object
        progress_callback: Optional callback function(folder, files_searched, files_found)
        found_callback: Optional callback function(code_file, found_models) called when references are found
        max_files: Maximum number of files to search per folder (default: 10000)
        
    Returns:
        Dictionary mapping code file path to list of referenced models
    """
    if config is None:
        config = Config()
    
    if code_folders is None:
        code_folders = config.code_folders
    
    # Build search terms from model filenames and model names
    search_terms: Set[str] = set()
    for model in models:
        # Add filename (with and without extension)
        search_terms.add(model.path.name)
        search_terms.add(model.path.stem)
        # Add model name if different
        if model.model_name.lower() != model.path.stem.lower():
            search_terms.add(model.model_name.lower())
    
    # File extensions to search
    code_extensions = ['.py', '.yml', '.yaml', '.json', '.toml', '.txt', '.md']
    
    # Directories to skip (common non-code directories)
    skip_dirs = {
        '.git', '.svn', '.hg', '.bzr',  # Version control
        '__pycache__', '.pytest_cache', '.mypy_cache',  # Python caches
        'node_modules', '.next', '.nuxt',  # Node.js
        '.venv', 'venv', 'env', '.env',  # Virtual environments
        '.idea', '.vscode', '.vs',  # IDE directories
        'build', 'dist', '.build', '.dist',  # Build artifacts
        '.cache', 'cache',  # Caches
        'target',  # Rust/Java builds
        '.gradle',  # Gradle
    }
    
    # Results: code file -> list of models referenced
    references: Dict[Path, List[ModelInfo]] = {}
    
    # Search each code folder
    for folder_str in code_folders:
        try:
            folder = Path(folder_str).expanduser().resolve()
            if not folder.exists() or not folder.is_dir():
                continue
            
            files_searched = 0
            files_found = 0
            
            # Recursively search for code files
            for code_file in folder.rglob("*"):
                # Stop if we've searched too many files
                if files_searched >= max_files:
                    break
                
                # Skip directories in skip list
                if code_file.is_dir():
                    if code_file.name in skip_dirs:
                        # Skip this directory and its contents
                        continue
                    continue
                
                if not code_file.is_file():
                    continue
                
                # Skip files in skipped directories (check parent path)
                if any(skip_dir in code_file.parts for skip_dir in skip_dirs):
                    continue
                
                if code_file.suffix.lower() not in code_extensions:
                    continue
                
                # Skip large files (likely not code)
                try:
                    if code_file.stat().st_size > 10 * 1024 * 1024:  # 10MB
                        continue
                except OSError:
                    continue
                
                files_searched += 1
                
                # Search file for model references
                found_models = _search_file_for_models(code_file, models, search_terms)
                if found_models:
                    references[code_file] = found_models
                    files_found += 1
                    # Call found callback immediately when references are found
                    if found_callback:
                        found_callback(code_file, found_models)
                
                # Call progress callback every 100 files
                if progress_callback and files_searched % 100 == 0:
                    progress_callback(folder, files_searched, files_found)
            
            if progress_callback:
                progress_callback(folder, files_searched, files_found)
        except (OSError, PermissionError):
            # Skip inaccessible folders
            continue
    
    return references


def _search_file_for_models(
    code_file: Path,
    models: List[ModelInfo],
    search_terms: Set[str]
) -> List[ModelInfo]:
    """
    Search a single file for model references.
    
    Args:
        code_file: Path to code file
        models: List of models to search for
        search_terms: Set of search terms (filenames, model names)
        
    Returns:
        List of models referenced in the file
    """
    found_models: List[ModelInfo] = []
    
    try:
        with open(code_file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read().lower()
            
            # Check each model
            for model in models:
                # Check if filename appears
                if model.path.name.lower() in content or model.path.stem.lower() in content:
                    found_models.append(model)
                    continue
                
                # Check if model name appears
                if model.model_name.lower() in content:
                    found_models.append(model)
                    continue
                
                # Check if any search term appears (for partial matches)
                for term in search_terms:
                    if term.lower() in content:
                        # Verify this term is related to this model
                        if (term.lower() in model.path.name.lower() or
                            term.lower() in model.model_name.lower()):
                            if model not in found_models:
                                found_models.append(model)
                            break
    except (OSError, UnicodeDecodeError):
        # Skip files we can't read
        pass
    
    return found_models
