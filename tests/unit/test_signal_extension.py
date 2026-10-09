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
    mapping, module = extension_paths("signal")
    assert module.read_bytes().startswith(b"\0asm")
    registry = Registry(packages=[mapping])
    package = json.loads(mapping.read_text())
    specs = {p["id"]: p for p in package["plugins"][0]["params"]}
    controls = []
    for source, rule in package["mappings"][0]["params"].items():
        spec = specs[rule["target"]]
        kind = {"slider": 10, "checkbox": 4, "popup": 7}[spec["type"]]
        value = spec["default"] + 1 if kind == 7 else spec["default"]
        controls.append((source, value, kind, 1))
    controls.append(("ADBE Signal-0012", False, 4, 1))
    source = tmp_path / "original.ffx"
    source.write_bytes(ffx([("ADBE Signal", controls)]))
    return source, inspect_file(source), registry, package


def test_all_controls_raw_units_and_permanent_losses(setup, tmp_path):
    source, doc, registry, package = setup
    result, report = preview(doc, registry=registry)
    assert report.status == "PARTIAL" and report.effects[0].parameters_converted == 34
    values = {p["id"]: p["value"] for p in result["effects"][0]["properties"]}
    assert values["phase"] == 2 and values["frequency"] == 0.62
    assert values["vhs"] == 0 and values["lowpass_out"] == 2
    assert "destruction" not in values
    sliders = [p for p in doc.presets[0].effects[0].parameters if p.metadata.get("kind") == 10]
    assert len(sliders) == 26 and all(p.value.unit is None for p in sliders)
    assert any(w.path == "ADBE Signal-0012" and w.loss for w in report.effects[0].warnings)
    assert package["plugins"][0]["api"] == 2
    target = tmp_path / "strict.json"
    assert convert_file(source, target, strict=True, registry=registry).status == "FAILED"
    assert not target.exists()


@pytest.mark.parametrize(
    "id,value",
    [("0001", -1), ("0002", 101), ("0003", 65), ("0008", 2), ("0011", 4), ("0022", -1), ("0034", 4)],
)
def test_invalid_bounds_refuse_whole_creation(setup, id, value):
    _, doc, registry, _ = setup
    next(p for p in doc.presets[0].effects[0].parameters if p.id == "ADBE Signal-" + id).value.data = value
    output, report = preview(doc, registry=registry)
    assert output["effects"] == [] and report.effects[0].parameters_converted == 0


def test_missing_control_refuses_creation_and_selected_update_is_allowed(setup):
    _, doc, registry, _ = setup
    effect = doc.presets[0].effects[0]
    effect.parameters = [p for p in effect.parameters if p.id.endswith("0002")]
    output, _ = preview(doc, registry=registry)
    assert output["effects"] == []
    effect.feature = "effect-properties"
    effect.metadata.update(application="existing", source_effect_index=2)
    output, report = preview(doc, registry=registry)
    assert report.effects[0].parameters_converted == 1
    assert output["effects"][0]["application"] == "existing"
    assert output["effects"][0]["properties"][0]["id"] == "strength"


def test_fractional_seed_and_all_explicit_menu_choices(setup):
    _, doc, registry, _ = setup
    next(p for p in doc.presets[0].effects[0].parameters if p.id.endswith("0001")).value.data = 1.25
    for source, target in [("0011", "vhs"), ("0034", "lowpass_out")]:
        for choice in [1, 2, 3]:
            next(p for p in doc.presets[0].effects[0].parameters if p.id.endswith(source)).value.data = choice
            output, _ = preview(doc, registry=registry)
            values = {p["id"]: p["value"] for p in output["effects"][0]["properties"]}
            assert values[target] == choice - 1 and values["seed"] == 1.25
