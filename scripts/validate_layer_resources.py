"""Validate Layer plans only in the disposable native development Session.

Creates original solid layers, applies every catalogued native Layer property,
checks UID persistence and tests explicit unbinding. No Adobe reference is inferred.
"""

import argparse
import json
import math
import subprocess
from pathlib import Path

from craft_bridge.core.safety import BridgeError
from craft_bridge.core.validation import validate_plan
from craft_bridge.exporters.effectcraft.exporter import (
    EffectCraftPlan,
    LayerReference,
    PlanEffect,
    PlanProperty,
    preview_commands,
)
from craft_bridge.integrations.control import ControlClient
from craft_bridge.integrations.effectcraft import apply_plan
from craft_bridge.mappings.registry import Registry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--harness", type=Path, default=Path("artifacts/native-target/debug/craft-bridge-native-validation"))
    args = parser.parse_args()
    if args.output.exists():
        parser.error("A new output directory and the owned native Session are required")
    args.output.mkdir(parents=True)
    registry = Registry(packages=[])
    effects = registry.catalog["effectcraft"]["effects"]
    selected = {id: [p for p, spec in specs.items() if spec["kind"] == "Layer"] for id, specs in effects.items()}
    selected = {id: props for id, props in selected.items() if props}
    assert len(selected) == 42 and sum(map(len, selected.values())) == 71
    with ControlClient(args.port) as client:
        cid = client.execute("comp.new", {"name": "Owned Layer resource audit", "width": 16, "height": 8})["comp"]
        source = client.execute("layer.newSolid", {"comp": cid, "name": "Original resource source"})["layer"]
        target = client.execute("layer.newSolid", {"comp": cid, "name": "Original resource target"})["layer"]
        inactive = client.execute("comp.new", {"name": "Owned inactive context sentinel"})["comp"]
    records = []
    for id, props in sorted(selected.items()):
        plan = EffectCraftPlan(version=4, name="Original synthetic resource audit", catalog_commit=registry.catalog["effectcraft"]["commit"],
                               source_sha256="0" * 64, effects=[PlanEffect(ref="fx0", effect=id, source="original-synthetic",
                               properties=[PlanProperty(id=p, kind="Layer", value=LayerReference(layer_ref="source")) for p in props])])
        plan.commands = preview_commands(plan)
        validate_plan(plan.model_dump(mode="json"), registry)
        applied = apply_plan(plan, layer="Original resource target", comp=cid, layer_bindings={"source": "Original resource source"},
                             port=args.port, confirmed=True)
        assert applied["preflight"]["layer_resource_uids"] == {"source": source}
        prefix = applied["bindings"]["fx0"]["path"]
        with ControlClient(args.port) as client:
            assert client.execute("comp.info")["id"] == inactive
            for p in props:
                actual = client.execute("prop.get", {"comp": cid, "layer": target, "path": prefix + "/" + p})
                assert actual["type"] == "layer" and actual["value"] == source and actual["keys"] == []
        records.append({"effect": id, "properties": props, "prefix": prefix, "source_uid": source, "effect_uid": applied["bindings"]["fx0"]["uid"]})
        (args.output / (str(len(records)) + ".plan.json")).write_text(plan.model_dump_json(indent=2) + "\n")
    # Explicit null can update the existing component without changing its UID.
    first = records[0]
    clear = EffectCraftPlan(version=4, name="Original explicit unbind", catalog_commit=registry.catalog["effectcraft"]["commit"],
                            source_sha256="0" * 64, effects=[PlanEffect(ref="fx0", effect=first["effect"], source="original-synthetic",
                            application="existing", source_effect_index=0,
                            properties=[PlanProperty(id=first["properties"][0], kind="Layer", value=LayerReference(layer_ref=None))])])
    clear.commands = preview_commands(clear)
    applied = apply_plan(clear, layer="Original resource target", comp=cid, port=args.port, confirmed=True)
    assert applied["bindings"]["fx0"]["uid"] == first["effect_uid"]
    project = (args.output / "layer-resources.ecproj").resolve()
    with ControlClient(args.port) as client:
        before = client.execute("layer.tree", {"comp": cid, "layer": target, "depth": 2})
    for selector in ("Original resource target", "missing layer"):
        try:
            plan = validate_plan(json.loads((args.output / "1.plan.json").read_text()), registry)
            apply_plan(plan, layer="Original resource target", comp=cid, layer_bindings={"source": selector}, port=args.port, confirmed=True)
        except BridgeError:
            pass
        else:
            raise AssertionError("Self/missing layer was accepted")
        with ControlClient(args.port) as client:
            assert client.execute("layer.tree", {"comp": cid, "layer": target, "depth": 2}) == before
    with ControlClient(args.port) as client:
        client.execute("file.saveAs", {"path": str(project)})
        client.execute("file.open", {"path": str(project)})
        for record in records:
            for p in record["properties"]:
                actual = client.execute("prop.get", {"comp": cid, "layer": target, "path": record["prefix"] + "/" + p})
                expected = None if record is first and p == first["properties"][0] else source
                assert actual["value"] == expected and actual["type"] == "layer"
    # Independent small images test the official EffectHost's second-image routing.
    source_pixels = [[.2, .1, .3, 1], [.1, .4, .2, 1], [.3, .2, .1, 1], [.4, .3, .2, 1]]
    second = [[.1, .2, .1, 1], [.2, .1, .3, 1], [.1, .3, .2, 1], [.2, .1, .1, 1]]
    render_cases = []
    for operator, expected in [(0, second), (1, [[a[c] + b[c] if c < 3 else 1 for c in range(4)] for a, b in zip(source_pixels, second, strict=True)]),
                               (3, [[a[c] * b[c] if c < 3 else 1 for c in range(4)] for a, b in zip(source_pixels, second, strict=True)])]:
        payload = {"effect": "ec.channel.compoundarithmetic", "params": {"secondSource": source, "operator": operator},
                   "width": 2, "height": 2, "pixels": source_pixels,
                   "inputs": [{"uid": source, "width": 2, "height": 2, "pixels": second}]}
        path = args.output / f"renderer-{operator}.json"
        path.write_text(json.dumps(payload))
        proc = subprocess.run([str(args.harness.resolve()), "layer-render", str(path.resolve())], capture_output=True, text=True, check=True, timeout=30)
        actual = json.loads(proc.stdout)
        assert actual["requested_layer_uids"] == [source]
        assert all(math.isclose(x, y, abs_tol=1e-6) for a, b in zip(actual["pixels"], expected, strict=True) for x, y in zip(a, b, strict=True))
        render_cases.append({"operator": operator, "exact_source_uid_requested": True, "independent_pixels_verified": True})
    summary = {"native_effects": len(records), "native_layer_properties": sum(len(r["properties"]) for r in records),
               "saved_and_reopened": True, "existing_effect_uid_preserved": True, "explicit_null_unbind_verified": True,
               "inactive_comp_preserved": True, "self_missing_refused_without_mutation": True, "native_host_renderer_cases": render_cases,
               "source_ffx_layer_decoding_claimed": False, "adobe_visual_comparison": False}
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (args.output / "components.json").write_text(json.dumps(records, indent=2) + "\n")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
