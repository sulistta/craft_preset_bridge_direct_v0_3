import json
from pathlib import Path

import pytest

from craft_bridge.core.models import BezierHandles, Keyframe, Parameter, ParameterValue
from craft_bridge.core.pipeline import inspect_file, preview
from craft_bridge.core.safety import BridgeError
from craft_bridge.core.validation import validate_plan
from craft_bridge.exporters.common import mapped_parameter, transform
from craft_bridge.mappings.registry import Registry, Rule
from tests.helpers import ffx, path


@pytest.mark.parametrize(
    "source,target,params,expected",
    [
        (
            "ADBE Exposure2",
            "ec.color.exposure",
            [(1, 2.0, 7), (3, -0.5, 10), (5, 1.4, 10), (8, 2.5, 10), (22, 1.0, 4)],
            {
                "channels": 1,
                "master/exposure": -0.5,
                "master/gamma": 1.4,
                "red/redExposure": 2.5,
                "bypassLinearLight": True,
            },
        ),
        (
            "ADBE Black&White",
            "ec.color.blackwhite",
            [(1, 160.0, 10), (6, -40.0, 10), (7, 1.0, 4), (8, [255.0, 127.5, 63.75, 0.0], 5, 4)],
            {"reds": 160.0, "magentas": -40.0, "tint": True, "tintColor": [0.5, 0.25, 0.0, 1.0]},
        ),
        (
            "ADBE Invert",
            "ec.channel.invert",
            [(1, 16.0, 7), (2, 32.0, 2)],
            {"channel": 12, "blend": 32.0},
        ),
        (
            "ADBE Box Blur2",
            "ec.blur.fastbox",
            [(1, 22.0, 2), (2, 4.0, 1), (3, 3.0, 7), (4, 1.0, 4)],
            {"radius": 22.0, "iterations": 4.0, "dimensions": 2, "repeatEdge": True},
        ),
        (
            "ADBE Tile",
            "ec.stylize.motiontile",
            [(1, [0.25, 0.75], 6, 2), (4, 345.0, 1), (6, 1.0, 4)],
            {"tileCenter": [480.0, 810.0], "outputWidth": 345.0, "mirrorEdges": True},
        ),
        (
            "ADBE Noise2",
            "ec.noise.noise",
            [(1, 4.0, 1), (2, 0.0, 4), (3, 1.0, 4)],
            {"amount": 4.0, "color": False, "clip": True},
        ),
        (
            "ADBE Noise HLS2",
            "ec.noise.noisehls",
            [(1, 3.0, 7), (3, 18.0, 1), (6, 90.0, 3)],
            {"noise": 2, "lightness": 18.0, "noisePhase": 90.0},
        ),
        (
            "ADBE Noise HLS Auto2",
            "ec.noise.noisehlsauto",
            [(1, 2.0, 7), (6, 24.0, 1)],
            {"noise": 1, "noiseAnimationSpeed": 24.0},
        ),
        (
            "ADBE Wave Warp",
            "ec.distort.wavewarp",
            [(1, 9.0, 7), (6, 10.0, 7), (2, 329.0, 1)],
            {"waveType": 8, "pinning": 7, "height": 329.0},
        ),
        (
            "ADBE Optics Compensation",
            "ec.distort.opticscompensation",
            [(1, 53.9, 1), (3, 2.0, 7), (4, [1.1, -0.2], 6, 2), (6, 3.0, 7)],
            {"fieldOfView": 53.9, "fovOrientation": 1, "viewCenter": [2112.0, -216.0], "resize": 2},
        ),
        (
            "ADBE Upscale",
            "ec.distort.upscale",
            [(1, 200.0, 1), (2, 50.0, 1), (7, 20.0, 1), (5, 2.0, 7)],
            {"scale": 200.0, "reduceNoise": 50.0, "detail": 20.0, "alpha": 1},
        ),
        (
            "ADBE CameraShakeDeblur",
            "ec.blur.camerashakedeblur",
            [(1, 2.0, 1), (2, 2.0, 7), (3, 150.0, 1), (4, 25.0, 1)],
            {"blurDuration": 2.0, "deblurMethod": 1, "strength": 150.0, "shakeSensitivity": 25.0},
        ),
        (
            "ADBE Tint",
            "ec.color.tint",
            [(1, [255.0, 0.0, 127.5, 255.0], 5, 4), (3, 18.0, 1)],
            {"black": [0.0, 0.5, 1.0, 1.0], "amount": 18.0},
        ),
        (
            "ADBE Tritone",
            "ec.color.tritone",
            [(2, [127.5, 255.0, 0.0, 63.75], 5, 4), (4, 30.0, 1)],
            {"midtones": [1.0, 0.0, 0.25, 0.5], "blend": 30.0},
        ),
        (
            "ADBE 4ColorGradient",
            "ec.generate.fourcolor",
            [(1, [0.1, 0.9], 6, 2), (2, [255.0, 255.0, 0.0, 0.0], 5, 4), (14, 7.0, 7)],
            {
                "positionsColors/point1": [192.0, 972.0],
                "positionsColors/color1": [1.0, 0.0, 0.0, 1.0],
                "blendingMode": 5,
            },
        ),
    ],
)
def test_extended_mappings_preserve_units_and_menu_meaning(tmp_path, source, target, params, expected):
    file = tmp_path / "extended.ffx"
    file.write_bytes(ffx([(source, [(source + "-" + str(p[0]).zfill(4), *p[1:]) for p in params])]))
    payload, report = preview(inspect_file(file), source_size=(1920, 1080))
    plan = validate_plan(payload)
    assert report.status == "SUCCESS"
    assert plan.effects[0].effect == target
    assert {p.id: p.value for p in plan.effects[0].properties} == expected


