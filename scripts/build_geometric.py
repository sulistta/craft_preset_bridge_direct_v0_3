"""Rebuild the original dependency-free renderer with the pinned Rust toolchain."""

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CRATE = ROOT / "src/craft_bridge/extensions/geometric"
TARGET = ROOT / "artifacts/geometric-target"
subprocess.run(
    [
        "cargo",
        "+1.98.1",
        "build",
        "--locked",
        "--release",
        "--target",
        "wasm32-unknown-unknown",
        "--manifest-path",
        str(CRATE / "Cargo.toml"),
        "--target-dir",
        str(TARGET),
    ],
    check=True,
    cwd=ROOT,
)
shutil.copyfile(
    TARGET / "wasm32-unknown-unknown/release/craft_bridge_geometric.wasm", CRATE / "bridge_geometric.wasm"
)
print(CRATE / "bridge_geometric.wasm")
