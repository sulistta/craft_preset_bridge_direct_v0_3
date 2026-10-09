"""Original synthetic pixel/time audit through the official WASM loader.

No Adobe comparison or private inputs. Strict render errors must surface, not fall back.
"""

import argparse
import hashlib
import json
import math
import subprocess
import time
from pathlib import Path

from craft_bridge.extensions import extension_paths


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--harness", type=Path, default=Path("artifacts/native-target/debug/craft-bridge-native-validation")
    )
    parser.add_argument("--hd", action="store_true")
    parser.add_argument("--render-timeout", type=float, default=300, help="Timeout per frame in seconds; Full HD CPU/WASM may take minutes")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Use a new directory")
    args.output.mkdir(parents=True)
    _, module = extension_paths("shake")
    results = []

    def run(name, params, pixels=None, **extra):
        case = {"params": params, "strict_render": True, **extra}
        if pixels is not None:
            case["pixels"] = pixels
        path = args.output / (name + ".json")
        path.write_text(json.dumps(case))
        start = time.monotonic()
        process = subprocess.run(
            [str(args.harness.resolve()), "plugin-render", str(module), str(path)],
            capture_output=True,
            text=True,
            timeout=args.render_timeout,
        )
        if process.returncode:
            raise RuntimeError(process.stderr)
        out = json.loads(process.stdout)
        results.append({"name": name, "seconds": time.monotonic() - start, "strict_render": True})
        return out

    def check(actual, expected):
        assert len(actual) == len(expected)
        assert all(
            abs(a - b) < 3e-6
            for p, q in zip(actual, expected, strict=True)
            for a, b in zip(p, q, strict=True)
        )

    pixels = [[1, 0, 0, 1], [0, 1, 0, 1], [0, 0, 1, 1]]
    base = {"x_rand_amp": 0, "y_rand_amp": 0, "frequency": 1, "x_wave_amp": 1, "x_wave_freq": 1, "wrap_x": 1}
    check(run("quarter-wave", base, pixels, time=0.25), [pixels[2], pixels[0], pixels[1]])
    check(run("half-wave", base, pixels, time=0.5), pixels)
    check(
        run("preview-half-scale", base, pixels, time=0.25, scale=0.5),
        [[0.5, 0, 0.5, 1], [0.5, 0.5, 0, 1], [0, 0.5, 0.5, 1]],
    )
    check(run("black-border", {**base, "wrap_x": 0}, pixels, time=0.25), [[0, 0, 0, 0], pixels[0], pixels[1]])
    check(run("reflect-border", {**base, "wrap_x": 2}, pixels, time=0.25), [pixels[0], pixels[0], pixels[1]])
    square = [[1, 0, 0, 1], [0, 1, 0, 1], [0, 0, 1, 1], [1, 1, 0, 1]]
    rot = {"x_rand_amp": 0, "y_rand_amp": 0, "frequency": 1, "tilt_wave_amp": 90, "tilt_wave_freq": 1}
    check(
        run("rotation", rot, square, time=0.25, width=2, height=2),
        [square[2], square[0], square[3], square[1]],
    )
    hdr = [[2, 1, 0.5, 0.5], [0, 0, 0, 0], [0.25, 0.5, 0.75, 1]]
    check(run("hdr-alpha-identity", {"amplitude": 0}, hdr, time=1), hdr)
    check(
        run("opaque-mode", {"amplitude": 0, "opacity": 0}, hdr),
        [[2, 1, 0.5, 1], [0, 0, 0, 1], [0.25, 0.5, 0.75, 1]],
    )
    check(
        run("rgb-independent-amplitude", {**base, "red_amplitude": 0}, pixels, time=0.25),
        [[1, 0, 1, 1], [0, 0, 0, 1], [0, 1, 0, 1]],
    )
    times = [0.25 + ((i + 0.5) / 8 - 0.5) / 30 for i in range(8)]
    displacement = sum(math.sin(2 * math.pi * t) for t in times) / 8
    check(
        run("motion-blur", {**base, "motion_blur": True, "blur_length": 1}, pixels, time=0.25),
        [
            [1 - displacement, 0, displacement, 1],
            [displacement, 1 - displacement, 0, 1],
            [0, displacement, 1 - displacement, 1],
        ],
    )
    check(run("twitch-stillness", {"style": 1, "stillness": 1}, pixels, time=0.25), pixels)
    check(run("jumpy-center", {"style": 2, "center_bias": 1}, pixels, time=0.25), pixels)
    texture = [[x / 7, y / 5, (x + y) / 12, 1] for y in range(5) for x in range(7)]
    random = {"x_rand_amp": 2, "y_rand_amp": 1, "seed": 0.25, "rgb_randomness": 0.5}
    original = run("noise-time", random, texture, time=0.17, width=7, height=5)
    assert run("repeatability", random, texture, time=0.17, width=7, height=5) == original
    assert run("fractional-seed", {**random, "seed": 0.5}, texture, time=0.17, width=7, height=5) != original
    assert run("another-time", random, texture, time=0.27, width=7, height=5) != original
    if args.hd:
        out = run(
            "full-hd-8-samples-rgb",
            {**random, "motion_blur": True, "z_rand_amp": 100, "tilt_rand_amp": 5},
            time=0.17,
            width=1920,
            height=1080,
            fill=[0.5, 0.25, 0.125, 1],
            summary=True,
        )
        assert out["pixels"] == 1920 * 1080 and out["sum_rgb"] > 0
    summary = {
        "original_synthetic_only": True,
        "module_sha256": hashlib.sha256(module.read_bytes()).hexdigest(),
        "cases": results,
        "adobe_visual_comparison": False,
    }
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
