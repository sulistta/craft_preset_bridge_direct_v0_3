"""Source descriptor/mapping checks, independent of private fixtures and images."""

import json

import pytest

from craft_bridge.core.pipeline import convert_file, inspect_file, preview
from craft_bridge.extensions import extension_paths
from craft_bridge.mappings.registry import Registry
from tests.helpers import ffx


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv("CRAFT_BRIDGE_CONFIG", str(tmp_path / "config"))
    mapping, module = extension_paths("geometric")
    assert module.read_bytes().startswith(b"\0asm")
    registry = Registry(packages=[mapping])
    package = json.loads(mapping.read_text())
    specs = {p["id"]: p for p in package["plugins"][0]["params"]}
    controls = []
    for source, rule in package["mappings"][0]["params"].items():
        spec = specs[rule["target"]]
        kind = 10 if rule["target"] == "skip" else {"slider": 2, "checkbox": 4, "popup": 7}[spec["type"]]
        value = spec["default"] + 1 if kind == 7 else spec["default"]
        controls.append((source, value, kind, 1))
    controls.append(("SatoriGeometricFilters-0001", 1, 7, 1))
    source = tmp_path / "original.ffx"
    source.write_bytes(ffx([("SatoriGeometricFilters", controls)]))
    return source, inspect_file(source), registry, package


def test_all_raw_controls_and_permanent_losses(setup, tmp_path):
    source, doc, registry, package = setup
    result, report = preview(doc, registry=registry)
    assert report.status == "PARTIAL" and report.effects[0].parameters_converted == 21
    values = {p["id"]: p["value"] for p in result["effects"][0]["properties"]}
    assert values["shape"] == 2 and values["strategy"] == 1 and values["skip"] == 0
    assert values["angle"] == 228 and values["seed"] == 777
    assert any(w.path == "SatoriGeometricFilters-0001" and w.loss for w in report.effects[0].warnings)
    assert package["plugins"][0]["api"] == 4
    target = tmp_path / "strict.json"
    assert convert_file(source, target, strict=True, registry=registry).status == "FAILED"
    assert not target.exists()


@pytest.mark.parametrize("id,value", [("0027", 0.5), ("0005", 10001), ("0006", 17), ("0004", 7), ("0018", 6), ("0022", 4)])
def test_invalid_bounds_or_fractional_skip_refuses(setup,id,value):
    _,doc,registry,_=setup
    next(p for p in doc.presets[0].effects[0].parameters if p.id.endswith(id)).value.data=value
    if id == "0027":
        from craft_bridge.core.safety import BridgeError
        with pytest.raises(BridgeError, match="inteiro"):
            preview(doc,registry=registry)
        return
    result,report=preview(doc,registry=registry)
    # Plan validation can reject a temporal scalar after mapping, too.
    if result["effects"]:
        from craft_bridge.core.safety import BridgeError
        from craft_bridge.core.validation import validate_plan
        with pytest.raises(BridgeError):
            validate_plan(result,registry)
    else:
        assert report.effects[0].parameters_converted == 0


def test_missing_control_refuses_creation(setup):
    _,doc,registry,_=setup
    doc.presets[0].effects[0].parameters.pop(0)
    result,_=preview(doc,registry=registry)
    assert result["effects"] == []
