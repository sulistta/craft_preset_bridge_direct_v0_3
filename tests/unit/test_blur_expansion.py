"""Synthetic regression cases for real-source menu and unit differences."""

import json
from pathlib import Path

import pytest

from craft_bridge.core.models import BezierHandles, Keyframe, Parameter, ParameterValue
from craft_bridge.core.pipeline import convert_file, inspect_file, preview
from craft_bridge.core.safety import BridgeError
from craft_bridge.core.validation import validate_filmcraft, validate_plan
from craft_bridge.exporters.common import mapped_parameter
from craft_bridge.mappings.registry import Registry, Rule
from tests.helpers import ffx


def write_effect(tmp_path, source, parameters):
    file = tmp_path / "blur.ffx"
    file.write_bytes(ffx([(source, [(source + "-" + str(p[0]).zfill(4), *p[1:]) for p in parameters])]))
    return file


@pytest.mark.parametrize(
    "source,target,parameters,expected",
    [
        (
            "ADBE Radial Blur",
            "ec.blur.radial",
            [(1, 63.0, 2), (2, [0.25, 0.75], 6, 2), (3, 2, 7), (4, 2, 7)],
            {"amount": 63.0, "center": [480.0, 810.0], "type": 1, "antialiasing": 1},
        ),
        (
            "CC Radial Blur",
            "ec.blur.ccradial",
            [(1, 7, 7), (2, -25.0, 2), (3, 75.0, 2), (4, [0.75, 0.25], 6, 2)],
            {"type": 4, "amount": -25.0, "quality": 75.0, "center": [1440.0, 270.0]},
        ),
        (
            "ADBE Camera Lens Blur",
            "ec.blur.cameralens",
            [
                (1, 33.0, 10), (3, 8, 7), (4, 22.0, 10), (5, 1.5, 10), (6, 45.0, 3),
                (7, 100.0, 10), (11, 5, 7), (12, 2, 7), (13, 0.0, 10), (14, 1, 4),
                (17, 25.0, 10), (18, 0.8, 10), (19, 30.0, 10), (21, 1, 4), (22, 0, 4),
            ],
            {
                "blurRadius": 33.0, "irisProperties/irisShape": 7,
                "irisProperties/irisRoundness": 22.0, "irisProperties/irisAspectRatio": 1.5,
                "irisProperties/irisRotation": 45.0, "irisProperties/diffractionFringe": 100.0,
                "blurMap/channel": 1, "blurMap/placement": 1, "blurMap/blurFocalDistance": 0.0,
                "blurMap/invertBlurMap": True, "highlight/specularBrightness": 25.0,
                "highlight/specularThreshold": 204.0, "highlight/highlightSaturation": 30.0,
                "repeatEdge": True, "useLinear": False,
            },
        ),
        (
            "CC Scale Wipe",
            "ec.transition.ccscalewipe",
            [(1, 5.7, 2), (2, [0.1, 0.9], 6, 2), (3, 90.0, 3)],
            {"stretch": 5.7, "center": [192.0, 972.0], "direction": 90.0},
        ),
    ],
)
def test_blur_and_scale_wipe_non_neutral_values(tmp_path, source, target, parameters, expected):
    payload, report = preview(inspect_file(write_effect(tmp_path, source, parameters)), source_size=(1920, 1080))
    plan = validate_plan(payload)
    assert report.status == "SUCCESS"
    assert plan.effects[0].effect == target
    assert {p.id: p.value for p in plan.effects[0].properties} == expected


@pytest.mark.parametrize(
    "source,parameter,value",
    [
        ("CC Radial Blur", 1, 4),  # Menu separator.
        ("CC Radial Blur", 1, 6),  # Scratch, absent from the destination.
        ("ADBE Radial Blur", 4, 1),  # Low, ignored by the native renderer.
        ("ADBE Camera Lens Blur", 3, 9),  # Source menu has no Circle entry.
        ("ADBE Camera Lens Blur", 11, 2),  # Red is not native combined Color.
        ("ADBE Camera Lens Blur", 11, 3),
        ("ADBE Camera Lens Blur", 11, 4),
    ],
)
def test_unrepresentable_choices_are_reported_and_strict_suppresses_output(tmp_path, source, parameter, value):
    file = write_effect(tmp_path, source, [(2 if source == "CC Radial Blur" else 1, 4.0, 2), (parameter, value, 7)])
    payload, report = preview(inspect_file(file))
    assert report.status == "PARTIAL"
    assert len(payload["effects"][0]["properties"]) == 1
    assert any(w.code == "PARAMETER_REJECTED" for w in report.effects[0].warnings)
    out = tmp_path / "strict.json"
    assert convert_file(file, out, strict=True).status == "FAILED"
    assert not out.exists()


