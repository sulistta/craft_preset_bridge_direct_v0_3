"""Original FFX controls and explicit resource replacement; no private fixtures."""

import json

import pytest

from craft_bridge.core.pipeline import convert_file, inspect_file, preview
from craft_bridge.core.resources import SourceLayerBindings
from craft_bridge.extensions import extension_paths
from craft_bridge.mappings.registry import Registry
from tests.helpers import ffx


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv("CRAFT_BRIDGE_CONFIG", str(tmp_path / "config"))
    mapping, module = extension_paths("hotspots")
    assert module.read_bytes().startswith(b"\0asm")
    registry = Registry(packages=[mapping])
    package = json.loads(mapping.read_text())
    specs = {p["id"]: p for p in package["plugins"][0]["params"]}
    controls = []
    for source, rule in package["mappings"][0]["params"].items():
        spec = specs[rule["target"]]
        kind = {"slider": 2, "checkbox": 4, "popup": 7, "color": 5, "layer": 0}[spec["type"]]
        value = spec["default"]
        if kind == 0:
            value = 0
        elif kind == 7:
            value += 1
        elif kind == 5:
            value = [value[3] * 255, *[v * 255 for v in value[:3]]]
        controls.append((source, value, kind, 4, None, 30720, 7) if kind == 5 else (source, value, kind))
    source = tmp_path / "original.ffx"
    source.write_bytes(ffx([("S_Hotspots", controls)]))
    doc = inspect_file(source)
    bindings = SourceLayerBindings(source_sha256=doc.source.sha256, bindings=[{"effect_index": 0, "parameter": "S_Hotspots-0001", "layer_ref": None}])
    return source, doc, registry, bindings


def test_explicit_null_preserves_processing_and_lossy_resource(setup, tmp_path):
    source, doc, registry, bindings = setup
    before = doc.model_dump()
    plan, report = preview(doc, registry=registry, source_layers=bindings)
    assert doc.model_dump() == before
    assert report.status == "PARTIAL" and report.effects[0].parameters_converted == 10
    values = {p["id"]: p["value"] for p in plan["effects"][0]["properties"]}
    assert values["mask"] == {"layer_ref": None}
    assert values["blur_mask"] == 12 and values["opacity"] == 1
    assert values["add_color"] == [0., 0., 0., 1.]
    assert any(w.code == "SOURCE_LAYER_REPLACED" and w.loss for w in report.effects[0].warnings)
    assert any(w.code == "UNDECODED_VALUE" and w.loss for w in report.effects[0].warnings)
    path = tmp_path / "strict.json"
    assert convert_file(source, path, strict=True, registry=registry, source_layers=bindings).status == "FAILED"
    assert not path.exists()


def test_missing_replacement_never_becomes_implicit_null(setup):
    _, doc, registry, _ = setup
    plan, report = preview(doc, registry=registry)
    assert plan["effects"] == [] and report.effects[0].parameters_converted == 0
    assert any(w.code == "REQUIRED_SOURCE_DATA" for w in report.effects[0].warnings)


@pytest.mark.parametrize("id,value", [("0050", 8193), ("0051", -1), ("0053", 65), ("0055", 4), ("0540", 3), ("0054", -1)])
def test_invalid_processing_refuses_complete_creation(setup, id, value):
    _, doc, registry, bindings = setup
    next(p for p in doc.presets[0].effects[0].parameters if p.id.endswith(id)).value.data = value
    plan, report = preview(doc, registry=registry, source_layers=bindings)
    assert plan["effects"] == [] and report.effects[0].parameters_converted == 0
