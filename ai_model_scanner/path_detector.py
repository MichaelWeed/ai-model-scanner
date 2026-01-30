"""Platform-aware path detection for AI model tools."""

import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

# Platform detection
IS_WINDOWS = sys.platform == "win32"
IS_MACOS = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")


def detect_ollama_paths() -> List[Path]:
    """
    Detect Ollama model storage paths.
    
    Returns:
        List of detected Ollama paths
    """
    paths: List[Path] = []
    
    # Check environment variable first
    ollama_models = os.getenv("OLLAMA_MODELS")
    if ollama_models:
        path = Path(ollama_models).expanduser()
        if path.exists():
            paths.append(path)
    
    # Try to query Ollama CLI for model storage location
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            # Ollama stores models in a default location
            # On macOS: ~/.ollama/models or /usr/local/var/ollama/models
            # On Linux: ~/.ollama/models or /usr/share/ollama/models
            # On Windows: %USERPROFILE%\.ollama\models or %LOCALAPPDATA%\ollama\models
            if IS_WINDOWS:
                default_paths = [
                    Path.home() / ".ollama" / "models",
                    Path(os.getenv("LOCALAPPDATA", "")) / "ollama" / "models",
                ]
            elif IS_MACOS:
                default_paths = [
                    Path.home() / ".ollama" / "models",
                    Path("/usr/local/var/ollama/models"),
                ]
            else:  # Linux
                default_paths = [
                    Path.home() / ".ollama" / "models",
                    Path("/usr/share/ollama/models"),
                ]
            
            for path in default_paths:
                if path.exists():
                    paths.append(path)
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    
    # Fallback to common paths
    if not paths:
        paths.extend(_get_common_ollama_paths())
    
    return paths


def detect_lm_studio_paths() -> List[Path]:
    """
    Detect LM Studio model storage paths.
    
    Returns:
        List of detected LM Studio paths
    """
    paths: List[Path] = []
    
    if IS_WINDOWS:
        # Windows: Check %LOCALAPPDATA%\LMStudio\models
        localappdata = os.getenv("LOCALAPPDATA", "")
        if localappdata:
            lm_paths = [
                Path(localappdata) / "LMStudio" / "models",
                Path(localappdata) / "lmstudio" / "models",
            ]
            for path in lm_paths:
                if path.exists():
                    paths.append(path)
        
        # Also check registry (optional, advanced)
        # Could use winreg module, but skip for now
    
    elif IS_MACOS:
        # macOS: Application Support and dot-directory (~/.lmstudio used by some LM Studio installs)
        app_support = Path.home() / "Library" / "Application Support"
        lm_paths = [
            app_support / "LMStudio" / "models",
            app_support / "com.lmstudio.LMStudio" / "models",
            Path.home() / ".lmstudio" / "models",  # Dot-directory used by some LM Studio versions
        ]
        for path in lm_paths:
            if path.exists():
                paths.append(path)
    
    else:  # Linux
        # Linux: ~/.local/share/lmstudio/models or ~/.config/lmstudio/models
        linux_paths = [
            Path.home() / ".local" / "share" / "lmstudio" / "models",
            Path.home() / ".config" / "lmstudio" / "models",
            Path.home() / ".lmstudio" / "models",
        ]
        for path in linux_paths:
            if path.exists():
                paths.append(path)
    
    # Fallback to common paths if none detected
    if not paths:
        paths.extend(_get_common_lm_studio_paths())
    
    return paths


def detect_comfyui_paths() -> List[Path]:
    """
    Detect ComfyUI installation paths.
    
    Returns:
        List of detected ComfyUI model directories
    """
    paths: List[Path] = []
    
    # ComfyUI typically stores models in ComfyUI/models/* subdirectories
    # Common locations:
    comfyui_base_paths = []
    
    if IS_WINDOWS:
        comfyui_base_paths = [
            Path.home() / "ComfyUI",
            Path("C:/ComfyUI"),
            Path(os.getenv("PROGRAMFILES", "")) / "ComfyUI",
        ]
    else:
        comfyui_base_paths = [
            Path.home() / "ComfyUI",
            Path("/opt/ComfyUI"),
            Path("/usr/local/ComfyUI"),
        ]
    
    model_subdirs = ["checkpoints", "loras", "unet", "vae", "clip"]
    
    for base_path in comfyui_base_paths:
        if base_path.exists():
            for subdir in model_subdirs:
                model_path = base_path / "models" / subdir
                if model_path.exists():
                    paths.append(model_path)
    
    # Fallback to common paths
    if not paths:
        paths.extend(_get_common_comfyui_paths())
    
    return paths


