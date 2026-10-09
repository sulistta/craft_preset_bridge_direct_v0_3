"""XML original sintético; presets externos não são redistribuídos."""

import xml.etree.ElementTree as ET

import pytest

from craft_bridge.core.pipeline import convert_file, inspect_file, preview
from tests.helpers import premiere


def legacy_file(tmp_path, match, params, *, animation=False):
    root = ET.fromstring(premiere(animation=animation))
    root.find("FilterPreset/FilterMatchName").text = match
    refs = root.find("VideoFilterComponent/Component/Params")
    refs.clear()
    root.remove(root.find("VideoComponentParam"))
    for index, (identifier, control, value) in enumerate(params):
        obj = str(30 + index)
        ET.SubElement(refs, "Param", Index=str(index), ObjectRef=obj)
        node = ET.SubElement(root, "VideoComponentParam", ObjectID=obj)
        for tag, text in {
            "ParameterID": identifier, "ParameterControlType": control,
            "Name": "Controle sintético", "StartKeyframe": f"-91445760000000000,{value},0,0,0,0,0,0",
            "CurrentValue": "999", "IsTimeVarying": str(animation).lower(),
            "Keyframes": f"0,{value},0,0,0,0,0,0;254016000000,{value},0,0,0,0,0,0;" if animation else "",
        }.items():
            ET.SubElement(node, tag).text = text
    path = tmp_path / "legacy.prfpset"
    path.write_bytes(ET.tostring(root))
    return path


@pytest.mark.parametrize("raw,expected", [("17", 17), ("17.", 17), ("4e3", 4000)])
def test_integer_slider_saved_constant(tmp_path, raw, expected):
    path = legacy_file(tmp_path, "AE.ADBE Mosaic", [("1", "1", raw)])
    p = inspect_file(path).presets[0].effects[0].parameters[0]
    assert p.value.kind == "number" and p.value.data == expected
    assert p.origin["CurrentValue"] == "999" and not p.warnings


@pytest.mark.parametrize("raw", ["2.5", "nan", "inf", "true", "bad"])
def test_integer_slider_invalid_never_becomes_zero(tmp_path, raw):
    path = legacy_file(tmp_path, "AE.ADBE Mosaic", [("1", "1", raw)])
    doc = inspect_file(path)
    assert doc.presets[0].effects[0].parameters[0].value.data is None
    assert preview(doc)[1].status == "UNSUPPORTED"


def test_mosaic_native_blocks_and_render_loss_strict(tmp_path):
    path = legacy_file(tmp_path, "AE.ADBE Mosaic", [("1", "1", "23"), ("2", "1", "11"), ("3", "4", "true")])
    out, report = preview(inspect_file(path))
    effect = out["presets"][0]["effects"][0]
    assert effect["effect"] == "mosaic"
    assert effect["params"] == {"horizontal": {"value": {"Float": 23}}, "vertical": {"value": {"Float": 11}}}
    assert report.status == "PARTIAL" and report.effects[0].parameters_converted == 2
    assert any(w.code == "MAPPING_APPROXIMATION" and "Sharp" in w.message for w in report.effects[0].warnings)
    destination = tmp_path / "out.json"
    assert convert_file(path, destination, strict=True).status == "FAILED"
    assert not destination.exists()


def test_native_range_rejects_without_clamping(tmp_path):
    path = legacy_file(tmp_path, "AE.ADBE Mosaic", [("1", "1", "4001"), ("2", "1", "0")])
    assert preview(inspect_file(path))[1].status == "UNSUPPORTED"


def test_channel_blur_does_not_guess_dimensions_menu(tmp_path):
    path = legacy_file(tmp_path, "AE.ADBE Channel Blur", [
        ("1", "2", "28"), ("2", "2", "12"), ("3", "2", "0"), ("4", "2", "3"),
        ("5", "4", "true"), ("6", "7", "1"),
    ])
    out, report = preview(inspect_file(path))
    params = out["presets"][0]["effects"][0]["params"]
    assert params["red"]["value"] == {"Float": 28}
    assert params["repeat_edge"]["value"] == {"Bool": True}
    assert "dimensions" not in params and len(params) == 5
    assert report.status == "PARTIAL"
    assert any(w.path == "6" and w.loss for w in report.effects[0].warnings)


def test_legacy_geometry_requires_size_and_preserves_points(tmp_path):
    path = legacy_file(tmp_path, "AE.ADBE Geometry", [("1", "6", "0.25:0.75"), ("2", "6", "0.5:0.25"), ("9", "4", "true"), ("10", "2", "180")])
    doc = inspect_file(path)
    assert preview(doc)[1].status == "UNSUPPORTED"
    out, report = preview(doc, source_size=(800, 600))
    params = out["presets"][0]["effects"][0]["params"]
    assert params["anchor"]["value"] == {"Vec2": {"x": 200, "y": 450}}
    assert params["position"]["value"] == {"Vec2": {"x": 400, "y": 150}}
    assert "shutter_angle" not in params and report.status == "PARTIAL"


def test_integer_animation_keeps_unknown_curves_refused(tmp_path):
    path = legacy_file(tmp_path, "AE.ADBE Mosaic", [("1", "1", "9")], animation=True)
    doc = inspect_file(path)
    assert [k.value for k in doc.presets[0].effects[0].parameters[0].keyframes] == [9, 9]
    assert preview(doc, keyframe_mode="AnchorToIn")[1].status == "UNSUPPORTED"
