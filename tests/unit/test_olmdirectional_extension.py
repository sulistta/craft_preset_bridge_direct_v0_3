"""Original controls and documented inactive resource; no private fixtures."""

import json

import pytest

from craft_bridge.core.models import ConversionWarning
from craft_bridge.core.pipeline import convert_file, inspect_file, preview
from craft_bridge.core.resources import SourceLayerBindings
from craft_bridge.core.safety import BridgeError
from craft_bridge.extensions import extension_paths
from craft_bridge.mappings.registry import Registry
from tests.helpers import ffx

PREFIX = "OLM Directional Blur-"


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv("CRAFT_BRIDGE_CONFIG", str(tmp_path / "config"))
    mapping, _ = extension_paths("olmdirectional")
    registry = Registry(packages=[mapping])
    package = json.loads(mapping.read_text())
    kinds = {"0001": 3, "0002": 10, "0003": 2, "0005": 1, "0006": 1, "0007": 2, "0010": 1, "0011": 1, "0012": 2, "0015": 2, "0016": 7, "0017": 0, "0018": 1, "0019": 3, "0020": 10}
    specs = {p["id"]: p for p in package["plugins"][0]["params"]}
    controls = []
    for id, rule in package["mappings"][0]["params"].items():
        value = specs[rule["target"]]["default"]
        if rule["kind"] == "Layer":
            value = 0
        elif rule["kind"] == "Choice":
            value += 1
        controls.append((id, value, kinds[id[-4:]]))
    source = tmp_path / "original.ffx"
    source.write_bytes(ffx([("OLM Directional Blur", controls)]))
    return source, inspect_file(source), registry


@pytest.mark.parametrize("mode", [1, 2])
def test_static_smooth_or_block_proves_inactivity_without_decoding_layer(setup, tmp_path, mode):
    source, doc, registry = setup
    next(p for p in doc.presets[0].effects[0].parameters if p.id == PREFIX + "0016").value.data = mode
    before = doc.model_dump()
    plan, report = preview(doc, registry=registry)
    assert doc.model_dump() == before
    assert report.status == "PARTIAL" and report.effects[0].parameters_converted == 15
    values = {p["id"]: p["value"] for p in plan["effects"][0]["properties"]}
    assert values["noise"] == {"layer_ref": None} and values["front"] == 140 and values["angle"] == 106
    assert doc.presets[0].effects[0].parameters[0].value.kind == "unknown"
    assert any(w.code == "SOURCE_LAYER_INACTIVE" and w.loss for w in report.effects[0].warnings)
    assert any(w.code == "UNDECODED_VALUE" and w.loss for w in report.effects[0].warnings)
    assert not any(w.code == "SOURCE_LAYER_REPLACED" for w in report.effects[0].warnings)
    output = tmp_path / "strict.json"
    assert convert_file(source, output, strict=True, registry=registry).status == "FAILED"
    assert not output.exists()


def test_active_layer_requires_explicit_binding_and_preserves_loss(setup):
    _, doc, registry = setup
    next(p for p in doc.presets[0].effects[0].parameters if p.id == PREFIX + "0016").value.data = 3
    plan, _ = preview(doc, registry=registry)
    assert not plan["effects"]
    binding = SourceLayerBindings(source_sha256=doc.source.sha256, bindings=[{"effect_index": 0, "parameter": PREFIX + "0017", "layer_ref": "noise"}])
    plan, report = preview(doc, registry=registry, source_layers=binding)
    values = {p["id"]: p["value"] for p in plan["effects"][0]["properties"]}
    assert values["noise"] == {"layer_ref": "noise"} and values["noise_type"] == 2
    assert any(w.code == "SOURCE_LAYER_REPLACED" for w in report.effects[0].warnings)


@pytest.mark.parametrize("invalid", ["expression", "animated", "missing", "duplicate", "bool", "unknown"])
def test_uncertain_selector_never_authorizes_inactive_null(setup, invalid):
    _, doc, registry = setup
    effect = doc.presets[0].effects[0]
    selector = next(p for p in effect.parameters if p.id == PREFIX + "0016")
    if invalid == "expression":
        selector.warnings.append(ConversionWarning(code="EXPRESSION", message="Original expression is never evaluated"))
    elif invalid == "animated":
        selector.metadata["animated"] = True
    elif invalid == "missing":
        effect.parameters.remove(selector)
    elif invalid == "duplicate":
        effect.parameters.append(selector.model_copy(deep=True))
    elif invalid == "bool":
        selector.value.data = True
    else:
        selector.value.kind = "unknown"
        selector.value.data = None
    plan, report = preview(doc, registry=registry)
    assert not plan["effects"] and report.effects[0].parameters_converted == 0


@pytest.mark.parametrize("invalid", ["expression", "animated"])
def test_inactive_selector_does_not_bypass_resource_animation_refusal(setup, invalid):
    _, doc, registry = setup
    resource = next(p for p in doc.presets[0].effects[0].parameters if p.id == PREFIX + "0017")
    if invalid == "expression":
        resource.warnings.append(ConversionWarning(code="EXPRESSION", message="Original expression is never evaluated"))
    else:
        resource.metadata["animated"] = True
    plan, report = preview(doc, registry=registry)
    assert not plan["effects"] and report.effects[0].parameters_converted == 0


@pytest.mark.parametrize("suffix,value", [("0005", 4001), ("0003", 101), ("0015", -1), ("0016", 4), ("0020", 0)])
def test_invalid_processing_refuses_whole_creation(setup, suffix, value):
    _, doc, registry = setup
    next(p for p in doc.presets[0].effects[0].parameters if p.id == PREFIX + suffix).value.data = value
    plan, _ = preview(doc, registry=registry)
    assert not plan["effects"]


@pytest.mark.parametrize("invalid", ["nonresource", "nonmenu", "outside", "duplicate", "notrequired"])
def test_inactivity_package_requires_proven_resource_menu(setup, tmp_path, invalid):
    _, _, _ = setup
    package = json.loads(extension_paths("olmdirectional")[0].read_text())
    mapping = package["mappings"][0]
    rule = mapping["params"][PREFIX + "0017"]
    if invalid == "nonresource":
        mapping["params"][PREFIX + "0005"]["inactive_when"] = rule["inactive_when"]
    elif invalid == "nonmenu":
        rule["inactive_when"] = {PREFIX + "0005": [1]}
    elif invalid == "outside":
        rule["inactive_when"] = {PREFIX + "0016": [4]}
    elif invalid == "duplicate":
        rule["inactive_when"] = {PREFIX + "0016": [1, 1]}
    else:
        mapping["required_on_create"].remove(PREFIX + "0016")
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(package))
    with pytest.raises(BridgeError):
        Registry(packages=[path])
