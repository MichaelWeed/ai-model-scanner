"""CLI interface for AI Model Scanner."""

import csv
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from .cache import get_cache_info, load_scan_results, save_scan_results
from .config import Config
from .duplicate_detector import find_duplicates, get_duplicate_stats
from .formatters import Formatter
from .model_analyzer import ModelInfo
from .path_detector import detect_lm_studio_paths
from .reference_finder import find_references
from .scanner import Scanner
from .utils import check_command_available, format_size, parse_size
from .watcher import ModelWatcher

app = typer.Typer(
    name="ai-model-scanner",
    help="Lightweight cross-platform tool to scan for local AI model files",
    add_completion=False
)
console = Console()


@app.command()
def scan(
    root: Optional[str] = typer.Option(
        None,
        "--root",
        "-r",
        help="Root directory to scan (default: home directory)"
    ),
    min_size: str = typer.Option(
        "500MB",
        "--min-size",
        "-s",
        help="Minimum file size (e.g., 500MB, 1GB)"
    ),
    full_scan: bool = typer.Option(
        False,
        "--full-scan",
        help="Skip known paths, perform full system scan (disables incremental scanning)"
    ),
    no_incremental: bool = typer.Option(
        False,
        "--no-incremental",
        help="Disable incremental scanning (scan all directories even if unchanged)"
    ),
    export: Optional[str] = typer.Option(
        None,
        "--export",
        "-e",
        help="Export format: json, csv, or txt"
    ),
    show_recent: bool = typer.Option(
        False,
        "--show-recent",
        help="Highlight files accessed in last 30 days"
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be scanned without actually scanning"
    ),
    find_references_flag: bool = typer.Option(
        False,
        "--find-references",
        help="Search code files for model references"
    ),
    health: bool = typer.Option(
        False,
        "--health",
        help="Check Ollama/LM Studio CLI for registered models"
    ),
    learn_paths: bool = typer.Option(
        False,
        "--learn-paths",
        help="Learn new model paths from discovered files and save to config"
    ),
) -> None:
    """Scan for AI model files on your system."""
    config = Config()
    
    # Parse minimum size
    try:
        min_size_bytes = parse_size(min_size)
    except ValueError as e:
        console.print(f"[red]Error:[/red] Invalid size format: {min_size}")
        console.print(f"  {e}")
        raise typer.Exit(1)
    
    # Determine root directory
    if root is None:
        root_path = Path.home()
    else:
        root_path = Path(root).expanduser().resolve()
        if not root_path.exists():
            console.print(f"[red]Error:[/red] Root directory does not exist: {root}")
            raise typer.Exit(1)
    
    if dry_run:
        console.print("[yellow]Dry run mode - showing scan configuration:[/yellow]")
        console.print(f"  Root: {root_path}")
        console.print(f"  Min size: {min_size}")
        console.print(f"  Full scan: {full_scan}")
        if not full_scan:
            known_paths = config.get_all_known_paths()
            console.print(f"  Known paths to scan: {len(known_paths)}")
            for path in known_paths[:5]:  # Show first 5
                console.print(f"    - {path}")
            if len(known_paths) > 5:
                console.print(f"    ... and {len(known_paths) - 5} more")
        raise typer.Exit(0)
    
    # Initialize scanner
    scanner = Scanner(config)
    scanner.min_size_bytes = min_size_bytes
    
    # Create progress bar
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console
    ) as progress:
        # Perform scan
        console.print("[bold cyan]Starting scan...[/bold cyan]")
        if learn_paths:
            console.print("[yellow]Path learning enabled - discovered paths will be saved to config[/yellow]")
        use_incremental = not no_incremental and not full_scan
        models = scanner.scan(
            root=root_path, 
            full_scan=full_scan, 
            progress=progress, 
            learn_paths=learn_paths,
            use_incremental=use_incremental
        )
    
    if not models:
        console.print("[yellow]No models found matching criteria.[/yellow]")
        raise typer.Exit(0)
    
    # Save scan results to cache for later use
    scan_params = {
        'root': str(root_path),
        'min_size': min_size,
        'full_scan': full_scan,
    }
    save_scan_results(models, scan_params)
    
    # Find duplicates
    duplicates = find_duplicates(models)
    
    # Health check
    if health:
        _perform_health_check(models, console)
    
    # Find references if requested
    references = None
    if find_references_flag:
        console.print("\n[cyan]Searching for code references...[/cyan]")
        console.print("[dim]This may take a moment. Scanning code files for model references...[/dim]")
        console.print("[dim]Paths will appear below as references are found:[/dim]\n")
        
        streaming_callback = _create_streaming_callback(console)
        references = find_references(
            models,
            config=config,
            found_callback=streaming_callback
        )
        console.print()  # Blank line after streaming
        
        if references:
            console.print(f"[green]✓ Found references in {len(references)} files[/green]")
            for code_file, ref_models in list(references.items())[:10]:  # Show first 10
                console.print(f"  {code_file}: {len(ref_models)} models")
            if len(references) > 10:
                console.print(f"  ... and {len(references) - 10} more files")
        else:
            console.print("[yellow]No code references found[/yellow]")
    
    # Format output
    formatter = Formatter(console)
    
    if export:
        # Export to file directly
        output_path = Path.cwd() / f"models.{export}"
        if export.lower() == "json":
            formatter.export_json(models, output_path)
        elif export.lower() == "csv":
            formatter.export_csv(models, output_path)
        elif export.lower() == "txt":
            formatter.export_txt(models, output_path)
        else:
            console.print(f"[red]Error:[/red] Unknown export format: {export}")
            console.print("  Supported formats: json, csv, txt")
            raise typer.Exit(1)
        console.print(f"\n[green]✓ Exported to {output_path}[/green]")
    else:
        # Display table first
        formatter.format_table(
            models,
            duplicates=duplicates,
            group_by_tool=config.group_by_tool,
            show_recent=show_recent
        )
        
        # Show references if found
        if references:
            console.print("\n[bold]Code References:[/bold]")
            for code_file, ref_models in list(references.items())[:20]:  # Show first 20
                console.print(f"\n  [cyan]{code_file}[/cyan]")
                for model in ref_models[:5]:  # Show first 5 models per file
                    console.print(f"    - {model.model_name} ({model.size_human})")
                if len(ref_models) > 5:
                    console.print(f"    ... and {len(ref_models) - 5} more")
        
        # Offer interactive export after showing results
        console.print("\n[yellow]Export results?[/yellow] (json/csv/txt or Enter to skip)")
        console.print("[dim]Tip: Results are cached - run 'duplicates' or 'cleanup' without rescanning[/dim]")
        try:
            export_choice = input("  Format: ").strip().lower()
            if export_choice in ['json', 'csv', 'txt']:
                output_path = Path.cwd() / f"models.{export_choice}"
                if export_choice == "json":
                    formatter.export_json(models, output_path)
                elif export_choice == "csv":
                    formatter.export_csv(models, output_path)
                elif export_choice == "txt":
                    formatter.export_txt(models, output_path)
                console.print(f"[green]✓ Exported to {output_path}[/green]")
        except (EOFError, KeyboardInterrupt):
            # Handle non-interactive environments (pipes, scripts, etc.)
            pass


