"""Original synthetic pixels, independent formula reference and official WASM loader.

Source parameter sets are read only from an explicitly supplied authorized corpus.
They remain in the output audit and must not be published as private fixtures.
"""

import argparse
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


def f32(v):
    return struct.unpack("f", struct.pack("f", v))[0]


def reference(image, w, h, params):
    """Small independent direct summation, not the renderer's rolling window."""
    p = params
    normal = p["opacity"] == 1

    def rgb(px):
        return [max(-1e6, min(1e6, (px[ch] / px[3] if px[3] else 0) if normal else px[ch])) for ch in range(3)]

    image = [[f32(c) for c in px] for px in image]
    clean = [[*[f32(c * px[3]) for c in rgb(px)], px[3]] for px in image] if normal else image

    def blur(radius):
        integer = math.floor(radius)
        fraction = radius - integer
        weights = [(i, 1) for i in range(-integer, integer + 1)]
        weights += [(-integer - 1, fraction), (integer + 1, fraction)]
        src = clean
        for horizontal in (True, False):
            out = []
            for y in range(h):
                for x in range(w):
                    samples = [(src[y * w + min(w - 1, max(0, x + i))] if horizontal else
                                src[min(h - 1, max(0, y + i)) * w + x], weight) for i, weight in weights]
                    out.append([f32(sum(px[ch] * weight for px, weight in samples) / (2 * radius + 1)) for ch in range(4)])
            src = out
        return src

    delta = [[0.] * 3 for _ in image]
    edge = [0.] * len(image)
    if p["quality"] == 0:
        previous = image
        for band, (factor, name) in enumerate(zip((.5, 1, 2, 4), ("tiny", "small", "medium", "large"), strict=True)):
            following = blur(p["detail_size"] * factor)
            for i, (a, b) in enumerate(zip(previous, following, strict=True)):
                a, b = rgb(a), rgb(b)
                for ch in range(3):
                    delta[i][ch] += (p[name] - 1) * (a[ch] - b[ch])
                if band == 1:
                    edge[i] = f32(max(abs(c - d) for c, d in zip(rgb(image[i]), b, strict=True)))
            previous = following
    low = blur(p["width"])
    output = []
    for i, (src, blurred) in enumerate(zip(image, low, strict=True)):
        a, b = rgb(src), rgb(blurred)
        d = [delta[i][ch] + a[ch] - b[ch] for ch in range(3)]
        e = edge[i] if p["quality"] == 0 else max(abs(a[ch] - b[ch]) for ch in range(3))
        gate = max(0, min(1, 1 - e / p["threshold"])) if p["threshold"] else 0
        dy = sum(d[ch] * (.2126, .7152, .0722)[ch] for ch in range(3))
        out = src.copy()
        for ch, name in enumerate(("red", "green", "blue")):
            if p[name]:
                c = a[ch] + p["amplitude"] * gate * p[name] * (p["luma"] * dy + p["chroma"] * (d[ch] - dy))
                out[ch] = f32(c * src[3] if normal else c)
        if p["opacity"] == 0:
            out[3] = 1
        output.append(out)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--corpus", type=Path)
    parser.add_argument("--hd", action="store_true")
    parser.add_argument("--4k", dest="uhd", action="store_true", help="Audit the memory/fuel budget with a full nonuniform UHD frame")
    parser.add_argument("--harness", type=Path, default=Path("artifacts/native-target/debug/craft-bridge-native-validation"))
    args = parser.parse_args()
    if args.output.exists() or args.corpus is not None and not args.corpus.is_dir():
        parser.error("New output and existing optional authorized corpus required")
    args.output.mkdir(parents=True)
    mapping, module = extension_paths("sharpen")
    manifest = json.loads(mapping.read_text())["plugins"][0]
    defaults = {p["id"]: p["default"] for p in manifest["params"]}
    results = []

    def run(name, params, pixels=None, **extra):
        payload = {"params": params, "strict_render": True, **extra}
        if pixels is not None:
            payload["pixels"] = pixels
        path = args.output / (name + ".json")
        path.write_text(json.dumps(payload))
        start = time.monotonic()
        process = subprocess.run([str(args.harness.resolve()), "plugin-render", str(module), str(path.resolve())],
                                 capture_output=True, text=True, timeout=300, check=True)
        output = json.loads(process.stdout)
        (args.output / (name + ".result.json")).write_text(json.dumps(output))
        results.append({"case": name, "seconds": time.monotonic() - start, "strict_render": True})
        print(name, results[-1]["seconds"], flush=True)
        return output

    def close(a, b):
        assert len(a) == len(b)
        assert all(math.isclose(x, y, abs_tol=4e-6, rel_tol=3e-6) for p, q in zip(a, b, strict=True) for x, y in zip(p, q, strict=True))

    image = [[(x % 3) * .08, y * .06, ((x + y) % 4) * .05, .5 + (x % 3) * .25] for y in range(5) for x in range(7)]
    for quality in range(2):
        for opacity in range(3):
            p = {**defaults, "quality": quality, "opacity": opacity, "detail_size": .7, "width": 1.2, "threshold": .8}
            close(run(f"reference-q{quality}-a{opacity}", p, image, width=7, height=5), reference(image, 7, 5, p))
    hdr = [[2., -1., .5, .5], [4., .2, -2., 1.], [.2, .3, .1, 0.]]
    for opacity in range(3):
        expected = [px[:3] + [1.] for px in hdr] if opacity == 0 else hdr
        close(run(f"zero-amp-hdr-a{opacity}", {"amplitude": 0, "opacity": opacity}, hdr), expected)
    p = {**defaults, "quality": 0, "opacity": 2, "threshold": .8, "detail_size": .7, "width": 1.2}
    baseline = run("best-band-baseline", p, image, width=7, height=5)
    for name in ("tiny", "small", "medium", "large"):
        changed = {**p, name: 5}
        result = run("best-band-" + name, changed, image, width=7, height=5)
        close(result, reference(image, 7, 5, changed))
        assert result != baseline
    for name in ("red", "green", "blue", "luma", "chroma"):
        changed = {**p, name: 0}
        result = run("suppress-" + name, changed, image, width=7, height=5)
        close(result, reference(image, 7, 5, changed))
        assert result != baseline
    changed = {**p, "amplitude": -1}
    close(run("negative-amp", changed, image, width=7, height=5), reference(image, 7, 5, changed))
    close(run("threshold-zero-identity", {"threshold": 0}, hdr), hdr)
    close(run("constant-hdr", {}, [[2., -1., .5, .5]] * 35, width=7, height=5), [[2., -1., .5, .5]] * 35)
    hidden = [[1e6, -1e6, .5, 0.], [.2, .3, .1, .5], [.1, .1, .2, 1.]]
    sanitized = [[0.] * 4, *hidden[1:]]
    assert run("hidden-color", {"threshold": 1e6}, hidden) == run("hidden-color-zero", {"threshold": 1e6}, sanitized)
    half = run("half-scale", p, image, width=7, height=5, scale=.5, time=-1)
    close(half, run("half-radii", {**p, "width": p["width"] / 2, "detail_size": p["detail_size"] / 2}, image, width=7, height=5, time=200))
    for quality in range(2):
        extreme = {v["id"]: v.get("max", len(v.get("options", [])) - 1) for v in manifest["params"]}
        extreme["quality"] = quality
        assert all(math.isfinite(v) for px in run(f"upper-bounds-q{quality}", extreme, hdr, scale=16) for v in px)
    real = []
    if args.corpus:
        registry = Registry(packages=[mapping])
        texture = [[x * .001, y * .001, ((x + y) % 13) * .004, .5 + (x % 3) * .25] for y in range(49) for x in range(65)]
        for file in sorted(args.corpus.rglob("*.ffx")):
            doc = inspect_file(file)
            if not any(e.identifier.match_name == "S_Sharpen" for e in doc.presets[0].effects):
                continue
            plan, _ = preview(doc, registry=registry)
            for effect in plan["effects"]:
                if effect["source"] != "S_Sharpen":
                    continue
                params = {p["id"]: p["value"] for p in effect["properties"]}
                result = run("real-controls-" + str(len(real)), params, texture, width=65, height=49)
                assert all(math.isfinite(v) for px in result for v in px)
                assert result != texture
                assert all(px[3] == src[3] for px, src in zip(result, texture, strict=True))
                real.append({"source_sha256": doc.source.sha256, "params": params, "application": effect["application"]})
        assert len(real) == 1
    if args.hd:
        for quality in range(2):
            hd = run(f"full-hd-nonuniform-q{quality}", {"quality": quality, "width": 26.9, "threshold": .5},
                     fill=[0, 0, 0, 1], width=1920, height=1080, summary=True,
                     checker={"cell": 13, "first": [.2, .3, .4, .5], "second": [.5, .1, .2, 1.]})
            assert hd["pixels"] == 1920 * 1080 and all(math.isfinite(v) for v in hd["center"])
    if args.uhd:
        uhd = run("uhd-nonuniform-best", {"width": 26.9, "threshold": .5},
                  fill=[0, 0, 0, 1], width=3840, height=2160, summary=True,
                  checker={"cell": 13, "first": [.2, .3, .4, .5], "second": [.5, .1, .2, 1.]})
        assert uhd["pixels"] == 3840 * 2160 and all(math.isfinite(v) for v in uhd["center"])
    audit = {"cases": results, "real_control_sets": real, "synthetic_pixels_only": True,
             "adobe_visual_comparison": False, "module_sha256": hashlib.sha256(module.read_bytes()).hexdigest()}
    (args.output / "summary.json").write_text(json.dumps(audit, indent=2) + "\n")


if __name__ == "__main__":
    main()
