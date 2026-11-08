"""Resolve Blender consistently for headless checks and the GUI executor."""
import shutil
from pathlib import Path

MAC_BLENDER = Path('/Applications/Blender.app/Contents/MacOS/Blender')


def resolve_blender(binary: str = 'blender') -> str:
    resolved = shutil.which(binary)
    if resolved:
        return resolved
    if binary == 'blender' and MAC_BLENDER.is_file():
        return str(MAC_BLENDER)
    return binary