@app.command()
def watch(
    paths: Optional[str] = typer.Option(
        None,
        "--paths",
        "-p",
        help="Comma-separated paths to watch (default: known tool paths)"
    ),
    min_size: str = typer.Option(
        "500MB",
        "--min-size",
        "-s",
        help="Minimum file size for notifications"
    ),
) -> None:
    """Watch file system for new model files (background daemon)."""
    try:
        config = Config()
        
        # Parse minimum size
        try:
            min_size_bytes = parse_size(min_size)
            config.watcher_min_size_mb = min_size_bytes / (1024 * 1024)
        except ValueError as e:
            console.print(f"[red]Error:[/red] Invalid size format: {min_size}")
            console.print(f"  {e}")
            raise typer.Exit(1)
        
        # Parse paths
        watch_paths = None
        if paths:
            watch_paths = [p.strip() for p in paths.split(",")]
        
        # Create and start watcher
        watcher = ModelWatcher(config)
        console.print("[bold cyan]Starting file system watcher...[/bold cyan]")
        watcher.run(paths=watch_paths)
    except KeyboardInterrupt:
        console.print("\n[yellow]Watcher stopped by user[/yellow]")
        raise typer.Exit(0)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def health(
    root: Optional[str] = typer.Option(
        None,
        "--root",
        "-r",
        help="Root directory to scan for comparison"
    ),
) -> None:
    """Check Ollama/LM Studio CLI and cross-reference with scanned models."""
    config = Config()
    
    # Determine root directory
    if root is None:
        root_path = Path.home()
    else:
        root_path = Path(root).expanduser().resolve()
    
    # Perform quick scan
    console.print("[cyan]Scanning for models...[/cyan]")
    scanner = Scanner(config)
    models = scanner.scan(root=root_path, full_scan=False)
    
    # Perform health check
    _perform_health_check(models, console)


@app.command()
def duplicates(
    root: Optional[str] = typer.Option(
        None,
        "--root",
        "-r",
        help="Root directory to scan (default: use cached results if available)"
    ),
    min_size: str = typer.Option(
        "500MB",
        "--min-size",
        "-s",
        help="Minimum file size (e.g., 500MB, 1GB)"
    ),
    export: Optional[str] = typer.Option(
        None,
        "--export",
        "-e",
        help="Export format: json, csv, or txt"
    ),
    use_cache: bool = typer.Option(
        True,
        "--use-cache/--no-cache",
        help="Use cached scan results if available (default: True)"
    ),
) -> None:
    """Show detailed duplicate analysis with code references."""
    config = Config()
    models = None
    
    # Try to load from cache first
    if use_cache:
        cached = load_scan_results(max_age_hours=24)
        if cached:
            models, cached_params = cached
            cache_info = get_cache_info()
            if cache_info:
                console.print(f"[green]✓ Using cached scan results ({cache_info['age_human']} old)[/green]")
                console.print(f"[dim]  Cached from: {cached_params.get('root', 'unknown')}, min_size: {cached_params.get('min_size', 'unknown')}[/dim]")
    
    # Scan if no cache or cache disabled
    if models is None:
        # Parse minimum size
        try:
            min_size_bytes = parse_size(min_size)
        except ValueError as e:
            console.print(f"[red]Error:[/red] Invalid size format: {min_size}")
            console.print(f"  {e}")
            raise typer.Exit(1)
        
        # Determine root directory
        if root is None:
            root_path = Path.home()
        else:
            root_path = Path(root).expanduser().resolve()
            if not root_path.exists():
                console.print(f"[red]Error:[/red] Root directory does not exist: {root}")
                raise typer.Exit(1)
        
        # Scan for models
        console.print("[cyan]Scanning for models...[/cyan]")
        scanner = Scanner(config)
        scanner.min_size_bytes = min_size_bytes
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            models = scanner.scan(root=root_path, full_scan=False, progress=progress)
        
        # Save to cache
        scan_params = {
            'root': str(root_path),
            'min_size': min_size,
            'full_scan': False,
        }
        save_scan_results(models, scan_params)
    
    if not models:
        console.print("[yellow]No models found.[/yellow]")
        raise typer.Exit(0)
    
    # Find duplicates
    duplicates_dict = find_duplicates(models)
    
    if not duplicates_dict:
        console.print("[green]No duplicates found![/green]")
        raise typer.Exit(0)
    
    # Find code references for all models
    console.print("\n[cyan]Searching for code references...[/cyan]")
    console.print("[dim]This may take a moment. Scanning code files for model references...[/dim]")
    console.print("[dim]Paths will appear below as references are found:[/dim]\n")
    
    streaming_callback = _create_streaming_callback(console)
    
    try:
        all_references = find_references(
            models, 
            config=config,
            progress_callback=lambda folder, searched, found: None,  # Silent progress
            found_callback=streaming_callback
        )
        # Print final summary if callback supports it
        if hasattr(streaming_callback, 'finalize'):
            streaming_callback.finalize()
        console.print(f"[green]✓[/green] Reference search complete")
    except KeyboardInterrupt:
        console.print("\n[yellow]Reference search interrupted by user[/yellow]")
        all_references = {}
    except Exception as e:
        console.print(f"\n[yellow]Warning: Reference search failed: {e}[/yellow]")
        all_references = {}
    
    # Build reverse lookup: model path -> list of code files referencing it
    model_to_references: Dict[Path, List[Path]] = {}
    for code_file, ref_models in all_references.items():
        for model in ref_models:
            if model.path not in model_to_references:
                model_to_references[model.path] = []
            model_to_references[model.path].append(code_file)
    
    # Display detailed duplicate analysis
    _show_duplicate_analysis(duplicates_dict, model_to_references, console)
    
    # Export if requested
    if export:
        _export_duplicates(duplicates_dict, model_to_references, export, console)


