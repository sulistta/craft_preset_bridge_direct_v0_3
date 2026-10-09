"""Original two-image transition through Bridge and the experimental API 3 host."""

import argparse
import json
import math
import os
import runpy
import select
import subprocess
from pathlib import Path

from craft_bridge.core.models import Interpolation, Keyframe
from craft_bridge.core.pipeline import preview
from craft_bridge.core.resources import SourceLayerBindings
from craft_bridge.core.validation import validate_plan
from craft_bridge.exporters.effectcraft.exporter import PlanProperty, preview_commands
from craft_bridge.extensions import extension_paths
from craft_bridge.integrations.control import ControlClient
from craft_bridge.integrations.effectcraft import apply_plan
from craft_bridge.mappings.registry import Registry

ROOT = Path(__file__).resolve().parents[1]


def document(package):
    # Reuse an original IR builder; labels below explicitly distinguish this effect.
    builder = runpy.run_path(str(ROOT / "scripts/validate_mathops_renderer.py"))["document"]
    doc = builder(package)
    effect = doc.presets[0].effects[0]
    effect.identifier.match_name = "S_DissolveShake"
    effect.name = "Original dissolve shake"
    doc.presets[0].name = "Original two-image transition"
    return doc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--harness", type=Path, default=ROOT / "artifacts/native-target/debug/craft-bridge-multi-input-probe"
    )
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Use a new output directory")
    out = args.output.resolve()
    out.mkdir(parents=True)
    os.environ["CRAFT_BRIDGE_CONFIG"] = str(out / "config")
    mapping, module = extension_paths("dissolveshake")
    registry = Registry()
    registry.install(mapping)
    package = json.loads(mapping.read_text())
    audit = []
    with (out / "host.log").open("w") as log:
        process = subprocess.Popen(
            [str(args.harness.resolve()), "--serve"], stdout=subprocess.PIPE, stderr=log, text=True
        )
        try:
            assert process.stdout is not None and select.select([process.stdout], [], [], 20)[0]
            ready = process.stdout.readline().strip()
            assert ready.startswith("Bridge experimental host ready: "), ready
            port = int(ready.rsplit(" ", 1)[1])
            with ControlClient(port) as client:
                loaded = client.execute("effect.plugins.load", {"path": str(module)})
                assert loaded["loaded"][0]["api"] == 3
                client.execute("file.projectSettings", {"bitDepth": 32})
                client.execute(
                    "comp.new",
                    {"name": "Original dissolve", "width": 8, "height": 4, "frameRate": 30, "duration": 3},
                )
                cid = client.execute("comp.info")["id"]
                background = client.execute("layer.newSolid", {"name": "Background", "color": "#00ff00"})[
                    "layer"
                ]
                target = client.execute("layer.newSolid", {"name": "Target", "color": "#ff0000"})["layer"]
                client.execute(
                    "layer.setSwitch", {"comp": cid, "layer": background, "switch": "video", "value": False}
                )

            def converted(changes, animated=False, bound=True):
                doc = document(package)
                values = {
                    "S_DissolveShake-0054": 0.0,
                    "S_DissolveShake-0056": False,
                    "S_DissolveShake-0053": 1.0,
                    **changes,
                }
                for p in doc.presets[0].effects[0].parameters:
                    if p.id in values:
                        p.value.data = values[p.id]
                    if animated and p.id == "S_DissolveShake-0052":
                        p.metadata["animated"] = True
                        p.keyframes = [
                            Keyframe(
                                ticks=t,
                                time_base=30,
                                value=v,
                                in_interp=[Interpolation.LINEAR],
                                out_interp=[Interpolation.LINEAR],
                            )
                            for t, v in [(0, 0.0), (30, 100.0)]
                        ]
                bindings = SourceLayerBindings(
                    source_sha256=doc.source.sha256,
                    bindings=[
                        {
                            "effect_index": 0,
                            "parameter": "S_DissolveShake-0001",
                            "layer_ref": "second" if bound else None,
                        }
                    ],
                )
                result, report = preview(doc, registry=registry, source_layers=bindings)
                assert report.effects[0].parameters_converted == 41 and report.status == "PARTIAL"
                return validate_plan(result, registry)

            def reset():
                with ControlClient(port) as client:
                    client.execute("effect.removeAll", {"comp": cid, "layer": target})
                    info = next(
                        layer
                        for layer in client.execute("comp.info", {"comp": cid})["layers"]
                        if layer["id"] == target
                    )
                    if info["stretch"] != 100.0:
                        client.execute("layer.timeStretch", {"comp": cid, "layer": target, "percent": 100})
                    client.execute(
                        "layer.timing",
                        {"comp": cid, "layer": target, "start": 0.0, "in": 0.0, "out": 31 / 30},
                    )

            def check(client, t, factor, scale=1.0, bound=True):
                expected = [1 - factor, factor if bound else 0.0, 0.0, 1.0 if bound else 1 - factor]
                image = client.execute("bridge.probe.render", {"comp": cid, "time": t, "scale": scale})
                assert (image["width"], image["height"]) == ((8, 4) if scale == 1 else (4, 2))
                assert all(
                    math.isclose(x, y, abs_tol=3e-6, rel_tol=3e-6)
                    for pixel in image["pixels"]
                    for x, y in zip(pixel, expected, strict=True)
                ), (t, image, expected)
                return {"time": t, "scale": scale, "pixel": image["pixels"][0]}

            def run(
                name,
                changes,
                samples,
                animated=False,
                bound=True,
                timing=None,
                stretch=None,
                reverse=False,
                reopen=False,
            ):
                reset()
                plan = converted(changes, animated, bound)
                (out / (name + ".plan.json")).write_text(plan.model_dump_json(indent=2))
                applied = apply_plan(
                    plan,
                    layer=target,
                    comp=cid,
                    port=port,
                    confirmed=True,
                    layer_bindings={"second": "Background"} if bound else {},
                )
                with ControlClient(port) as client:
                    if timing:
                        client.execute("layer.timing", {"comp": cid, "layer": target, **timing})
                    if stretch:
                        client.execute(
                            "layer.timeStretch", {"comp": cid, "layer": target, "percent": stretch}
                        )
                    if reverse:
                        client.execute("layer.timeReverse", {"comp": cid, "layer": target})
                    pixels = [check(client, t, f, scale, bound) for scale in [1.0, 0.5] for t, f in samples]
                    if reopen:
                        project = out / (name + ".ecproj")
                        client.execute("file.saveAs", {"path": str(project)})
                        client.execute("file.open", {"path": str(project)})
                        check(client, *samples[1], bound=bound)
                        path = applied["bindings"]["fx0"]["path"]
                        restored = client.execute(
                            "prop.get", {"comp": cid, "layer": target, "path": path + "/background"}
                        )
                        assert type(restored["value"]) is int and restored["value"] == background
                audit.append({"case": name, "samples": pixels, "reopened": reopen})
                print(name, "verified", flush=True)
                return plan, applied

            for percent in [0.0, 25.0, 50.0, 75.0, 100.0]:
                run("manual-" + str(int(percent)), {"S_DissolveShake-0052": percent}, [(0.0, percent / 100)])
            run("reverse-direction", {"S_DissolveShake-0050": 2}, [(0.0, 1.0)])
            for percent in [25.0, 50.0, 75.0]:
                factor = max(0.0, min(1.0, (percent / 100 - 0.5) * 3 + 0.5))
                run(
                    "speed-" + str(int(percent)),
                    {"S_DissolveShake-0052": percent, "S_DissolveShake-0053": 3.0},
                    [(0.0, factor)],
                )
            run("explicit-null", {"S_DissolveShake-0052": 50.0}, [(0.0, 0.5)], bound=False)
            run(
                "auto-trim-shift",
                {"S_DissolveShake-0051": 2},
                [(0.2, 0.0), (0.7, 0.5), (1.2, 1.0)],
                timing={"start": 0.1, "in": 0.2, "out": 37 / 30},
            )
            run(
                "auto-stretch",
                {"S_DissolveShake-0051": 2},
                [(0.0, 0.0), (61 / 60, 0.5), (61 / 30, 1.0)],
                stretch=200.0,
            )
            run(
                "auto-time-reverse",
                {"S_DissolveShake-0051": 2},
                [(0.0, 0.0), (0.5, 0.5), (1.0, 1.0)],
                reverse=True,
            )
            run(
                "auto-one-frame", {"S_DissolveShake-0051": 2}, [(0.0, 1.0)], timing={"in": 0.0, "out": 1 / 30}
            )
            animated, applied = run(
                "animated-percent", {}, [(0.0, 0.0), (0.5, 0.5), (1.0, 1.0)], animated=True, reopen=True
            )
            path = applied["bindings"]["fx0"]["path"]
            with ControlClient(port) as client:
                before = client.execute(
                    "prop.get", {"comp": cid, "layer": target, "path": path + "/background"}
                )
                before_keys = client.execute(
                    "prop.get", {"comp": cid, "layer": target, "path": path + "/dissolve"}
                )
            selected = animated.model_copy(deep=True)
            selected.effects[0].application = "existing"
            selected.effects[0].source_effect_index = 0
            selected.effects[0].properties = [PlanProperty(id="seed", kind="Float", value=0.103)]
            selected.commands = preview_commands(selected)
            apply_plan(selected, layer=target, comp=cid, port=port, confirmed=True)
            with ControlClient(port) as client:
                assert (
                    client.execute("prop.get", {"comp": cid, "layer": target, "path": path + "/background"})
                    == before
                )
                assert (
                    client.execute("prop.get", {"comp": cid, "layer": target, "path": path + "/dissolve"})
                    == before_keys
                )
                check(client, 0.5, 0.5)
            # Auxiliary source content can change while target properties/time stay fixed.
            with ControlClient(port) as client:
                client.execute("layer.settings", {"comp": cid, "layer": background, "color": "#0000ff"})
                for scale in [1.0, 0.5]:
                    image = client.execute("bridge.probe.render", {"comp": cid, "time": 0.5, "scale": scale})
                    assert all(
                        math.isclose(a, b, abs_tol=3e-6)
                        for pixel in image["pixels"]
                        for a, b in zip(pixel, [0.5, 0.0, 0.5, 1.0], strict=True)
                    )
                client.execute("layer.settings", {"comp": cid, "layer": background, "color": "#00ff00"})
                check(client, 0.5, 0.5)
            audit.append({"case": "auxiliary-image-change", "same_target_time_and_properties": True})
            print("auxiliary-image-change verified", flush=True)
            # Nonuniform source through the official native Gradient Ramp; compare a
            # one-pixel wave shift with independent bilinear/reflected samples.
            reset()
            with ControlClient(port) as client:
                fx = client.execute(
                    "effect.apply", {"comp": cid, "layer": target, "effect": "ec.generate.gradientramp"}
                )
                ramp = fx["paths"][0]
                for id, value in [
                    ("start", [0.0, 0.0]),
                    ("end", [8.0, 0.0]),
                    ("startColor", [0.0, 0.0, 0.0, 1.0]),
                    ("endColor", [1.0, 1.0, 1.0, 1.0]),
                ]:
                    client.execute(
                        "prop.set", {"comp": cid, "layer": target, "path": ramp + "/" + id, "value": value}
                    )
                baseline = {
                    scale: client.execute("bridge.probe.render", {"comp": cid, "time": 0.25, "scale": scale})
                    for scale in [1.0, 0.5]
                }
            wave = converted(
                {
                    "S_DissolveShake-0052": 50.0,
                    "S_DissolveShake-0054": 1.0,
                    "S_DissolveShake-0055": 1.0,
                    "S_DissolveShake-0061": 0.0,
                    "S_DissolveShake-0066": 0.0,
                    "S_DissolveShake-0063": 1.0,
                    "S_DissolveShake-0064": 1.0,
                }
            )
            apply_plan(
                wave,
                layer=target,
                comp=cid,
                port=port,
                confirmed=True,
                layer_bindings={"second": "Background"},
            )
            wave_samples = []
            with ControlClient(port) as client:
                for scale in [1.0, 0.5]:
                    image = client.execute("bridge.probe.render", {"comp": cid, "time": 0.25, "scale": scale})
                    w = image["width"]
                    h = image["height"]
                    base = baseline[scale]["pixels"]
                    offset = scale
                    for y in range(h):
                        for x in range(w):
                            pos = x - offset
                            left = math.floor(pos)
                            f = pos - left

                            def at(i, w=w, base=base, y=y):
                                j = i % (2 * w)
                                return base[y * w + (j if j < w else 2 * w - 1 - j)]

                            a = [(1 - f) * u + f * v for u, v in zip(at(left), at(left + 1), strict=True)]
                            expected = [a[0] * 0.5, a[1] * 0.5 + 0.5, a[2] * 0.5, 1.0]
                            assert all(
                                math.isclose(u, v, abs_tol=3e-6, rel_tol=3e-6)
                                for u, v in zip(image["pixels"][y * w + x], expected, strict=True)
                            ), (scale, x, image["pixels"][y * w + x], expected)
                    wave_samples.append({"scale": scale, "pixels": image["pixels"]})
            audit.append({"case": "nonuniform-wave", "samples": wave_samples, "reopened": False})
            print("nonuniform-wave verified", flush=True)
            (out / "summary.json").write_text(
                json.dumps(
                    {
                        "cases": audit,
                        "selected_resources_and_animation_preserved": True,
                        "source_fixtures": "original synthetic only",
                        "experimental_api": 3,
                        "host_revision": 2,
                        "adobe_visual_comparison": False,
                        "all_source_effects_supported": False,
                    },
                    indent=2,
                )
                + "\n"
            )
        finally:
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=10)


if __name__ == "__main__":
    main()
