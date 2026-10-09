"""Original two/three-image cases through Bridge and the experimental Session.

No Adobe implementation, private fixture or user's application is opened.
"""

import argparse
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
from craft_bridge.core.pipeline import preview
from craft_bridge.core.resources import SourceLayerBindings
from craft_bridge.core.validation import validate_plan
from craft_bridge.extensions import extension_paths
from craft_bridge.integrations.control import ControlClient
from craft_bridge.integrations.effectcraft import apply_plan
from craft_bridge.mappings.registry import Registry

ROOT = Path(__file__).resolve().parents[1]


def operation(a, b, op):
    # Public elementary operation definitions, independent scalar reference.
    if op == 0:
        return a + b
    if op == 1:
        return a - b
    if op == 2:
        return a * b
    if op == 3:
        return a / b if abs(b) >= 1e-12 else 0
    if op == 4:
        return 1 - (1 - a) * (1 - b)
    if op == 5:
        return (a + b) / 2
    if op == 6:
        return 2 * a * b if b <= 0.5 else 1 - 2 * (1 - a) * (1 - b)
    if op == 7:
        return min(a, b)
    if op == 8:
        return max(a, b)
    if op == 9:
        return abs(a - b)
    if op == 10:
        return a * (1 - b) + b * (1 - a)
    if op in (11, 12, 13):
        x, y = int(a * 255 + 0.5), int(b * 255 + 0.5)
        return (x ^ y if op == 11 else x & y if op == 12 else x | y) / 255
    if op == 14:
        return a % abs(b) if b else 0
    if op == 15:
        return math.floor(a / abs(b) + 0.5) * abs(b) if b else 0
    if op == 16:
        remainder = a % (2 * abs(b)) if b else 0
        return min(remainder, 2 * abs(b) - remainder) if b else 0
    raise ValueError(op)


