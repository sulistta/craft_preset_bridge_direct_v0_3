"""Original synthetic FFX controls, never private fixtures."""

import json

import pytest

from craft_bridge.core.pipeline import convert_file, inspect_file, preview
from craft_bridge.extensions import extension_paths
from craft_bridge.mappings.registry import Registry
from tests.helpers import ffx


@pytest.fixture
def directional(tmp_path, monkeypatch):
    monkeypatch.setenv("CRAFT_BRIDGE_CONFIG", str(tmp_path / "config"))
    mapping, module = extension_paths("directional")
    assert module.read_bytes().startswith(b"\0asm")
    Registry().install(mapping)
    return json.loads(mapping.read_text())


def test_twelve_controls_exact_menu_order_and_strict(directional, tmp_path):
    manifest = directional["plugins"][0]
    specs = {p["id"]: p for p in manifest["params"]}
    params = []
    for source, rule in directional["mappings"][0]["params"].items():
        spec = specs[rule["target"]]
        kind = {"slider": 2, "checkbox": 4, "popup": 7}[spec["type"]]
        if source.endswith("0003"):
            kind = 3
        value = spec["default"] + 1 if kind == 7 else spec["default"]
        params.append((source, value, kind))
    file = tmp_path / "synthetic.ffx"
    file.write_bytes(ffx([("BCC3Directional Blur", params)]))
    out, report = preview(inspect_file(file))
    assert report.status == "PARTIAL" and report.effects[0].parameters_converted == 12
    effect = out["effects"][0]
    assert effect["effect"] == "org.craftbridge.directional" and effect["plugin_fingerprint"]
    values = {p["id"]: p["value"] for p in effect["properties"]}
    assert values["apply_mode"] == values["channels"] == 0
    assert values["apply_mix"] == 100 and values["deviation"] == 255
    assert values["avoid_clipping"] is False and values["displace"] is False
    assert sum(w.code == "MAPPING_APPROXIMATION" and w.loss for w in report.effects[0].warnings) == 4
    output = tmp_path / "strict.json"
    assert convert_file(file, output, strict=True).status == "FAILED"
    assert not output.exists()
    mapping, module = extension_paths("directional")
    assert json.loads(mapping.with_name("manifest.json").read_text()) == manifest
    assert module.stat().st_size < 200_000


@pytest.mark.parametrize("id,value,kind", [
    ("0009", 28, 7), ("0011", 10, 7), ("0002", -1, 2),
    ("0002", 8193, 2), ("0003", 36001, 3), ("0004", 101, 2),
    ("0005", -1, 2), ("0006", 256, 2), ("0015", -1, 2),
    ("0010", 101, 2), ("0013", -1, 2), ("0007", .5, 2),
])
def test_invalid_controls_refused(directional, tmp_path, id, value, kind):
    file = tmp_path / "invalid.ffx"
    file.write_bytes(ffx([("BCC3Directional Blur", [("BCC3Directional Blur-"+id, value, kind)])]))
    out, report = preview(inspect_file(file))
    assert not out["effects"] and report.status == "UNSUPPORTED"


def test_beat_mask_and_canvas_limit_are_explicit_losses(directional, tmp_path):
    file = tmp_path / "dependencies.ffx"
    file.write_bytes(ffx([("BCC3Directional Blur", [
        ("BCC3Directional Blur-0002", 72, 2), ("BCC3Directional Blur-0007", True, 4),
        ("BCC3Directional Blur-3236", True, 4), ("BCC3Directional Blur-11010125", 0, 11),
    ])]))
    out, report = preview(inspect_file(file))
    assert len(out["effects"][0]["properties"]) == 2
    assert any(w.path == "BCC3Directional Blur-3236" and w.loss for w in report.effects[0].warnings)
    assert any(w.path == "BCC3Directional Blur-11010125" and w.loss for w in report.effects[0].warnings)
    assert any("canvas" in w.message and w.loss for w in report.effects[0].warnings)


def test_angle_bezier_and_boolean_hold_are_preserved(directional, tmp_path):
    file = tmp_path / "animated.ffx"
    file.write_bytes(ffx([("BCC3Directional Blur", [
        ("BCC3Directional Blur-0003", 0, 3, 1, [(0, 0, 2), (30720, 90, 2)], 30720, 0),
        ("BCC3Directional Blur-0008", False, 4, 1, [(0, False, 3), (30720, True, 3)], 30720, 0),
    ])]))
    out, report = preview(inspect_file(file))
    props = {p["id"]: p for p in out["effects"][0]["properties"]}
    assert props["angle"]["keyframes"][1]["value"] == 90
    assert props["angle"]["keyframes"][1]["handles"]["in_influence"] == [1/3]
    assert all(k["out_interp"] == ["Hold"] for k in props["displace"]["keyframes"])
    assert report.effects[0].keyframes_preserved == 4
