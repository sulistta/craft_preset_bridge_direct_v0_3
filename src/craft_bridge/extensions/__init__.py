"""Bundled original renderers; installing maps never loads executable modules."""

from importlib.resources import files
from pathlib import Path

from craft_bridge.core.safety import BridgeError

NAMES = ("glow", "shake", "stretch", "diffusion", "modulation", "glint", "pixelsort", "flicker", "median", "directional", "sharpen", "colorize", "mathops", "dissolveshake", "heatwave", "signal", "geometric", "pixelencoder", "hotspots", "hfhotspots", "olmdirectional", "godrays")


def extension_paths(name: str) -> tuple[Path, Path]:
    if name not in NAMES:
        raise BridgeError("Extensão desconhecida.")
    root = files(__package__).joinpath(name)
    mapping = Path(str(root.joinpath("mapping.json"))).resolve()
    module = Path(str(root.joinpath(f"bridge_{name}.wasm"))).resolve()
    if not mapping.is_file() or not module.is_file():
        raise BridgeError("Extensão incompleta: reconstrua ou reinstale o pacote.")
    return mapping, module
