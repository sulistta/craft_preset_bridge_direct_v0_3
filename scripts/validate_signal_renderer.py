"""Original images and independent math through a disposable native Session."""

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
                name="Original Signal",
                effects=[
                    Effect(
                        name="Original analog transmission",
                        order=0,
                        identifier=EffectIdentifier(match_name="ADBE Signal"),
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
    mapping, module = extension_paths("signal")
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
                    {
                        "width": 16,
                        "height": 8,
                        "frameRate": 30,
                        "duration": 2,
                        "name": "Original signal audit",
                    },
                )
                cid = client.execute("comp.info")["id"]
                target = client.execute("layer.newSolid", {"color": "#404040", "name": "Original gray"})[
                    "layer"
                ]

            neutral = dict(
                seed=0.0,
                strength=100.0,
                amplification=1.0,
                cutoff=100.0,
                luma_noise=0.0,
                chroma_noise=0.0,
                hue_noise=0.0,
                chroma_loss=0.0,
                sharpen=0.0,
                connections=0.0,
                vhs=0,
                luma_enable=False,
                quantize=0.0,
                tape_enable=False,
                thick=0.0,
                fine=0.0,
                distortion_speed=0.0,
                roll_speed=0.0,
                lowpass_in=False,
                lowpass_out=0,
                phase_shift=0.0,
                phase_offset=0.0,
                s_video=True,
                chroma_vertical=False,
                sharpen_enable=False,
                scan_blur=0.0,
            )

            def image(client, time=0.3, scale=1.0):
                frame = client.execute("bridge.probe.render", {"comp": cid, "time": time, "scale": scale})
                assert (frame["width"], frame["height"]) == ((16, 8) if scale == 1.0 else (8, 4))
                assert all(math.isfinite(v) for px in frame["pixels"] for v in px)
                return frame

            def uniform(frame, value):
                assert all(
                    math.isclose(a, b, abs_tol=4e-6, rel_tol=4e-6)
                    for px in frame["pixels"]
                    for a, b in zip(px, value, strict=True)
                ), (frame, value)

            def converted(changes, animated=False):
                doc = document(package)
                specs = {p["id"]: p for p in package["plugins"][0]["params"]}
                rules = package["mappings"][0]["params"]
                for p in doc.presets[0].effects[0].parameters:
                    dest = rules[p.id]["target"]
                    if dest in changes:
                        p.value.data = changes[dest] + 1 if specs[dest]["type"] == "popup" else changes[dest]
                    if animated and dest == "amplification":
                        p.metadata["animated"] = True
                        p.keyframes = [
                            Keyframe(
                                ticks=t,
                                time_base=30,
                                value=v,
                                in_interp=[Interpolation.LINEAR],
                                out_interp=[Interpolation.LINEAR],
                            )
                            for t, v in [(0, 1.0), (30, 3.0)]
                        ]
                raw, report = preview(doc, registry=registry)
                assert report.status == "PARTIAL" and report.effects[0].parameters_converted == 34
                return validate_plan(raw, registry)

            def reset(client, gradient):
                client.execute("effect.removeAll", {"comp": cid, "layer": target})
                if gradient:
                    path = client.execute(
                        "effect.apply", {"comp": cid, "layer": target, "effect": "ec.generate.gradientramp"}
                    )["paths"][0]
                    for id, value in [
                        ("start", [0, 0]),
                        ("end", [16, 0]),
                        ("startColor", [1, 0, 0, 1]),
                        ("endColor", [0, 0.5, 1, 1]),
                    ]:
                        client.execute(
                            "prop.set",
                            {"comp": cid, "layer": target, "path": path + "/" + id, "value": value},
                        )

            def apply(name, changes, gradient=False, animated=False):
                with ControlClient(port) as client:
                    reset(client, gradient)
                plan = converted(changes, animated)
                (out / (name + ".plan.json")).write_text(plan.model_dump_json(indent=2))
                result = apply_plan(plan, layer=target, comp=cid, port=port, confirmed=True)
                return plan, result["bindings"]["fx0"]["path"]

            g = 64 / 255
            for name, changes, expected in [
                ("zero-strength", {"strength": 0.0}, g),
                ("independent-amplification", neutral | {"amplification": 3.0, "strength": 50.0}, 2 * g),
                (
                    "independent-modulation",
                    neutral | {"luma_enable": True, "frequency": 0.0, "phase": 90.0, "lightness": 0.5},
                    1.5 * g,
                ),
                (
                    "tape-probability-zero",
                    neutral | {"tape_enable": True, "te_start": 0.0, "te_end": 1.0, "te_probability": 0.0},
                    g,
                ),
            ]:
                apply(name, changes)
                with ControlClient(port) as client:
                    for scale in [1.0, 0.5]:
                        uniform(image(client, scale=scale), [expected] * 3 + [1.0])
                audit.append({"case": name, "full_half": True, "independent_expected_gray": expected})
            with ControlClient(port) as client:
                reset(client, True)
                before = [image(client, scale=s) for s in [1.0, 0.5]]
            apply("neutral-gradient", neutral, gradient=True)
            with ControlClient(port) as client:
                after = [image(client, scale=s) for s in [1.0, 0.5]]
            for a, b in zip(before, after, strict=True):
                assert all(
                    abs(x - y) < 4e-6
                    for px, py in zip(a["pixels"], b["pixels"], strict=True)
                    for x, y in zip(px, py, strict=True)
                )
            audit.append({"case": "neutral-gradient", "independent_upstream_pixels": True})
            for control in ["vhs", "lowpass_out"]:
                frames = []
                for value in range(3):
                    settings = neutral | {"lowpass_in": True, "cutoff": 40.0, control: value}
                    apply(f"{control}-{value}", settings, gradient=True)
                    with ControlClient(port) as client:
                        frames.append([image(client, scale=s) for s in [1.0, 0.5]])
                    audit.append({"case": f"{control}-{value}", "full_half": True})
                assert all(a != b for a, b in zip(frames, frames[1:], strict=False))
            apply("temporal-noise", neutral | {"seed": 1.25, "luma_noise": 20.0}, gradient=True)
            with ControlClient(port) as client:
                frames = [image(client, time=t) for t in [0.0, 0.3, 0.6, 0.0]]
                assert frames[0] == frames[3] and frames[0] != frames[1] != frames[2]
                half = image(client, time=0.3, scale=0.5)
                client.execute("file.saveAs", {"path": str(out / "temporal.ecproj")})
                client.execute("file.open", {"path": str(out / "temporal.ecproj")})
                assert image(client, time=0.3) == frames[1]
                assert image(client, time=0.3, scale=0.5) == half
                client.execute("layer.timing", {"comp": cid, "layer": target, "in": 0.0, "out": 31 / 30})
                client.execute("layer.timeReverse", {"comp": cid, "layer": target})
                assert image(client, time=0.7) == frames[1]
                client.execute("layer.timeReverse", {"comp": cid, "layer": target})
            audit.append({"case": "temporal-noise", "reopen_repeat_reverse_verified": True})
            plan, path = apply("animated-amplification", neutral, animated=True)
            with ControlClient(port) as client:
                for scale in [1.0, 0.5]:
                    uniform(image(client, time=0.5, scale=scale), [2 * g] * 3 + [1.0])
                keys = client.execute(
                    "prop.get", {"comp": cid, "layer": target, "path": path + "/amplification"}
                )
            selected = plan.model_copy(deep=True)
            selected.effects[0].application = "existing"
            selected.effects[0].source_effect_index = 0
            selected.effects[0].properties = [PlanProperty(id="seed", kind="Float", value=1.5)]
            selected.commands = preview_commands(selected)
            apply_plan(selected, layer=target, comp=cid, port=port, confirmed=True)
            with ControlClient(port) as client:
                assert keys == client.execute(
                    "prop.get", {"comp": cid, "layer": target, "path": path + "/amplification"}
                )
                client.execute("file.saveAs", {"path": str(out / "animated.ecproj")})
                client.execute("file.open", {"path": str(out / "animated.ecproj")})
                uniform(image(client, time=0.5), [2 * g] * 3 + [1.0])
            audit.append({"case": "animated-amplification", "linear_selected_reopen": True})
            if args.real_presets:
                count = 0
                for file in sorted(args.real_presets.rglob("*.ffx")):
                    before_hash = hashlib.sha256(file.read_bytes()).hexdigest()
                    doc = inspect_file(file)
                    if not any(e.identifier.match_name == "ADBE Signal" for e in doc.presets[0].effects):
                        continue
                    raw, report = preview(doc, registry=registry)
                    real = validate_plan(raw, registry)
                    real.effects = [e for e in real.effects if e.source == "ADBE Signal"]
                    real.commands = preview_commands(real)
                    assert len(real.effects) == 1 and len(real.effects[0].properties) == 34
                    with ControlClient(port) as client:
                        reset(client, True)
                    applied = apply_plan(real, layer=target, comp=cid, port=port, confirmed=True)
                    path = applied["bindings"][real.effects[0].ref]["path"]

                    def readback(client, path, effect):
                        for p in effect.properties:
                            assert (
                                client.execute(
                                    "prop.get", {"comp": cid, "layer": target, "path": path + "/" + p.id}
                                )["value"]
                                == p.value
                            )

                    with ControlClient(port) as client:
                        readback(client, path, real.effects[0])
                        frames = [image(client, scale=s) for s in [1.0, 0.5]]
                        client.execute("file.saveAs", {"path": str(out / f"real-controls-{count}.ecproj")})
                        client.execute("file.open", {"path": str(out / f"real-controls-{count}.ecproj")})
                        readback(client, path, real.effects[0])
                        assert frames == [image(client, scale=s) for s in [1.0, 0.5]]
                    assert hashlib.sha256(file.read_bytes()).hexdigest() == before_hash
                    count += 1
                    audit.append(
                        {
                            "case": "real-controls",
                            "source_sha256": before_hash,
                            "values_persisted": 34,
                            "full_half_reopen": True,
                        }
                    )
                assert count == 2
            (out / "summary.json").write_text(
                json.dumps(
                    {
                        "cases": audit,
                        "api": 2,
                        "source": "Original test images; optional real scalar controls only",
                        "adobe_visual_comparison": False,
                    },
                    indent=2,
                )
                + "\n"
            )
            print(f"{len(audit)} Signal cases verified", flush=True)
        finally:
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=10)


if __name__ == "__main__":
    main()
