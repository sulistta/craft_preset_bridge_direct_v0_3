"""Original multi-input plan through Bridge, TCP and the experimental native host.

Starts only the disposable probe built from scripts/effectcraft-multi-input/probe.
Uses synthetic solids/WAT; never opens a user project or private preset.
"""

import argparse
import json
import os
import select
import subprocess
from pathlib import Path

from craft_bridge.core.models import Interpolation, Keyframe
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

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = {
    "api": 2,
    "bridge_host_revision": 1,
    "id": "org.craftbridge.test.layer_mix",
    "name": "Bridge Layer Mix Probe",
    "category": "Bridge Validation",
    "version": "0.1.0",
    "params": [
        {"id": "source", "name": "Source", "type": "layer", "default": None},
        {
            "id": "sourceSource",
            "name": "Source mode",
            "type": "popup",
            "default": 0,
            "options": ["Source", "Masks", "Effects & Masks"],
        },
        {"id": "mix", "name": "Mix", "type": "slider", "default": 1.0, "min": 0, "max": 1},
    ],
}


def module() -> str:
    raw = json.dumps(MANIFEST, separators=(",", ":")).encode()
    data = "".join(f"\\{v:02x}" for v in raw)
    components = "\n".join(
        f"""
      local.get $i
      local.get $i f32.load offset={offset} f32.const 1 local.get $mix f32.sub f32.mul
      local.get $other f32.load offset={offset} local.get $mix f32.mul f32.add
      f32.store offset={offset}"""
        for offset in (0, 4, 8, 12)
    )
    return f'''(module
      (memory (export "memory") 2)
      (data (i32.const 16) "{data}")
      (func (export "ec_api_version") (result i32) i32.const 2)
      (func (export "ec_manifest_ptr") (result i32) i32.const 16)
      (func (export "ec_manifest_len") (result i32) i32.const {len(raw)})
      (func (export "ec_alloc") (param i32) (result i32) i32.const 65536)
      (func (export "ec_render_v2") (param $px i32) (param $w i32) (param $h i32)
        (param $params i32) (param $np i32) (param $time f64) (param $scale f64)
        (param $table i32) (param $nt i32) (result i32)
        (local $i i32) (local $end i32) (local $other i32) (local $mix f32)
        local.get $table i32.load offset=92 i32.eqz if i32.const 0 return end
        local.get $nt i32.const 2 i32.ne if i32.const 1 return end
        local.get $np i32.const 4 i32.ne if i32.const 2 return end
        local.get $table i32.load offset=100 local.get $w i32.ne if i32.const 3 return end
        local.get $table i32.load offset=104 local.get $h i32.ne if i32.const 4 return end
        local.get $params f64.load offset=24 f32.demote_f64 local.set $mix
        local.get $table i32.load offset=96 local.set $other
        local.get $px local.set $i
        local.get $px local.get $w local.get $h i32.mul i32.const 16 i32.mul i32.add local.set $end
        block $done loop $pixels
          local.get $i local.get $end i32.ge_u br_if $done
          {components}
          local.get $i i32.const 16 i32.add local.set $i
          local.get $other i32.const 16 i32.add local.set $other
          br $pixels
        end end i32.const 0))'''


def plan(registry: Registry, animated: bool = False) -> EffectCraftPlan:
    mix = PlanProperty(id="mix", kind="Float", value=0.5)
    if animated:
        mix.keyframes = [
            Keyframe(
                ticks=ticks,
                time_base=30,
                value=value,
                in_interp=[Interpolation.LINEAR],
                out_interp=[Interpolation.LINEAR],
            )
            for ticks, value in [(0, 0.0), (30, 1.0)]
        ]
    result = EffectCraftPlan(
        version=4,
        name="Original two-input Bridge probe",
        source_sha256="0" * 64,
        catalog_commit=registry.catalog["effectcraft"]["commit"],
        effects=[
            PlanEffect(
                ref="fx0",
                effect=MANIFEST["id"],
                source="original-synthetic",
                plugin_fingerprint=registry.plugins[MANIFEST["id"]].fingerprint(),
                properties=[
                    PlanProperty(id="source", kind="Layer", value=LayerReference(layer_ref="second")),
                    PlanProperty(id="sourceSource", kind="Choice", value=0),
                    mix,
                ],
            )
        ],
    )
    result.commands = preview_commands(result)
    return validate_plan(result.model_dump(mode="json"), registry)


