"""Compile the original dependency-free scene renderer; runtime builders patch data only."""

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CRATE = ROOT / "src/craft_bridge/extensions/flare"
TARGET = ROOT / "artifacts/flare-target"
subprocess.run([
    "cargo", "+1.98.1", "build", "--locked", "--release", "--target", "wasm32-unknown-unknown",
    "--manifest-path", str(CRATE / "Cargo.toml"), "--target-dir", str(TARGET),
], check=True, cwd=ROOT)
module = CRATE / "bridge_flare_template.wasm"
shutil.copyfile(TARGET / "wasm32-unknown-unknown/release/craft_bridge_flare.wasm", module)
(CRATE / "template.json").write_text(json.dumps({
    "format": "craftbridge.flare-template", "version": 1, "toolchain": "Rust 1.98.1",
    "sha256": hashlib.sha256(module.read_bytes()).hexdigest(),
    "note": "Original template; only fixed active data slots may be replaced. No user scenes bundled.",
}, indent=2) + "\n")
print(module)
