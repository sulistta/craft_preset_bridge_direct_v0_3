"""Audit the original glow through the official WASM loader, not Adobe.

Uses strict renderer errors: a trap/fuel exhaustion must not pass as an unchanged frame.
Writes original synthetic inputs only; no private preset/image is required.
"""

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path

from craft_bridge.extensions import extension_paths


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--harness", type=Path, default=Path("artifacts/native-target/debug/craft-bridge-native-validation"))
    parser.add_argument("--hd", action="store_true", help="Also run an actual 1920x1080 WASM frame")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Use a new output directory")
    args.output.mkdir(parents=True)
    _, module = extension_paths("glow")
    results = []
    def run(name, params, pixels=None, **extra):
        case = {"params": params, "strict_render": True, **extra}
        if pixels is not None:
            case["pixels"] = pixels
        path = args.output / (name + ".json")
        path.write_text(json.dumps(case))
        start = time.monotonic()
        process = subprocess.run([str(args.harness.resolve()), "plugin-render", str(module), str(path)], capture_output=True, text=True, timeout=60)
        if process.returncode != 0:
            raise RuntimeError(process.stderr)
        actual = json.loads(process.stdout)
        results.append({"name": name, "seconds": time.monotonic() - start, "pixels": extra.get("width", len(pixels or [])) * extra.get("height", 1), "strict_render": True})
        return actual
    def check(actual, expected):
        assert len(actual) == len(expected)
        assert all(abs(a - b) < 2e-6 for px, qx in zip(actual, expected, strict=True) for a, b in zip(px, qx, strict=True))
    pixels = [[0.25, 0.25, 0.25, 1.0], [2.0, 2.0, 2.0, 1.0], [0.75, 0.75, 0.75, 0.5], [1, 1, 1, 0]]
    base = {"radius": 0, "threshold": 100, "threshold_smooth": 0, "exposure": 4, "source_opacity": 0, "blend": 1, "unmult": True}
    check(run("threshold-hdr", base, pixels), [[0, 0, 0, 0], [8, 8, 8, 1], [3, 3, 3, 1], [0, 0, 0, 0]])
    check(run("screen", {**base, "blend": 0}, pixels), [[0, 0, 0, 0], [1, 1, 1, 1], [1, 1, 1, 1], [0, 0, 0, 0]])
    check(run("opaque-input", {**base, "view": 0, "unmult": False}, pixels), [[0, 0, 0, 1], [8, 8, 8, 1], [3, 3, 3, 1], [0, 0, 0, 1]])
    check(run("tint", {**base, "threshold": 0, "tint_enabled": True, "tint": [0.25, 0.5, 1.0, 1.0], "tint_mix": 50}, [[0.2, 0.3, 0.4, 1.0]]), [[0.5, 0.9, 1.6, 1]])
    check(run("smooth-midpoint", {**base, "exposure": 1, "threshold_smooth": 100, "view": 0}, [[1, 1, 1, 1]]), [[0.5, 0.5, 0.5, 0.5]])
    w = h = 129
    impulse = [[0, 0, 0, 0] for _ in range(w * h)]
    impulse[64 * w + 64] = [4, 2, 1, 1]
    blur = {**base, "radius": 48, "threshold": 0, "exposure": 1}
    out = run("impulse", blur, impulse, width=w, height=h)
    assert abs(sum(p[0] for p in out) - 4) < 1e-5
    assert out[64 * w + 65][0] > out[64 * w + 75][0] > 0
    assert out[64 * w + 65] == out[65 * w + 64]
    assert run("deterministic", blur, impulse, width=w, height=h) == out
    half = run("preview-scale", blur, impulse, width=w, height=h, scale=0.5)
    assert half[64 * w + 64][0] > out[64 * w + 64][0]
    if args.hd:
        # Large radius exercises the actual bounded O(pixels) WASM path and its fuel budget.
        out = run("full-hd", {**blur, "radius": 2000}, width=1920, height=1080, fill=[0.5, 0.25, 0.125, 1], summary=True)
        assert out["pixels"] == 1920 * 1080
        assert out["sum_rgb"] > 0 and out["center"][0] != 0.5
    summary = {"original_synthetic_only": True, "module_sha256": hashlib.sha256(module.read_bytes()).hexdigest(), "cases": results, "adobe_visual_comparison": False}
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
