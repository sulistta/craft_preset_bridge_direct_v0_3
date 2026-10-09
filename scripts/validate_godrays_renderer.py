"""Original analytic impulses through Session; private source controls opt-in."""

import argparse
import hashlib
import json
import math
import os
import runpy
import select
import subprocess
from pathlib import Path

from craft_bridge.core.pipeline import inspect_file, preview
from craft_bridge.core.validation import validate_plan
from craft_bridge.exporters.effectcraft.exporter import preview_commands
from craft_bridge.extensions import extension_paths
from craft_bridge.integrations.control import ControlClient
from craft_bridge.integrations.effectcraft import apply_plan
from craft_bridge.mappings.registry import Registry

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "PEGR"


def document(package):
    doc = runpy.run_path(str(ROOT / "scripts/validate_signal_renderer.py"))["document"](package)
    doc.presets[0].effects[0].identifier.match_name = SOURCE
    return doc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--real-presets", type=Path)
    parser.add_argument("--harness", type=Path, default=ROOT / "artifacts/native-target/debug/craft-bridge-multi-input-probe")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Use a new output directory")
    out = args.output.resolve()
    out.mkdir(parents=True)
    os.environ["CRAFT_BRIDGE_CONFIG"] = str(out / "config")
    fixture = out / "original-impulse.wat"
    runpy.run_path(str(ROOT / "scripts/validate_olmdirectional_renderer.py"))["impulse_module"](fixture)
    mapping, module = extension_paths("godrays")
    package = json.loads(mapping.read_text())
    registry = Registry()
    registry.install(mapping)
    rules = package["mappings"][0]["params"]
    audit = []
    with (out / "host.log").open("w") as log:
        process = subprocess.Popen([str(args.harness.resolve()), "--serve"], stdout=subprocess.PIPE, stderr=log, text=True)
        try:
            assert process.stdout is not None and select.select([process.stdout], [], [], 20)[0]
            ready = process.stdout.readline().strip()
            assert ready.startswith("Bridge experimental host ready: "), ready
            port = int(ready.rsplit(" ", 1)[1])
            with ControlClient(port) as client:
                assert client.execute("effect.plugins.load", {"path": str(module)})["loaded"][0]["api"] == 2
                assert client.execute("effect.plugins.load", {"path": str(fixture)})["loaded"][0]["api"] == 1
                client.execute("file.projectSettings", {"bitDepth": 32})
                client.execute("comp.new", {"width": 16, "height": 8, "frameRate": 30, "duration": 2, "name": "Original ray integration proof"})
                cid = client.execute("comp.info")["id"]
                target = client.execute("layer.newSolid", {"color": "#808080", "name": "Original source"})["layer"]

            def plan_for(changes):
                doc = document(package)
                changes = {"position": [1 / 32, 1 / 16], "quality": 4, "samples": 2., "view": 1, **changes}
                for p in doc.presets[0].effects[0].parameters:
                    rule = rules[p.id]
                    if rule["target"] not in changes:
                        continue
                    value = changes[rule["target"]]
                    if rule["operation"] == "minus_one":
                        value += 1
                    elif rule["operation"] == "enum_map":
                        value = next(int(k) for k, v in rule["choices"].items() if v == value)
                    p.value.data = value
                raw, report = preview(doc, registry=registry)
                assert report.status == "PARTIAL" and report.effects[0].parameters_converted == 25
                return validate_plan(raw, registry)

            def apply(plan, impulse=True):
                with ControlClient(port) as client:
                    client.execute("effect.removeAll", {"comp": cid, "layer": target})
                    if impulse:
                        client.execute("effect.apply", {"comp": cid, "layer": target, "effect": "org.craftbridge.test.olm.impulse"})
                return apply_plan(plan, layer=target, comp=cid, port=port, confirmed=True)

            def image(client, scale=1., time=0.):
                frame = client.execute("bridge.probe.render", {"comp": cid, "time": time, "scale": scale})
                assert (frame["width"], frame["height"]) == ((16, 8) if scale == 1. else (8, 4))
                assert all(math.isfinite(v) for p in frame["pixels"] for v in p)
                return frame["pixels"]

            # At half resolution the same logical center is (3.75,1.75), so
            # its bilinear sample of the original fixture is 0.75², not 1.
            for name, changes, outer, center in [
                ("zoom-out", {}, 0.5, 1.),
                ("zoom-in", {"direction": 1}, 0., 1.),
                ("zoom-both", {"direction": 2}, 0.25, 1.),
                ("luma-threshold-refusal", {"threshold": 100.}, 0., 0.),
                ("chroma-selection", {"threshold_mode": 1, "threshold": 50.}, 0.5, 1.),
                ("normalized-decay", {"decay": 2.}, math.exp(-2) / (1 + math.exp(-2)), 1.),
            ]:
                apply(plan_for(changes))
                with ControlClient(port) as client:
                    full = image(client)
                    for i, px in enumerate(full):
                        expected = center if i == 4 * 16 + 8 else outer
                        assert all(math.isclose(v, expected if k in (0, 3) else 0., abs_tol=1e-6) for k, v in enumerate(px)), (name, i, px)
                    if name in {"zoom-out", "zoom-in", "zoom-both"}:
                        half = image(client, .5)
                        for i, px in enumerate(half):
                            expected = .78125 if i == 2 * 8 + 4 else outer * .5625
                            assert all(math.isclose(v, expected if k in (0, 3) else 0., abs_tol=1e-6) for k, v in enumerate(px)), (name, "half", i, px)
                audit.append({"case": name, "analytic": True})
            apply(plan_for({"mode": 0, "spin": 90., "position": [-1 / 32, 1 / 16]}))
            with ControlClient(port) as client:
                pixels = image(client)
                assert pixels[4 * 16 + 8] == [.5, 0., 0., .5]
                assert all(math.isclose(v, e, abs_tol=1e-6) for v, e in zip(pixels[5 * 16 + 7], [.5, 0., 0., .5], strict=True))
            audit.append({"case": "degree-spin", "analytic": True})
            apply(plan_for({"left": 10.}))
            with ControlClient(port) as client:
                assert all(px == [0.] * 4 for px in image(client))
            audit.append({"case": "logical-trim", "analytic": True})
            apply(plan_for({"samples": 16., "noise": 100., "chromatic": 50.}))
            with ControlClient(port) as client:
                before = image(client, time=0.)
                assert image(client, time=1.) == before and image(client, time=0.) == before
                client.execute("file.saveAs", {"path": str(out / "original.ecproj")})
                client.execute("file.open", {"path": str(out / "original.ecproj")})
                assert image(client) == before
            audit.append({"case": "static-noise-chromatic-reopened", "pixel_persistence": True})
            if args.real_presets:
                count = 0
                for file in sorted(args.real_presets.rglob("*.ffx")):
                    doc = inspect_file(file)
                    if not any(e.identifier.match_name == SOURCE for e in doc.presets[0].effects):
                        continue
                    original = doc.model_dump()
                    before_hash = doc.source.sha256
                    raw, report = preview(doc, registry=registry)
                    assert report.status == "PARTIAL" and doc.model_dump() == original
                    plan = validate_plan(raw, registry)
                    plan.effects = [e for e in plan.effects if e.source == SOURCE]
                    plan.commands = preview_commands(plan)
                    assert len(plan.effects) == 1 and len(plan.effects[0].properties) == 25
                    result = apply(plan, impulse=False)
                    path = result["bindings"][plan.effects[0].ref]["path"]
                    values = {p.id: p.value for p in plan.effects[0].properties}
                    # Verified actual settings select unclipped uniform input,
                    # final Screen, full opacity, repeat and own Unmult.
                    assert values["threshold"] == 0 and values["smooth"] == 50
                    assert values["repeat"] and values["unmult"] and values["view"] == 2
                    assert values["blend"] == 0 and values["opacity"] == 100
                    assert all(values[key] == 0 for key in ["left", "top", "right", "bottom", "expansion"])
                    gray = 128 / 255
                    ray = gray * 2 ** values["exposure"]
                    expected = gray + ray - gray * ray
                    with ControlClient(port) as client:
                        for reopened in [False, True]:
                            if reopened:
                                client.execute("file.saveAs", {"path": str(out / "real-controls.ecproj")})
                                client.execute("file.open", {"path": str(out / "real-controls.ecproj")})
                            for p in plan.effects[0].properties:
                                assert client.execute("prop.get", {"comp": cid, "layer": target, "path": path + "/" + p.id})["value"] == p.value
                            for scale in [1., .5]:
                                assert all(all(math.isclose(v, expected, abs_tol=1e-5) for v in px[:3]) and px[3] == 1. for px in image(client, scale))
                    assert hashlib.sha256(file.read_bytes()).hexdigest() == before_hash
                    audit.append({"case": "real-controls-original-pixels", "source_sha256": before_hash, "controls": 25, "full_half": True, "reopened": True})
                    count += 1
                assert count == 1
            (out / "summary.json").write_text(json.dumps({"cases": audit, "adobe_visual_comparison": False}, indent=2) + "\n")
            print(f"{len(audit)} native cases verified")
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)


if __name__ == "__main__":
    main()
