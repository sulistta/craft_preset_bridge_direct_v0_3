"""Original source descriptors, not private presets or visual equivalence."""

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
    mapping, module = extension_paths("heatwave")
    assert module.read_bytes().startswith(b"\0asm")
    registry = Registry()
    registry.install(mapping)
    package = json.loads(mapping.read_text())
    specs = {p["id"]: p for p in package["plugins"][0]["params"]}
    controls = []
    for source, rule in package["mappings"][0]["params"].items():
        spec = specs[rule["target"]]
        kind = {"slider": 10, "layer": 0, "checkbox": 4, "popup": 7, "point": 6}[spec["type"]]
        if source.endswith("0003"):
            kind = 3
        value = spec["default"] if kind != 0 else 0
        if kind == 7:
            value += 1
        controls.append((source, value, kind, 2 if kind == 6 else 1))
    source = tmp_path / "original.ffx"
    source.write_bytes(ffx([("Universe_Distort_Heatwave", controls)]))
    doc = inspect_file(source)
    bindings = SourceLayerBindings(
        source_sha256=doc.source.sha256,
        bindings=[{"effect_index": 0, "parameter": "Universe_Distort_Heatwave-0025", "layer_ref": None}],
    )
    return source, doc, registry, bindings, package


def test_complete_controls_points_and_strict(setup, tmp_path):
    source, doc, registry, bindings, package = setup
    result, report = preview(doc, registry=registry, source_size=(16, 8), source_layers=bindings)
    assert result["version"] == 4 and report.status == "PARTIAL"
    assert report.effects[0].parameters_converted == 25
    values = {p["id"]: p["value"] for p in result["effects"][0]["properties"]}
    assert values["mask"] == {"layer_ref": None}
    assert values["point_a"] == [8.0, 2.0] and values["point_b"] == [8.0, 6.0]
    assert values["mask_position"] == [8.0, 4.0] and values["direction"] == 90.0
    assert values["shape"] == values["wave_type"] == values["output"] == values["mask_channel"] == 0
    assert package["plugins"][0]["api"] == 2 and package["plugins"][0]["bridge_host_revision"] == 1
    target = tmp_path / "strict.json"
    assert (
        convert_file(
            source, target, strict=True, registry=registry, source_size=(16, 8), source_layers=bindings
        ).status
        == "FAILED"
    )
    assert not target.exists()


def test_missing_mask_binding_refuses_without_inventing_none(setup):
    _, doc, registry, _, _ = setup
    output, report = preview(doc, registry=registry, source_size=(16, 8))
    assert output["effects"] == [] and report.effects[0].parameters_converted == 0
    assert any(w.code == "UNDECODED_VALUE" for w in report.effects[0].warnings)


def test_missing_size_refuses_whole_creation(setup):
    _, doc, registry, bindings, _ = setup
    output, report = preview(doc, registry=registry, source_layers=bindings)
    assert output["effects"] == [] and report.effects[0].parameters_converted == 0


@pytest.mark.parametrize(
    "id,value",
    [
        ("0001", 4),
        ("0016", 4),
        ("0019", 5),
        ("0026", 3),
        ("0030", 6),
        ("0002", 101),
        ("0005", -1),
        ("0027", -1),
        ("0031", -101),
    ],
)
def test_menus_and_bounds_refuse_whole_creation(setup, id, value):
    _, doc, registry, bindings, _ = setup
    next(
        p for p in doc.presets[0].effects[0].parameters if p.id == "Universe_Distort_Heatwave-" + id
    ).value.data = value
    output, report = preview(doc, registry=registry, source_size=(16, 8), source_layers=bindings)
    assert output["effects"] == [] and report.effects[0].parameters_converted == 0


def test_all_saved_menu_entries_have_explicit_order(setup):
    _, doc, registry, bindings, _ = setup
    for id, count in [("0001", 3), ("0016", 3), ("0019", 4), ("0026", 2), ("0030", 5)]:
        param = next(
            p for p in doc.presets[0].effects[0].parameters if p.id == "Universe_Distort_Heatwave-" + id
        )
        target = registry.find("ffx", "effectcraft", "Universe_Distort_Heatwave").params[param.id].target
        for value in range(1, count + 1):
            param.value.data = value
            output, _ = preview(doc, registry=registry, source_size=(16, 8), source_layers=bindings)
            assert (
                next(p for p in output["effects"][0]["properties"] if p["id"] == target)["value"] == value - 1
            )


def test_selected_controls_do_not_replace_resources_or_geometry(setup):
    _, doc, registry, _, _ = setup
    effect = doc.presets[0].effects[0]
    effect.feature = "effect-properties"
    effect.metadata.update(application="existing", source_effect_index=2)
    effect.parameters = [p for p in effect.parameters if p.id.endswith(("0002", "0004"))]
    output, report = preview(doc, registry=registry)
    assert report.effects[0].parameters_converted == 2 and output["effects"][0]["application"] == "existing"
    assert {p["id"] for p in output["effects"][0]["properties"]} == {"intensity", "speed"}
