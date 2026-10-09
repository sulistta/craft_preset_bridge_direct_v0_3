import pytest

from craft_bridge.core.pipeline import inspect_file, preview
from craft_bridge.core.validation import validate_plan
from tests.helpers import ffx


def document(tmp_path, params):
    p = tmp_path / "lumetri.ffx"
    p.write_bytes(
        ffx([("ADBE Lumetri", [(f"ADBE Lumetri-{i:04}", value, kind) for i, value, kind in params])])
    )
    return inspect_file(p)


def test_lumetri_groups_and_none_menus_with_nonneutral_values(tmp_path):
    doc = document(
        tmp_path,
        [
            (3, 1, 4),
            (23, 1, 4),
            (50, 1, 4),
            (26, 100, 10),
            (62, 1, 4),
            (5, 1, 7),
            (7, 18, 10),
            (11, -1.2, 10),
            (14, -32, 10),
            (25, 1, 7),
            (28, 22, 10),
            (31, 150, 10),
            (51, -1.5, 10),
            (54, 70, 10),
        ],
    )
    payload, report = preview(doc)
    plan = validate_plan(payload)
    props = {p.id: p.value for p in plan.effects[0].properties}
    assert props == {
        "highDynamicRange": True,
        "basicCorrection/inputLut": 0,
        "basicCorrection/whiteBalance/temperature": 18,
        "basicCorrection/tone/exposure": -1.2,
        "basicCorrection/tone/shadows": -32,
        "creative/look": 0,
        "creative/lookIntensity": 100,
        "creative/adjustments/fadedFilm": 22,
        "creative/adjustments/creativeSaturation": 150,
        "vignette/vignetteAmount": -1.5,
        "vignette/vignetteFeather": 70,
    }
    # Group switches cannot be retained as editable controls in this engine.
    assert report.status == "PARTIAL"


@pytest.mark.parametrize("group", [[], [(3, 0, 4)], [(3, 1, 1)], [(3, 1, 4), (3, 1, 4)]])
def test_lumetri_missing_disabled_wrong_type_or_duplicate_group_cannot_apply(tmp_path, group):
    payload, report = preview(document(tmp_path, [*group, (7, 50, 10)]))
    assert not payload["effects"] and report.status == "UNSUPPORTED"
    assert any(
        w.code == "PARAMETER_REJECTED" and "Condição" in w.message for e in report.effects for w in e.warnings
    )


def test_creative_nondefault_intensity_cannot_change_unrelated_adjustments(tmp_path):
    payload, report = preview(document(tmp_path, [(23, 1, 4), (26, 20, 10), (28, 30, 10)]))
    assert not payload["effects"] and report.status == "UNSUPPORTED"


def test_lumetri_builtin_lut_names_are_not_matched_by_index(tmp_path):
    payload, report = preview(document(tmp_path, [(3, 1, 4), (5, 5, 7), (7, 18, 10)]))
    props = {p["id"] for p in payload["effects"][0]["properties"]}
    assert "basicCorrection/inputLut" not in props
    assert "basicCorrection/whiteBalance/temperature" in props and report.status == "PARTIAL"
