import json
from pathlib import Path

import pytest

from craft_bridge.core.models import Interpolation, Keyframe
from craft_bridge.core.pipeline import (
    batch_convert,
    batch_csv,
    convert_file,
    html_report,
    inspect_file,
    preview,
)
from craft_bridge.core.safety import BridgeError, atomic_write
from craft_bridge.core.validation import validate_filmcraft, validate_plan
from craft_bridge.mappings.registry import Registry
from tests.helpers import ffx, premiere


def test_filmcraft_native_schema_and_golden(premiere_file):
    output, report = preview(inspect_file(premiere_file))
    assert report.status == "SUCCESS"
    assert output == json.loads(Path("tests/golden/blur.filmcraft.json").read_text())
    validate_filmcraft(output, Registry())


def test_mapping_order_and_parameters(tmp_path):
    p = tmp_path / "stack.prfpset"
    p.write_bytes(premiere(effects=2))
    output, report = preview(inspect_file(p))
    assert len(output["presets"][0]["effects"]) == 2
    assert report.effects[1].parameters_converted == 1


def test_unknown_effect_is_unsupported(tmp_path):
    p = tmp_path / "unknown.prfpset"
    p.write_bytes(premiere(unknown=True))
    _, report = preview(inspect_file(p))
    assert report.status == "UNSUPPORTED"
    assert report.effects[0].target is None


def test_no_effect_is_not_success(tmp_path):
    from tests.helpers import container

    p = tmp_path / "empty.ffx"
    p.write_bytes(container("FaFX", container("besc"), tag="RIFX"))
    _, report = preview(inspect_file(p))
    assert report.status == "UNSUPPORTED"


def test_normalized_geometry_requires_resolution(premiere_file):
    doc = inspect_file(premiere_file)
    effect = doc.presets[0].effects[0]
    effect.identifier.match_name = "AE.ADBE Geometry2"
    p = effect.parameters[0]
    p.id = "2"
    p.value.kind = "point"
    p.value.data = [0.5, 0.25]
    p.value.unit = "normalized-frame"
    _, report = preview(doc)
    assert report.status == "UNSUPPORTED"
    output, report = preview(doc, source_size=(1280, 720))
    assert output["presets"][0]["effects"][0]["params"]["position"]["value"] == {
        "Vec2": {"x": 640.0, "y": 180.0}
    }
    assert report.status == "SUCCESS"
    assert report.effects[0].transformations


def test_filmcraft_keyframes_in_intermediate_are_exported(premiere_file):
    doc = inspect_file(premiere_file)
    param = doc.presets[0].effects[0].parameters[0]
    param.keyframes = [
        Keyframe(
            ticks=0,
            time_base=30720,
            value=0.0,
            in_interp=[Interpolation.LINEAR],
            out_interp=[Interpolation.LINEAR],
        ),
        Keyframe(
            ticks=30720,
            time_base=30720,
            value=50.0,
            in_interp=[Interpolation.HOLD],
            out_interp=[Interpolation.HOLD],
        ),
    ]
    output, report = preview(doc, keyframe_mode="AnchorToOut")
    preset = output["presets"][0]
    assert preset["keyframes"] == "AnchorToOut"
    assert preset["effects"][0]["params"]["blurriness"]["keyframes"][1]["time"] == 254016000000
    assert report.effects[0].keyframes_preserved == 2


def test_unknown_interpolation_is_rejected(tmp_path):
    p = tmp_path / "animation.prfpset"
    p.write_bytes(premiere(animation=True))
    _, report = preview(inspect_file(p))
    assert report.status == "UNSUPPORTED"


@pytest.mark.parametrize(
    "source,target,parameters,expected",
    [
        ("ADBE Sharpen", "ec.blur.sharpen", [("ADBE Sharpen-0001", 15.0, 1)], {"amount": 15.0}),
        (
            "ADBE Unsharp Mask2",
            "ec.blur.unsharp",
            [
                ("ADBE Unsharp Mask2-0001", 30.0, 1),
                ("ADBE Unsharp Mask2-0002", 5.0, 1),
                ("ADBE Unsharp Mask2-0003", 2.0, 1),
            ],
            {"amount": 30.0, "radius": 5.0, "threshold": 2.0},
        ),
        (
            "ADBE Brightness & Contrast 2",
            "ec.color.brightnesscontrast",
            [
                ("ADBE Brightness & Contrast 2-0001", 35.0, 1),
                ("ADBE Brightness & Contrast 2-0002", 20.0, 1),
                ("ADBE Brightness & Contrast 2-0003", 0.0, 4),
            ],
            {"brightness": 35.0, "contrast": 20.0, "useLegacy": False},
        ),
        (
            "ADBE Gaussian Blur 2",
            "ec.blur.gaussian",
            [
                ("ADBE Gaussian Blur 2-0001", 20.0, 1),
                ("ADBE Gaussian Blur 2-0002", 1.0, 7),
                ("ADBE Gaussian Blur 2-0003", 1.0, 4),
            ],
            {"blurriness": 20.0, "dimensions": 0, "repeatEdge": True},
        ),
        (
            "ADBE Directional Blur",
            "ec.blur.directional",
            [("ADBE Directional Blur-0001", 90.0, 3), ("ADBE Directional Blur-0002", 30.0, 1)],
            {"direction": 90.0, "length": 30.0},
        ),
        (
            "ADBE Geometry2",
            "ec.distort.transform",
            [("ADBE Geometry2-0001", [0.5, 0.5], 6, 2), ("ADBE Geometry2-0012", 2.0, 7)],
            {"anchor": [960.0, 540.0], "sampling": 1},
        ),
    ],
)
def test_effectcraft_maps_individually(tmp_path, source, target, parameters, expected):
    p = tmp_path / "case.ffx"
    p.write_bytes(ffx([(source, parameters)]))
    output, report = preview(inspect_file(p), source_size=(1920, 1080))
    assert report.status == (
        "PARTIAL" if source in ("ADBE Gaussian Blur 2", "ADBE Directional Blur") else "SUCCESS"
    )
    plan = validate_plan(output)
    assert plan.effects[0].effect == target
    assert {pr.id: pr.value for pr in plan.effects[0].properties} == expected