def test_radial_amount_outside_native_range_is_not_clamped(tmp_path):
    file = write_effect(tmp_path, "ADBE Radial Blur", [(1, 231.0, 2), (3, 2, 7)])
    payload, report = preview(inspect_file(file))
    assert report.status == "PARTIAL"
    assert {p["id"] for p in payload["effects"][0]["properties"]} == {"type"}
    assert any("231.0" in w.message and "intervalo" in w.message for w in report.effects[0].warnings)


def test_lens_layer_reference_and_nonzero_focal_distance_remain_explicit_losses(tmp_path):
    file = write_effect(tmp_path, "ADBE Camera Lens Blur", [(1, 7.0, 10), (10, 0.0, 0), (13, 0.5, 10)])
    payload, report = preview(inspect_file(file))
    assert report.status == "PARTIAL"
    assert [p["id"] for p in payload["effects"][0]["properties"]] == ["blurRadius"]
    warnings = report.effects[0].warnings
    assert any(w.code == "COMPLEX_PARAMETER" for w in warnings)
    assert any(w.path == "ADBE Camera Lens Blur-0013" and w.code == "PARAMETER_REJECTED" for w in warnings)


def test_lens_threshold_scales_values_and_bezier_speeds():
    param = Parameter(
        id="threshold", name="threshold", value=ParameterValue(kind="number", data=0.8),
        keyframes=[Keyframe(
            ticks=15, time_base=30, value=0.6, in_interp=["Bezier"], out_interp=["Bezier"],
            handles=BezierHandles(in_speed=[0.2], out_speed=[-0.4], in_influence=[0.25], out_influence=[0.75]),
        )],
    )
    result = mapped_parameter(
        param, Rule(target="threshold", operation="times_255"), {"kind": "Float", "min": 0, "max": 255}, None
    )
    assert result["value"] == 204.0
    key = result["keyframes"][0]
    assert key.value == 153.0 and key.seconds == 0.5
    assert key.handles.in_speed == [51.0] and key.handles.out_speed == [-102.0]
    assert key.handles.in_influence == [0.25] and key.handles.out_influence == [0.75]
    assert param.keyframes[0].handles.in_speed == [0.2]


def test_complete_filmcraft_catalog_keeps_native_animation_capabilities():
    native = json.loads((Path(__file__).parents[2] / "docs/catalogs/filmcraft.json").read_text())
    catalog = Registry().catalog["filmcraft"]["effects"]
    assert len(native) == len(catalog) == 303
    for effect in native:
        assert set(catalog[effect["id"]]) == {p["id"] for p in effect["params"]}
        for param in effect["params"]:
            spec = catalog[effect["id"]][param["id"]]
            assert spec["animatable"] == param["animatable"]
            if isinstance(param["kind"], dict) and "Choice" in param["kind"]:
                assert spec["options"] == param["kind"]["Choice"]


def test_filmcraft_rejects_keyframes_on_non_animatable_native_parameter(premiere_file):
    document = inspect_file(premiere_file)
    param = document.presets[0].effects[0].parameters[0]
    param.id = "2"
    param.value = ParameterValue(kind="enum", data=0)
    param.keyframes = [Keyframe(ticks=0, time_base=30, value=0, in_interp=["Hold"], out_interp=["Hold"])]
    _, report = preview(document)
    assert report.status == "UNSUPPORTED"
    assert any("não aceita animação" in w.message for w in report.effects[0].warnings)
    # Validate imported JSON as well as conversion, preventing hand-edited bypasses.
    payload, _ = preview(inspect_file(premiere_file))
    payload["presets"][0]["effects"][0]["params"] = {
        "dimensions": {"value": {"Choice": 0}, "keyframes": [
            {"time": 0, "value": {"Choice": 0}, "interp": "Hold"},
        ]},
    }
    with pytest.raises(BridgeError, match="não aceita animação"):
        validate_filmcraft(payload, Registry())
