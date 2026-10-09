"""Controles e XML/RIFX originais sintéticos; nenhum fixture privado distribuído."""

import json

import pytest

from craft_bridge.core.pipeline import convert_file, inspect_file, preview
from craft_bridge.extensions import extension_paths
from craft_bridge.mappings.registry import Registry
from tests.helpers import ffx


@pytest.fixture
def modulation(tmp_path, monkeypatch):
    monkeypatch.setenv("CRAFT_BRIDGE_CONFIG", str(tmp_path / "config"))
    mapping, module = extension_paths("modulation")
    assert module.read_bytes().startswith(b"\0asm")
    Registry().install(mapping)
    return json.loads(mapping.read_text())


def test_twelve_controls_strict_and_contract(modulation, tmp_path):
    manifest = modulation["plugins"][0]
    specs = {p["id"]: p for p in manifest["params"]}
    params = []
    for source, rule in modulation["mappings"][0]["params"].items():
        spec = specs[rule["target"]]
        kind = {"slider": 10, "checkbox": 4, "popup": 7}[spec["type"]]
        value = spec["default"] + 1 if kind == 7 else spec["default"]
        params.append((source, value, kind))
    source = tmp_path / "original-synthetic.ffx"
    source.write_bytes(ffx([("ADBE Checkout", params)]))
    out, report = preview(inspect_file(source))
    assert report.status == "PARTIAL" and report.effects[0].parameters_converted == 12
    effect = out["effects"][0]
    assert effect["plugin_fingerprint"] and effect["effect"] == "org.craftbridge.modulation"
    values = {p["id"]: p["value"] for p in effect["properties"]}
    assert values["direction"] == values["orientation"] == 0
    assert values["opacity"] == 255  # raw coefficient, no inferred unit conversion
    assert sum(w.code == "MAPPING_APPROXIMATION" for w in report.effects[0].warnings) == 4
    output = tmp_path / "strict.json"
    result = convert_file(source, output, strict=True)
    assert result.status == "FAILED" and not output.exists()
    mapping, module = extension_paths("modulation")
    assert json.loads(mapping.with_name("manifest.json").read_text()) == manifest
    assert module.stat().st_size < 200_000
    assert (mapping.parent / "licenses/Rust-1.98.1-COPYRIGHT-library.html").is_file()


@pytest.mark.parametrize("source,value,kind", [
    ("0001", -0.1, 10), ("0001", 4.1, 10), ("0002", 4.1, 10),
    ("0003", 4097, 10), ("0009", 256, 10), ("0007", 3, 7),
    ("0011", 0, 7), ("0004", 0.5, 10),
])
def test_unknown_menu_range_or_boolean_refused(modulation, tmp_path, source, value, kind):
    file = tmp_path / "invalid.ffx"
    file.write_bytes(ffx([("ADBE Checkout", [("ADBE Checkout-" + source, value, kind)])]))
    out, report = preview(inspect_file(file))
    assert not out["effects"] and report.status == "UNSUPPORTED"


def test_scalar_bezier_preserves_speed_influence_and_keys(modulation, tmp_path):
    file = tmp_path / "animated.ffx"
    file.write_bytes(ffx([("ADBE Checkout", [
        ("ADBE Checkout-0001", .8, 10, 1, [(0, .8, 2), (30720, 1.2, 2)], 30720, 0),
    ])]))
    out, report = preview(inspect_file(file))
    prop = out["effects"][0]["properties"][0]
    assert prop["id"] == "omega" and len(prop["keyframes"]) == 2
    assert prop["keyframes"][1]["handles"]["in_influence"] == [1 / 3]
    assert report.effects[0].keyframes_preserved == 2