def rendered(client: ControlClient, cid: int, time: float, expected: list[float], scale: float = 1.0) -> dict:
    image = client.execute("bridge.probe.render", {"comp": cid, "time": time, "scale": scale})
    assert (image["width"], image["height"]) == ((8, 4) if scale == 1 else (4, 2))
    assert image["pixels"] == [expected] * (image["width"] * image["height"]), image
    return image


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--harness", type=Path, default=ROOT / "artifacts/native-target/debug/craft-bridge-multi-input-probe"
    )
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Use a new output directory")
    output = args.output.resolve()
    output.mkdir(parents=True)
    os.environ["CRAFT_BRIDGE_CONFIG"] = str(output / "config")
    package = {
        "format": "craftbridge.mappings",
        "version": 2,
        "name": "layer-probe",
        "plugins": [MANIFEST],
        "mappings": [],
    }
    package_path = output / "package.json"
    package_path.write_text(json.dumps(package, indent=2))
    Registry().install(package_path)
    registry = Registry()
    module_path = output / "original-mix.wat"
    module_path.write_text(module())
    with (output / "host.log").open("w") as log:
        process = subprocess.Popen(
            [str(args.harness.resolve()), "--serve"], stdout=subprocess.PIPE, stderr=log, text=True
        )
        try:
            assert process.stdout is not None
            assert select.select([process.stdout], [], [], 20)[0], "host startup timed out"
            ready = process.stdout.readline().strip()
            assert ready.startswith("Bridge experimental host ready: "), ready
            port = int(ready.rsplit(" ", 1)[1])
            with ControlClient(port) as client:
                loaded = client.execute("effect.plugins.load", {"path": str(module_path)})
                assert loaded["loaded"][0]["api"] == 2
                client.execute("file.projectSettings", {"bitDepth": 32})
                client.execute(
                    "comp.new",
                    {
                        "name": "Original Bridge composition",
                        "width": 8,
                        "height": 4,
                        "frameRate": 30,
                        "duration": 2,
                    },
                )
                cid = client.execute("comp.info")["id"]
                source = client.execute("layer.newSolid", {"name": "Green resource", "color": "#00ff00"})[
                    "layer"
                ]
                target = client.execute("layer.newSolid", {"name": "Red target", "color": "#ff0000"})["layer"]
                rendered(client, cid, 0, [1, 0, 0, 1])
            static = plan(registry)
            (output / "static-plan.json").write_text(static.model_dump_json(indent=2))
            static_applied = apply_plan(
                static,
                layer=target,
                comp=cid,
                port=port,
                confirmed=True,
                layer_bindings={"second": "Green resource"},
            )
            with ControlClient(port) as client:
                static_pixels = rendered(client, cid, 0, [0.5, 0.5, 0, 1])
                # Own new project: remove the original probe effect before the animated test.
                client.execute("effect.removeAll", {"comp": cid, "layer": target})
            animated = plan(registry, animated=True)
            (output / "animated-plan.json").write_text(animated.model_dump_json(indent=2))
            project = output / "original-animated.ecproj"
            applied = apply_plan(
                animated,
                layer=target,
                comp=cid,
                port=port,
                confirmed=True,
                layer_bindings={"second": "Green resource"},
                save_project=project,
            )
            path = applied["bindings"]["fx0"]["path"]
            with ControlClient(port) as client:
                samples = [
                    rendered(client, cid, t, expected, scale)
                    for scale in [1.0, 0.5]
                    for t, expected in [(0, [1, 0, 0, 1]), (0.5, [0.5, 0.5, 0, 1]), (1, [0, 1, 0, 1])]
                ]
                client.execute("file.open", {"path": str(project)})
                restored = client.execute(
                    "prop.get", {"comp": cid, "layer": target, "path": path + "/source"}
                )
                assert (
                    restored["type"] == "layer"
                    and type(restored["value"]) is int
                    and restored["value"] == source
                )
                rendered(client, cid, 0.5, [0.5, 0.5, 0, 1])
                before_keys = client.execute(
                    "prop.get", {"comp": cid, "layer": target, "path": path + "/mix"}
                )
            unbind = plan(registry)
            effect = unbind.effects[0]
            effect.application = "existing"
            effect.source_effect_index = 0
            effect.properties = [
                PlanProperty(id="source", kind="Layer", value=LayerReference(layer_ref=None))
            ]
            unbind.commands = preview_commands(unbind)
            unbound = apply_plan(unbind, layer=target, comp=cid, port=port, confirmed=True)
            with ControlClient(port) as client:
                rendered(client, cid, 0.5, [1, 0, 0, 1])
                after_keys = client.execute("prop.get", {"comp": cid, "layer": target, "path": path + "/mix"})
                assert before_keys == after_keys
            audit = {
                "official_upstream_abi": False,
                "source_effect_support_added": False,
                "all_source_effects_supported": False,
                "loaded": loaded,
                "static_apply": static_applied,
                "static_pixels": static_pixels,
                "animated_apply": applied,
                "samples": samples,
                "restored_layer": restored,
                "explicit_unbind": unbound,
                "unselected_animation_preserved": True,
            }
            (output / "summary.json").write_text(json.dumps(audit, indent=2) + "\n")
            print(
                "Bridge API 2: static/two-image animation, full/half pixels, exact Layer, save/reopen and explicit unbind verified"
            )
        finally:
            # Only the child process created above; never another application.
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=10)


if __name__ == "__main__":
    main()
