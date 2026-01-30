"""Output formatters - Rich table, JSON, CSV, TXT export."""

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

from rich.console import Console
from rich.table import Table
from rich.text import Text

from .duplicate_detector import find_duplicates
from .model_analyzer import ModelInfo


class Formatter:
    """Formatter for model scan results."""
    
    def __init__(self, console: Optional[Console] = None):
        """
        Initialize formatter.
        
        Args:
            console: Rich console instance (creates new if None)
        """
        self.console = console or Console()
    
    def format_table(
        self,
        models: List[ModelInfo],
        duplicates: Optional[Dict[str, List[ModelInfo]]] = None,
        group_by_tool: bool = True,
        show_recent: bool = False
    ) -> None:
        """
        Format models as Rich table.
        
        Args:
            models: List of ModelInfo objects
            duplicates: Optional dictionary of duplicates (computed if None)
            group_by_tool: Whether to group by tool
            show_recent: Whether to highlight recent files
        """
        if not models:
            self.console.print("[yellow]No models found.[/yellow]")
            return
        
        if duplicates is None:
            duplicates = find_duplicates(models)
        
        # Create duplicate lookup for highlighting
        duplicate_paths = set()
        for dup_list in duplicates.values():
            duplicate_paths.update(model.path for model in dup_list)
        
        if group_by_tool:
            # Group by tool
            by_tool = defaultdict(list)
            for model in models:
                by_tool[model.tool].append(model)
            
            # Sort tools by total size
            tool_order = sorted(
                by_tool.keys(),
                key=lambda t: sum(m.size for m in by_tool[t]),
                reverse=True
            )
            
            for tool in tool_order:
                tool_models = sorted(by_tool[tool], key=lambda m: m.size, reverse=True)
                self._print_tool_table(tool, tool_models, duplicate_paths, show_recent)
        else:
            # Single table, sorted by size
            sorted_models = sorted(models, key=lambda m: m.size, reverse=True)
            self._print_table("All Models", sorted_models, duplicate_paths, show_recent)
        
        # Print summary
        self._print_summary(models, duplicates)
    
    def _print_tool_table(
        self,
        tool: str,
        models: List[ModelInfo],
        duplicate_paths: set,
        show_recent: bool
    ) -> None:
        """Print table for a specific tool."""
        table = Table(title=f"{tool} ({len(models)} models)", show_header=True, header_style="bold magenta")
        table.add_column("Model Name", style="cyan", no_wrap=False)
        table.add_column("Size", justify="right", style="green")
        table.add_column("Modified", style="blue")
        table.add_column("Path", style="dim", no_wrap=False)
        
        if show_recent:
            table.add_column("Recent", justify="center", style="yellow")
        
        for model in models:
            # Highlight duplicates
            name_text = Text(model.model_name)
            if model.path in duplicate_paths:
                name_text.stylize("bold red")
            
            path_str = str(model.path)
            if len(path_str) > 60:
                path_str = "..." + path_str[-57:]
            
            row = [
                name_text,
                model.size_human,
                model.modified_date.strftime("%Y-%m-%d"),
                path_str,
            ]
            
            if show_recent:
                row.append("✓" if model.is_recent else "")
            
            table.add_row(*row)
        
        self.console.print(table)
        self.console.print()
    
    def _print_table(
        self,
        title: str,
        models: List[ModelInfo],
        duplicate_paths: set,
        show_recent: bool
    ) -> None:
        """Print single table for all models."""
        table = Table(title=title, show_header=True, header_style="bold magenta")
        table.add_column("Tool", style="yellow")
        table.add_column("Model Name", style="cyan", no_wrap=False)
        table.add_column("Size", justify="right", style="green")
        table.add_column("Modified", style="blue")
        table.add_column("Path", style="dim", no_wrap=False)
        
        if show_recent:
            table.add_column("Recent", justify="center", style="yellow")
        
        for model in models:
            # Highlight duplicates
            name_text = Text(model.model_name)
            if model.path in duplicate_paths:
                name_text.stylize("bold red")
            
            path_str = str(model.path)
            if len(path_str) > 60:
                path_str = "..." + path_str[-57:]
            
            row = [
                model.tool,
                name_text,
                model.size_human,
                model.modified_date.strftime("%Y-%m-%d"),
                path_str,
            ]
            
            if show_recent:
                row.append("✓" if model.is_recent else "")
            
            table.add_row(*row)
        
        self.console.print(table)
        self.console.print()
    
    def _print_summary(
        self,
        models: List[ModelInfo],
        duplicates: Dict[str, List[ModelInfo]]
    ) -> None:
        """Print summary statistics."""
        total_size = sum(m.size for m in models)
        total_size_human = self._format_size(total_size)
        
        self.console.print("[bold]Summary:[/bold]")
        self.console.print(f"  Total models found: {len(models)}")
        self.console.print(f"  Total disk space: {total_size_human}")
        
        if duplicates:
            from .duplicate_detector import get_duplicate_stats
            stats = get_duplicate_stats(duplicates)
            self.console.print(f"  Duplicate groups: {stats['duplicate_groups']}")
            self.console.print(f"  Duplicate files: {stats['duplicate_files']}")
            self.console.print(f"  Wasted space: {stats['wasted_space_human']}")
    
    def export_json(self, models: List[ModelInfo], output_path: Path) -> None:
        """
        Export models to JSON file.
        
        Args:
            models: List of ModelInfo objects
            output_path: Path to output file
        """
        data = {
            'models': [model.to_dict() for model in models],
            'summary': {
                'total_models': len(models),
                'total_size': sum(m.size for m in models),
                'total_size_human': self._format_size(sum(m.size for m in models)),
            }
        }
        
        # Add duplicate information
        duplicates = find_duplicates(models)
        if duplicates:
            from .duplicate_detector import get_duplicate_stats
            stats = get_duplicate_stats(duplicates)
            data['duplicates'] = {
                hash_val: [m.to_dict() for m in models_list]
                for hash_val, models_list in duplicates.items()
            }
            data['duplicate_stats'] = stats
        
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        self.console.print(f"[green]Exported {len(models)} models to {output_path}[/green]")
    
    def export_csv(self, models: List[ModelInfo], output_path: Path) -> None:
        """
        Export models to CSV file.
        
        Args:
            models: List of ModelInfo objects
            output_path: Path to output file
        """
        with open(output_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Path', 'Size', 'Size (Human)', 'Modified Date', 'Extension',
                'Model Name', 'Tool', 'Hash', 'Is Recent'
            ])
            
            for model in sorted(models, key=lambda m: m.size, reverse=True):
                writer.writerow([
                    str(model.path),
                    model.size,
                    model.size_human,
                    model.modified_date.isoformat(),
                    model.extension,
                    model.model_name,
                    model.tool,
                    model.hash,
                    model.is_recent,
                ])
        
        self.console.print(f"[green]Exported {len(models)} models to {output_path}[/green]")
    
    def export_txt(self, models: List[ModelInfo], output_path: Path) -> None:
        """
        Export models to plain text file.
        
        Args:
            models: List of ModelInfo objects
            output_path: Path to output file
        """
        with open(output_path, 'w') as f:
            f.write("AI Model Scanner Results\n")
            f.write("=" * 80 + "\n\n")
            
            # Group by tool
            by_tool = defaultdict(list)
            for model in models:
                by_tool[model.tool].append(model)
            
            tool_order = sorted(
                by_tool.keys(),
                key=lambda t: sum(m.size for m in by_tool[t]),
                reverse=True
            )
            
            for tool in tool_order:
                f.write(f"\n{tool}\n")
                f.write("-" * 80 + "\n")
                tool_models = sorted(by_tool[tool], key=lambda m: m.size, reverse=True)
                
                for model in tool_models:
                    f.write(f"  {model.model_name}\n")
                    f.write(f"    Size: {model.size_human}\n")
                    f.write(f"    Modified: {model.modified_date.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"    Path: {model.path}\n")
                    if model.hash:
                        f.write(f"    Hash: {model.hash}\n")
                    f.write("\n")
            
            # Summary
            total_size = sum(m.size for m in models)
            f.write("\n" + "=" * 80 + "\n")
            f.write("Summary\n")
            f.write("-" * 80 + "\n")
            f.write(f"Total models: {len(models)}\n")
            f.write(f"Total disk space: {self._format_size(total_size)}\n")
            
            duplicates = find_duplicates(models)
            if duplicates:
                from .duplicate_detector import get_duplicate_stats
                stats = get_duplicate_stats(duplicates)
                f.write(f"Duplicate groups: {stats['duplicate_groups']}\n")
                f.write(f"Duplicate files: {stats['duplicate_files']}\n")
                f.write(f"Wasted space: {stats['wasted_space_human']}\n")
        
        self.console.print(f"[green]Exported {len(models)} models to {output_path}[/green]")
    
    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Format bytes to human-readable size string."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"
