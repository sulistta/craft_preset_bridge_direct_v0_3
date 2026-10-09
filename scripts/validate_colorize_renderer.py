"""Original pixels and independent colorsys reference in the official WASM loader.

Optional real control sets stay only in a local audit, never distributed as fixtures.
"""

import argparse
import colorsys
import hashlib
import json
import math
import struct
import subprocess
import time
from pathlib import Path

from craft_bridge.core.pipeline import inspect_file, preview
from craft_bridge.extensions import extension_paths
from craft_bridge.mappings.registry import Registry


def f32(value):
    return struct.unpack("f", struct.pack("f", value))[0]


def reference(image, params):
    p = params
    def limit(v):
        return max(0, min(1, v))
    def adjust(v, amount):
        return limit(v * (1 + amount / 100) if amount < 0 else v + (1 - v) * amount / 100)
    knots = []
    space = p["color_space"]
    for i in range(1, 7):
        if 1 < i < 6 and not p[f"color{i}_on"]:
            continue
        color = p[f"color{i}"]
        rgb = color[:3]
        if p["hue"] or p["saturation"] or p["lightness"]:
            hue, light, sat = colorsys.rgb_to_hls(*map(limit, rgb))
            rgb = list(colorsys.hls_to_rgb((hue + p["hue"] / 360) % 1, adjust(light, p["lightness"]), adjust(sat, p["saturation"])))
        if space == 1:
            hue, light, sat = colorsys.rgb_to_hls(*map(limit, rgb))
            rgb = [hue, sat, light]
        elif space == 2:
            rgb = list(colorsys.rgb_to_hsv(*map(limit, rgb)))
        knots.append([*rgb, limit(color[3])])
    result = []
    for original in image:
        src = [f32(v) for v in original]
        if p["mix"] == 100:
            result.append(src)
            continue
        alpha = src[3]
        rgb = [c / alpha for c in src[:3]] if alpha else [0, 0, 0]
        metric = [sum(c * w for c, w in zip(rgb, (.2126, .7152, .0722), strict=True)), *rgb][p["input"] % 4]
        if p["input"] >= 4:
            metric = 1 - metric
        black, white = p["black_point"] / 100, p["white_point"] / 100
        t = int(metric >= white) if white == black else limit((metric - black) / (white - black))
        t = t * p["loop_count"] + p["gradient_offset"] / 100
        if p["loop_mode"] == 0:
            t = limit(t)
        elif p["loop_mode"] == 1:
            t = t if 0 <= t <= 1 else t % 1
        else:
            t %= 2
            t = t if t <= 1 else 2 - t
        t = t ** (2 ** (-p["squeeze"] / 25))
        index = min(len(knots) - 2, math.floor(t * (len(knots) - 1)))
        f = limit(t * (len(knots) - 1) - index)
        power = 2 ** (p["color_ease"] / 25)
        f = f ** power / (f ** power + (1 - f) ** power)
        a, b = knots[index].copy(), knots[index + 1].copy()
        if space:
            if not a[1]:
                a[0] = b[0]
            if not b[1]:
                b[0] = a[0]
            b[0] = a[0] + (b[0] - a[0] + .5) % 1 - .5
        color = [v + (w - v) * f for v, w in zip(a, b, strict=True)]
        if space == 1:
            color[:3] = colorsys.hls_to_rgb(color[0] % 1, color[2], color[1])
        elif space == 2:
            color[:3] = colorsys.hsv_to_rgb(color[0] % 1, color[1], color[2])
        target_alpha = alpha * color[3]
        mix = p["mix"] / 100
        rgb = [v if alpha else 0 for v in src[:3]]
        result.append([*[f32(v * mix + w * target_alpha * (1 - mix)) for v, w in zip(rgb, color[:3], strict=True)],
                       f32(alpha * mix + target_alpha * (1 - mix))])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--corpus", type=Path)
    parser.add_argument("--hd", action="store_true")
    parser.add_argument("--4k", dest="uhd", action="store_true")
    parser.add_argument("--harness", type=Path, default=Path("artifacts/native-target/debug/craft-bridge-native-validation"))
    args = parser.parse_args()
    if args.output.exists() or args.corpus is not None and not args.corpus.is_dir():
        parser.error("New output directory and existing optional authorized corpus required")
    args.output.mkdir(parents=True)
    mapping, module = extension_paths("colorize")
    manifest = json.loads(mapping.read_text())["plugins"][0]
    defaults = {p["id"]: p["default"] for p in manifest["params"]}
    image = [[x * .03, y * .04, ((x + y) % 4) * .04, .5 + (x % 3) * .25] for y in range(5) for x in range(7)]
    results = []

    def run(name, params, pixels=image, **extra):
        payload = {"params": params, "strict_render": True, "width": 7, "height": 5, "pixels": pixels, **extra}
        if pixels is None:
            payload.pop("pixels")
        path = args.output / (name + ".json")
        path.write_text(json.dumps(payload))
        start = time.monotonic()
        proc = subprocess.run([str(args.harness.resolve()), "plugin-render", str(module), str(path.resolve())],
                              capture_output=True, text=True, check=True, timeout=60)
        actual = json.loads(proc.stdout)
        (args.output / (name + ".result.json")).write_text(json.dumps(actual))
        if pixels is not None:
            expected = reference(pixels, {**defaults, **params})
            assert len(actual) == len(expected)
            assert all(math.isclose(x, y, abs_tol=4e-6, rel_tol=3e-6) for a, b in zip(actual, expected, strict=True) for x, y in zip(a, b, strict=True)), name
        results.append({"case": name, "seconds": time.monotonic() - start, "strict_render": True, "reference_verified": pixels is not None})
        print(name, results[-1]["seconds"], flush=True)
        return actual

    colored = {**defaults, "color1": [.1, .2, .7, 1.], "color3": [.8, .1, .2, 1.], "color3_on": True,
               "color6": [.3, .9, .2, .5], "mix": 13.}
    for space in range(3):
        for channel in range(8):
            run(f"reference-space{space}-input{channel}", {**colored, "input": channel, "color_space": space})
    for i in range(2, 6):
        run(f"optional-color{i}", {**colored, f"color{i}": [.3, .6, .1, .6], f"color{i}_on": True})
    for name, value in [("black_point", 20), ("white_point", 70), ("squeeze", -70), ("squeeze", 70),
                        ("color_ease", -80), ("color_ease", 80), ("hue", -420), ("saturation", -70),
                        ("saturation", 80), ("lightness", -70), ("lightness", 80), ("mix", 100)]:
        run(f"control-{name}-{value}", {**colored, name: value})
    for mode in range(3):
        run(f"loop{mode}-offset-negative", {**colored, "loop_mode": mode, "loop_count": 3.4, "gradient_offset": -67})
        run(f"loop{mode}-offset-positive", {**colored, "loop_mode": mode, "loop_count": 4, "gradient_offset": 37})
    run("coincident-thresholds", {**colored, "black_point": 50, "white_point": 50})
    run("reversed-thresholds", {**colored, "black_point": 100, "white_point": 0})
    hidden = [[1e6, -1e6, .5, 0.], [.2, .1, .3, .5], [2., -1., .5, 1.]]
    run("hidden-hdr", colored, hidden, width=3, height=1)
    run("exact-bypass-hdr", {"mix": 100}, hidden, width=3, height=1)
    baseline = run("scale-time-baseline", colored)
    assert run("scale-time-independent", colored, scale=.5, time=-123) == baseline
    for hue in (0, 120):
        run(f"tiny-hsl-knots-hue{hue}", {"color_space": 1, "hue": hue,
            "color1": [1e-200, 0., 0., 1.], "color6": [1e-200, 0., 0., 1.]})
    real = []
    if args.corpus:
        registry = Registry(packages=[mapping])
        for file in sorted(args.corpus.rglob("*.ffx")):
            doc = inspect_file(file)
            if not any(e.identifier.match_name == "BCC3Colorize" for e in doc.presets[0].effects):
                continue
            plan, _ = preview(doc, registry=registry)
            for effect in plan["effects"]:
                if effect["source"] != "BCC3Colorize":
                    continue
                params = {p["id"]: p["value"] for p in effect["properties"]}
                assert len(params) == 23
                run("real-controls-" + str(len(real)), params)
                real.append({"source_sha256": doc.source.sha256, "params": params, "application": effect["application"]})
        assert len(real) == 4
    for label, enabled, width, height in [("full-hd", args.hd, 1920, 1080), ("uhd", args.uhd, 3840, 2160)]:
        if enabled:
            actual = run(label + "-nonuniform", colored, None, width=width, height=height, summary=True, fill=[0, 0, 0, 1],
                         checker={"cell": 13, "first": [.2, .3, .4, .5], "second": [.5, .1, .2, 1.]})
            assert actual["pixels"] == width * height and all(math.isfinite(v) for v in actual["center"])
    summary = {"cases": results, "real_control_sets": real, "synthetic_pixels_only": True, "adobe_visual_comparison": False,
               "module_sha256": hashlib.sha256(module.read_bytes()).hexdigest()}
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")


if __name__ == "__main__":
    main()