@app.command()
def cleanup(
    root: Optional[str] = typer.Option(
        None,
        "--root",
        "-r",
        help="Root directory to scan (default: use cached results if available)"
    ),
    min_size: str = typer.Option(
        "500MB",
        "--min-size",
        "-s",
        help="Minimum file size (e.g., 500MB, 1GB)"
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be deleted without actually deleting"
    ),
    use_cache: bool = typer.Option(
        True,
        "--use-cache/--no-cache",
        help="Use cached scan results if available (default: True)"
    ),
) -> None:
    """Find duplicates, check code references, and offer to delete unreferenced copies."""
    config = Config()
    models = None
    
    # Try to load from cache first
    if use_cache:
        cached = load_scan_results(max_age_hours=24)
        if cached:
            models, cached_params = cached
            cache_info = get_cache_info()
            if cache_info:
                console.print(f"[green]✓ Using cached scan results ({cache_info['age_human']} old)[/green]")
    
    # Scan if no cache or cache disabled
    if models is None:
        # Parse minimum size
        try:
            min_size_bytes = parse_size(min_size)
        except ValueError as e:
            console.print(f"[red]Error:[/red] Invalid size format: {min_size}")
            console.print(f"  {e}")
            raise typer.Exit(1)
        
        # Determine root directory
        if root is None:
            root_path = Path.home()
        else:
            root_path = Path(root).expanduser().resolve()
            if not root_path.exists():
                console.print(f"[red]Error:[/red] Root directory does not exist: {root}")
                raise typer.Exit(1)
        
        # Scan for models
        console.print("[cyan]Scanning for models...[/cyan]")
        scanner = Scanner(config)
        scanner.min_size_bytes = min_size_bytes
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            models = scanner.scan(root=root_path, full_scan=False, progress=progress)
        
        # Save to cache
        scan_params = {
            'root': str(root_path),
            'min_size': min_size,
            'full_scan': False,
        }
        save_scan_results(models, scan_params)
    
    if not models:
        console.print("[yellow]No models found.[/yellow]")
        raise typer.Exit(0)
    
    # Find duplicates
    duplicates_dict = find_duplicates(models)
    
    if not duplicates_dict:
        console.print("[green]No duplicates found![/green]")
        raise typer.Exit(0)
    
    # Find code references
    console.print("\n[cyan]Searching for code references...[/cyan]")
    console.print("[dim]This may take a moment. Scanning code files for model references...[/dim]")
    console.print("[dim]Paths will appear below as references are found:[/dim]\n")
    
    streaming_callback = _create_streaming_callback(console)
    
    try:
        all_references = find_references(
            models, 
            config=config,
            progress_callback=lambda folder, searched, found: None,  # Silent progress
            found_callback=streaming_callback
        )
        # Print final summary if callback supports it
        if hasattr(streaming_callback, 'finalize'):
            streaming_callback.finalize()
        console.print(f"[green]✓[/green] Reference search complete")
    except KeyboardInterrupt:
        console.print("\n[yellow]Reference search interrupted by user[/yellow]")
        all_references = {}
    except Exception as e:
        console.print(f"\n[yellow]Warning: Reference search failed: {e}[/yellow]")
        all_references = {}
    
    # Build reverse lookup
    model_to_references: Dict[Path, List[Path]] = {}
    for code_file, ref_models in all_references.items():
        for model in ref_models:
            if model.path not in model_to_references:
                model_to_references[model.path] = []
            model_to_references[model.path].append(code_file)
    
    # Perform cleanup
    _perform_cleanup(duplicates_dict, model_to_references, dry_run, console)


@app.command()
def show(
    show_recent: bool = typer.Option(
        False,
        "--show-recent",
        help="Highlight files accessed in last 30 days"
    ),
    use_cache: bool = typer.Option(
        True,
        "--use-cache/--no-cache",
        help="Use cached scan results if available (default: True)"
    ),
) -> None:
    """Display cached scan results as a table without rescanning."""
    from .formatters import Formatter
    from .duplicate_detector import find_duplicates
    
    config = Config()
    
    # Try to load from cache
    if use_cache:
        cached = load_scan_results(max_age_hours=24)
        if cached:
            models, cached_params = cached
            cache_info = get_cache_info()
            if cache_info:
                console.print(f"[green]✓ Using cached scan results ({cache_info['age_human']} old)[/green]")
                console.print(f"[dim]  Cached from: {cached_params.get('root', 'unknown')}, min_size: {cached_params.get('min_size', 'unknown')}[/dim]\n")
        else:
            console.print("[yellow]No cached scan results found. Run 'scan' first.[/yellow]")
            raise typer.Exit(1)
    else:
        console.print("[yellow]Cache disabled. Use 'scan' to scan and display results.[/yellow]")
        raise typer.Exit(1)
    
    if not models:
        console.print("[yellow]No models in cache.[/yellow]")
        raise typer.Exit(0)
    
    # Find duplicates for display
    duplicates = find_duplicates(models)
    
    # Display table
    formatter = Formatter(console)
    formatter.format_table(
        models,
        duplicates=duplicates,
        group_by_tool=config.group_by_tool,
        show_recent=show_recent
    )


