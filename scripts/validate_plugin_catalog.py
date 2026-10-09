"""Native extension audit with an original synthetic WebAssembly gain renderer.

Run only against the disposable development harness with the WASM loader enabled.
No Adobe/plugin fixture or visual-equivalence claim is involved.
"""

import argparse
import json
import os
import subprocess
from pathlib import Path

from craft_bridge.core.models import (
    Effect,
    EffectIdentifier,
    Parameter,
    ParameterValue,
    Preset,
    PresetDocument,
    SourceMetadata,
)
from craft_bridge.core.pipeline import preview
from craft_bridge.core.validation import validate_plan
from craft_bridge.integrations.control import ControlClient
from craft_bridge.integrations.effectcraft import apply_plan
from craft_bridge.mappings.registry import Registry

MANIFEST = {
    "api": 1, "id": "org.craftbridge.test.gain", "name": "Bridge Gain Probe",
    "category": "Bridge Validation", "version": "1.0.0",
    "params": [
        {"id": "gain", "name": "Gain", "type": "slider", "default": 1.0, "min": 0, "max": 4},
        {"id": "enabled", "name": "Enabled", "type": "checkbox", "default": True},
        {"id": "channel", "name": "Channel", "type": "popup", "default": 0, "options": ["All", "Red"]},
    ],
}


def probe_wat() -> str:
    raw = json.dumps(MANIFEST, separators=(",", ":")).encode()
    data = "".join(f"\\{b:02x}" for b in raw)
    return f'''(module
      (memory (export "memory") 2)
      (data (i32.const 16) "{data}")
      (func (export "ec_api_version") (result i32) i32.const 1)
      (func (export "ec_manifest_ptr") (result i32) i32.const 16)
      (func (export "ec_manifest_len") (result i32) i32.const {len(raw)})
      (func (export "ec_alloc") (param $n i32) (result i32)
        (local $pages i32)
        local.get $n i32.const 131071 i32.add i32.const 16 i32.shr_u
        memory.size i32.sub local.tee $pages i32.const 0 i32.gt_s
        if local.get $pages memory.grow drop end i32.const 65536)
      (func (export "ec_render") (param $px i32) (param $w i32) (param $h i32)
        (param $params i32) (param $np i32) (param $t f64) (param $scale f64) (result i32)
        (local $gain f32) (local $red i32) (local $i i32) (local $end i32)
        local.get $np i32.const 3 i32.lt_s if i32.const 1 return end
        local.get $params f64.load offset=8 f64.const 0 f64.eq if i32.const 0 return end
        local.get $params f64.load f32.demote_f64 local.set $gain
        local.get $params f64.load offset=16 f64.const 1 f64.eq local.set $red
        local.get $px local.set $i
        local.get $px local.get $w local.get $h i32.mul i32.const 16 i32.mul i32.add local.set $end
        block $done loop $pixels
          local.get $i local.get $end i32.ge_u br_if $done
          local.get $i local.get $i f32.load local.get $gain f32.mul f32.store
          local.get $red i32.eqz if
            local.get $i local.get $i f32.load offset=4 local.get $gain f32.mul f32.store offset=4
            local.get $i local.get $i f32.load offset=8 local.get $gain f32.mul f32.store offset=8
          end
          local.get $i i32.const 16 i32.add local.set $i br $pixels
        end end i32.const 0))'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--port", type=int, default=20088)
    parser.add_argument("--harness", type=Path, default=Path("artifacts/native-target/debug/craft-bridge-native-validation"))
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Use a new output directory")
    args.output.mkdir(parents=True)
    output = args.output.resolve()
    os.environ["CRAFT_BRIDGE_CONFIG"] = str(output / "config")
    module = output / "gain.wat"
    module.write_text(probe_wat())
    with ControlClient(args.port) as client:
        loaded = client.execute("effect.plugins.load", {"path": str(module)})
        assert loaded["loaded"][0]["id"] == MANIFEST["id"]
        listing = client.execute("effect.plugins.list")
        assert listing["api"] == 1 and listing["wasm"] is True
    package = {"format": "craftbridge.mappings", "version": 2, "name": "gain-probe", "plugins": [MANIFEST], "mappings": [{
        "source": "Bridge Gain Probe", "source_format": "ffx", "target": "effectcraft", "effect": MANIFEST["id"],
        "params": {"ProbeGain": {"target": "gain", "kind": "Float"}, "ProbeOn": {"target": "enabled", "kind": "Bool"}, "ProbeChannel": {"target": "channel", "kind": "Choice"}},
        "evidence": "Original synthetic WebAssembly module; official API v1; not an Adobe fixture",
        "validation": "synthetic-only", "target_commit": Registry().catalog["effectcraft"]["commit"],
    }]}
    package_path = output / "package.json"
    package_path.write_text(json.dumps(package, indent=2))
    Registry().install(package_path)
    document = PresetDocument(source=SourceMetadata(path="synthetic-probe", format="ffx", size=0, sha256="0" * 64), presets=[Preset(name="Synthetic plugin probe", effects=[Effect(
        name="Bridge Gain Probe", identifier=EffectIdentifier(match_name="Bridge Gain Probe"), order=0,
        parameters=[Parameter(id=i, name=i, value=ParameterValue(kind=k, data=v)) for i, k, v in [("ProbeGain", "number", 2.0), ("ProbeOn", "boolean", True), ("ProbeChannel", "enum", 1)]],
    )])])
    payload, report = preview(document)
    assert report.status == "PARTIAL"
    plan = validate_plan(payload)
    (output / "plan.json").write_text(json.dumps(payload, indent=2))
    with ControlClient(args.port) as client:
        client.execute("comp.new", {"name": "Bridge plugin validation", "width": 32, "height": 16})
        client.execute("layer.newSolid", {"name": "Plugin target"})
    comp = "Bridge plugin validation"
    applied = apply_plan(plan, layer="#1", comp=comp, port=args.port, confirmed=True, save_project=output / "native-validation.ecproj")
    with ControlClient(args.port) as client:
        snapshots = [client.execute("prop.get", {"layer": "#1", "comp": comp, "path": applied["bindings"]["fx0"]["path"] + "/" + p.id}) for p in plan.effects[0].properties]
        client.execute("file.open", {"path": str(output / "native-validation.ecproj")})
        reopened = [client.execute("prop.get", {"layer": "#1", "comp": comp, "path": applied["bindings"]["fx0"]["path"] + "/" + p.id}) for p in plan.effects[0].properties]
        assert snapshots == reopened
    pixels = [[0.2, 0.3, 0.4, 1.0], [0.05, 0.1, 0.15, 0.5], [1.2, 0.4, 0.6, 1.0], [0, 0, 0, 0]]
    for enabled, channel in ((True, 0), (True, 1), (False, 0)):
        case = output / f"render-{enabled}-{channel}.json"
        case.write_text(json.dumps({"params": {"gain": 2, "enabled": enabled, "channel": channel}, "pixels": pixels}))
        actual = json.loads(subprocess.check_output([str(args.harness.resolve()), "plugin-render", str(module), str(case)], timeout=30))
        expected = [[v * (2 if enabled and (i == 0 or (channel == 0 and i < 3)) else 1) for i, v in enumerate(pixel)] for pixel in pixels]
        assert all(abs(a - b) < 1e-6 for px, qx in zip(actual, expected, strict=True) for a, b in zip(px, qx, strict=True))
    summary = {"api": 1, "wasm_loaded": True, "synthetic_only": True, "native_properties": 3, "project_reopen_verified": True, "render_cases": 3, "render_samples": 12, "adobe_visual_comparison": False}
    (output / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
