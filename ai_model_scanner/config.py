"""Configuration management for AI Model Scanner."""

import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

try:
    import toml
    TOML_AVAILABLE = True
except ImportError:
    toml = None
    TOML_AVAILABLE = False

from .path_detector import (
    detect_comfyui_paths,
    detect_huggingface_paths,
    detect_lm_studio_paths,
    detect_ollama_paths,
    detect_mlx_paths,
    get_platform_common_paths,
)


class Config:
    """Configuration manager with defaults and file loading."""
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize configuration.
        
        Args:
            config_path: Optional path to config file. If None, uses default location.
        """
        if config_path is None:
            config_path = self._get_default_config_path()
        
        self.config_path = config_path
        self.config_data: Dict = {}
        # Cache default paths to avoid repeated detection
        self._default_paths_cache: Optional[Dict[str, List[str]]] = None
        self.load_config()
    
    @staticmethod
    def _get_default_config_path() -> Path:
        """Get platform-specific default config path."""
        if sys.platform == "win32":
            # Windows: %APPDATA%\ai-model-scanner\config.toml
            appdata = os.getenv("APPDATA", "")
            if appdata:
                config_dir = Path(appdata) / "ai-model-scanner"
            else:
                config_dir = Path.home() / ".config" / "ai-model-scanner"
        else:
            # macOS/Linux: ~/.config/ai-model-scanner/config.toml
            config_dir = Path.home() / ".config" / "ai-model-scanner"
        
        return config_dir / "config.toml"
    
    def _get_default_paths(self) -> Dict[str, List[str]]:
        """Get default paths using path detector with fallback to common paths."""
        if self._default_paths_cache is not None:
            return self._default_paths_cache
        
        # Try to detect paths dynamically
        detected_paths = {
            "ollama": [str(p) for p in detect_ollama_paths()],
            "lm_studio": [str(p) for p in detect_lm_studio_paths()],
            "comfyui": [str(p) for p in detect_comfyui_paths()],
            "huggingface": [str(p) for p in detect_huggingface_paths()],
            "mlx": [str(p) for p in detect_mlx_paths()],
        }
        
        # Fallback to common paths if detection found nothing
        common_paths = get_platform_common_paths()
        for tool, paths in detected_paths.items():
            if not paths:
                detected_paths[tool] = common_paths.get(tool, [])
        
        self._default_paths_cache = detected_paths
        return detected_paths
    
    @property
    def DEFAULT_OLLAMA_PATHS(self) -> List[str]:
        """Default Ollama paths."""
        return self._get_default_paths().get("ollama", [])
    
    @property
    def DEFAULT_LM_STUDIO_PATHS(self) -> List[str]:
        """Default LM Studio paths."""
        return self._get_default_paths().get("lm_studio", [])
    
    @property
    def DEFAULT_COMFYUI_PATHS(self) -> List[str]:
        """Default ComfyUI paths."""
        return self._get_default_paths().get("comfyui", [])
    
    @property
    def DEFAULT_HUGGINGFACE_PATHS(self) -> List[str]:
        """Default Hugging Face paths."""
        return self._get_default_paths().get("huggingface", [])
    
    @property
    def DEFAULT_MLX_PATHS(self) -> List[str]:
        """Default MLX paths."""
        return self._get_default_paths().get("mlx", [])
    
    @property
    def DEFAULT_CODE_FOLDERS(self) -> List[str]:
        """Default code folders to scan."""
        if sys.platform == "win32":
            return [
                str(Path.home() / "Documents"),
                str(Path.home() / "Projects"),
                str(Path.home() / "code"),
            ]
        else:
            return [
                "~/Documents",
                "~/Projects",
                "~/code"
            ]
    
    def load_config(self) -> None:
        """Load configuration from file or use defaults."""
        if not TOML_AVAILABLE:
            self.config_data = {}
            return
        
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    self.config_data = toml.load(f)
            except Exception:
                # If config file is invalid, use defaults
                self.config_data = {}
    
    def save_config(self) -> None:
        """Save configuration to file."""
        if not TOML_AVAILABLE:
            return
        
        # Ensure config directory exists
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(self.config_path, 'w') as f:
                toml.dump(self.config_data, f)
        except Exception as e:
            # Silently fail - don't break scanning if config can't be saved
            pass
    
    def add_discovered_path(self, tool_name: str, path: str) -> bool:
        """
        Add a discovered path to the appropriate tool's path list.
        
        Args:
            tool_name: Name of the tool (e.g., "Ollama", "ComfyUI")
            path: Path string to add
            
        Returns:
            True if path was added, False if it already exists
        """
        # Map tool names to config keys
        tool_mapping = {
            "Ollama": "ollama_paths",
            "LM Studio": "lm_studio_paths",
            "ComfyUI": "comfyui_paths",
            "Hugging Face": "huggingface_paths",
            "MLX": "mlx_paths",
        }
        
        config_key = tool_mapping.get(tool_name)
        if not config_key:
            return False  # Unknown tool, don't save
        
        # Initialize tools section if needed
        if "tools" not in self.config_data:
            self.config_data["tools"] = {}
        
        # Get current paths or use defaults
        current_paths = self.config_data["tools"].get(config_key, [])
        if not current_paths:
            # Use defaults if not set - access the property
            default_property_name = f"DEFAULT_{config_key.upper()}"
            if hasattr(self, default_property_name):
                default_paths = getattr(self, default_property_name)
                current_paths = list(default_paths) if isinstance(default_paths, (list, tuple)) else []
            else:
                current_paths = []
        
        # Check if path already exists
        if path in current_paths:
            return False
        
        # Add path
        current_paths.append(path)
        self.config_data["tools"][config_key] = current_paths
        
        # Save to file
        self.save_config()
        return True
    
    def get(self, section: str, key: str, default=None):
        """
        Get configuration value.
        
        Args:
            section: Configuration section name
            key: Configuration key name
            default: Default value if not found
            
        Returns:
            Configuration value or default
        """
        return self.config_data.get(section, {}).get(key, default)
    
    @property
    def min_size_mb(self) -> int:
        """Minimum file size in MB."""
        return self.get("scanner", "min_size_mb", 500)
    
    @property
    def known_paths_only(self) -> bool:
        """Whether to only scan known paths."""
        return self.get("scanner", "known_paths_only", False)
    
    @property
    def scan_roots(self) -> List[str]:
        """Root directories to scan."""
        return self.get("scanner", "scan_roots", ["~/"])
    
    @property
    def ollama_paths(self) -> List[str]:
        """Ollama model paths."""
        return self.get("tools", "ollama_paths", self.DEFAULT_OLLAMA_PATHS)
    
    @property
    def lm_studio_paths(self) -> List[str]:
        """LM Studio model paths."""
        return self.get("tools", "lm_studio_paths", self.DEFAULT_LM_STUDIO_PATHS)
    
    @property
    def comfyui_paths(self) -> List[str]:
        """ComfyUI model paths."""
        return self.get("tools", "comfyui_paths", self.DEFAULT_COMFYUI_PATHS)
    
    @property
    def huggingface_paths(self) -> List[str]:
        """Hugging Face cache paths."""
        return self.get("tools", "huggingface_paths", self.DEFAULT_HUGGINGFACE_PATHS)
    
    @property
    def mlx_paths(self) -> List[str]:
        """MLX model paths."""
        return self.get("tools", "mlx_paths", self.DEFAULT_MLX_PATHS)
    
    @property
    def code_folders(self) -> List[str]:
        """Code folders to scan."""
        return self.get("tools", "code_folders", self.DEFAULT_CODE_FOLDERS)
    
    def get_all_known_paths(self) -> List[str]:
        """
        Get all known tool paths.
        
        Returns:
            List of all known paths
        """
        paths = []
        paths.extend(self.ollama_paths)
        paths.extend(self.lm_studio_paths)
        paths.extend(self.comfyui_paths)
        paths.extend(self.huggingface_paths)
        paths.extend(self.mlx_paths)
        return paths
    
    @property
    def default_format(self) -> str:
        """Default output format."""
        return self.get("output", "default_format", "table")
    
    @property
    def group_by_tool(self) -> bool:
        """Whether to group results by tool."""
        return self.get("output", "group_by_tool", True)
    
    @property
    def show_duplicates(self) -> bool:
        """Whether to show duplicates."""
        return self.get("output", "show_duplicates", True)
    
    @property
    def watcher_min_size_mb(self) -> int:
        """Minimum file size for watcher notifications."""
        return self.get("watcher", "min_size_mb", 500)
    
    @property
    def watcher_paths(self) -> List[str]:
        """Paths to watch."""
        paths = self.get("watcher", "watch_paths", [])
        if not paths:
            return self.get_all_known_paths()
        return paths