@app.command()
def report(
    format: str = typer.Option(
        "csv",
        "--format",
        "-f",
        help="Export format: csv or json (default: csv)"
    ),
    output: Optional[str] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output directory (default: Desktop)"
    ),
    use_cache: bool = typer.Option(
        True,
        "--use-cache/--no-cache",
        help="Use cached scan results if available (default: True)"
    ),
) -> None:
    """Generate deprecation report: models referenced in code and unreferenced models."""
    from datetime import datetime
    
    config = Config()
    
    # Load models from cache or scan
    models = None
    if use_cache:
        cached = load_scan_results(max_age_hours=24)
        if cached:
            models, cached_params = cached
            cache_info = get_cache_info()
            if cache_info:
                console.print(f"[green]✓ Using cached scan results ({cache_info['age_human']} old)[/green]")
    
    if models is None:
        console.print("[cyan]Scanning for models...[/cyan]")
        scanner = Scanner(config)
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            models = scanner.scan(root=Path.home(), full_scan=False, progress=progress)
        save_scan_results(models, {'root': str(Path.home()), 'min_size': '500MB'})
    
    if not models:
        console.print("[yellow]No models found.[/yellow]")
        raise typer.Exit(0)
    
    # Find code references
    console.print("\n[cyan]Searching for code references...[/cyan]")
    console.print("[dim]This may take a moment. Scanning code files for model references...[/dim]")
    console.print("[dim]Paths will appear below as references are found:[/dim]\n")
    
    streaming_callback = _create_streaming_callback(console)
    
    try:
        all_references = find_references(
            models,
            config=config,
            progress_callback=lambda folder, searched, found: None,
            found_callback=streaming_callback
        )
        # Print final summary if callback supports it
        if hasattr(streaming_callback, 'finalize'):
            streaming_callback.finalize()
        console.print(f"[green]✓[/green] Reference search complete")
    except Exception as e:
        console.print(f"\n[yellow]Warning: Reference search failed: {e}[/yellow]")
        all_references = {}
    
    # Build reverse lookup: model path -> list of code files referencing it
    model_to_references: Dict[Path, List[Path]] = {}
    for code_file, ref_models in all_references.items():
        for model in ref_models:
            if model.path not in model_to_references:
                model_to_references[model.path] = []
            model_to_references[model.path].append(code_file)
    
    # Find duplicates
    duplicates_dict = find_duplicates(models)
    
    # Determine output directory
    if output:
        output_dir = Path(output).expanduser().resolve()
    else:
        # Default to Desktop
        if sys.platform == "win32":
            desktop = Path.home() / "Desktop"
        else:
            desktop = Path.home() / "Desktop"
        output_dir = desktop
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate timestamp for filenames
    timestamp = datetime.now().strftime("%Y-%m-%d")
    
    # File 1: Models referenced in code
    referenced_models = []
    for model in models:
        refs = model_to_references.get(model.path, [])
        if refs:
            referenced_models.append({
                'model_path': str(model.path),
                'model_name': model.model_name,
                'size': model.size,
                'size_human': model.size_human,
                'tool': model.tool,
                'referenced_in': ';'.join(str(ref) for ref in refs),
                'reference_count': len(refs),
            })
    
    # File 2: Unreferenced models
    unreferenced_models = []
    for model in models:
        refs = model_to_references.get(model.path, [])
        if not refs:
            # Check if it's a duplicate
            is_dup = False
            dup_hash = ''
            for hash_val, dup_models in duplicates_dict.items():
                if model in dup_models:
                    is_dup = True
                    dup_hash = hash_val
                    break
            
            unreferenced_models.append({
                'model_path': str(model.path),
                'model_name': model.model_name,
                'size': model.size,
                'size_human': model.size_human,
                'tool': model.tool,
                'is_duplicate': is_dup,
                'duplicate_hash': dup_hash if is_dup else '',
            })
    
    # Export files
    if format.lower() == "json":
        # JSON export
        ref_file = output_dir / f"model_references_{timestamp}.json"
        unref_file = output_dir / f"unreferenced_models_{timestamp}.json"
        
        with open(ref_file, 'w') as f:
            json.dump(referenced_models, f, indent=2)
        
        with open(unref_file, 'w') as f:
            json.dump(unreferenced_models, f, indent=2)
    else:
        # CSV export (default)
        ref_file = output_dir / f"model_references_{timestamp}.csv"
        unref_file = output_dir / f"unreferenced_models_{timestamp}.csv"
        
        if referenced_models:
            with open(ref_file, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'model_path', 'model_name', 'size', 'size_human', 'tool',
                    'referenced_in', 'reference_count'
                ])
                writer.writeheader()
                writer.writerows(referenced_models)
        
        if unreferenced_models:
            with open(unref_file, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'model_path', 'model_name', 'size', 'size_human', 'tool',
                    'is_duplicate', 'duplicate_hash'
                ])
                writer.writeheader()
                writer.writerows(unreferenced_models)
    
    console.print(f"\n[green]✓ Report generated:[/green]")
    if referenced_models:
        console.print(f"  • {ref_file}")
        console.print(f"    {len(referenced_models)} models referenced in code")
    if unreferenced_models:
        console.print(f"  • {unref_file}")
        console.print(f"    {len(unreferenced_models)} unreferenced models")
    
    if duplicates_dict:
        dup_count = sum(len(dup_models) - 1 for dup_models in duplicates_dict.values())
        console.print(f"\n[dim]Found {len(duplicates_dict)} duplicate groups ({dup_count} duplicate files)[/dim]")
        console.print(f"[dim]Use 'keep' command to remove duplicates one at a time[/dim]")


