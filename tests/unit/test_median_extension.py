"""Original synthetic FFX controls, never private fixtures."""

import json

import pytest

from craft_bridge.core.pipeline import convert_file, inspect_file, preview
from craft_bridge.extensions import extension_paths
from craft_bridge.mappings.registry import Registry
from tests.helpers import ffx


@pytest.fixture
def median(tmp_path, monkeypatch):
    monkeypatch.setenv("CRAFT_BRIDGE_CONFIG", str(tmp_path / "config"))
    mapping, module = extension_paths("median")
    assert module.read_bytes().startswith(b"\0asm")
    Registry().install(mapping)
    return json.loads(mapping.read_text())


def test_ten_controls_menu_order_and_strict(median, tmp_path):
    manifest = median["plugins"][0]
    specs = {p["id"]: p for p in manifest["params"]}
    params = []
    for source, rule in median["mappings"][0]["params"].items():
        spec = specs[rule["target"]]
        kind = {"slider": 2, "checkbox": 4, "popup": 7}[spec["type"]]
        if source.endswith("0805"):
            kind = 3  # evidenced angle source, degrees conserved
        value = spec["default"] + 1 if kind == 7 else spec["default"]
        params.append((source, value, kind))
    file = tmp_path / "synthetic.ffx"
    file.write_bytes(ffx([("BCC3Median", params)]))
    out, report = preview(inspect_file(file))
    assert report.status == "PARTIAL" and report.effects[0].parameters_converted == 10
    effect = out["effects"][0]
    assert effect["effect"] == "org.craftbridge.median" and effect["plugin_fingerprint"]
    values = {p["id"]: p["value"] for p in effect["properties"]}
    assert values["mode"] == 2 and values["channel"] == 0
    assert values["level"] == 100 and values["mix"] == 0
    assert sum(w.code == "MAPPING_APPROXIMATION" and w.loss for w in report.effects[0].warnings) == 4
    output = tmp_path / "strict.json"
    assert convert_file(file, output, strict=True).status == "FAILED"
    assert not output.exists()
    mapping, module = extension_paths("median")
    assert json.loads(mapping.with_name("manifest.json").read_text()) == manifest
    assert module.stat().st_size < 200_000


@pytest.mark.parametrize("id,value,kind", [
    ("0852", 5, 7), ("0851", 10, 7), ("0801", -1, 2),
    ("0806", 513, 2), ("0805", 36001, 3), ("0802", 101, 2),
    ("0807", -1, 2), ("0520", 101, 2), ("0803", .5, 2),
])
def test_invalid_menus_limits_or_bool_refused(median, tmp_path, id, value, kind):
    file = tmp_path / "invalid.ffx"
    file.write_bytes(ffx([("BCC3Median", [("BCC3Median-"+id, value, kind)])]))
    out, report = preview(inspect_file(file))
    assert not out["effects"] and report.status == "UNSUPPORTED"


def test_opaque_mask_and_compositing_are_losses(median, tmp_path):
    file = tmp_path / "with-unsupported-controls.ffx"
    file.write_bytes(ffx([("BCC3Median", [
        ("BCC3Median-0801", 12, 2), ("BCC3Median-0853", 3, 7),
        ("BCC3Median-11010096", 0, 0),
    ])]))
    out, report = preview(inspect_file(file))
    assert len(out["effects"][0]["properties"]) == 1
    assert any(w.path == "BCC3Median-0853" and w.loss for w in report.effects[0].warnings)
    assert any(w.path == "BCC3Median-11010096" and w.loss for w in report.effects[0].warnings)


def test_scalar_angle_bezier_and_fractional_hold(median, tmp_path):
    file = tmp_path / "animated.ffx"
    file.write_bytes(ffx([("BCC3Median", [
        ("BCC3Median-0805", 0, 3, 1, [(0, 0, 2), (30720, 45, 2)], 30720, 0),
        ("BCC3Median-0804", False, 4, 1, [(0, False, 3), (30720, True, 3)], 30720, 0),
    ])]))
    out, report = preview(inspect_file(file))
    props = {p["id"]: p for p in out["effects"][0]["properties"]}
    assert props["angle"]["keyframes"][1]["value"] == 45
    assert props["angle"]["keyframes"][1]["handles"]["in_influence"] == [1/3]
    assert all(k["out_interp"] == ["Hold"] for k in props["fractional"]["keyframes"])
    assert report.effects[0].keyframes_preserved == 4
