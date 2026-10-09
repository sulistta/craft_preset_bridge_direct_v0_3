"""Original FFX controls and explicit replacements; no private fixtures."""
import copy
import json

import pytest
from pydantic import ValidationError

from craft_bridge.cli.main import parser, run
from craft_bridge.core.models import ConversionWarning
from craft_bridge.core.pipeline import batch_convert, convert_file, inspect_file, preview
from craft_bridge.core.resources import SourceLayerBindings
from craft_bridge.core.safety import BridgeError
from craft_bridge.extensions import extension_paths
from craft_bridge.mappings.registry import Package, Registry
from tests.helpers import ffx


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv("CRAFT_BRIDGE_CONFIG", str(tmp_path / "config"))
    path, module = extension_paths("mathops")
    assert module.read_bytes().startswith(b"\0asm")
    registry = Registry()
    registry.install(path)
    package = json.loads(path.read_text())
    specs = {p["id"]: p for p in package["plugins"][0]["params"]}
    params = []
    for source, rule in package["mappings"][0]["params"].items():
        spec = specs[rule["target"]]
        kind = {"slider": 2, "layer": 0, "checkbox": 4, "popup": 7}[spec["type"]]
        value = spec["default"] if kind != 0 else 0
        if kind == 7:
            value += 1
        if source == "S_MathOps-0052":
            value = -0.04
        if source == "S_MathOps-0541":
            value = 12
        params.append((source, value, kind))
    source = tmp_path / "original.ffx"
    source.write_bytes(ffx([("S_MathOps", params)]))
    doc = inspect_file(source)
    binding = SourceLayerBindings(source_sha256=doc.source.sha256, bindings=[
        {"effect_index": 0, "parameter": "S_MathOps-0001", "layer_ref": "second"},
        {"effect_index": 0, "parameter": "S_MathOps-0003", "layer_ref": None},
    ])
    return source, doc, registry, binding, package


def test_explicit_resources_values_loss_and_strict(setup, tmp_path):
    source, doc, registry, binding, package = setup
    before = doc.model_dump()
    output, report = preview(doc, registry=registry, source_layers=binding)
    assert doc.model_dump() == before
    assert report.status == "PARTIAL" and report.effects[0].parameters_converted == 17
    assert output["version"] == 4
    values = {p["id"]: p["value"] for p in output["effects"][0]["properties"]}
    assert values["source_b"] == {"layer_ref": "second"} and values["mask"] == {"layer_ref": None}
    assert values["a_darks"] == -0.04 and values["blur_mask"] == 12
    warnings = report.effects[0].warnings
    assert sum(w.code == "SOURCE_LAYER_REPLACED" and w.loss for w in warnings) == 2
    assert sum(w.code == "UNDECODED_VALUE" and w.loss for w in warnings) == 2
    target = tmp_path / "strict.json"
    result = convert_file(source, target, strict=True, registry=registry, source_layers=binding)
    assert result.status == "FAILED" and not target.exists()
    assert json.loads(extension_paths("mathops")[0].with_name("manifest.json").read_text()) == package["plugins"][0]


def test_no_or_missing_binding_refuses_whole_creation(setup):
    _, doc, registry, binding, _ = setup
    for layers in [None, binding.model_copy(update={"bindings": binding.bindings[:1]})]:
        output, report = preview(doc, registry=registry, source_layers=layers)
        assert report.status == "UNSUPPORTED" and output["effects"] == []
        assert report.effects[0].parameters_converted == 0
        assert any(w.code == "REQUIRED_SOURCE_DATA" for w in report.effects[0].warnings)


@pytest.mark.parametrize("fault", ["hash", "effect", "preset", "parameter", "duplicate", "missing_property"])
def test_scoped_bindings_never_apply_to_another_source(setup, fault):
    _, doc, registry, binding, _ = setup
    data = binding.model_dump()
    if fault == "hash":
        data["source_sha256"] = "0" * 64
    elif fault == "effect":
        data["bindings"][0]["effect_index"] = 1
    elif fault == "preset":
        data["bindings"][0]["preset_index"] = 1
    elif fault == "parameter":
        data["bindings"][0]["parameter"] = "S_MathOps-0052"
    elif fault == "duplicate":
        data["bindings"].append(data["bindings"][0])
    else:
        doc.presets[0].effects[0].parameters = [p for p in doc.presets[0].effects[0].parameters if p.id != "S_MathOps-0001"]
    with pytest.raises((BridgeError, ValidationError)):
        preview(doc, registry=registry, source_layers=SourceLayerBindings.model_validate(data))


