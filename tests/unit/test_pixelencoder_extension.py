"""Original FFX structures; not private Adobe fixtures or visual comparison."""

import json

import pytest

from craft_bridge.core.pipeline import convert_file, inspect_file, preview
from craft_bridge.extensions import extension_paths
from craft_bridge.mappings.registry import Registry
from tests.helpers import ffx


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv("CRAFT_BRIDGE_CONFIG", str(tmp_path / "config"))
    mapping, module = extension_paths("pixelencoder")
    assert module.read_bytes().startswith(b"\0asm")
    registry = Registry(packages=[mapping])
    package = json.loads(mapping.read_text())
    specs = {p["id"]: p for p in package["plugins"][0]["params"]}
    controls = []
    for source, rule in package["mappings"][0]["params"].items():
        spec = specs[rule["target"]]
        kind = {"slider": 10, "checkbox": 4, "popup": 7, "color": 5}[spec["type"]]
        value = spec["default"]
        if kind == 7:
            value += 1
        elif kind == 5:
            value = [value[3] * 255, *[v * 255 for v in value[:3]]]
        controls.append((source, value, kind, 4, None, 30720, 7) if kind == 5 else (source, value, kind, 1))
    source = tmp_path / "original.ffx"
    source.write_bytes(ffx([("ADBE PixelEncoder - AEPlugins", controls)]))
    return source, inspect_file(source), registry


def test_raw_controls_argb_colors_and_strict_losses(setup, tmp_path):
    source, doc, registry = setup
    plan, report = preview(doc, registry=registry)
    assert report.status == "PARTIAL" and report.effects[0].parameters_converted == 16
    values = {p["id"]: p["value"] for p in plan["effects"][0]["properties"]}
    assert values["foreground"] == [1., 0., 0., 1.]
    assert values["background"] == [0., 0., 0., 1.]
    assert values["pattern"] == 1 and values["behavior"] == 0
    assert values["brightness"] == -50 and values["contrast"] == 150
    assert all(p.value.unit is None for p in doc.presets[0].effects[0].parameters if p.metadata.get("kind") == 10)
    path = tmp_path / "strict.json"
    assert convert_file(source, path, strict=True, registry=registry).status == "FAILED"
    assert not path.exists()


@pytest.mark.parametrize("id,value", [("0003", 11), ("0021", 4), ("0011", 0), ("0005", 1001), ("0004", -101), ("0020", 10001)])
def test_out_of_bounds_refuses_complete_creation(setup, id, value):
    _, doc, registry = setup
    next(p for p in doc.presets[0].effects[0].parameters if p.id.endswith(id)).value.data = value
    plan, report = preview(doc, registry=registry)
    assert plan["effects"] == [] and report.effects[0].parameters_converted == 0


def test_missing_control_refuses_creation(setup):
    _, doc, registry = setup
    doc.presets[0].effects[0].parameters.pop()
    plan, _ = preview(doc, registry=registry)
    assert plan["effects"] == []
