"""Original controls and selected groups, not private Adobe fixtures."""

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
    mapping, module = extension_paths("dissolveshake")
    assert module.read_bytes().startswith(b"\0asm")
    registry = Registry()
    registry.install(mapping)
    package = json.loads(mapping.read_text())
    specs = {p["id"]: p for p in package["plugins"][0]["params"]}
    controls = []
    for source, rule in package["mappings"][0]["params"].items():
        spec = specs[rule["target"]]
        kind = {"slider": 2, "layer": 0, "checkbox": 4, "popup": 7}[spec["type"]]
        value = spec["default"] if kind != 0 else 0
        if kind == 7:
            value += 1
        if source == "S_DissolveShake-0058":
            value = 0.103
        controls.append((source, value, kind))
    source = tmp_path / "original.ffx"
    source.write_bytes(ffx([("S_DissolveShake", controls)]))
    doc = inspect_file(source)
    bindings = SourceLayerBindings(
        source_sha256=doc.source.sha256,
        bindings=[{"effect_index": 0, "parameter": "S_DissolveShake-0001", "layer_ref": "background"}],
    )
    return source, doc, registry, bindings, package


def test_all_controls_seed_reference_and_strict(setup, tmp_path):
    source, doc, registry, bindings, package = setup
    output, report = preview(doc, registry=registry, source_layers=bindings)
    assert output["version"] == 4 and report.status == "PARTIAL"
    assert report.effects[0].parameters_converted == 41
    values = {p["id"]: p["value"] for p in output["effects"][0]["properties"]}
    assert values["background"] == {"layer_ref": "background"} and values["seed"] == 0.103
    assert values["auto_trans"] == values["direction"] == 0 and values["wrap_x"] == values["wrap_y"] == 2
    assert sum(w.code == "SOURCE_LAYER_REPLACED" and w.loss for w in report.effects[0].warnings) == 1
    target = tmp_path / "strict.json"
    assert (
        convert_file(source, target, strict=True, registry=registry, source_layers=bindings).status
        == "FAILED"
    )
    assert not target.exists()
    assert package["plugins"][0]["api"] == 3 and package["plugins"][0]["bridge_host_revision"] == 2


def test_missing_background_never_infers_default_null(setup):
    _, doc, registry, _, _ = setup
    output, report = preview(doc, registry=registry)
    assert output["effects"] == [] and report.effects[0].parameters_converted == 0
    assert any(w.code == "UNDECODED_VALUE" for w in report.effects[0].warnings)


@pytest.mark.parametrize(
    "id,value",
    [
        ("0050", 3),
        ("0051", 3),
        ("0052", 101),
        ("0052", -1),
        ("0053", 0.5),
        ("0057", 101),
        ("0058", -1),
        ("0059", 0),
        ("0060", 4),
        ("0081", 4),
    ],
)
def test_unknown_menus_and_bounds_refuse_whole_creation(setup, id, value):
    _, doc, registry, bindings, _ = setup
    param = next(p for p in doc.presets[0].effects[0].parameters if p.id == "S_DissolveShake-" + id)
    param.value.data = value
    output, report = preview(doc, registry=registry, source_layers=bindings)
    assert output["effects"] == [] and report.effects[0].parameters_converted == 0


def test_synthetic_auto_trans_yes_is_preserved_without_invented_times(setup):
    _, doc, registry, bindings, _ = setup
    next(p for p in doc.presets[0].effects[0].parameters if p.id == "S_DissolveShake-0051").value.data = 2
    output, report = preview(doc, registry=registry, source_layers=bindings)
    props = {p["id"]: p["value"] for p in output["effects"][0]["properties"]}
    assert props["auto_trans"] == 1 and not any("time" in id or "duration" in id for id in props)
    assert report.status == "PARTIAL"


def test_selected_controls_keep_background_and_unselected_state(setup):
    _, doc, registry, _, _ = setup
    effect = doc.presets[0].effects[0]
    effect.feature = "effect-properties"
    effect.metadata.update(application="existing", source_effect_index=2)
    effect.parameters = [
        p for p in effect.parameters if p.id in ("S_DissolveShake-0052", "S_DissolveShake-0058")
    ]
    output, report = preview(doc, registry=registry)
    assert report.effects[0].parameters_converted == 2 and output["effects"][0]["application"] == "existing"
    assert {p["id"] for p in output["effects"][0]["properties"]} == {"dissolve", "seed"}
