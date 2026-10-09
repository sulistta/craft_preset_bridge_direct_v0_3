"""Original synthetic Colorize controls, not private Adobe fixtures."""

import json

import pytest

from craft_bridge.core.pipeline import convert_file, inspect_file, preview
from craft_bridge.extensions import extension_paths
from craft_bridge.mappings.registry import Registry
from tests.helpers import ffx


@pytest.fixture
def colorize(tmp_path, monkeypatch):
    monkeypatch.setenv("CRAFT_BRIDGE_CONFIG", str(tmp_path / "config"))
    mapping, module = extension_paths("colorize")
    assert module.read_bytes().startswith(b"\0asm")
    Registry().install(mapping)
    return json.loads(mapping.read_text())


def controls(package, changes=None, missing=None):
    changes = changes or {}
    specs = {p["id"]: p for p in package["plugins"][0]["params"]}
    output = []
    for source, rule in package["mappings"][0]["params"].items():
        if source == missing:
            continue
        spec = specs[rule["target"]]
        kind = {"slider": 2, "checkbox": 4, "popup": 7, "color": 5}[spec["type"]]
        value = spec["default"]
        if kind == 7:
            value += 1
        elif kind == 5:
            value = [value[3] * 255, *[c * 255 for c in value[:3]]]
        value = changes.get(source, value)
        output.append((source, value, kind, 4 if kind == 5 else 1))
    return output


def test_twenty_three_controls_required_data_menus_and_loss_report(colorize, tmp_path):
    source = tmp_path / "original.ffx"
    source.write_bytes(ffx([("BCC3Colorize", controls(colorize, {
        "BCC3Colorize-6488072": 5,
        "BCC3Colorize-6488066": 3,
        "BCC3Colorize-6488067": [128, 64, 32, 16],
        "BCC3Colorize-6488075": 450,
        "BCC3Colorize-0116": 25,
    }))]))
    output, report = preview(inspect_file(source))
    assert report.status == "PARTIAL" and report.effects[0].parameters_converted == 23
    effect = output["effects"][0]
    assert effect["effect"] == "org.craftbridge.colorize" and effect["plugin_fingerprint"]
    values = {p["id"]: p["value"] for p in effect["properties"]}
    assert values["input"] == 4 and values["color_space"] == 2 and values["loop_mode"] == 0
    assert values["color1"] == [64 / 255, 32 / 255, 16 / 255, 128 / 255]
    assert values["hue"] == 450 and values["mix"] == 25
    assert sum(w.code == "MAPPING_APPROXIMATION" and w.loss for w in report.effects[0].warnings) == 5
    target = tmp_path / "strict.json"
    assert convert_file(source, target, strict=True).status == "FAILED" and not target.exists()
    mapping, module = extension_paths("colorize")
    assert json.loads(mapping.with_name("manifest.json").read_text()) == colorize["plugins"][0]
    assert module.stat().st_size < 200_000
    assert (mapping.parent / "licenses/Rust-1.98.1-COPYRIGHT-library.html").is_file()


@pytest.mark.parametrize("id,value", [
    ("6488072", 9), ("6488072", 0), ("6488072", 1.5),
    ("6488066", 4), ("6488086", 4), ("6488079", -1), ("6488079", 1001),
    ("6488069", -1001), ("6488070", 1001), ("6488071", 101),
    ("6488080", 1e6 + 1), ("6488073", -101), ("6488075", 1e9 + 1),
    ("6488076", -101), ("6488077", 101), ("0116", 101),
])
def test_pixelchooser_unknown_menus_and_out_of_bounds_never_create_default_effect(colorize, tmp_path, id, value):
    source = tmp_path / "invalid.ffx"
    source.write_bytes(ffx([("BCC3Colorize", controls(colorize, {"BCC3Colorize-" + id: value}))]))
    output, report = preview(inspect_file(source))
    assert report.status == "UNSUPPORTED" and output["effects"] == []
    assert report.effects[0].parameters_converted == 0
    assert any(w.code == "PARAMETER_REJECTED" and w.path == "BCC3Colorize-" + id for w in report.effects[0].warnings)


def test_missing_mandatory_color_refuses_creation(colorize, tmp_path):
    source = tmp_path / "missing.ffx"
    source.write_bytes(ffx([("BCC3Colorize", controls(colorize, missing="BCC3Colorize-6488067"))]))
    output, report = preview(inspect_file(source))
    assert report.status == "UNSUPPORTED" and output["effects"] == []
    assert any(w.code == "REQUIRED_SOURCE_DATA" for w in report.effects[0].warnings)


def test_mocha_tracking_and_preview_controls_remain_visible_losses(colorize, tmp_path):
    source = tmp_path / "dependencies.ffx"
    params = controls(colorize) + [
        ("BCC3Colorize-10158087", 0, 0), ("BCC3Colorize-11010125", 0, 11),
        ("BCC3Colorize-6488065", 0, 9), ("BCC3Colorize-4194305", 0, 0),
    ]
    source.write_bytes(ffx([("BCC3Colorize", params)]))
    output, report = preview(inspect_file(source))
    assert len(output["effects"][0]["properties"]) == 23 and report.status == "PARTIAL"
    for id in ("10158087", "11010125", "6488065", "4194305"):
        assert any(w.path == "BCC3Colorize-" + id and w.loss for w in report.effects[0].warnings)


def test_scalar_bezier_color_components_and_discrete_hold_preserved(colorize, tmp_path):
    params = [p for p in controls(colorize) if p[0] not in (
        "BCC3Colorize-6488075", "BCC3Colorize-6488067", "BCC3Colorize-6488066")]
    params.extend([
        ("BCC3Colorize-6488075", 0, 3, 1, [(0, 0, 2), (30720, 90, 2)], 30720, 0),
        ("BCC3Colorize-6488067", [255, 0, 0, 0], 5, 4,
         [(0, [255, 0, 0, 0], 2), (30720, [128, 64, 32, 16], 2)], 30720, 0),
        ("BCC3Colorize-6488066", 1, 7, 1, [(0, 1, 3), (30720, 2, 3)], 30720, 0),
    ])
    source = tmp_path / "animated.ffx"
    source.write_bytes(ffx([("BCC3Colorize", params)]))
    output, report = preview(inspect_file(source))
    properties = {p["id"]: p for p in output["effects"][0]["properties"]}
    assert properties["hue"]["keyframes"][1]["value"] == 90
    assert properties["color1"]["keyframes"][1]["value"] == [64 / 255, 32 / 255, 16 / 255, 128 / 255]
    assert properties["color1"]["keyframes"][0]["handles"]["in_influence"] == [1 / 3] * 4
    assert properties["color_space"]["keyframes"][1]["value"] == 1
    assert report.effects[0].keyframes_preserved == 6