@app.command()
def keep(
    model_path: str = typer.Argument(..., help="Path to the model file to keep (all duplicates will be deleted)"),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be deleted without actually deleting"
    ),
    use_cache: bool = typer.Option(
        True,
        "--use-cache/--no-cache",
        help="Use cached scan results if available (default: True)"
    ),
) -> None:
    """Keep a specific model and delete all its duplicate copies."""
    from .duplicate_detector import find_duplicates
    
    # Resolve the model path
    keep_path = Path(model_path).expanduser().resolve()
    
    if not keep_path.exists():
        console.print(f"[red]Error:[/red] Model file does not exist: {keep_path}")
        raise typer.Exit(1)
    
    if not keep_path.is_file():
        console.print(f"[red]Error:[/red] Path is not a file: {keep_path}")
        raise typer.Exit(1)
    
    # Load models from cache or scan
    models = None
    if use_cache:
        cached = load_scan_results(max_age_hours=24)
        if cached:
            models, cached_params = cached
            cache_info = get_cache_info()
            if cache_info:
                console.print(f"[green]✓ Using cached scan results ({cache_info['age_human']} old)[/green]")
    
    if models is None:
        console.print("[cyan]Scanning for models...[/cyan]")
        config = Config()
        scanner = Scanner(config)
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            models = scanner.scan(root=Path.home(), full_scan=False, progress=progress)
        save_scan_results(models, {'root': str(Path.home()), 'min_size': '500MB'})
    
    if not models:
        console.print("[yellow]No models found.[/yellow]")
        raise typer.Exit(0)
    
    # Find the model in the list
    keep_model = None
    for model in models:
        if model.path == keep_path:
            keep_model = model
            break
    
    if not keep_model:
        console.print(f"[yellow]Warning:[/yellow] Model not found in scan results: {keep_path}")
        console.print("[dim]The file may be below the minimum size threshold or not a recognized model format.[/dim]")
        raise typer.Exit(1)
    
    if not keep_model.hash:
        console.print(f"[yellow]Warning:[/yellow] Model hash not computed. Computing now...")
        from .model_analyzer import compute_hash
        keep_model.hash = compute_hash(keep_path)
    
    # Find all duplicates
    duplicates_dict = find_duplicates(models)
    
    # Find duplicates of this specific model
    duplicate_group = duplicates_dict.get(keep_model.hash, [])
    
    if len(duplicate_group) <= 1:
        console.print(f"[green]✓ No duplicates found for: {keep_model.model_name}[/green]")
        console.print(f"  Path: {keep_path}")
        raise typer.Exit(0)
    
    # Filter out the one we're keeping
    to_delete = [m for m in duplicate_group if m.path != keep_path]
    
    if not to_delete:
        console.print(f"[green]✓ No duplicates to delete (only one copy exists)[/green]")
        raise typer.Exit(0)
    
    # Deduplicate to_delete by path (in case same path appears multiple times)
    unique_to_delete = []
    seen_delete_paths = set()
    for model in to_delete:
        if model.path not in seen_delete_paths:
            unique_to_delete.append(model)
            seen_delete_paths.add(model.path)
    
    # Show summary
    total_size = sum(m.size for m in unique_to_delete)
    console.print(f"\n[bold]Keeping:[/bold] {keep_model.model_name}")
    console.print(f"  Path: {keep_path}")
    console.print(f"  Size: {keep_model.size_human}")
    
    console.print(f"\n[bold]Found {len(unique_to_delete)} duplicate(s) to remove:[/bold]")
    for i, model in enumerate(unique_to_delete, 1):
        console.print(f"  {i}. {model.path} ({model.size_human})")
    
    console.print(f"\n[bold]Total space to free:[/bold] {format_size(total_size)}")
    
    if dry_run:
        console.print(f"\n[yellow]Dry run: Would delete {len(unique_to_delete)} duplicate files[/yellow]")
        raise typer.Exit(0)
    
    # Ask for confirmation
    console.print(f"\n[yellow]Delete {len(unique_to_delete)} duplicate files?[/yellow]")
    console.print(f"This will free up {format_size(total_size)} of disk space.")
    response = input("  [y/N]: ").strip().lower()
    
    if response != 'y':
        console.print("[yellow]Operation cancelled.[/yellow]")
        raise typer.Exit(0)
    
    # Delete the duplicates
    deleted_count = 0
    deleted_space = 0
    errors = []
    
    for model in unique_to_delete:
        try:
            # Verify file still exists and hash matches
            if not model.path.exists():
                console.print(f"[yellow]Skipping (file no longer exists):[/yellow] {model.path}")
                continue
            
            # Verify hash matches (safety check)
            if model.hash:
                from .model_analyzer import compute_hash
                current_hash = compute_hash(model.path)
                if current_hash != model.hash:
                    console.print(f"[yellow]Skipping (hash mismatch - file may have changed):[/yellow] {model.path}")
                    continue
            
            model.path.unlink()
            deleted_count += 1
            deleted_space += model.size
            console.print(f"[green]Deleted:[/green] {model.path}")
        except FileNotFoundError:
            # File was already deleted (race condition or already gone)
            console.print(f"[dim]Already deleted:[/dim] {model.path}")
        except Exception as e:
            errors.append((model.path, str(e)))
            console.print(f"[red]Error deleting {model.path}:[/red] {e}")
    
    if errors:
        console.print(f"\n[yellow]Warning:[/yellow] {len(errors)} file(s) could not be deleted")
    
    console.print(f"\n[green]✓ Deleted {deleted_count} duplicate file(s), freed {format_size(deleted_space)}[/green]")
    
    # Update cache by removing deleted models
    remaining_models = [m for m in models if m.path != keep_path and m.path.exists()]
    remaining_models.append(keep_model)  # Keep the one we're keeping
    save_scan_results(remaining_models, {'root': str(Path.home()), 'min_size': '500MB'})