def document(package):
    specs = {p["id"]: p for p in package["plugins"][0]["params"]}
    params = []
    for source, rule in package["mappings"][0]["params"].items():
        spec = specs[rule["target"]]
        kind = {"slider": "number", "layer": "unknown", "checkbox": "boolean", "popup": "enum"}[spec["type"]]
        value = spec["default"]
        if kind == "enum":
            value += 1
        warnings = (
            [ConversionWarning(code="UNDECODED_VALUE", message="Original opaque reference test")]
            if kind == "unknown"
            else []
        )
        params.append(
            Parameter(
                id=source,
                name=spec["name"],
                value=ParameterValue(kind=kind, data=value),
                metadata={"animated": False},
                warnings=warnings,
            )
        )
    return PresetDocument(
        source=SourceMetadata(path="original-synthetic", format="ffx", size=0, sha256="0" * 64),
        presets=[
            Preset(
                name="Original MathOps test",
                effects=[
                    Effect(
                        name="Original math",
                        identifier=EffectIdentifier(match_name="S_MathOps"),
                        order=0,
                        parameters=params,
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
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Use a new output directory")
    out = args.output.resolve()
    out.mkdir(parents=True)
    os.environ["CRAFT_BRIDGE_CONFIG"] = str(out / "config")
    mapping, module = extension_paths("mathops")
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
                assert loaded["loaded"][0]["api"] == 2
                client.execute("file.projectSettings", {"bitDepth": 32})
                client.execute(
                    "comp.new",
                    {"name": "Original MathOps", "width": 8, "height": 4, "frameRate": 30, "duration": 2},
                )
                cid = client.execute("comp.info")["id"]
                client.execute("layer.newSolid", {"name": "Second", "color": "#206040"})
                client.execute("layer.newSolid", {"name": "White mask", "color": "#ffffff"})
                client.execute("layer.newSolid", {"name": "Black mask", "color": "#000000"})
                target = client.execute("layer.newSolid", {"name": "Target", "color": "#408020"})["layer"]
            a, b = [64 / 255, 128 / 255, 32 / 255], [32 / 255, 96 / 255, 64 / 255]

            def run(name, op=0, darks=0, mask=None, invert=False, animated=False, source_b="second"):
                with ControlClient(port) as client:
                    client.execute("effect.removeAll", {"comp": cid, "layer": target})
                doc = document(package)
                values = {
                    "S_MathOps-0002": op + 1,
                    "S_MathOps-0052": darks,
                    "S_MathOps-0541": 12.0,
                    "S_MathOps-0542": invert,
                }
                for p in doc.presets[0].effects[0].parameters:
                    if p.id in values:
                        p.value.data = values[p.id]
                    if p.id == "S_MathOps-0052" and animated:
                        p.metadata["animated"] = True
                        p.keyframes = [
                            Keyframe(
                                ticks=t,
                                time_base=30,
                                value=v,
                                in_interp=[Interpolation.LINEAR],
                                out_interp=[Interpolation.LINEAR],
                            )
                            for t, v in [(0, 0.0), (30, -0.04)]
                        ]
                layers = SourceLayerBindings(
                    source_sha256=doc.source.sha256,
                    bindings=[
                        {"effect_index": 0, "parameter": "S_MathOps-0001", "layer_ref": source_b},
                        {
                            "effect_index": 0,
                            "parameter": "S_MathOps-0003",
                            "layer_ref": "matte" if mask else None,
                        },
                    ],
                )
                output, report = preview(doc, registry=registry, source_layers=layers)
                assert report.status == "PARTIAL" and report.effects[0].parameters_converted == 17
                plan = validate_plan(output, registry)
                (out / (name + ".plan.json")).write_text(plan.model_dump_json(indent=2))
                bindings = {"second": "Second"} if source_b else {}
                if mask:
                    bindings["matte"] = mask
                project = out / (name + ".ecproj") if animated else None
                applied = apply_plan(
                    plan,
                    layer=target,
                    comp=cid,
                    port=port,
                    confirmed=True,
                    layer_bindings=bindings,
                    save_project=project,
                )
                cases = []
                with ControlClient(port) as client:
                    for scale in [1.0, 0.5]:
                        for t in [0.0, 0.5, 1.0] if animated else [0.0]:
                            dark = -0.04 * t if animated else darks
                            adjusted = [x * (1 - dark) + dark for x in a]
                            bv = b if source_b else [0.0] * 3
                            expected = [operation(x, y, op) for x, y in zip(adjusted, bv, strict=True)]
                            if mask and ((mask == "Black mask") != invert):
                                expected = a.copy()
                            expected += [1.0]
                            image = client.execute(
                                "bridge.probe.render", {"comp": cid, "time": t, "scale": scale}
                            )
                            assert (image["width"], image["height"]) == ((8, 4) if scale == 1 else (4, 2))
                            assert all(
                                math.isclose(x, y, abs_tol=3e-6, rel_tol=3e-6)
                                for px in image["pixels"]
                                for x, y in zip(px, expected, strict=True)
                            ), (name, t, image, expected)
                            cases.append({"time": t, "scale": scale, "pixel": image["pixels"][0]})
                    if project:
                        client.execute("file.open", {"path": str(project)})
                        restored = client.execute(
                            "bridge.probe.render", {"comp": cid, "time": 0.5, "scale": 1.0}
                        )
                        assert restored["pixels"][0] == cases[1]["pixel"]
                        path = applied["bindings"]["fx0"]["path"]
                        prop = client.execute(
                            "prop.get", {"comp": cid, "layer": target, "path": path + "/source_b"}
                        )
                        assert prop["type"] == "layer" and type(prop["value"]) is int
                audit.append(
                    {
                        "case": name,
                        "samples": cases,
                        "parameters": report.effects[0].parameters_converted,
                        "reopened": bool(project),
                    }
                )
                print(name, "verified", flush=True)

            for op in range(17):
                run("operation-" + str(op), op=op)
            run("nonneutral-darks", darks=-0.04)
            run("black-mask", mask="Black mask")
            run("white-mask", mask="White mask")
            run("inverted-black-mask", mask="Black mask", invert=True)
            run("explicit-null-source", source_b=None)
            run("animated-darks", animated=True)
            (out / "summary.json").write_text(
                json.dumps(
                    {
                        "cases": audit,
                        "experimental_host": True,
                        "approximate": True,
                        "adobe_visual_comparison": False,
                        "all_source_effects_supported": False,
                        "source_fixtures": "original synthetic only",
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
