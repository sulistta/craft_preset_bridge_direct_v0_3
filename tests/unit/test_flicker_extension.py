"""Original synthetic FFX inputs; no private fixture redistributed."""

import json

import pytest

from craft_bridge.core.pipeline import convert_file, inspect_file, preview
from craft_bridge.extensions import extension_paths
from craft_bridge.mappings.registry import Registry
from tests.helpers import ffx


@pytest.fixture
def flicker(tmp_path, monkeypatch):
    monkeypatch.setenv("CRAFT_BRIDGE_CONFIG", str(tmp_path / "config"))
    mapping, module = extension_paths("flicker")
    assert module.read_bytes().startswith(b"\0asm")
    Registry().install(mapping)
    return json.loads(mapping.read_text())


def test_fourteen_controls_raw_seed_and_strict(flicker, tmp_path):
    manifest = flicker["plugins"][0]
    rules = flicker["mappings"][0]["params"]
    specs = {p["id"]: p for p in manifest["params"]}
    params = [(source, specs[rule["target"]]["default"], 2) for source, rule in rules.items()]
    file = tmp_path / "original-synthetic.ffx"
    file.write_bytes(ffx([("S_Flicker", params)]))
    out, report = preview(inspect_file(file))
    assert report.status == "PARTIAL" and report.effects[0].parameters_converted == 14
    effect = out["effects"][0]
    assert effect["effect"] == "org.craftbridge.flicker" and effect["plugin_fingerprint"]
    values = {p["id"]: p["value"] for p in effect["properties"]}
    assert values["seed"] == .123 and values["rand_freq"] == 30
    assert sum(w.code == "MAPPING_APPROXIMATION" and w.loss for w in report.effects[0].warnings) == 4
    output = tmp_path / "strict.json"
    assert convert_file(file, output, strict=True).status == "FAILED"
    assert not output.exists()
    mapping, module = extension_paths("flicker")
    assert json.loads(mapping.with_name("manifest.json").read_text()) == manifest
    assert module.stat().st_size < 200_000
    assert (mapping.parent / "licenses/Rust-1.98.1-COPYRIGHT-library.html").is_file()


@pytest.mark.parametrize("id,value,kind", [
    ("0050", -0.1, 2), ("0050", 1001, 2), ("0051", -1, 2),
    ("0052", 1001, 2), ("0053", 10001, 2), ("0055", -1, 2),
    ("0056", 1e6 + 1, 2), ("0062", 1001, 2), ("0063", 1e9 + 1, 2),
    ("0050", True, 4),
])
def test_invalid_type_or_renderer_domain_refused(flicker, tmp_path, id, value, kind):
    file = tmp_path / "invalid.ffx"
    file.write_bytes(ffx([("S_Flicker", [("S_Flicker-" + id, value, kind)])]))
    out, report = preview(inspect_file(file))
    assert not out["effects"] and report.status == "UNSUPPORTED"


def test_bezier_coefficients_preserved_without_scaling(flicker, tmp_path):
    file = tmp_path / "animated.ffx"
    file.write_bytes(ffx([("S_Flicker", [
        ("S_Flicker-0050", .2, 2, 1, [(0, .2, 2), (30720, .8, 2)], 30720, 0),
    ])]))
    out, report = preview(inspect_file(file))
    prop = out["effects"][0]["properties"][0]
    assert prop["id"] == "amplitude" and prop["keyframes"][1]["value"] == .8
    assert len(prop["keyframes"]) == report.effects[0].keyframes_preserved == 2
    assert prop["keyframes"][1]["handles"]["in_influence"] == [1 / 3]
