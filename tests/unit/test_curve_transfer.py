"""Static curve transfer preserves the LUT and never claims source interpolation."""

import struct

import pytest

from craft_bridge.core.models import Keyframe, Parameter, ParameterValue
from craft_bridge.core.pipeline import inspect_file, preview
from craft_bridge.core.safety import BridgeError
from craft_bridge.core.validation import validate_filmcraft, validate_plan
from craft_bridge.exporters.common import mapped_parameter, transform
from craft_bridge.exporters.effectcraft.exporter import preview_commands
from craft_bridge.mappings.registry import Mapping, Package, Registry, Rule
from craft_bridge.parsers.ffx.arbitrary import CURVES, curve_lut_text
from tests.unit.test_arbitrary import arbitrary_ffx


def curve_blob():
    luts = [
        list(range(256)), [255 - x for x in range(256)], [0] * 128 + [255] * 128,
        [min(255, x * 2) for x in range(256)], [127] * 256,
    ]
    # Deliberately keep identity control points: values must come from the LUT.
    record = struct.pack(">32H2I", *([0, 0, 255, 255] + [0] * 28), 2, 1)
    blob = struct.pack(">2H", 1, 1) + bytes(v for lut in luts for v in lut) + record * 5
    return blob, luts


def test_every_channel_uses_its_own_lut_even_when_points_disagree(tmp_path):
    blob, luts = curve_blob()
    file = tmp_path / "curves.ffx"
    file.write_bytes(arbitrary_ffx(CURVES, blob))
    doc = inspect_file(file)
    payload, report = preview(doc)
    plan = validate_plan(payload)
    assert report.status == "PARTIAL" and report.effects[0].parameters_converted == 5
    assert doc.diagnostics["opaque_count"] == 0
    assert plan.effects[0].effect == "ec.color.curves"
    assert [p.id for p in plan.effects[0].properties] == ["rgb", "red", "green", "blue", "alpha"]
    for prop, lut in zip(plan.effects[0].properties, luts, strict=True):
        assert prop.kind == "Text" and not prop.keyframes
        pairs = [tuple(map(float, token.split(","))) for token in prop.value.split()]
        assert len(pairs) == 256
        assert [x for x, _ in pairs] == [x / 255 for x in range(256)]
        assert [y for _, y in pairs] == [v / 255 for v in lut]
    assert any(w.code == "CURVES_INTERPOLATION" and w.loss for w in report.effects[0].warnings)
    assert all(p.metadata.get("derived_from") == CURVES for p in doc.presets[0].effects[0].parameters[1:])
    assert any(isinstance(c.get("params", {}).get("value"), str) for c in plan.commands)


@pytest.mark.parametrize("animated,copies", [(True, 1), (False, 2), (False, 0)])
def test_curve_animation_or_multiple_blobs_are_never_flattened(tmp_path, animated, copies):
    blob, _ = curve_blob()
    file = tmp_path / "curves.ffx"
    file.write_bytes(arbitrary_ffx(CURVES, blob, animated=animated, copies=copies))
    doc = inspect_file(file)
    payload, report = preview(doc)
    assert report.status == "UNSUPPORTED" and not payload["effects"]
    assert not any(p.metadata.get("derived_from") == CURVES for p in doc.presets[0].effects[0].parameters)


@pytest.mark.parametrize("text", [
    "bad", "0,0", "0,0 0,1 1,1", "0,0 1,nan", "0,0 1,2", "0,0 1,1;bad",
    "0_0,0 1,1", "٠,٠ ١,١", "0,0\x1c1,1", "0,0 0.0000001,0.5 1,1",
])
def test_plan_cannot_exploit_native_silent_curve_token_skipping(tmp_path, text):
    blob, _ = curve_blob()
    file = tmp_path / "curves.ffx"
    file.write_bytes(arbitrary_ffx(CURVES, blob))
    payload, _ = preview(inspect_file(file))
    plan = validate_plan(payload)
    plan.effects[0].properties[0].value = text
    plan.commands = preview_commands(plan)
    with pytest.raises(BridgeError, match="Curva textual"):
        validate_plan(plan.model_dump(mode="json"))


@pytest.mark.parametrize("value", [1, True, [0.0], "\0", "é" * 32769])
def test_text_requires_bounded_utf8_without_nul(value):
    with pytest.raises(BridgeError, match="Texto estático"):
        transform(value, Rule(target="rgb", kind="Text"), None)


def test_structured_text_keyframes_are_refused_before_conversion():
    param = Parameter(
        id="text", name="text", value=ParameterValue(kind="text", data="0,0 1,1"),
        keyframes=[Keyframe(ticks=0, time_base=30, value="0,0 1,1", in_interp=["Hold"], out_interp=["Hold"])],
    )
    with pytest.raises(BridgeError, match="Animação de texto"):
        mapped_parameter(param, Rule(target="rgb", kind="Text"), {"kind": "Text"}, None)


def test_imported_plan_cannot_bypass_static_only_text(tmp_path):
    blob, _ = curve_blob()
    file = tmp_path / "curves.ffx"
    file.write_bytes(arbitrary_ffx(CURVES, blob))
    payload, _ = preview(inspect_file(file))
    plan = validate_plan(payload)
    prop = plan.effects[0].properties[0]
    prop.keyframes = [Keyframe(ticks=0, time_base=30, value=prop.value, in_interp=["Hold"], out_interp=["Hold"])]
    plan.commands = preview_commands(plan)
    with pytest.raises(BridgeError, match="Animação de texto"):
        validate_plan(plan.model_dump(mode="json"))


def test_filmcraft_static_text_has_native_serde_wrapper(premiere_file):
    # Synthetic IR + explicit test mapping, never claimed as an Adobe fixture.
    registry = Registry()
    target, prop = "simple_text", "text"
    registry._add(Package(name="text-test", mappings=[Mapping(
        source="Synthetic static text", source_format="prfpset", target="filmcraft", effect=target,
        params={"1": Rule(target=prop, kind="Text")}, evidence="synthetic IR/native Text catalog",
        validation="test-only", target_commit=registry.catalog["filmcraft"]["commit"],
    )]))
    document = inspect_file(premiere_file)
    document.presets[0].effects[0].identifier.match_name = "Synthetic static text"
    document.presets[0].effects[0].parameters[0].value = ParameterValue(kind="text", data="Texto estático")
    payload, report = preview(document, registry=registry)
    assert report.status == "SUCCESS"
    assert payload["presets"][0]["effects"][0]["params"][prop]["value"] == {"Text": "Texto estático"}
    validate_filmcraft(payload, registry)


def test_hidden_native_strings_are_typed_without_guessing_numeric_hidden_fields():
    catalog = Registry().catalog["effectcraft"]["effects"]
    assert catalog["ec.color.curves"]["rgb"]["kind"] == "Text"
    assert catalog["ec.color.curves"]["channel"]["kind"] == "Opaque"
    assert catalog["ec.distort.meshwarp"]["mesh"]["kind"] == "Text"


@pytest.mark.parametrize("lut", [[], [1] * 255, [256] * 256, [False] * 256, [1.0] * 256])
def test_curve_encoding_rejects_invalid_lut(lut):
    with pytest.raises(BridgeError, match="LUT"):
        curve_lut_text({"lut": lut})