@app.command()
def export(
    format: str = typer.Option(
        "json",
        "--format",
        "-f",
        help="Export format: json, csv, or txt"
    ),
    output: Optional[str] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file path (default: models.{format} in current directory)"
    ),
    use_cache: bool = typer.Option(
        True,
        "--use-cache/--no-cache",
        help="Use cached scan results if available (default: True)"
    ),
) -> None:
    """Export cached scan results to a file."""
    from .formatters import Formatter
    
    # Try to load from cache
    if use_cache:
        cached = load_scan_results(max_age_hours=24)
        if cached:
            models, cached_params = cached
            cache_info = get_cache_info()
            if cache_info:
                console.print(f"[green]✓ Using cached scan results ({cache_info['age_human']} old)[/green]")
        else:
            console.print("[yellow]No cached scan results found. Run 'scan' first.[/yellow]")
            raise typer.Exit(1)
    else:
        console.print("[yellow]Cache disabled. Use 'scan --export' to export during scan.[/yellow]")
        raise typer.Exit(1)
    
    if not models:
        console.print("[yellow]No models in cache.[/yellow]")
        raise typer.Exit(0)
    
    # Determine output path
    if output:
        output_path = Path(output)
    else:
        output_path = Path.cwd() / f"models.{format}"
    
    # Export
    formatter = Formatter(console)
    if format.lower() == "json":
        formatter.export_json(models, output_path)
    elif format.lower() == "csv":
        formatter.export_csv(models, output_path)
    elif format.lower() == "txt":
        formatter.export_txt(models, output_path)
    else:
        console.print(f"[red]Error:[/red] Unknown export format: {format}")
        console.print("  Supported formats: json, csv, txt")
        raise typer.Exit(1)
    
    console.print(f"[green]✓ Exported {len(models)} models to {output_path}[/green]")


def _perform_health_check(models: list, console: Console) -> None:
    """
    Perform health check against Ollama/LM Studio CLI.
    
    Args:
        models: List of ModelInfo objects
        console: Rich console instance
    """
    console.print("\n[bold]Health Check:[/bold]")
    
    # Check Ollama
    if check_command_available("ollama"):
        console.print("\n[green]✓[/green] Ollama CLI detected")
        try:
            import subprocess
            result = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                if len(lines) > 1:  # Header + models
                    console.print(f"  Registered models: {len(lines) - 1}")
                    for line in lines[1:6]:  # Show first 5
                        console.print(f"    {line.strip()}")
                    if len(lines) > 6:
                        console.print(f"    ... and {len(lines) - 6} more")
                else:
                    console.print("  No models registered")
            else:
                console.print("  [yellow]Could not list models (Ollama may not be running)[/yellow]")
        except Exception as e:
            console.print(f"  [yellow]Error checking Ollama: {e}[/yellow]")
    else:
        console.print("\n[yellow]✗[/yellow] Ollama CLI not found")
    
    # Check LM Studio (no standard CLI, but we can check if it's installed)
    lm_studio_paths = detect_lm_studio_paths()
    lm_studio_found = len(lm_studio_paths) > 0
    
    # Also check if any scanned models are from LM Studio
    lm_models = [m for m in models if "LM Studio" in m.tool]
    
    if lm_studio_found or lm_models:
        console.print("\n[green]✓[/green] LM Studio installation detected")
        if lm_studio_paths:
            console.print(f"  Model directories: {len(lm_studio_paths)}")
            for path in lm_studio_paths[:3]:  # Show first 3 paths
                console.print(f"    • {path}")
            if len(lm_studio_paths) > 3:
                console.print(f"    ... and {len(lm_studio_paths) - 3} more")
        if lm_models:
            console.print(f"  Found {len(lm_models)} model files")
        elif lm_studio_found:
            console.print("  No model files found in LM Studio directories")
    else:
        console.print("\n[yellow]✗[/yellow] LM Studio not detected")
    
    # Show details for other tools (ComfyUI, Hugging Face, etc.)
    by_tool = {}
    for model in models:
        by_tool[model.tool] = by_tool.get(model.tool, 0) + 1
    
    # Show other tools that have models
    other_tools = {tool: count for tool, count in by_tool.items() 
                   if tool not in ["Ollama", "LM Studio"] and count > 0}
    
    if other_tools:
        console.print("\n[bold]Other Tools Detected:[/bold]")
        for tool, count in sorted(other_tools.items(), key=lambda x: x[1], reverse=True):
            console.print(f"  [cyan]{tool}:[/cyan] {count} model(s)")
            # Show sample paths for this tool
            tool_models = [m for m in models if m.tool == tool]
            if tool_models:
                # Group by directory
                dirs = {}
                for model in tool_models[:10]:  # Show up to 10 models
                    dir_path = model.path.parent
                    if dir_path not in dirs:
                        dirs[dir_path] = []
                    dirs[dir_path].append(model)
                
                for dir_path, dir_models in list(dirs.items())[:3]:  # Show up to 3 directories
                    dir_str = str(dir_path)
                    if len(dir_str) > 60:
                        dir_str = "..." + dir_str[-57:]
                    console.print(f"    • {dir_str} ({len(dir_models)} file(s))")
                if len(dirs) > 3:
                    console.print(f"    ... and {len(dirs) - 3} more directory(ies)")
    
    # Summary
    console.print(f"\n[bold]Summary:[/bold]")
    console.print(f"  Total models scanned: {len(models)}")
    for tool, count in sorted(by_tool.items(), key=lambda x: x[1], reverse=True):
        console.print(f"  {tool}: {count} models")