def test_native_catalog_snapshot_matches_generated_types():
    raw = json.loads((Path(__file__).parents[2] / "docs/catalogs/effectcraft.json").read_text())
    catalog = Registry().catalog["effectcraft"]["effects"]
    assert len(raw) == len(catalog) == 306
    for effect in raw:
        assert set(catalog[effect["id"]]) == {p["id"] for p in effect["params"]}
        for param in effect["params"]:
            kind = param["ui"]["kind"]
            if kind == "Popup":
                assert catalog[effect["id"]][param["id"]]["max"] == len(param["ui"]["options"]) - 1


def test_enum_separators_and_unsupported_options_are_rejected():
    registry = Registry()
    for source, param, value in [
        ("ADBE Wave Warp", "0006", 4),
        ("ADBE 4ColorGradient", "0014", 3),
        ("ADBE Upscale", "0005", 1),
        ("ADBE Invert", "0001", 5),
        ("ADBE Invert", "0001", 10),
        ("ADBE Invert", "0001", 15),
    ]:
        rule = registry.find("ffx", "effectcraft", source).params[source + "-" + param]
        with pytest.raises(BridgeError, match="sem equivalência"):
            transform(value, rule, None)


def test_color_channels_and_ease_are_reordered_and_scaled():
    param = Parameter(
        id="color",
        name="color",
        value=ParameterValue(kind="color", data=[255.0, 0.0, 127.5, 255.0]),
        keyframes=[
            Keyframe(
                ticks=0,
                time_base=30720,
                value=[255.0, 0.0, 127.5, 255.0],
                in_interp=["Bezier"] * 4,
                out_interp=["Bezier"] * 4,
                handles=BezierHandles(
                    in_speed=[255.0, 510.0, 765.0, 1020.0],
                    out_speed=[255.0] * 4,
                    in_influence=[0.1, 0.2, 0.3, 0.4],
                    out_influence=[0.5] * 4,
                ),
            )
        ],
    )
    result = mapped_parameter(
        param, Rule(target="color", kind="Color", operation="argb255_to_rgba"), {"kind": "Color"}, None
    )
    key = result["keyframes"][0]
    assert key.value == [0.0, 0.5, 1.0, 1.0]
    assert key.handles.in_speed == [2.0, 3.0, 4.0, 1.0]
    assert key.handles.in_influence == [0.2, 0.3, 0.4, 0.1]


