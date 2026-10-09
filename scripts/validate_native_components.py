"""Validate source-filtered components in the isolated native development harness.

Creates new compositions, applies typed plans, then saves/reopens via official commands.
Only use with scripts/native-validation's disposable Session, not a user's desktop Session.
Private corpus values/reports stay in the explicitly supplied output directory.
"""

import argparse
import json
import math
from collections import Counter
from pathlib import Path

from native_time_grid import exact_frame_rate

from craft_bridge.core.pipeline import inspect_file, preview
from craft_bridge.core.safety import BridgeError
from craft_bridge.core.validation import validate_plan
from craft_bridge.exporters.effectcraft.exporter import preview_commands
from craft_bridge.integrations.control import ControlClient
from craft_bridge.integrations.effectcraft import apply_plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--source", action="append", required=True)
    parser.add_argument("--port", type=int, default=19877)
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--skip-existing", action="store_true", help="Audit created components only; selected components require validate_selected_components.py")
    parser.add_argument("--audit-time-refusals", action="store_true", help="Verify native preflight refusal for incompatible source key times, then continue the audit")
    args = parser.parse_args()
    if not args.corpus.is_dir() or args.output.exists():
        parser.error("Existing local corpus and a new output directory are required")
    args.output.mkdir(parents=True)
    reports, results = [], []
    skipped_existing = 0
    time_refusals = []
    rates = (30, 24000 / 1001, 24, 25, 30000 / 1001, 60, 50, 60000 / 1001, 120, 47.952, 95.904, 239.76)
    for file in sorted(args.corpus.rglob("*.ffx")):
        document = inspect_file(file)
        payload, report = preview(document, source_size=(args.width, args.height))
        reports.append(report.model_dump(mode="json"))
        if report.status not in ("SUCCESS", "PARTIAL"):
            continue
        full = validate_plan(payload)
        for effect in full.effects:
            if effect.source not in args.source:
                continue
            if effect.application != "create":
                if args.skip_existing:
                    skipped_existing += 1
                    continue
                raise ValueError("Existing effects require a separate preservation validation")
            plan = full.model_copy(deep=True)
            plan.effects = [effect]
            plan.commands = preview_commands(plan)
            keys = [k for p in effect.properties for k in p.keyframes]
            fps = next((f for f in rates if all(
                math.isclose(round(k.seconds * f) / f, k.seconds, rel_tol=1e-12, abs_tol=1e-9) for k in keys
            )), None)
            if fps is None:
                fps = exact_frame_rate(keys)
            if fps is None:
                if not args.audit_time_refusals:
                    raise ValueError("No tested frame rate preserves every source key")
                comp = "Bridge refused " + args.output.name + " " + str(len(time_refusals))
                with ControlClient(args.port) as client:
                    client.execute("comp.new", {"name": comp, "frameRate": 30})
                    client.execute("layer.newSolid", {"name": "Owned refusal target"})
                    before = client.execute("layer.tree", {"layer": "#1", "depth": 2})
                try:
                    apply_plan(plan, layer="#1", comp=comp, port=args.port, confirmed=True)
                except BridgeError as error:
                    assert "arredondaria" in str(error)
                else:
                    raise AssertionError("Native preflight accepted incompatible key times")
                with ControlClient(args.port) as client:
                    assert client.execute("layer.tree", {"layer": "#1", "depth": 2}) == before
                time_refusals.append({"source_sha256": document.source.sha256, "effect": effect.effect, "keyframes": len(keys), "preflight_refused_without_property_mutation": True})
                continue
            comp = "Bridge component " + args.output.name + " " + str(len(results))
            with ControlClient(args.port) as client:
                client.execute("comp.new", {"name": comp, "frameRate": fps, "duration": 20,
                                            "width": args.width, "height": args.height})
                client.execute("layer.newSolid", {"name": "Isolated native validation", "comp": comp})
            applied = apply_plan(plan, layer="#1", comp=comp, port=args.port, confirmed=True)
            prefix = applied["bindings"][effect.ref]["path"]
            snapshots = {}
            with ControlClient(args.port) as client:
                for prop in effect.properties:
                    snapshots[prop.id] = client.execute("prop.get", {
                        "layer": "#1", "comp": comp, "path": prefix + "/" + prop.id,
                    })
            (args.output / f"{len(results):03}.json").write_text(plan.model_dump_json(indent=2) + "\n")
            results.append({
                "source_sha256": document.source.sha256, "source": effect.source,
                "effect": effect.effect, "comp": comp, "prefix": prefix, "frame_rate": fps,
                "parameters": len(effect.properties), "keyframes": len(keys),
                "applied": applied, "properties": snapshots,
            })
            print(effect.source, len(effect.properties), len(keys), fps, flush=True)
    if not results:
        raise ValueError("No requested components found; no validation claimed")
    project = (args.output / "native-validation.ecproj").resolve()
    with ControlClient(args.port) as client:
        client.execute("file.saveAs", {"path": str(project)})
        client.execute("file.open", {"path": str(project)})
        for component in results:
            for prop_id, expected in component["properties"].items():
                actual = client.execute("prop.get", {
                    "layer": "#1", "comp": component["comp"], "path": component["prefix"] + "/" + prop_id,
                })
                # Exact serialization comparison includes values, key times,
                # interpolation and any ease fields exposed by the official API.
                if actual != expected:
                    raise AssertionError(f"Saved/reopened property differs: {component['effect']}/{prop_id}")
    summary = {
        "files": len(reports), "status": dict(Counter(r["status"] for r in reports)),
        "mapped_effects": dict(Counter(e["target"] for r in reports for e in r["effects"] if e["parameters_converted"])),
        "converted_parameters": sum(e["parameters_converted"] for r in reports for e in r["effects"]),
        "preserved_keyframes": sum(e["keyframes_preserved"] for r in reports for e in r["effects"]),
        "reference_size": [args.width, args.height],
        "native_components": len(results), "native_component_effects": dict(Counter(r["effect"] for r in results)),
        "native_verified_parameters": sum(r["parameters"] for r in results),
        "native_verified_keyframes": sum(r["keyframes"] for r in results),
        "project_reopen_verified": True, "adobe_visual_comparison": False,
        "skipped_existing_components": skipped_existing,
        "native_time_refusals": time_refusals,
    }
    for name, value in [("reports", reports), ("components", results), ("summary", summary)]:
        (args.output / (name + ".json")).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