def _show_duplicate_analysis(
    duplicates: Dict[str, List[ModelInfo]],
    model_to_references: Dict[Path, List[Path]],
    console: Console
) -> None:
    """Show detailed duplicate analysis with code references."""
    from .duplicate_detector import get_duplicate_stats
    
    stats = get_duplicate_stats(duplicates)
    
    console.print(f"\n[bold]Duplicate Analysis[/bold]")
    console.print(f"  Duplicate groups: {stats['duplicate_groups']}")
    console.print(f"  Duplicate files: {stats['duplicate_files']}")
    console.print(f"  Wasted space: {stats['wasted_space_human']}")
    
    console.print("\n[bold]Detailed Duplicate Groups:[/bold]\n")
    
    for i, (hash_val, dup_models) in enumerate(duplicates.items(), 1):
        file_size = dup_models[0].size
        wasted = file_size * (len(dup_models) - 1)
        
        console.print(f"[bold cyan]Group {i}:[/bold cyan] {dup_models[0].model_name}")
        console.print(f"  Size: {format_size(file_size)}")
        console.print(f"  Copies: {len(dup_models)}")
        console.print(f"  Wasted: {format_size(wasted)}")
        console.print(f"  Hash: {hash_val[:16]}...")
        
        # Show each duplicate with references
        for j, model in enumerate(dup_models, 1):
            refs = model_to_references.get(model.path, [])
            status = "[green]✓ Referenced[/green]" if refs else "[yellow]⚠ Not referenced[/yellow]"
            
            console.print(f"\n  [bold]Copy {j}:[/bold] {status}")
            console.print(f"    Path: {model.path}")
            
            if refs:
                console.print(f"    Referenced in {len(refs)} file(s):")
                for ref_file in refs[:5]:  # Show first 5
                    # Truncate path for readability
                    ref_str = str(ref_file)
                    if len(ref_str) > 80:
                        ref_str = "..." + ref_str[-77:]
                    console.print(f"      • {ref_str}")
                if len(refs) > 5:
                    console.print(f"      ... and {len(refs) - 5} more")
            else:
                console.print(f"    [dim]No code references found[/dim]")
        
        console.print()  # Blank line between groups


def _export_duplicates(
    duplicates: Dict[str, List[ModelInfo]],
    model_to_references: Dict[Path, List[Path]],
    export_format: str,
    console: Console
) -> None:
    """Export duplicate analysis to file."""
    output_path = Path.cwd() / f"duplicates.{export_format}"
    
    # Convert to list format for export
    export_data = []
    for hash_val, dup_models in duplicates.items():
        for model in dup_models:
            refs = model_to_references.get(model.path, [])
            export_data.append({
                **model.to_dict(),
                'hash': hash_val,
                'duplicate_group_size': len(dup_models),
                'references': [str(ref) for ref in refs],
                'is_referenced': len(refs) > 0,
            })
    
    if export_format.lower() == "json":
        # Write JSON manually since we have custom structure
        with open(output_path, 'w') as f:
            json.dump(export_data, f, indent=2)
        console.print(f"[green]Exported duplicates to {output_path}[/green]")
    elif export_format.lower() == "csv":
        # Custom CSV export for duplicates
        with open(output_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'model_name', 'path', 'size', 'size_human', 'tool', 'hash',
                'duplicate_group_size', 'is_referenced', 'references'
            ])
            writer.writeheader()
            for item in export_data:
                row = item.copy()
                row['references'] = '; '.join(row['references'])
                writer.writerow(row)
        console.print(f"[green]Exported duplicates to {output_path}[/green]")
    elif export_format.lower() == "txt":
        with open(output_path, 'w') as f:
            f.write("Duplicate Analysis\n")
            f.write("=" * 80 + "\n\n")
            for hash_val, dup_models in duplicates.items():
                f.write(f"Group: {dup_models[0].model_name}\n")
                f.write(f"Hash: {hash_val}\n")
                f.write(f"Copies: {len(dup_models)}\n\n")
                for model in dup_models:
                    refs = model_to_references.get(model.path, [])
                    f.write(f"  {model.path}\n")
                    f.write(f"    Referenced: {'Yes' if refs else 'No'}\n")
                    if refs:
                        f.write(f"    References:\n")
                        for ref in refs:
                            f.write(f"      - {ref}\n")
                    f.write("\n")
        console.print(f"[green]Exported duplicates to {output_path}[/green]")
    else:
        console.print(f"[red]Error:[/red] Unknown export format: {export_format}")
        raise typer.Exit(1)


def _create_streaming_callback(console: Console, max_display: int = 5):
    """
    Create a callback function that streams paths as they're found.
    Only displays the last N paths to avoid flooding the terminal.
    
    Args:
        console: Rich console for output
        max_display: Maximum number of paths to display at once (default: 5)
        
    Returns:
        Tuple of (callback function, state dict with 'count' and 'recent_paths')
    """
    from collections import deque
    
    state = {
        "count": 0,
        "recent_paths": deque(maxlen=max_display)
    }
    
    def callback(code_file: Path, found_models: List[ModelInfo]) -> None:
        """Stream paths as they're found."""
        state["count"] += 1
        count = state["count"]
        path_str = str(code_file)
        # Truncate long paths for display
        if len(path_str) > 75:
            path_str = "..." + path_str[-72:]
        
        # Add to recent paths buffer
        state["recent_paths"].append(path_str)
        recent_paths = state["recent_paths"]
        
        # Display strategy:
        # - First max_display files: print each one
        # - After that: print summary every 10 files showing last N paths
        if count <= max_display:
            # Print first few individually so user sees it's working
            console.print(f"[dim]  [{count}] Found in:[/dim] {path_str}")
        elif count % 10 == 0:
            # Print summary with last N paths (overwrite previous summary)
            # Use carriage return to go back to start of line
            summary = f"[dim]Found {count} reference(s)... (last {len(recent_paths)}: "
            recent_list = ", ".join([p.split("/")[-1] for p in recent_paths])  # Just filenames
            if len(recent_list) > 50:
                recent_list = recent_list[:47] + "..."
            console.print(f"\r{summary}{recent_list})[/dim]", end="")
            console.file.flush()
    
    def finalize():
        """Print final summary when search completes."""
        count = state["count"]
        recent_paths = state["recent_paths"]
        if count > max_display:
            # Print final summary on new line
            console.print()  # New line after any in-progress summary
            summary = f"[dim]Found {count} reference(s) total (last {len(recent_paths)} paths shown)[/dim]"
            console.print(summary)
    
    callback.finalize = finalize  # Attach finalize method to callback
    callback.state = state  # Attach state for access
    
    return callback