@pytest.mark.parametrize("fault", ["raw_uid", "missing_ref", "bool_index", "float_index"])
def test_binding_schema_rejects_coercions_and_implicit_null(setup, fault):
    data = setup[3].model_dump()
    if fault == "raw_uid":
        data["bindings"][0]["layer_ref"] = 123
    elif fault == "missing_ref":
        del data["bindings"][0]["layer_ref"]
    else:
        data["bindings"][0]["effect_index"] = True if fault == "bool_index" else 0.0
    with pytest.raises(ValidationError):
        SourceLayerBindings.model_validate(data)


@pytest.mark.parametrize("fault", ["expression", "animation", "declared_keys", "missing_animation_evidence"])
def test_static_replacement_never_overrides_animation(setup, fault):
    _, doc, registry, binding, _ = setup
    param = next(p for p in doc.presets[0].effects[0].parameters if p.id == "S_MathOps-0001")
    if fault == "expression":
        param.warnings.append(ConversionWarning(code="EXPRESSION", message="Original expression bytes"))
    elif fault == "animation":
        param.metadata["animated"] = True
    elif fault == "declared_keys":
        param.metadata["keyframes_declared"] = 2
    else:
        param.metadata.pop("animated")
    output, report = preview(doc, registry=registry, source_layers=binding)
    assert output["effects"] == [] and report.effects[0].parameters_converted == 0
    assert any(w.code == "PARAMETER_REJECTED" for w in report.effects[0].warnings)


@pytest.mark.parametrize("fault", ["operation", "kind", "required", "limits"])
def test_layer_rules_must_declare_replacement_and_loss(setup, fault):
    package = copy.deepcopy(setup[4])
    rule = package["mappings"][0]["params"]["S_MathOps-0001"]
    if fault == "operation":
        rule["operation"] = "identity"
    elif fault == "kind":
        rule["kind"] = "Float"
    elif fault == "required":
        package["mappings"][0]["required_on_create"].remove("S_MathOps-0001")
    else:
        package["mappings"][0]["limitations"] = []
    with pytest.raises(BridgeError):
        Registry(packages=[])._add(Package.model_validate(package))


def test_cli_json_binding_and_batch_refusal(setup, tmp_path, capsys):
    source, _, _, binding, _ = setup
    path = tmp_path / "bindings.json"
    path.write_text(binding.model_dump_json())
    assert run(parser().parse_args(["convert", str(source), "--source-layers", str(path), "--out", str(tmp_path / "plan.json"), "--dry-run", "--json"])) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "PARTIAL"
    with pytest.raises(BridgeError, match="específicos"):
        batch_convert(tmp_path, tmp_path / "out", source_layers=binding)


def test_selected_scalar_controls_keep_resource_properties_unselected(setup):
    _, doc, registry, _, _ = setup
    effect = doc.presets[0].effects[0]
    effect.feature = "effect-properties"
    effect.metadata.update(application="existing", source_effect_index=2)
    effect.parameters = [p for p in effect.parameters if p.id == "S_MathOps-0052"]
    output, report = preview(doc, registry=registry)
    assert report.status == "PARTIAL" and len(output["effects"]) == 1
    assert output["effects"][0]["application"] == "existing"
    assert [p["id"] for p in output["effects"][0]["properties"]] == ["a_darks"]


@pytest.mark.parametrize("id,value", [("0002", 18), ("0052", -65), ("0541", 8193)])
def test_required_controls_are_not_replaced_with_defaults(setup, id, value):
    _, doc, registry, binding, _ = setup
    param = next(p for p in doc.presets[0].effects[0].parameters if p.id == "S_MathOps-" + id)
    param.value.data = value
    output, report = preview(doc, registry=registry, source_layers=binding)
    assert output["effects"] == [] and report.effects[0].parameters_converted == 0
