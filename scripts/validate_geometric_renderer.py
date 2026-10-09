"""Original geometric images through an isolated Session; private FFX opt-in."""

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
    mapping, module = extension_paths("geometric")
    package = json.loads(mapping.read_text())
    registry = Registry()
    registry.install(mapping)
    builder = runpy.run_path(str(ROOT / "scripts/validate_signal_renderer.py"))["document"]
    audit = []
    with (out / "host.log").open("w") as log:
        process = subprocess.Popen([str(args.harness.resolve()), "--serve"], stdout=subprocess.PIPE, stderr=log, text=True)
        try:
            assert process.stdout is not None and select.select([process.stdout], [], [], 20)[0]
            ready = process.stdout.readline().strip()
            assert ready.startswith("Bridge experimental host ready: "), ready
            port = int(ready.rsplit(" ", 1)[1])
            with ControlClient(port) as client:
                assert client.execute("effect.plugins.load", {"path": str(module)})["loaded"][0]["api"] == 4
                client.execute("file.projectSettings", {"bitDepth": 32})
                client.execute("comp.new", {"width": 64, "height": 64, "frameRate": 30, "duration": 2, "name": "Original geometric proof"})
                cid = client.execute("comp.info")["id"]
                target = client.execute("layer.newSolid", {"color": "#404040", "name": "Original source"})["layer"]

            def plan_for(changes):
                doc = builder(package)
                effect = doc.presets[0].effects[0]
                effect.identifier.match_name = "SatoriGeometricFilters"
                for p in effect.parameters:
                    rule = package["mappings"][0]["params"][p.id]
                    if rule["target"] in changes:
                        v = changes[rule["target"]]
                        p.value.data = v + 1 if rule["operation"] == "minus_one" else v
                raw, report = preview(doc, registry=registry)
                assert report.status == "PARTIAL" and report.effects[0].parameters_converted == 21
                return validate_plan(raw, registry)

            def image(client, time=0., scale=1.):
                frame = client.execute("bridge.probe.render", {"comp": cid, "time": time, "scale": scale})
                assert frame["width"] == frame["height"] == int(64 * scale)
                assert all(math.isfinite(v) for px in frame["pixels"] for v in px)
                return frame["pixels"]

            for shape in range(6):
                with ControlClient(port) as client:
                    client.execute("effect.removeAll", {"comp": cid, "layer": target})
                plan = plan_for({"count": 12., "size": 8., "growth": 4., "shape": shape, "keep": False, "fill": True, "strategy": 1})
                apply_plan(plan, layer=target, comp=cid, port=port, confirmed=True)
                with ControlClient(port) as client:
                    for scale in [1., 0.5]:
                        px = image(client, scale=scale)
                        assert any(p[3] > 0 for p in px) and any(p[3] == 0 for p in px), shape
                audit.append({"case": "original-shape", "shape": shape, "full_half": True})
            with ControlClient(port) as client:
                client.execute("effect.removeAll", {"comp": cid, "layer": target})
                prefix = client.execute("effect.apply", {"comp": cid, "layer": target, "effect": "ec.color.brightnesscontrast"})["paths"][0]
                for t, value in [(0., 0.), (1., 100.)]:
                    client.execute("prop.addKey", {"comp": cid, "layer": target, "path": prefix + "/brightness", "time": t, "value": value})
                expected = {(t, scale): image(client, t, scale) for t in [0., 0.1, 0.2] for scale in [1., 0.5]}
            plan = plan_for({"count": 0., "skip": 2., "keep": True})
            apply_plan(plan, layer=target, comp=cid, port=port, confirmed=True)
            with ControlClient(port) as client:
                for now, held in [(0., 0.), (2 / 30, 0.), (3 / 30, 0.1), (5 / 30, 0.1), (6 / 30, 0.2)]:
                    for scale in [1., 0.5]:
                        assert image(client, now, scale) == expected[(held, scale)]
                    audit.append({"case": "original-held-prefix", "now": now, "held": held, "full_half": True})
                client.execute("file.saveAs", {"path": str(out / "original.ecproj")})
                client.execute("file.open", {"path": str(out / "original.ecproj")})
                assert image(client, 5 / 30) == expected[(0.1, 1.)]
                audit.append({"case": "original-reopened"})
            if args.real_presets:
                real_count = 0
                for file in sorted(args.real_presets.rglob("*.ffx")):
                    before = hashlib.sha256(file.read_bytes()).hexdigest()
                    doc = inspect_file(file)
                    if not any(e.identifier.match_name == "SatoriGeometricFilters" for e in doc.presets[0].effects):
                        continue
                    raw, _ = preview(doc, registry=registry)
                    real = validate_plan(raw, registry)
                    real.effects = [e for e in real.effects if e.source == "SatoriGeometricFilters"]
                    real.commands = preview_commands(real)
                    assert len(real.effects) == 1 and len(real.effects[0].properties) == 21
                    with ControlClient(port) as client:
                        client.execute("effect.removeAll", {"comp": cid, "layer": target})
                    applied = apply_plan(real, layer=target, comp=cid, port=port, confirmed=True)
                    with ControlClient(port) as client:
                        path = applied["bindings"][real.effects[0].ref]["path"]
                        for reopened in [False, True]:
                            if reopened:
                                client.execute("file.saveAs", {"path": str(out / "real-controls.ecproj")})
                                client.execute("file.open", {"path": str(out / "real-controls.ecproj")})
                            for p in real.effects[0].properties:
                                assert client.execute("prop.get", {"comp": cid, "layer": target, "path": path + "/" + p.id})["value"] == p.value
                            image(client)
                    assert hashlib.sha256(file.read_bytes()).hexdigest() == before
                    audit.append({"case": "real-static-controls-original-pixels", "source_sha256": before, "properties": 21, "reopened": True})
                    real_count += 1
                assert real_count == 1
            (out / "summary.json").write_text(json.dumps({"cases": audit, "no_adobe_comparison": True}, indent=2) + "\n")
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
