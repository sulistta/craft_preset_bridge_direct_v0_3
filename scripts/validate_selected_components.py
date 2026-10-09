"""Audit selected source components against an owned, disposable native Session.

Prepares destination effects at their original stack indices only in test compositions.
Checks untouched controls, disabled state, keys/eases and saved-project roundtrip.
Never use against a desktop project. Inputs/results stay in the supplied private output.
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
from craft_bridge.mappings.registry import Registry


def effects_tree(client, comp):
    tree = client.execute("layer.tree", {"comp": comp, "layer": "#1", "depth": 2})
    return next(group["children"] for group in tree["properties"]["children"] if group["match"] == "effects")


def native_properties(project):
    def walk(obj):
        if isinstance(obj, dict):
            if obj.get("node") == "Prop":
                yield obj["uid"], obj
            for value in obj.values():
                yield from walk(value)
        elif isinstance(obj, list):
            for value in obj:
                yield from walk(value)
    return dict(walk(json.loads(project.read_text())))


def check_eases(source, native):
    checked = 0
    for key, actual in zip(source.keyframes, native.get("keys", []), strict=True):
        for side, codes in (("in", key.in_interp), ("out", key.out_interp)):
            if codes[0].value != "Bezier":
                continue
            assert key.handles is not None
            ease = actual[side + "_ease"]
            assert len(ease) == 1
            assert math.isclose(ease[0]["speed"], getattr(key.handles, side + "_speed")[0], rel_tol=1e-9, abs_tol=1e-9)
            assert math.isclose(ease[0]["influence"], getattr(key.handles, side + "_influence")[0], rel_tol=1e-9, abs_tol=1e-9)
            checked += 1
    return checked



def segment_sample(a, b, fraction):
    """Independent scalar cubic/time inversion, not a copy of the native solver."""
    if a.out_interp[0].value == "Hold" or isinstance(a.value, bool):
        return a.value
    duration = b.seconds - a.seconds
    def handle(key, side):
        if getattr(key, side + "_interp")[0].value != "Bezier":
            return (b.value - a.value) / duration, 1 / 3
        return getattr(key.handles, side + "_speed")[0], getattr(key.handles, side + "_influence")[0]
    out_speed, out_inf = handle(a, "out")
    in_speed, in_inf = handle(b, "in")
    def cubic(p0, p1, p2, p3, u):
        v = 1 - u
        return v**3 * p0 + 3*v*v*u*p1 + 3*v*u*u*p2 + u**3*p3
    low, high = 0.0, 1.0
    for _ in range(64):
        mid = (low + high) / 2
        if cubic(0, out_inf, 1-in_inf, 1, mid) < fraction:
            low = mid
        else:
            high = mid
    return cubic(a.value, a.value + out_speed*out_inf*duration,
                 b.value - in_speed*in_inf*duration, b.value, (low + high) / 2)


def curve_samples(prop):
    for a, b in zip(prop.keyframes, prop.keyframes[1:], strict=False):
        for fraction in (0.25, 0.5, 0.75):
            yield a.seconds + fraction*(b.seconds-a.seconds), segment_sample(a, b, fraction)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--source", action="append", required=True)
    parser.add_argument("--file", dest="files", type=Path, action="append", help="Restrict validation to these authorized corpus files")
    parser.add_argument("--port", type=int, default=20089)
    parser.add_argument("--audit-time-refusals", action="store_true")
    args = parser.parse_args()
    if not args.corpus.is_dir() or args.output.exists():
        parser.error("Existing authorized corpus and a new output directory are required")
    if args.files and any(not p.is_file() or not p.resolve().is_relative_to(args.corpus.resolve()) for p in args.files):
        parser.error("Every --file must exist inside the authorized corpus")
    args.output.mkdir(parents=True)
    reports, results, plans, time_refusals = [], [], [], []
    rates = (30, 24000 / 1001, 24, 25, 30000 / 1001, 60, 50, 60000 / 1001, 120, 47.952, 95.904, 239.76)
    registry = Registry()
    for file in sorted(set(args.files) if args.files else args.corpus.rglob("*.ffx")):
        document = inspect_file(file)
        payload, report = preview(document, source_size=(1920, 1080))
        reports.append(report.model_dump(mode="json"))
        if report.status not in ("SUCCESS", "PARTIAL"):
            continue
        full = validate_plan(payload)
        for effect in full.effects:
            if effect.source not in args.source or effect.application != "existing":
                continue
            plan = full.model_copy(deep=True)
            plan.effects = [effect]
            plan.commands = preview_commands(plan)
            keys = [key for prop in effect.properties for key in prop.keyframes]
            fps = next((rate for rate in rates if all(math.isclose(round(key.seconds * rate) / rate, key.seconds, rel_tol=1e-12, abs_tol=1e-9) for key in keys)), None)
            if fps is None:
                fps = exact_frame_rate(keys)
            if fps is None:
                if not args.audit_time_refusals:
                    raise ValueError("No audited frame rate preserves all source times")
                comp = "Bridge selected refused " + args.output.name + " " + str(len(time_refusals))
                with ControlClient(args.port) as client:
                    client.execute("comp.new", {"name": comp, "frameRate": 30})
                    client.execute("layer.newSolid", {"name": "Owned refusal target"})
                    for _ in range(effect.source_effect_index + 1):
                        client.execute("effect.apply", {"effect": effect.effect})
                    before = client.execute("layer.tree", {"layer": "#1", "depth": 2})
                try:
                    apply_plan(plan, layer="#1", comp=comp, port=args.port, confirmed=True)
                except BridgeError as error:
                    assert "arredondaria" in str(error)
                else:
                    raise AssertionError("Native preflight accepted incompatible source key times")
                with ControlClient(args.port) as client:
                    assert client.execute("layer.tree", {"comp": comp, "layer": "#1", "depth": 2}) == before
                time_refusals.append({"source_sha256": document.source.sha256, "keyframes": len(keys),
                                      "preflight_refused_without_property_mutation": True})
                continue
            index = effect.source_effect_index
            assert index is not None
            comp = "Bridge selected " + args.output.name + " " + str(len(results))
            unselected = next((id for id in registry.catalog["effectcraft"]["effects"][effect.effect]
                               if id not in {prop.id for prop in effect.properties}), None)
            assert unselected is not None
            spec = registry.catalog["effectcraft"]["effects"][effect.effect][unselected]
            value = spec["default"]
            # An original, clearly nondefault sentinel. Never derived from a private preset.
            sentinel = 75.0 if spec["kind"] == "Float" and spec.get("min", 0) <= 75 <= spec.get("max", 100) else value
            if spec["kind"] == "Choice" and spec["max"] != value:
                sentinel = spec["max"]
            with ControlClient(args.port) as client:
                client.execute("comp.new", {"name": comp, "frameRate": fps, "duration": 20, "width": 1920, "height": 1080})
                client.execute("layer.newSolid", {"name": "Owned selected target", "comp": comp})
                for _ in range(index):
                    client.execute("effect.apply", {"effect": "ec.blur.sharpen", "comp": comp, "layer": "#1"})
                created = client.execute("effect.apply", {"effect": effect.effect, "comp": comp, "layer": "#1"})
                assert created["paths"] == [f"effects/#{index + 1}"]
                prefix = created["paths"][0]
                client.execute("effect.toggle", {"effect": created["effects"][0], "value": False, "comp": comp, "layer": "#1"})
                client.execute("prop.set", {"path": prefix + "/" + unselected, "value": sentinel, "comp": comp, "layer": "#1"})
                before = effects_tree(client, comp)
                preserved = client.execute("prop.get", {"comp": comp, "layer": "#1", "path": prefix + "/" + unselected})
            # keys.select ignores a comp parameter. Prove application to an inactive target
            # activates that target before selecting/interpolating any keys.
            with ControlClient(args.port) as client:
                client.execute("comp.new", {"name": comp + " distraction", "width": 32, "height": 16})
                client.execute("layer.newSolid", {"name": "Must remain untouched"})
                distraction = client.execute("layer.tree", {"layer": "#1", "depth": 2})
            applied = apply_plan(plan, layer="#1", comp=comp, port=args.port, confirmed=True)
            assert applied["preflight"]["activate_comp"] is not None
            assert applied["bindings"][effect.ref] == {"path": prefix, "uid": created["effects"][0]}
            snapshots, samples = {}, {}
            with ControlClient(args.port) as client:
                after = effects_tree(client, comp)
                assert [(e["uid"], e["effect"], e["enabled"]) for e in after] == [(e["uid"], e["effect"], e["enabled"]) for e in before]
                assert client.execute("prop.get", {"comp": comp, "layer": "#1", "path": prefix + "/" + unselected}) == preserved
                assert client.execute("layer.tree", {"comp": comp + " distraction", "layer": "#1", "depth": 2}) == distraction
                for prop in effect.properties:
                    snapshots[prop.id] = client.execute("prop.get", {"comp": comp, "layer": "#1", "path": prefix + "/" + prop.id})
                    samples[prop.id] = []
                    for time, expected in curve_samples(prop):
                        actual = client.execute("prop.get", {"comp": comp, "layer": "#1", "path": prefix + "/" + prop.id, "time": time})["value"]
                        assert actual is expected if isinstance(expected, bool) else math.isclose(actual, expected, rel_tol=1e-7, abs_tol=1e-6)
                        samples[prop.id].append({"time": time, "expected": expected, "actual": actual})
            (args.output / f"{len(results):03}.json").write_text(plan.model_dump_json(indent=2) + "\n")
            plans.append(plan)
            results.append({"source_sha256": document.source.sha256, "source": effect.source, "effect": effect.effect,
                            "comp": comp, "prefix": prefix, "frame_rate": fps, "parameters": len(effect.properties),
                            "keyframes": len(keys), "properties": snapshots, "unselected": unselected,
                            "preserved_property": preserved, "effect_tree": after, "curve_samples": samples, "inactive_target_applied": True})
            print(effect.source, len(effect.properties), len(keys), fps, flush=True)
    if not results:
        raise ValueError("No selected components found")
    project = (args.output / "native-validation.ecproj").resolve()
    with ControlClient(args.port) as client:
        client.execute("file.saveAs", {"path": str(project)})
        client.execute("file.open", {"path": str(project)})
        for result in results:
            comp, prefix = result["comp"], result["prefix"]
            assert [(e["uid"], e["effect"], e["enabled"]) for e in effects_tree(client, comp)] == [(e["uid"], e["effect"], e["enabled"]) for e in result["effect_tree"]]
            for id, expected in {**result["properties"], result["unselected"]: result["preserved_property"]}.items():
                assert client.execute("prop.get", {"comp": comp, "layer": "#1", "path": prefix + "/" + id}) == expected
                for sample in result["curve_samples"].get(id, []):
                    actual = client.execute("prop.get", {"comp": comp, "layer": "#1", "path": prefix + "/" + id, "time": sample["time"]})["value"]
                    assert actual == sample["actual"]
    native = native_properties(project)
    ease_sides = sum(check_eases(prop, native[result["properties"][prop.id]["uid"]]) for plan, result in zip(plans, results, strict=True) for prop in plan.effects[0].properties)
    summary = {"files": len(reports), "status": dict(Counter(r["status"] for r in reports)),
               "converted_parameters": sum(e["parameters_converted"] for r in reports for e in r["effects"]),
               "preserved_keyframes": sum(e["keyframes_preserved"] for r in reports for e in r["effects"]),
               "selected_components": len(results), "native_verified_parameters": sum(r["parameters"] for r in results),
               "native_verified_keyframes": sum(r["keyframes"] for r in results), "native_verified_bezier_sides": ease_sides,
               "intermediate_samples_verified": sum(len(samples) for result in results for samples in result["curve_samples"].values()),
               "inactive_target_verified": True, "existing_count_enabled_uid_preserved": True, "unselected_properties_preserved": True,
               "project_reopen_verified": True, "adobe_visual_comparison": False}
    summary["native_time_refusals"] = time_refusals
    for name, data in (("reports", reports), ("components", results), ("summary", summary)):
        (args.output / (name + ".json")).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