def test_normalized_point_bezier_does_not_masquerade_as_spatial_ease():
    param = Parameter(
        id="point",
        name="point",
        value=ParameterValue(kind="point", data=[0.5, 0.5]),
        keyframes=[
            Keyframe(
                ticks=0, time_base=30, value=[0.5, 0.5], in_interp=["Bezier"] * 2, out_interp=["Bezier"] * 2
            )
        ],
    )
    with pytest.raises(BridgeError, match="easing espacial"):
        mapped_parameter(
            param,
            Rule(target="point", kind="Vec2", operation="normalized_to_pixels"),
            {"kind": "Vec2"},
            (1920, 1080),
        )


@pytest.mark.parametrize("indices,valid", [([1, 3], True), ([7, 12], True), ([2, 1], False), ([1, 1], False)])
def test_original_effect_indices_are_rebased_only_with_structural_evidence(tmp_path, indices, valid):
    file = tmp_path / "gaps.ffx"
    file.write_bytes(
        ffx(
            [
                ("ADBE Sharpen", [("ADBE Sharpen-0001", 15.0, 1)]),
                ("ADBE Unsharp Mask2", [("ADBE Unsharp Mask2-0001", 35.0, 1)]),
            ],
            effect_indices=indices,
        )
    )
    doc = inspect_file(file)
    _, report = preview(doc)
    assert bool(report.effects[0].parameters_converted) is valid
    if valid:
        assert doc.presets[0].effects[0].metadata["association"] == "ordered-paths-and-parameter-namespace"


def test_gapped_indices_reject_mismatched_snapshot_namespace(tmp_path):
    file = tmp_path / "mismatch.ffx"
    file.write_bytes(ffx([("ADBE Sharpen", [("ADBE Unsharp Mask2-0001", 35.0, 1)])], effect_indices=[4]))
    _, report = preview(inspect_file(file))
    assert report.status == "UNSUPPORTED"
    assert report.effects[0].status == "Não decodificado"


def test_mixed_property_paths_do_not_consume_whole_effect_snapshots(tmp_path):
    file = tmp_path / "mixed.ffx"
    file.write_bytes(
        ffx(
            [("ADBE Sharpen", [("ADBE Sharpen-0001", 35.0, 1)])],
            effect_indices=[3],
            property_paths=[path(["ADBE Effect Parade", "S_Shake", "S_Shake-0001"])],
        )
    )
    doc = inspect_file(file)
    payload, report = preview(doc)
    assert doc.presets[0].effects[0].feature == "property"
    assert doc.presets[0].effects[1].parameters[0].value.data == 35.0
    assert payload["effects"][0]["properties"][0]["value"] == 35.0
    assert report.status == "PARTIAL"
    assert not any(w.code == "BLOCK_COUNT" for w in doc.warnings)


def test_legacy_plan_requires_reconversion_after_unit_correction(ffx_file):
    payload, _ = preview(inspect_file(ffx_file))
    assert payload["version"] == 3
    payload["version"] = 1
    with pytest.raises(BridgeError, match="reconverta"):
        validate_plan(payload)


@pytest.mark.parametrize("root", [[], None, "invalid"])
def test_non_object_plan_root_is_a_controlled_error(root):
    with pytest.raises(BridgeError, match="Plano EffectCraft inválido"):
        validate_plan(root)


@pytest.mark.parametrize("path", ["../amount", "nested/../../amount", "/amount", "group//amount"])
def test_nested_property_paths_refuse_traversal(path):
    from craft_bridge.exporters.effectcraft.exporter import PlanProperty

    with pytest.raises(ValueError):
        PlanProperty(id=path, kind="Float", value=15.0)
