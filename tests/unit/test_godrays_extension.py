"""Original synthetic transport proofs; no private Adobe fixtures redistributed."""

import json

import pytest

from craft_bridge.core.models import ConversionWarning
from craft_bridge.core.pipeline import convert_file, inspect_file, preview
from craft_bridge.extensions import extension_paths
from craft_bridge.mappings.registry import Registry
from tests.helpers import ffx


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv("CRAFT_BRIDGE_CONFIG", str(tmp_path / "config"))
    mapping, _ = extension_paths("godrays")
    package = json.loads(mapping.read_text())
    specs = {p["id"]: p for p in package["plugins"][0]["params"]}
    controls = []
    for id, rule in package["mappings"][0]["params"].items():
        value = specs[rule["target"]]["default"]
        kind = {"Float": 10, "Bool": 4, "Choice": 7, "Vec2": 6}[rule["kind"]]
        if id == "PEGR-0009":
            kind = 3
        if rule["operation"] == "minus_one":
            value += 1
        elif rule["operation"] == "enum_map":
            value = next(int(k) for k, v in rule["choices"].items() if v == value)
        controls.append((id, value, kind, 2 if kind == 6 else 1, None, 23976, 15 if kind == 6 else 1))
    path = tmp_path / "original.ffx"
    path.write_bytes(ffx([("PEGR", controls)]))
    return path, inspect_file(path), Registry(packages=[mapping]), package


def test_all_twenty_five_static_controls_preserved_with_explicit_losses(setup, tmp_path):
    path, doc, registry, package = setup
    before = doc.model_dump()
    point = next(p for p in doc.presets[0].effects[0].parameters if p.id == "PEGR-0002")
    point.value.data = [-0.125, 0.25]
    before = doc.model_dump()
    plan, report = preview(doc, registry=registry)
    assert doc.model_dump() == before
    assert report.status == "PARTIAL" and report.effects[0].parameters_converted == 25
    props = {p["id"]: p["value"] for p in plan["effects"][0]["properties"]}
    assert len(props) == 25 and props["position"] == [-0.125, 0.25]
    assert point.value.unit is None
    assert next(p for p in doc.presets[0].effects[0].parameters if p.id == "PEGR-0009").value.unit == "degrees"
    assert any(w.code == "MAPPING_APPROXIMATION" and w.loss for w in report.effects[0].warnings)
    assert len(package["mappings"][0]["required_on_create"]) == 25
    assert convert_file(path, tmp_path / "strict.json", strict=True, registry=registry).status == "FAILED"
    assert not (tmp_path / "strict.json").exists()


@pytest.mark.parametrize("source,target", [(1, 0), (2, 1), (3, 2), (4, 3), (6, 4)])
def test_quality_uses_explicit_table_skipping_source_separator(setup, source, target):
    _, doc, registry, _ = setup
    next(p for p in doc.presets[0].effects[0].parameters if p.id == "PEGR-0015").value.data = source
    plan, _ = preview(doc, registry=registry)
    assert next(p["value"] for p in plan["effects"][0]["properties"] if p["id"] == "quality") == target


@pytest.mark.parametrize("id,value", [
    ("0015", 5), ("0015", 7), ("0021", 3), ("0035", 1), ("0008", 100001),
    ("0016", 1), ("0017", 101), ("0011", 21), ("0010", -11), ("0025", -1),
])
def test_invalid_processing_refuses_entire_creation(setup, id, value):
    _, doc, registry, _ = setup
    next(p for p in doc.presets[0].effects[0].parameters if p.id == "PEGR-" + id).value.data = value
    plan, report = preview(doc, registry=registry)
    assert not plan["effects"] and report.effects[0].parameters_converted == 0
    assert any(w.code in {"PARAMETER_REJECTED", "REQUIRED_SOURCE_DATA"} and w.loss for w in report.effects[0].warnings)


@pytest.mark.parametrize("failure", ["missing", "unknown", "expression"])
def test_required_source_control_is_never_guessed(setup, failure):
    _, doc, registry, _ = setup
    effect = doc.presets[0].effects[0]
    parameter = next(p for p in effect.parameters if p.id == "PEGR-0035")
    if failure == "missing":
        effect.parameters.remove(parameter)
    elif failure == "unknown":
        parameter.value.kind, parameter.value.data = "unknown", None
    else:
        parameter.warnings.append(ConversionWarning(code="EXPRESSION", message="Expression never executed"))
    plan, report = preview(doc, registry=registry)
    assert not plan["effects"] and report.effects[0].parameters_converted == 0


def test_manifest_matches_mapping_and_original_wasm_is_present(setup):
    _, _, _, package = setup
    mapping, module = extension_paths("godrays")
    assert json.loads((mapping.parent / "manifest.json").read_text()) == package["plugins"][0]
    assert module.read_bytes().startswith(b"\0asm")