def _perform_cleanup(
    duplicates: Dict[str, List[ModelInfo]],
    model_to_references: Dict[Path, List[Path]],
    dry_run: bool,
    console: Console
) -> None:
    """Perform cleanup of unreferenced duplicates."""
    from .duplicate_detector import get_duplicate_stats
    
    stats = get_duplicate_stats(duplicates)
    
    console.print(f"\n[bold]Cleanup Analysis[/bold]")
    console.print(f"  Duplicate groups: {stats['duplicate_groups']}")
    console.print(f"  Wasted space: {stats['wasted_space_human']}")
    
    # Analyze each duplicate group
    to_delete: List[ModelInfo] = []
    has_references: List[tuple] = []  # (group_name, list of (model, refs))
    
    for hash_val, dup_models in duplicates.items():
        # Find which copies have references
        referenced_copies = []
        unreferenced_copies = []
        
        for model in dup_models:
            refs = model_to_references.get(model.path, [])
            if refs:
                referenced_copies.append((model, refs))
            else:
                unreferenced_copies.append(model)
        
        if referenced_copies:
            # Some copies are referenced - show them
            has_references.append((dup_models[0].model_name, referenced_copies, unreferenced_copies))
        else:
            # No references - can delete all but one
            if len(unreferenced_copies) > 1:
                # Keep the first one, delete the rest
                to_delete.extend(unreferenced_copies[1:])
    
    # Show groups with references
    if has_references:
        console.print(f"\n[bold yellow]⚠ Groups with code references:[/bold yellow]")
        console.print("[dim]These duplicates have at least one copy referenced in your code.[/dim]")
        console.print("[dim]Review manually - update code to point to one copy, then use 'keep' command.[/dim]\n")
        for group_name, referenced, unreferenced in has_references:
            console.print(f"[bold]{group_name}[/bold]")
            
            # Deduplicate referenced copies by path (in case same file appears multiple times)
            seen_paths = set()
            unique_referenced = []
            for model, refs in referenced:
                if model.path not in seen_paths:
                    seen_paths.add(model.path)
                    unique_referenced.append((model, refs))
                else:
                    # Merge references if same path appears again
                    for existing_model, existing_refs in unique_referenced:
                        if existing_model.path == model.path:
                            # Merge reference lists
                            combined_refs = list(set(existing_refs + refs))
                            unique_referenced.remove((existing_model, existing_refs))
                            unique_referenced.append((model, combined_refs))
                            break
            
            console.print(f"  Referenced copies ({len(unique_referenced)}):")
            for model, refs in unique_referenced:
                console.print(f"    • {model.path}")
                console.print(f"      Referenced in {len(refs)} file(s):")
                # Show unique reference files only
                unique_refs = list(set(refs))
                for ref_file in unique_refs[:3]:
                    ref_str = str(ref_file)
                    if len(ref_str) > 70:
                        ref_str = "..." + ref_str[-67:]
                    console.print(f"        - {ref_str}")
                if len(unique_refs) > 3:
                    console.print(f"        ... and {len(unique_refs) - 3} more")
            
            if unreferenced:
                # Deduplicate unreferenced copies too
                unique_unreferenced = []
                seen_unref_paths = set()
                for model in unreferenced:
                    if model.path not in seen_unref_paths:
                        seen_unref_paths.add(model.path)
                        unique_unreferenced.append(model)
                
                console.print(f"  Unreferenced copies ({len(unique_unreferenced)}):")
                for model in unique_unreferenced:
                    console.print(f"    • {model.path}")
            console.print()
    
    # Show groups ready for deletion
    if to_delete:
        # Deduplicate to_delete by path (in case same path appears multiple times)
        unique_to_delete = []
        seen_delete_paths = set()
        for model in to_delete:
            if model.path not in seen_delete_paths:
                unique_to_delete.append(model)
                seen_delete_paths.add(model.path)
        
        total_space = sum(m.size for m in unique_to_delete)
        console.print(f"\n[bold green]✓ Safe to delete ({len(unique_to_delete)} files, {format_size(total_space)}):[/bold green]\n")
        
        # Group by model name for display
        by_name = {}
        for model in unique_to_delete:
            if model.model_name not in by_name:
                by_name[model.model_name] = []
            by_name[model.model_name].append(model)
        
        for model_name, models_list in by_name.items():
            console.print(f"  [cyan]{model_name}[/cyan] ({len(models_list)} copies)")
            for model in models_list:
                console.print(f"    • {model.path}")
            console.print()
        
        if not dry_run:
            # Ask for confirmation
            console.print(f"[yellow]Delete {len(unique_to_delete)} unreferenced duplicate files?[/yellow]")
            console.print(f"This will free up {format_size(total_space)} of disk space.")
            response = input("  [y/N]: ").strip().lower()
            
            if response == 'y':
                deleted_count = 0
                deleted_space = 0
                errors = []
                for model in unique_to_delete:
                    # Check if file exists before trying to delete
                    if not model.path.exists():
                        console.print(f"[yellow]Skipping (file no longer exists):[/yellow] {model.path}")
                        continue
                    
                    try:
                        model.path.unlink()
                        deleted_count += 1
                        deleted_space += model.size
                        console.print(f"[green]Deleted:[/green] {model.path}")
                    except FileNotFoundError:
                        # File was already deleted (race condition or already gone)
                        console.print(f"[dim]Already deleted:[/dim] {model.path}")
                    except Exception as e:
                        errors.append((model.path, e))
                        console.print(f"[red]Error deleting {model.path}:[/red] {e}")
                
                if errors:
                    console.print(f"\n[yellow]Warning:[/yellow] {len(errors)} file(s) could not be deleted")
                console.print(f"\n[green]✓ Deleted {deleted_count} file(s), freed {format_size(deleted_space)}[/green]")
            else:
                console.print("[yellow]Cleanup cancelled.[/yellow]")
        else:
            console.print(f"[yellow]Dry run: Would delete {len(unique_to_delete)} files[/yellow]")
    else:
        console.print("\n[green]No unreferenced duplicates found - all duplicates are referenced in code![/green]")
        console.print("[yellow]Manual review recommended for referenced duplicates above.[/yellow]")


if __name__ == "__main__":
    app()
