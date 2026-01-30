"""Core scanning engine - coordinate file discovery across known paths and system scan."""

import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Optional, Set

from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from .cache import (
    is_directory_unchanged,
    load_directory_index,
    load_scan_results,
    save_directory_index,
    update_directory_index,
)
from .config import Config
from .model_analyzer import ModelInfo, analyze_model_file
from .utils import check_command_available, expand_path, get_model_extensions, is_model_extension


class Scanner:
    """Core scanning engine for discovering model files."""
    
    def __init__(self, config: Optional[Config] = None):
        """
        Initialize scanner.
        
        Args:
            config: Configuration object (creates default if None)
        """
        self.config = config or Config()
        self.model_extensions = get_model_extensions()
        self.min_size_bytes = self.config.min_size_mb * 1024 * 1024
    
    def scan_known_paths(
        self, 
        progress: Optional[Progress] = None,
        use_incremental: bool = True
    ) -> List[ModelInfo]:
        """
        Scan known tool paths for model files.
        
        Args:
            progress: Optional Rich progress bar
            use_incremental: If True, skip unchanged directories using cache
            
        Returns:
            List of discovered ModelInfo objects
        """
        known_paths = self.config.get_all_known_paths()
        all_models: List[ModelInfo] = []
        
        # Load directory index for incremental scanning
        directory_index = {}
        cached_models_by_dir = {}
        if use_incremental:
            directory_index = load_directory_index()
            # Try to load cached models
            cached_result = load_scan_results(max_age_hours=24 * 7)  # 7 days for directory cache
            if cached_result:
                cached_models, _ = cached_result
                # Group cached models by directory
                for model in cached_models:
                    dir_str = str(model.path.parent)
                    if dir_str not in cached_models_by_dir:
                        cached_models_by_dir[dir_str] = []
                    cached_models_by_dir[dir_str].append(model)
        
        skipped_count = 0
        scanned_count = 0
        
        task = None
        if progress:
            task = progress.add_task("[cyan]Scanning known paths...", total=len(known_paths))
        
        for path_str in known_paths:
            try:
                path = expand_path(path_str)
                if not path.exists() or not path.is_dir():
                    continue
                
                dir_str = str(path)
                
                # Check if directory is unchanged (incremental scan)
                if use_incremental and dir_str in directory_index:
                    cached_entry = directory_index[dir_str]
                    if is_directory_unchanged(path, cached_entry):
                        # Use cached models
                        if dir_str in cached_models_by_dir:
                            all_models.extend(cached_models_by_dir[dir_str])
                            skipped_count += 1
                            if progress and task is not None:
                                progress.update(task, advance=1)
                            continue
                
                # Directory changed or not in cache - scan it
                models = self._scan_directory(path, progress)
                all_models.extend(models)
                scanned_count += 1
                
                # Update directory index
                if use_incremental:
                    update_directory_index(path, models)
                    
            except (OSError, PermissionError) as e:
                # Skip inaccessible paths
                if progress:
                    progress.console.print(f"[yellow]Warning:[/yellow] Skipping {path_str}: {e}")
            
            if progress and task is not None:
                progress.update(task, advance=1)
        
        if progress and skipped_count > 0:
            progress.console.print(f"[dim]Skipped {skipped_count} unchanged directories, scanned {scanned_count} changed[/dim]")
        
        return all_models
    
    def scan_broad_system(self, root: Path, progress: Optional[Progress] = None) -> List[ModelInfo]:
        """
        Perform broad system scan for model files.
        
        Args:
            root: Root directory to scan
            progress: Optional Rich progress bar
            
        Returns:
            List of discovered ModelInfo objects
        """
        root = expand_path(str(root))
        
        if progress:
            progress.console.print(f"[cyan]Scanning system from {root}...[/cyan]")
        
        # Try to use fd (fastest), fallback to find, then mdfind
        files = self._find_files_with_tool(root, progress)
        
        # Filter by extension and size, then analyze
        models: List[ModelInfo] = []
        
        if progress:
            task = progress.add_task("[cyan]Analyzing files...", total=len(files))
        
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            for filepath in files:
                if is_model_extension(filepath.name, self.model_extensions):
                    future = executor.submit(
                        analyze_model_file,
                        filepath,
                        self.min_size_bytes,
                        compute_hash_value=True
                    )
                    futures.append(future)
            
            for future in as_completed(futures):
                try:
                    model = future.result()
                    if model:
                        models.append(model)
                except Exception as e:
                    if progress:
                        progress.console.print(f"[red]Error analyzing file:[/red] {e}")
                
                if progress and task is not None:
                    progress.update(task, advance=1)
        
        return models
    
    def _find_files_with_tool(self, root: Path, progress: Optional[Progress] = None) -> List[Path]:
        """
        Find files using fd, find, or mdfind.
        
        Args:
            root: Root directory to search
            progress: Optional Rich progress bar
            
        Returns:
            List of file paths
        """
        files: List[Path] = []
        
        # Try fd first (fastest)
        if check_command_available("fd"):
            try:
                # fd supports multiple -e flags for multiple extensions
                # -H/--hidden: include hidden dirs (e.g. ~/.lmstudio) so we don't miss models
                cmd = [
                    "fd",
                    "-t", "f",
                    "-H",  # Include hidden files/dirs (e.g. .lmstudio, .ollama)
                    "--size", f"+{self.config.min_size_mb}M",
                ]
                # Add extension filters
                for ext in self.model_extensions:
                    cmd.extend(["-e", ext.lstrip('.').lower()])
                
                cmd.extend([".", str(root)])
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=300,  # 5 minute timeout
                    cwd=str(root)
                )
                if result.returncode == 0:
                    files = [Path(line.strip()) for line in result.stdout.splitlines() if line.strip()]
                    if progress:
                        progress.console.print(f"[green]Found {len(files)} files using fd[/green]")
                    return files
            except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                pass
        
        # Fallback to find
        try:
            # Build find command with extension filters
            size_arg = f"+{self.config.min_size_mb}M"
            
            # Build: find root -type f -size +500M \( -iname "*.ext1" -o -iname "*.ext2" ... \)
            cmd = ["find", str(root), "-type", "f", "-size", size_arg]
            
            if self.model_extensions:
                cmd.append("(")
                for i, ext in enumerate(self.model_extensions):
                    if i > 0:
                        cmd.append("-o")
                    cmd.extend(["-iname", f"*{ext}"])
                cmd.append(")")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,  # 10 minute timeout for find
            )
            if result.returncode == 0:
                files = [Path(line.strip()) for line in result.stdout.splitlines() if line.strip()]
                if progress:
                    progress.console.print(f"[green]Found {len(files)} files using find[/green]")
                return files
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            if progress:
                progress.console.print(f"[yellow]find failed:[/yellow] {e}")
        
        # Windows-specific: Try dir command (less efficient but works)
        if sys.platform == "win32":
            try:
                # Use PowerShell to find files (more reliable than cmd)
                ext_filters = " -or ".join([f'$_.Extension -eq "{ext}"' for ext in self.model_extensions])
                ps_script = f'''
                Get-ChildItem -Path "{root}" -Recurse -File -ErrorAction SilentlyContinue |
                Where-Object {{ ({ext_filters}) -and $_.Length -ge {self.min_size_bytes} }} |
                Select-Object -ExpandProperty FullName
                '''
                cmd = ["powershell", "-Command", ps_script]
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=600,
                )
                if result.returncode == 0:
                    files = [Path(line.strip()) for line in result.stdout.splitlines() if line.strip()]
                    if files:
                        if progress:
                            progress.console.print(f"[green]Found {len(files)} files using PowerShell[/green]")
                        return files
            except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
                if progress:
                    progress.console.print(f"[yellow]PowerShell search failed:[/yellow] {e}")
        
        # macOS-specific: Try mdfind (Spotlight search) as fallback
        elif sys.platform == "darwin":
            try:
                # mdfind uses Spotlight metadata, so we search by file extension
                query_parts = []
                for ext in self.model_extensions:
                    query_parts.append(f'kMDItemFSName == "*{ext}"')
                
                query = " || ".join(query_parts)
                cmd = ["mdfind", "-onlyin", str(root), query]
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                if result.returncode == 0:
                    candidate_files = [Path(line.strip()) for line in result.stdout.splitlines() if line.strip()]
                    # Filter by size (mdfind doesn't support size filtering directly)
                    files = [
                        f for f in candidate_files
                        if f.exists() and f.stat().st_size >= self.min_size_bytes
                    ]
                    if progress:
                        progress.console.print(f"[green]Found {len(files)} files using mdfind[/green]")
                    return files
            except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
                if progress:
                    progress.console.print(f"[yellow]mdfind failed:[/yellow] {e}")
        
        # If all tools fail, fall back to manual directory traversal
        if progress:
            progress.console.print("[yellow]Falling back to manual directory scan...[/yellow]")
        return self._scan_directory_recursive(root)
    
    def _scan_directory(self, directory: Path, progress: Optional[Progress] = None) -> List[ModelInfo]:
        """
        Scan a single directory for model files.
        
        Args:
            directory: Directory to scan
            progress: Optional Rich progress bar
            
        Returns:
            List of ModelInfo objects
        """
        models: List[ModelInfo] = []
        
        try:
            for item in directory.rglob("*"):
                if item.is_file() and is_model_extension(item.name, self.model_extensions):
                    try:
                        if item.stat().st_size >= self.min_size_bytes:
                            model = analyze_model_file(
                                item,
                                self.min_size_bytes,
                                compute_hash_value=True
                            )
                            if model:
                                models.append(model)
                    except (OSError, PermissionError):
                        # Skip files we can't access
                        continue
        except (OSError, PermissionError):
            # Skip directories we can't access
            pass
        
        return models
    
    def _scan_directory_recursive(self, root: Path) -> List[Path]:
        """
        Recursively scan directory for model files (fallback method).
        
        Args:
            root: Root directory to scan
            
        Returns:
            List of file paths
        """
        files: List[Path] = []
        
        try:
            for item in root.rglob("*"):
                if item.is_file() and is_model_extension(item.name, self.model_extensions):
                    try:
                        if item.stat().st_size >= self.min_size_bytes:
                            files.append(item)
                    except (OSError, PermissionError):
                        continue
        except (OSError, PermissionError):
            pass
        
        return files
    
    def scan(
        self,
        root: Optional[Path] = None,
        full_scan: bool = False,
        progress: Optional[Progress] = None,
        learn_paths: bool = False,
        use_incremental: bool = True
    ) -> List[ModelInfo]:
        """
        Main scan method - coordinates known paths and broad system scan.
        
        Args:
            root: Root directory for broad scan (defaults to home)
            full_scan: If True, skip known paths and only do broad scan
            progress: Optional Rich progress bar
            learn_paths: If True, learn new paths from discovered models
            use_incremental: If True, use incremental scanning (skip unchanged dirs)
            
        Returns:
            List of all discovered ModelInfo objects
        """
        all_models: List[ModelInfo] = []
        seen_paths: Set[Path] = set()
        known_paths_set: Set[Path] = set()
        
        # Build set of known paths for comparison
        if not full_scan:
            for path_str in self.config.get_all_known_paths():
                try:
                    known_paths_set.add(expand_path(path_str))
                except Exception:
                    pass
        
        # Scan known paths unless full_scan is True
        if not full_scan:
            known_models = self.scan_known_paths(progress, use_incremental=use_incremental)
            all_models.extend(known_models)
            seen_paths.update(model.path for model in known_models)
        
        # Perform broad system scan
        if root is None:
            root = Path.home()
        
        broad_models = self.scan_broad_system(root, progress)
        
        # Deduplicate and learn paths
        discovered_paths_by_tool: dict = {}
        for model in broad_models:
            if model.path not in seen_paths:
                all_models.append(model)
                seen_paths.add(model.path)
                
                # Learn paths: extract parent directory if it's not in known paths
                if learn_paths and model.tool != "Unknown":
                    model_dir = model.path.parent
                    # Check if this directory (or a parent) should be learned
                    # Look for common patterns like "models", "checkpoints", etc.
                    path_str = str(model_dir).lower()
                    if any(pattern in path_str for pattern in ['models', 'checkpoints', 'loras', 'weights']):
                        # Check if this path or a parent is already known
                        is_known = False
                        for known_path in known_paths_set:
                            try:
                                if model_dir == known_path or model_dir.is_relative_to(known_path):
                                    is_known = True
                                    break
                            except (ValueError, AttributeError):
                                # Path comparison failed, skip
                                pass
                        
                        if not is_known:
                            # Store for learning (use the most specific directory with "models" in it)
                            if model.tool not in discovered_paths_by_tool:
                                discovered_paths_by_tool[model.tool] = set()
                            
                            # Find the best directory to learn (prefer directories with "models" in name)
                            current = model_dir
                            best_dir = current
                            for _ in range(3):  # Check up to 3 levels up
                                if 'models' in current.name.lower() or 'checkpoint' in current.name.lower():
                                    best_dir = current
                                    break
                                if current.parent == current:  # Reached root
                                    break
                                current = current.parent
                            
                            discovered_paths_by_tool[model.tool].add(best_dir)
        
        # Learn discovered paths
        if learn_paths and discovered_paths_by_tool:
            learned_count = 0
            for tool_name, paths in discovered_paths_by_tool.items():
                for path in paths:
                    # Convert to string, using ~ for home directory if applicable
                    path_str = str(path)
                    try:
                        home = Path.home()
                        if path.is_relative_to(home):
                            path_str = "~/" + str(path.relative_to(home))
                    except (ValueError, AttributeError):
                        pass
                    
                    if self.config.add_discovered_path(tool_name, path_str):
                        learned_count += 1
            
            if learned_count > 0 and progress:
                progress.console.print(f"\n[green]Learned {learned_count} new path(s) from discovered models[/green]")
        
        return all_models