def test_partial_strict_and_atomic_outputs(tmp_path, premiere_file):
    p = tmp_path / "partial.prfpset"
    p.write_bytes(
        premiere()
        .replace(b"</Params>", b'<Param Index="1" ObjectRef="13"/></Params>')
        .replace(
            b"</PremiereData>",
            b'<VideoComponentParam ObjectID="13"><ParameterID>999</ParameterID><ParameterControlType>8</ParameterControlType><StartKeyframe>0,12</StartKeyframe></VideoComponentParam></PremiereData>',
        )
    )
    out = tmp_path / "strict.json"
    report = convert_file(p, out, strict=True)
    assert report.status == "FAILED"
    assert not out.exists()
    assert Path(str(out) + ".report.json").exists()
    out = tmp_path / "partial.json"
    report = convert_file(p, out)
    assert report.status == "PARTIAL" and out.exists()
    assert Path(str(out) + ".report.html").exists()
    with pytest.raises(BridgeError):
        convert_file(p, out)
    with pytest.raises(BridgeError):
        convert_file(p, p)


def test_dry_run_and_invalid_file_reports(tmp_path, premiere_file):
    out = tmp_path / "dry.json"
    assert convert_file(premiere_file, out, dry_run=True).status == "SUCCESS"
    assert not out.exists() and not Path(str(out) + ".report.json").exists()
    p = tmp_path / "bad.ffx"
    p.write_bytes(b"bad")
    report = convert_file(p, tmp_path / "bad.json")
    assert report.status == "FAILED" and report.errors


def test_native_catalog_rejects_bad_ids(premiere_file):
    output, _ = preview(inspect_file(premiere_file))
    output["presets"][0]["effects"][0]["effect"] = "fake_effect"
    with pytest.raises(BridgeError):
        validate_filmcraft(output, Registry())


def test_plan_tampering_rejected(ffx_file):
    output, _ = preview(inspect_file(ffx_file))
    output["commands"].append({"command": "file.delete", "params": {"path": "/"}})
    with pytest.raises(BridgeError):
        validate_plan(output)


def test_invalid_types_ranges_and_duplicate_refs(ffx_file):
    output, _ = preview(inspect_file(ffx_file))
    for kind, value in [("Float", float("inf")), ("Float", -1), ("Bool", 1)]:
        bad = json.loads(json.dumps(output))
        bad["effects"][0]["properties"][0]["kind"] = kind
        bad["effects"][0]["properties"][0]["value"] = value
        with pytest.raises(BridgeError):
            validate_plan(bad)
    output["effects"].append(output["effects"][0])
    with pytest.raises(BridgeError):
        validate_plan(output)


def test_report_html_escapes_source(premiere_file):
    _, report = preview(inspect_file(premiere_file))
    report.source_path = "<script>alert(1)</script>"
    content = html_report(report)
    assert "<script>" not in content and "&lt;script&gt;" in content


def test_batch_failures_collisions_and_cancel(tmp_path):
    from threading import Event

    root = tmp_path / "in"
    for folder in ["a", "b"]:
        (root / folder).mkdir(parents=True)
        (root / folder / "same.prfpset").write_bytes(premiere())
    (root / "bad.ffx").write_bytes(b"bad")
    reports = batch_convert(root, tmp_path / "out")
    assert [r.status for r in reports].count("SUCCESS") == 2
    assert len([p for p in (tmp_path / "out").glob("*.prfpset.*.json") if ".report." not in p.name]) == 2
    assert any(r.status == "FAILED" for r in reports)
    event = Event()
    event.set()
    assert batch_convert(root, tmp_path / "cancelled", cancel=event) == []
    with pytest.raises(BridgeError):
        batch_convert(root, root)


def test_csv_formula_guard(premiere_file):
    _, report = preview(inspect_file(premiere_file))
    report.source_path = '=HYPERLINK("x")'
    assert "'=HYPERLINK" in batch_csv([report])


def test_atomic_write_refuses_existing_file_and_symlink(tmp_path):
    p = tmp_path / "x"
    atomic_write(p, "old")
    with pytest.raises(BridgeError):
        atomic_write(p, "new")
    assert p.read_text() == "old"
    s = tmp_path / "symlink"

    try:
        s.symlink_to(p)
    except OSError:
        pytest.skip("Criação de symlinks indisponível neste ambiente")
    with pytest.raises(BridgeError):
        atomic_write(s, "new")
    assert not list(tmp_path.glob(".craft-*"))


def test_mapping_package_validated_and_no_execution(tmp_path, monkeypatch):
    monkeypatch.setenv("CRAFT_BRIDGE_CONFIG", str(tmp_path / "config"))
    registry = Registry()
    mapping = next(iter(registry.mappings.values())).model_dump(mode="json")
    mapping["source"] = "Community exact source"
    package = {"format": "craftbridge.mappings", "version": 1, "name": "community", "mappings": [mapping]}
    p = tmp_path / "maps.json"
    p.write_text(json.dumps(package))
    installed = registry.install(p)
    assert installed.exists() and Registry().find("prfpset", "filmcraft", "Community exact source")
    package["mappings"][0]["params"]["1"]["operation"] = "eval"
    p.write_text(json.dumps(package))
    with pytest.raises(BridgeError):
        registry.read_package(p)
