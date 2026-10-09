"""Regression: mapping refusals must retain source losses in user reports."""

import json

import pytest

from craft_bridge.core.models import ConversionWarning
from craft_bridge.core.pipeline import convert_file, html_report, inspect_file, preview
from craft_bridge.mappings.registry import Registry
from tests.helpers import ffx


def test_unmapped_layer_reference_keeps_its_diagnostics_and_unknown_value(tmp_path):
    source = tmp_path / "original.ffx"
    source.write_bytes(ffx([("OriginalUnknown", [("OriginalUnknown-0001", 0, 0)])]))
    doc = inspect_file(source)
    param = doc.presets[0].effects[0].parameters[0]
    before = doc.model_dump(mode="json")
    plan, report = preview(doc, registry=Registry(packages=[]))
    assert report.status == "UNSUPPORTED" and plan["effects"] == []
    assert param.value.kind == "unknown" and param.value.data is None
    result = report.effects[0]
    for code in ("UNDECODED_VALUE", "COMPLEX_PARAMETER"):
        warning = next(w for w in result.warnings if w.code == code)
        assert warning.loss and warning.path == param.id and param.name in warning.message
    assert any(w.code == "NO_MAPPING" for w in result.warnings)
    assert doc.model_dump(mode="json") == before
    result.warnings[0].message = "changed report"
    assert doc.model_dump(mode="json") == before


@pytest.mark.parametrize("refusal", ["feature", "effect_decode", "required_missing", "required_rejected"])
def test_early_refusals_keep_parameter_warnings_once(tmp_path, refusal):
    source = tmp_path / "original.ffx"
    source.write_bytes(ffx())
    doc = inspect_file(source)
    effect = doc.presets[0].effects[0]
    param = effect.parameters[0]
    param.warnings.append(ConversionWarning(code="EXPRESSION", message="Opaque expression; never executed."))
    registry = Registry(packages=[])
    key = ("ffx", "effectcraft", effect.identifier.match_name)
    if refusal == "feature":
        effect.feature = "text"
    elif refusal == "effect_decode":
        effect.warnings.append(ConversionWarning(code="EFFECT_DECODE", message="Incomplete source block."))
    else:
        registry.mappings[key] = registry.mappings[key].model_copy(update={"required_on_create": [param.id]})
        if refusal == "required_missing":
            param.id = "OriginalOther-0001"
    before = doc.model_dump(mode="json")
    plan, report = preview(doc, registry=registry)
    assert plan["effects"] == [] and report.status == "UNSUPPORTED"
    warnings = [w for w in report.effects[0].warnings if w.code == "EXPRESSION"]
    assert len(warnings) == 1 and warnings[0].path == param.id
    assert warnings[0].message.startswith(f"{param.name} ({param.id}): ")
    assert doc.model_dump(mode="json") == before


def test_report_preserves_explicit_warning_path_and_severity(tmp_path):
    source = tmp_path / "original.ffx"
    source.write_bytes(ffx())
    doc = inspect_file(source)
    param = doc.presets[0].effects[0].parameters[0]
    param.warnings.append(ConversionWarning(code="ORIGINAL_NOTE", message="A source note.", path="source/child", loss=False))
    _, report = preview(doc, registry=Registry(packages=[]))
    assert report.status == "SUCCESS"
    warnings = [w for w in report.effects[0].warnings if w.code == "ORIGINAL_NOTE"]
    assert len(warnings) == 1 and warnings[0].path == "source/child" and not warnings[0].loss


def test_published_reports_keep_unmapped_dependencies_and_strict_never_publishes(tmp_path):
    source = tmp_path / "original.ffx"
    source.write_bytes(ffx([
        ("OriginalUnknown", [("OriginalUnknown-0001", 0, 0)]),
        ("ADBE Sharpen", [("ADBE Sharpen-0001", 15, 1)]),
    ]))
    original = source.read_bytes()
    output = tmp_path / "strict.json"
    report = convert_file(source, output, strict=True, registry=Registry(packages=[]))
    assert report.status == "FAILED" and report.output is None and not output.exists()
    persisted = json.loads(output.with_suffix(".json.report.json").read_text())
    warnings = persisted["effects"][0]["warnings"]
    assert {w["code"] for w in warnings} >= {"NO_MAPPING", "UNDECODED_VALUE", "COMPLEX_PARAMETER"}
    assert all(w["path"] == "OriginalUnknown-0001" for w in warnings if w["code"] != "NO_MAPPING")
    assert "OriginalUnknown-0001" in output.with_suffix(".json.report.html").read_text()
    assert source.read_bytes() == original


def test_parameter_context_is_escaped_in_html(tmp_path):
    source = tmp_path / "original.ffx"
    source.write_bytes(ffx([("OriginalUnknown", [("OriginalUnknown-0001", 0, 0)])]))
    doc = inspect_file(source)
    doc.presets[0].effects[0].parameters[0].name = '<script>alert("source")</script>'
    _, report = preview(doc, registry=Registry(packages=[]))
    rendered = html_report(report)
    assert "<script>" not in rendered and "&lt;script&gt;" in rendered
