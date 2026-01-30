"""File system watcher - monitor for new model files and send notifications."""

import sys
from pathlib import Path
from typing import List, Optional

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileSystemEvent
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    Observer = None
    FileSystemEventHandler = None

try:
    from plyer import notification
    PLYER_AVAILABLE = True
except ImportError:
    PLYER_AVAILABLE = False
    notification = None

from .config import Config
from .model_analyzer import analyze_model_file
from .utils import expand_path, get_model_extensions, is_model_extension


def send_notification(title: str, message: str) -> None:
    """
    Send cross-platform notification.
    
    Args:
        title: Notification title
        message: Notification message
    """
    if PLYER_AVAILABLE:
        try:
            notification.notify(
                title=title,
                message=message,
                timeout=5  # Notification timeout in seconds
            )
        except Exception:
            # Fallback: print to console
            print(f"{title}: {message}")
    else:
        # Fallback: print to console
        print(f"{title}: {message}")


class ModelFileHandler(FileSystemEventHandler):
    """Handler for file system events related to model files."""
    
    def __init__(self, min_size_bytes: int, extensions: List[str], callback=None):
        """
        Initialize handler.
        
        Args:
            min_size_bytes: Minimum file size in bytes
            extensions: List of model file extensions
            callback: Optional callback function (model_info) -> None
        """
        self.min_size_bytes = min_size_bytes
        self.extensions = extensions
        self.callback = callback
    
    def on_created(self, event: FileSystemEvent) -> None:
        """Handle file creation event."""
        if event.is_directory:
            return
        
        filepath = Path(event.src_path)
        
        # Check if it's a model file
        if not is_model_extension(filepath.name, self.extensions):
            return
        
        # Check file size (wait a moment for file to be fully written)
        try:
            import time
            time.sleep(1)  # Wait 1 second for file to be written
            
            if not filepath.exists():
                return
            
            stat = filepath.stat()
            if stat.st_size < self.min_size_bytes:
                return
            
            # Analyze the file
            model = analyze_model_file(
                filepath,
                self.min_size_bytes,
                compute_hash_value=False  # Skip hash for speed
            )
            
            if model:
                # Send notification
                title = "New AI Model Detected"
                message = f"{model.model_name} ({model.size_human})"
                send_notification(title, message)
                
                # Call callback if provided
                if self.callback:
                    self.callback(model)
        except (OSError, Exception) as e:
            # Ignore errors (file might be in use, etc.)
            pass


class ModelWatcher:
    """Watch file system for new model files."""
    
    def __init__(self, config: Optional[Config] = None):
        """
        Initialize watcher.
        
        Args:
            config: Configuration object (creates default if None)
        """
        if not WATCHDOG_AVAILABLE:
            raise ImportError("watchdog library is required for file watching. Install with: pip install watchdog")
        
        self.config = config or Config()
        self.observer = Observer()
        self.handlers: List[ModelFileHandler] = []
        self.min_size_bytes = self.config.watcher_min_size_mb * 1024 * 1024
        self.extensions = get_model_extensions()
    
    def watch_paths(self, paths: Optional[List[str]] = None, callback=None) -> None:
        """
        Start watching specified paths.
        
        Args:
            paths: List of paths to watch (defaults to config watcher_paths)
            callback: Optional callback function (model_info) -> None
        """
        if paths is None:
            paths = self.config.watcher_paths
        
        if not paths:
            raise ValueError("No paths specified for watching")
        
        # Create handler
        handler = ModelFileHandler(self.min_size_bytes, self.extensions, callback)
        self.handlers.append(handler)
        
        # Schedule watching for each path
        for path_str in paths:
            try:
                path = expand_path(path_str)
                if path.exists() and path.is_dir():
                    self.observer.schedule(handler, str(path), recursive=True)
                    print(f"Watching: {path}")
                else:
                    print(f"Warning: Path does not exist or is not a directory: {path}")
            except Exception as e:
                print(f"Error watching {path_str}: {e}")
    
    def start(self) -> None:
        """Start the observer."""
        if not self.observer.is_alive():
            self.observer.start()
            print("Watcher started. Press Ctrl+C to stop.")
    
    def stop(self) -> None:
        """Stop the observer."""
        if self.observer.is_alive():
            self.observer.stop()
            self.observer.join()
            print("Watcher stopped.")
    
    def run(self, paths: Optional[List[str]] = None, callback=None) -> None:
        """
        Run watcher (blocking).
        
        Args:
            paths: List of paths to watch
            callback: Optional callback function
        """
        self.watch_paths(paths, callback)
        self.start()
        
        try:
            import time
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()
            sys.exit(0)
