"""Tool detection - infer owning application from file paths."""

from pathlib import Path
from typing import Optional


def detect_tool(filepath: Path) -> str:
    """
    Infer the owning application/tool from file path.
    
    Args:
        filepath: Path to the model file
        
    Returns:
        Tool name (e.g., "Ollama", "LM Studio", "ComfyUI") or "Unknown"
    """
    # Normalize path separators for cross-platform compatibility
    # Convert Windows backslashes to forward slashes for consistent matching
    path_str = str(filepath).replace('\\', '/').lower()
    path_parts = path_str.split('/')
    
    # Check for Ollama
    if 'ollama' in path_str:
        return "Ollama"
    
    # Check for LM Studio
    if 'lmstudio' in path_str or 'lm-studio' in path_str or 'lm_studio' in path_str:
        return "LM Studio"
    
    # Check for ComfyUI
    if 'comfyui' in path_str or 'comfy-ui' in path_str or 'comfy_ui' in path_str:
        return "ComfyUI"
    
    # Check for Hugging Face
    if 'huggingface' in path_str or 'hugging_face' in path_str or '.cache/huggingface' in path_str:
        return "Hugging Face"
    
    # Check for MLX
    if 'mlx' in path_str and ('community' in path_str or 'application support' in path_str):
        return "MLX"
    
    # Check for Stable Diffusion (common patterns)
    if 'stable-diffusion' in path_str or 'stable_diffusion' in path_str or 'stablediffusion' in path_str:
        return "Stable Diffusion"
    
    # Check for PyTorch (common in model repos)
    if 'pytorch' in path_str or '.pth' in path_str.lower() or '.pt' in path_str.lower():
        # Only if it's clearly a model directory, not just any Python project
        if 'models' in path_str or 'checkpoints' in path_str or 'weights' in path_str:
            return "PyTorch"
    
    # Check for TensorFlow
    if 'tensorflow' in path_str or '.tflite' in path_str.lower() or '.mlmodel' in path_str.lower():
        if 'models' in path_str or 'checkpoints' in path_str:
            return "TensorFlow"
    
    # Check for common model storage patterns
    if 'models' in path_parts:
        model_index = path_parts.index('models')
        # Check parent directory name
        if model_index > 0:
            parent = path_parts[model_index - 1]
            if parent not in ['library', 'application', 'cache', 'var', 'local']:
                # Capitalize and return parent directory name as tool
                return parent.replace('-', ' ').replace('_', ' ').title()
    
    # Check for Git repos (common in code folders)
    if any(part in ['documents', 'projects', 'code', 'repos', 'repositories'] for part in path_parts):
        # Check if there's a .git directory nearby
        current = Path(filepath)
        for _ in range(5):  # Check up to 5 levels up
            if (current / '.git').exists():
                return "Git Repository"
            if current.parent == current:  # Reached root
                break
            current = current.parent
    
    return "Unknown"
