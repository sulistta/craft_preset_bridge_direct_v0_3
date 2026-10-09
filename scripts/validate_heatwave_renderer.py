"""Verify the original Heatwave renderer through a disposable native Session."""

import argparse
import hashlib
import json
import math
import os
import select
import subprocess
from pathlib import Path

from craft_bridge.core.models import (
    ConversionWarning,
    Effect,
    EffectIdentifier,
    Interpolation,
    Keyframe,
    Parameter,
    ParameterValue,
    Preset,
    PresetDocument,
    SourceMetadata,
)
from craft_bridge.core.pipeline import inspect_file, preview
from craft_bridge.core.resources import SourceLayerBindings
from craft_bridge.core.validation import validate_plan
from craft_bridge.exporters.effectcraft.exporter import PlanProperty, preview_commands
from craft_bridge.extensions import extension_paths
from craft_bridge.integrations.control import ControlClient
from craft_bridge.integrations.effectcraft import apply_plan
from craft_bridge.mappings.registry import Registry

ROOT = Path(__file__).resolve().parents[1]


def document(package):
    specs = {p["id"]: p for p in package["plugins"][0]["params"]}
    parameters = []
    for source, rule in package["mappings"][0]["params"].items():
        spec = specs[rule["target"]]
        kind = {
            "slider": "number",
            "point": "point",
            "popup": "enum",
            "layer": "unknown",
            "checkbox": "boolean",
        }[spec["type"]]
        value = spec["default"]
        if kind == "enum":
            value += 1
        parameters.append(
            Parameter(
                id=source,
                name=spec["name"],
                value=ParameterValue(kind=kind, data=value),
                metadata={"animated": False},
                warnings=[ConversionWarning(code="UNDECODED_VALUE", message="Original opaque test reference")]
                if kind == "unknown"
                else [],
            )
        )
    return PresetDocument(
        source=SourceMetadata(path="original-synthetic", format="ffx", size=0, sha256="0" * 64),
        presets=[
            Preset(
                name="Original Heatwave",
                effects=[
                    Effect(
                        name="Original noise distortion",
                        order=0,
                        identifier=EffectIdentifier(match_name="Universe_Distort_Heatwave"),
                        parameters=parameters,
                    )
                ],
            )
        ],
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--harness", type=Path, default=ROOT / "artifacts/native-target/debug/craft-bridge-multi-input-probe"
    )
    parser.add_argument("--real-presets", type=Path, help="Opt-in read-only local FFX corpus")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Use a new output directory")
    out = args.output.resolve()
    out.mkdir(parents=True)
    os.environ["CRAFT_BRIDGE_CONFIG"] = str(out / "config")
    mapping, module = extension_paths("heatwave")
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
                assert client.execute("effect.plugins.load", {"path": str(module)})["loaded"][0]["api"] == 2
                client.execute("file.projectSettings", {"bitDepth": 32})
                client.execute(
                    "comp.new",
                    {"name": "Original Heatwave", "width": 8, "height": 4, "frameRate": 30, "duration": 3},
                )
                cid = client.execute("comp.info")["id"]
                mask = client.execute("layer.newSolid", {"name": "Mask", "color": "#00ff00"})["layer"]
                target = client.execute("layer.newSolid", {"name": "Target", "color": "#ff0000"})["layer"]
                client.execute(
                    "layer.setSwitch", {"comp": cid, "layer": mask, "switch": "video", "value": False}
                )

            def converted(changes, bound=True, animated=False):
                doc = document(package)
                for p in doc.presets[0].effects[0].parameters:
                    if p.id in changes:
                        p.value.data = changes[p.id]
                    if animated and p.id == "Universe_Distort_Heatwave-0002":
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
                            "parameter": "Universe_Distort_Heatwave-0025",
                            "layer_ref": "mask" if bound else None,
                        }
                    ],
                )
                result, report = preview(doc, registry=registry, source_layers=bindings, source_size=(8, 4))
                assert report.status == "PARTIAL" and report.effects[0].parameters_converted == 25
                return validate_plan(result, registry)

            def image(client, time=0.3, scale=1.0):
                result = client.execute("bridge.probe.render", {"comp": cid, "time": time, "scale": scale})
                assert (result["width"], result["height"]) == ((8, 4) if scale == 1.0 else (4, 2))
                assert all(math.isfinite(v) for px in result["pixels"] for v in px)
                return result

            def uniform(result, value):
                assert all(
                    math.isclose(v, w, abs_tol=3e-6, rel_tol=3e-6)
                    for px in result["pixels"]
                    for v, w in zip(px, value, strict=True)
                ), (result, value)

            def apply(name, changes, bound=True, animated=False, gradient=False):
                with ControlClient(port) as client:
                    client.execute("effect.removeAll", {"comp": cid, "layer": target})
                    if gradient:
                        applied = client.execute(
                            "effect.apply",
                            {"comp": cid, "layer": target, "effect": "ec.generate.gradientramp"},
                        )
                        ramp = applied["paths"][0]
                        for id, value in [
                            ("start", [0, 0]),
                            ("end", [8, 0]),
                            ("startColor", [0, 0, 0, 1]),
                            ("endColor", [1, 1, 1, 1]),
                        ]:
                            client.execute(
                                "prop.set",
                                {"comp": cid, "layer": target, "path": ramp + "/" + id, "value": value},
                            )
                plan = converted(changes, bound, animated)
                (out / (name + ".plan.json")).write_text(plan.model_dump_json(indent=2))
                result = apply_plan(
                    plan,
                    layer=target,
                    comp=cid,
                    port=port,
                    confirmed=True,
                    layer_bindings={"mask": "Mask"} if bound else {},
                )
                return plan, result["bindings"]["fx0"]["path"]

            for name, changes, bound, expected in [
                (
                    "identity",
                    {"Universe_Distort_Heatwave-0002": 0.0, "Universe_Distort_Heatwave-0005": 0.0},
                    True,
                    [1, 0, 0, 1],
                ),
                ("bias-identity", {"Universe_Distort_Heatwave-0031": 100.0}, True, [1, 0, 0, 1]),
                ("mask-none", {"Universe_Distort_Heatwave-0030": 4}, False, [1, 1, 1, 1]),
                (
                    "layer-luminance",
                    {"Universe_Distort_Heatwave-0019": 4, "Universe_Distort_Heatwave-0030": 4},
                    True,
                    [0.7152, 0.7152, 0.7152, 1],
                ),
                (
                    "layer-alpha",
                    {
                        "Universe_Distort_Heatwave-0019": 4,
                        "Universe_Distort_Heatwave-0026": 2,
                        "Universe_Distort_Heatwave-0030": 4,
                    },
                    True,
                    [1, 1, 1, 1],
                ),
                (
                    "layer-null",
                    {"Universe_Distort_Heatwave-0019": 4, "Universe_Distort_Heatwave-0030": 4},
                    False,
                    [0, 0, 0, 1],
                ),
                (
                    "layer-null-inverted",
                    {
                        "Universe_Distort_Heatwave-0019": 4,
                        "Universe_Distort_Heatwave-0020": True,
                        "Universe_Distort_Heatwave-0030": 4,
                    },
                    False,
                    [1, 1, 1, 1],
                ),
                (
                    "zero-scale",
                    {
                        "Universe_Distort_Heatwave-0019": 4,
                        "Universe_Distort_Heatwave-0027": 0.0,
                        "Universe_Distort_Heatwave-0030": 4,
                    },
                    True,
                    [0, 0, 0, 1],
                ),
            ]:
                apply(name, changes, bound)
                with ControlClient(port) as client:
                    for scale in [1.0, 0.5]:
                        uniform(image(client, scale=scale), expected)
                audit.append({"case": name, "full_half": True})
                print(name, "verified", flush=True)
            for shape in [2, 3]:
                name = "geometry-" + str(shape)
                apply(
                    name,
                    {
                        "Universe_Distort_Heatwave-0019": shape,
                        "Universe_Distort_Heatwave-0024": 0.0,
                        "Universe_Distort_Heatwave-0030": 4,
                    },
                )
                with ControlClient(port) as client:
                    for scale in [1.0, 0.5]:
                        rendered = image(client, scale=scale)
                        w = rendered["width"]
                        for i, px in enumerate(rendered["pixels"]):
                            x, y = ((i % w + 0.5) / scale - 4, (i // w + 0.5) / scale - 2)
                            inside = (
                                (x * x + y * y <= 1.0) if shape == 2 else (abs(x) <= 1.0 and abs(y) <= 1.0)
                            )
                            assert px == ([1, 1, 1, 1] if inside else [0, 0, 0, 1])
                audit.append({"case": name, "independent_hard_geometry": True})
                print(name, "verified", flush=True)
            for wave in [1, 2, 3]:
                name = "wave-" + str(wave)
                apply(name, {"Universe_Distort_Heatwave-0001": wave, "Universe_Distort_Heatwave-0030": 2})
                with ControlClient(port) as client:
                    for scale in [1.0, 0.5]:
                        a = image(client, 0.0, scale)
                        b = image(client, 1.0, scale)
                        assert a["pixels"] != b["pixels"] and a == image(client, 0.0, scale)
                        assert all(0 <= v <= 1 for px in a["pixels"] for v in px)
                    client.execute("file.saveAs", {"path": str(out / (name + ".ecproj"))})
                    client.execute("file.open", {"path": str(out / (name + ".ecproj"))})
                    assert a == image(client, 0.0, 0.5)
                audit.append({"case": name, "temporal_cache_and_reopen": True})
                print(name, "verified", flush=True)
            for quality in [1, 2, 3]:
                name = "quality-" + str(quality)
                apply(name, {"Universe_Distort_Heatwave-0016": quality}, gradient=True)
                with ControlClient(port) as client:
                    for scale in [1.0, 0.5]:
                        assert image(client, 0.0, scale)["pixels"] != image(client, 1.0, scale)["pixels"]
                audit.append({"case": name, "nonuniform_temporal_source": True})
                print(name, "verified", flush=True)
            plan, path = apply(
                "animated-intensity", {"Universe_Distort_Heatwave-0005": 0.0}, animated=True, gradient=True
            )
            with ControlClient(port) as client:
                before = image(client, 0.0)
                after = image(client, 1.0)
                assert before["pixels"] != after["pixels"]
                resource = client.execute("prop.get", {"comp": cid, "layer": target, "path": path + "/mask"})
                keys = client.execute("prop.get", {"comp": cid, "layer": target, "path": path + "/intensity"})
                assert resource["value"] == mask
                client.execute("file.saveAs", {"path": str(out / "animated.ecproj")})
                client.execute("file.open", {"path": str(out / "animated.ecproj")})
                assert image(client, 1.0) == after
            selected = plan.model_copy(deep=True)
            selected.effects[0].application = "existing"
            selected.effects[0].source_effect_index = 1
            selected.effects[0].properties = [PlanProperty(id="speed", kind="Float", value=0.0)]
            selected.commands = preview_commands(selected)
            apply_plan(selected, layer=target, comp=cid, port=port, confirmed=True)
            with ControlClient(port) as client:
                assert (
                    client.execute("prop.get", {"comp": cid, "layer": target, "path": path + "/mask"})
                    == resource
                )
                assert (
                    client.execute("prop.get", {"comp": cid, "layer": target, "path": path + "/intensity"})
                    == keys
                )
            audit.append({"case": "animated-intensity", "selected_resources_keys_preserved": True})
            print("animated-intensity verified", flush=True)
            # Auxiliary changes at a fixed target time must bypass an incomplete cache key.
            apply(
                "auxiliary-update", {"Universe_Distort_Heatwave-0019": 4, "Universe_Distort_Heatwave-0030": 4}
            )
            with ControlClient(port) as client:
                uniform(image(client), [0.7152, 0.7152, 0.7152, 1])
                client.execute("layer.settings", {"comp": cid, "layer": mask, "color": "#0000ff"})
                uniform(image(client), [0.0722, 0.0722, 0.0722, 1])
            audit.append({"case": "auxiliary-update", "same_time": True})
            print("auxiliary-update verified", flush=True)
            if args.real_presets:
                count = 0
                for file in sorted(args.real_presets.rglob("*.ffx")):
                    before = hashlib.sha256(file.read_bytes()).hexdigest()
                    doc = inspect_file(file)
                    indices = [
                        i
                        for i, e in enumerate(doc.presets[0].effects)
                        if e.identifier.match_name == "Universe_Distort_Heatwave"
                    ]
                    if not indices:
                        continue
                    bindings = SourceLayerBindings(
                        source_sha256=before,
                        bindings=[
                            {
                                "effect_index": i,
                                "parameter": "Universe_Distort_Heatwave-0025",
                                "layer_ref": None,
                            }
                            for i in indices
                        ],
                    )
                    raw, report = preview(doc, registry=registry, source_layers=bindings, source_size=(8, 4))
                    real = validate_plan(raw, registry)
                    # The original gradient remains an independent test input, never user footage.
                    apply(
                        "real-input-gradient",
                        {"Universe_Distort_Heatwave-0002": 0.0, "Universe_Distort_Heatwave-0005": 0.0},
                        gradient=True,
                    )
                    with ControlClient(port) as client:
                        client.execute(
                            "effect.remove",
                            {"comp": cid, "layer": target, "effect": "org.craftbridge.heatwave"},
                        )
                    applied = apply_plan(real, layer=target, comp=cid, port=port, confirmed=True)

                    def readback(client, path, effect):
                        for prop in effect.properties:
                            actual = client.execute(
                                "prop.get", {"comp": cid, "layer": target, "path": path + "/" + prop.id}
                            )["value"]
                            expected = None if prop.kind == "Layer" else prop.value
                            assert actual == expected, (prop.id, actual, expected)

                    with ControlClient(port) as client:
                        for effect in real.effects:
                            path = applied["bindings"][effect.ref]["path"]
                            readback(client, path, effect)
                        frames = [image(client, scale=scale) for scale in [1.0, 0.5]]
                        project = out / "real-controls.ecproj"
                        client.execute("file.saveAs", {"path": str(project)})
                        client.execute("file.open", {"path": str(project)})
                        for effect in real.effects:
                            readback(client, applied["bindings"][effect.ref]["path"], effect)
                        assert frames == [image(client, scale=scale) for scale in [1.0, 0.5]]
                    assert hashlib.sha256(file.read_bytes()).hexdigest() == before
                    count += len(indices)
                    audit.append(
                        {
                            "case": "real-controls",
                            "decoded_controls": 24,
                            "manual_resource_replacements": 1,
                            "full_half_reopened": True,
                            "source_hash_unchanged": True,
                        }
                    )
                    print("real-controls verified", flush=True)
                assert count == 1
            (out / "summary.json").write_text(
                json.dumps(
                    {
                        "cases": audit,
                        "source_fixtures": "original synthetic + opt-in local real controls"
                        if args.real_presets
                        else "original synthetic only",
                        "api": 2,
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
