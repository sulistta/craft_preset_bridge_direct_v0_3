"""Original synthetic controls; private source data stays in opt-in tests."""

import json

import pytest

from craft_bridge.core.pipeline import convert_file, inspect_file, preview
from craft_bridge.extensions import extension_paths
from craft_bridge.mappings.registry import Registry
from tests.helpers import ffx


@pytest.fixture
def sharpen(tmp_path, monkeypatch):
    monkeypatch.setenv("CRAFT_BRIDGE_CONFIG", str(tmp_path / "config"))
    mapping, module = extension_paths("sharpen")
    assert module.read_bytes().startswith(b"\0asm")
    Registry().install(mapping)
    return json.loads(mapping.read_text())


def test_fifteen_processing_controls_menus_losses_and_strict(sharpen, tmp_path):
    manifest = sharpen["plugins"][0]
    specs = {p["id"]: p for p in manifest["params"]}
    controls = []
    for source, rule in sharpen["mappings"][0]["params"].items():
        spec = specs[rule["target"]]
        kind = 7 if spec["type"] == "popup" else 2
        controls.append((source, spec["default"] + (1 if kind == 7 else 0), kind))
    file = tmp_path / "synthetic.ffx"
    file.write_bytes(ffx([("S_Sharpen", controls)]))
    out, report = preview(inspect_file(file))
    assert report.status == "PARTIAL" and report.effects[0].parameters_converted == 15
    effect = out["effects"][0]
    assert effect["effect"] == "org.craftbridge.sharpen" and effect["plugin_fingerprint"]
    values = {p["id"]: p["value"] for p in effect["properties"]}
    assert values["quality"] == 0 and values["opacity"] == 1
    assert specs["quality"]["options"] == ["Best", "Fast"]
    assert specs["opacity"]["options"] == ["All Opaque", "Normal", "As Premult"]
    assert sum(w.code == "MAPPING_APPROXIMATION" and w.loss for w in report.effects[0].warnings) == 4
    target = tmp_path / "strict.json"
    assert convert_file(file, target, strict=True).status == "FAILED" and not target.exists()
    mapping, module = extension_paths("sharpen")
    assert json.loads(mapping.with_name("manifest.json").read_text()) == manifest
    assert module.stat().st_size < 200_000
    assert (mapping.parent / "licenses/Rust-1.98.1-COPYRIGHT-library.html").is_file()


@pytest.mark.parametrize("id,value,kind", [
    ("0001", 0, 7), ("0001", 3, 7), ("0001", 1.5, 7),
    ("0052", 4, 7), ("0050", -65, 2), ("0050", 65, 2),
    ("0105", -.1, 2), ("0106", 8193, 2), ("0107", -1, 2),
    ("0108", 65, 2), ("0051", -1, 2), ("0100", 65, 2),
    ("0104", -65, 2),
])
def test_invalid_bounds_and_menu_refused(sharpen, tmp_path, id, value, kind):
    file = tmp_path / "invalid.ffx"
    file.write_bytes(ffx([("S_Sharpen", [("S_Sharpen-" + id, value, kind)])]))
    out, report = preview(inspect_file(file))
    assert not out["effects"] and report.status == "UNSUPPORTED"


def test_matte_mocha_and_widget_are_reported(sharpen, tmp_path):
    file = tmp_path / "dependencies.ffx"
    file.write_bytes(ffx([("S_Sharpen", [
        ("S_Sharpen-0050", -1, 2), ("S_Sharpen-0002", 0, 0),
        ("S_Sharpen-0520", 0, 11), ("S_Sharpen-0200", True, 4),
    ])]))
    out, report = preview(inspect_file(file))
    assert out["effects"][0]["properties"][0]["value"] == -1
    warnings = report.effects[0].warnings
    assert all(any(w.path == "S_Sharpen-" + id and w.loss for w in warnings) for id in ("0002", "0520", "0200"))


def test_scalar_bezier_and_quality_hold(sharpen, tmp_path):
    file = tmp_path / "animated.ffx"
    file.write_bytes(ffx([("S_Sharpen", [
        ("S_Sharpen-0050", 1, 2, 1, [(0, 1, 2), (30720, 2, 2)], 30720, 0),
        ("S_Sharpen-0001", 1, 7, 1, [(0, 1, 3), (30720, 2, 3)], 30720, 0),
    ])]))
    out, report = preview(inspect_file(file))
    props = {p["id"]: p for p in out["effects"][0]["properties"]}
    assert props["amplitude"]["keyframes"][1]["handles"]["in_influence"] == [1 / 3]
    assert props["quality"]["keyframes"][1]["value"] == 1
    assert all(k["out_interp"] == ["Hold"] for k in props["quality"]["keyframes"])
    assert report.effects[0].keyframes_preserved == 4
