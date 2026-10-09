"""Build desktop nativo com Qt dinâmico; execute no sistema operacional alvo."""

import subprocess
import sys
from importlib.metadata import distribution
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if not (ROOT / "uv.lock").exists():
    raise SystemExit("uv.lock ausente")
license_dir = ROOT / "artifacts" / "dependency-licenses"
license_dir.mkdir(parents=True, exist_ok=True)
for name in [
    "PySide6",
    "PySide6-Essentials",
    "PySide6-Addons",
    "shiboken6",
    "pydantic",
    "pydantic-core",
    "jsonschema",
    "defusedxml",
]:
    dist = distribution(name)
    for entry in dist.files or []:
        if "license" in str(entry).lower() or "copying" in str(entry).lower():
            src = Path(dist.locate_file(entry))
            if src.is_file():
                dst = license_dir / (name + "-" + src.name)
                dst.write_bytes(src.read_bytes())
subprocess.run(
    [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name",
        "CraftPresetBridge",
        "--paths",
        str(ROOT / "src"),
        "--collect-all",
        "craft_bridge",
        "--collect-all",
        "defusedxml",
        "--copy-metadata",
        "PySide6",
        "--copy-metadata",
        "shiboken6",
        "--add-data",
        f"{ROOT / 'THIRD_PARTY_NOTICES.md'}:licenses",
        "--add-data",
        f"{ROOT / 'docs/licenses'}:licenses/references",
        "--add-data",
        f"{license_dir}:licenses/dependencies",
        str(ROOT / "scripts/gui_entry.py"),
    ],
    cwd=ROOT,
    check=True,
)