def detect_huggingface_paths() -> List[Path]:
    """
    Detect Hugging Face cache paths.
    
    Returns:
        List of detected Hugging Face cache directories
    """
    paths: List[Path] = []
    
    # Check HF_HOME environment variable
    hf_home = os.getenv("HF_HOME")
    if hf_home:
        path = Path(hf_home).expanduser()
        if path.exists():
            paths.append(path)
    
    # Check HF_HUB_CACHE (newer env var)
    hf_cache = os.getenv("HF_HUB_CACHE")
    if hf_cache:
        path = Path(hf_cache).expanduser()
        if path.exists():
            paths.append(path)
    
    # Default locations
    if IS_WINDOWS:
        default_paths = [
            Path.home() / ".cache" / "huggingface" / "hub",
            Path(os.getenv("LOCALAPPDATA", "")) / "huggingface" / "hub",
        ]
    else:
        default_paths = [
            Path.home() / ".cache" / "huggingface" / "hub",
        ]
    
    for path in default_paths:
        if path.exists() and path not in paths:
            paths.append(path)
    
    # Fallback to common paths
    if not paths:
        paths.extend(_get_common_huggingface_paths())
    
    return paths


def detect_mlx_paths() -> List[Path]:
    """
    Detect MLX model paths (macOS-specific).
    
    Returns:
        List of detected MLX paths (empty on non-macOS)
    """
    if not IS_MACOS:
        return []  # MLX is macOS-specific
    
    paths: List[Path] = []
    
    mlx_paths = [
        Path.home() / "mlx-community",
        Path.home() / "Library" / "Application Support" / "mlx",
    ]
    
    for path in mlx_paths:
        if path.exists():
            paths.append(path)
    
    return paths


def get_platform_common_paths() -> Dict[str, List[str]]:
    """
    Get common paths for all tools based on platform.
    
    Returns:
        Dictionary mapping tool names to lists of common paths (as strings)
    """
    return {
        "ollama": [str(p) for p in _get_common_ollama_paths()],
        "lm_studio": [str(p) for p in _get_common_lm_studio_paths()],
        "comfyui": [str(p) for p in _get_common_comfyui_paths()],
        "huggingface": [str(p) for p in _get_common_huggingface_paths()],
        "mlx": [str(p) for p in _get_common_mlx_paths()],
    }


def _get_common_ollama_paths() -> List[Path]:
    """Get common Ollama paths for current platform."""
    if IS_WINDOWS:
        return [
            Path.home() / "ollama" / "models",
            Path(os.getenv("LOCALAPPDATA", "")) / "ollama" / "models",
        ]
    elif IS_MACOS:
        return [
            Path.home() / "ollama" / "models",
            Path("/usr/local/var/ollama/models"),
        ]
    else:  # Linux
        return [
            Path.home() / "ollama" / "models",
            Path("/usr/share/ollama/models"),
        ]


def _get_common_lm_studio_paths() -> List[Path]:
    """Get common LM Studio paths for current platform."""
    if IS_WINDOWS:
        localappdata = os.getenv("LOCALAPPDATA", "")
        return [
            Path(localappdata) / "LMStudio" / "models" if localappdata else Path.home() / "LMStudio" / "models",
            Path.home() / ".lmstudio" / "models",
        ]
    elif IS_MACOS:
        app_support = Path.home() / "Library" / "Application Support"
        return [
            app_support / "LMStudio" / "models",
            app_support / "com.lmstudio.LMStudio" / "models",
            Path.home() / ".lmstudio" / "models",
        ]
    else:  # Linux
        return [
            Path.home() / ".local" / "share" / "lmstudio" / "models",
            Path.home() / ".config" / "lmstudio" / "models",
        ]


def _get_common_comfyui_paths() -> List[Path]:
    """Get common ComfyUI paths for current platform."""
    if IS_WINDOWS:
        return [
            Path.home() / "ComfyUI" / "models" / "checkpoints",
            Path.home() / "ComfyUI" / "models" / "loras",
            Path.home() / "ComfyUI" / "models" / "unet",
            Path.home() / "ComfyUI" / "models" / "vae",
            Path.home() / "ComfyUI" / "models" / "clip",
        ]
    else:
        return [
            Path.home() / "ComfyUI" / "models" / "checkpoints",
            Path.home() / "ComfyUI" / "models" / "loras",
            Path.home() / "ComfyUI" / "models" / "unet",
            Path.home() / "ComfyUI" / "models" / "vae",
            Path.home() / "ComfyUI" / "models" / "clip",
        ]


def _get_common_huggingface_paths() -> List[Path]:
    """Get common Hugging Face paths for current platform."""
    if IS_WINDOWS:
        return [
            Path.home() / ".cache" / "huggingface" / "hub",
        ]
    else:
        return [
            Path.home() / ".cache" / "huggingface" / "hub",
        ]


def _get_common_mlx_paths() -> List[Path]:
    """Get common MLX paths (macOS only)."""
    if IS_MACOS:
        return [
            Path.home() / "mlx-community",
            Path.home() / "Library" / "Application Support" / "mlx",
        ]
    return []
