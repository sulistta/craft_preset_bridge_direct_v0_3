"""Synthetic non-neutral corrections, verified units and dependency failures."""

import pytest

from craft_bridge.core.pipeline import convert_file, inspect_file, preview
from craft_bridge.core.validation import validate_plan
from craft_bridge.mappings.registry import Registry
from craft_bridge.parsers.ffx.neutralizer import SOURCE
from tests.helpers import ffx


def fixture(tmp_path, overrides=None, omit=(), duplicate=None):
    params = {}
    for first, values in ((3, (-20, 30, -10)), (9, (40, -60, 20)), (15, (-5, 15, -10))):
        for i, value in enumerate(values, first):
            params[i] = (value, 10, 1, None, 30, 7, 1, 0)
    for i in (1, 7, 13):
        # Deliberately stale, non-neutral UI colors must not contribute twice.
        params[i] = ([255, 200, 12, 90], 5, 4, None, 30, 7, 0, 4)
    for i, value in ((19, 35), (20, 45), (23, 0), (24, 100)):
        params[i] = (value, 10, 1, None, 30, 7, 1, 0)
    params[22] = (1, 7)
    params.update(overrides or {})
    rows = [(f"{SOURCE}-{i:04}", *value) for i, value in params.items() if i not in omit]
    if duplicate is not None:
        rows.append((f"{SOURCE}-{duplicate:04}", *params[duplicate]))
    file = tmp_path / "neutralizer.ffx"
    file.write_bytes(ffx([(SOURCE, rows)]))
    return file


def test_percent_rgb_uses_native_anchors_and_never_stale_picker(tmp_path):
    file = fixture(tmp_path)
    doc = inspect_file(file)
    payload, report = preview(doc)
    plan = validate_plan(payload)
    props = {p.id: p.value for p in plan.effects[0].properties}
    expected = {
        "shadowsBalance": [-0.2, 0.3, -0.1, 1], "midtonesBalance": [0.9, -0.1, 0.7, 1],
        "highlightsBalance": [0.95, 1.15, 0.9, 1], "pinning": 35, "blendWOriginal": 45,
    }
    assert props.keys() == expected.keys()
    for key, value in expected.items():
        assert props[key] == pytest.approx(value)
    assert report.status == "PARTIAL"
    assert any(w.code == "NEUTRALIZER_ALGORITHM" and w.loss for w in report.effects[0].warnings)
    params = doc.presets[0].effects[0].parameters
    assert all(next(p for p in params if p.id == f"{SOURCE}-{i:04}").metadata["administrative"] for i in (1, 7, 13, 3, 4, 5, 9, 10, 11, 15, 16, 17))
    derived = next(p for p in params if p.id == SOURCE + "/rgb/midtones")
    assert len(derived.origin["components"]) == 3
    assert derived.metadata["derived_from"] == [f"{SOURCE}-{i:04}" for i in (9, 10, 11)]
    destination = tmp_path / "strict.json"
    assert convert_file(file, destination, strict=True).status == "FAILED"
    assert not destination.exists()


@pytest.mark.parametrize("overrides,omit,duplicate", [
    ({9: (40, 10, 1, None, 30, 7, 0)}, (), None),  # Units not proven.
    ({9: (40, 10, 1, None, 30, 7, 3)}, (), None),  # Additional pixel-display flag.
    ({9: (40, 10, 1, None, 30, 8, 1)}, (), None),  # Spatial stream.
    ({9: (101, 10, 1, None, 30, 7, 1)}, (), None),
    ({9: (40, 10, 1, [(0, 40, 1), (30, -40, 1)], 30, 7, 1)}, (), None),
    ({}, (10,), None),
    ({}, (), 9),
    ({}, (7,), None),
    ({}, (), 7),
    ({7: ([255, 200, 12, 90], 5, 4, None, 30, 7, 0, 0)}, (), None),
])
def test_unproven_or_animated_rgb_does_not_become_static_color(tmp_path, overrides, omit, duplicate):
    document = inspect_file(fixture(tmp_path, overrides, omit, duplicate))
    payload, report = preview(document)
    props = {p["id"] for p in payload["effects"][0]["properties"]}
    assert "midtonesBalance" not in props
    assert {"shadowsBalance", "highlightsBalance", "pinning", "blendWOriginal"} <= props
    assert not any(p.id == SOURCE + "/rgb/midtones" for p in document.presets[0].effects[0].parameters)
    assert report.status == "PARTIAL"


@pytest.mark.parametrize("overrides,omit,duplicate", [
    ({22: (2, 7)}, (), None), ({22: (3, 7)}, (), None),
    ({23: (10, 10)}, (), None), ({24: (90, 10)}, (), None),
    ({}, (22,), None), ({}, (23,), None), ({}, (24,), None),
    ({}, (), 22),
    ({23: (0, 10, 1, [(0, 0, 1)], 30, 7, 1)}, (), None),
])
def test_view_points_missing_duplicate_or_animated_guards_refuse_effect(tmp_path, overrides, omit, duplicate):
    payload, report = preview(inspect_file(fixture(tmp_path, overrides, omit, duplicate)))
    assert not payload["effects"] and report.status == "UNSUPPORTED"
    assert any(w.code == "PARAMETER_REJECTED" for w in report.effects[0].warnings)


def test_neutralizer_native_anchors_match_audited_defaults():
    specs = Registry().catalog["effectcraft"]["effects"]["ec.color.cccolorneutralizer"]
    for tone, anchor in (("shadows", 0), ("midtones", 0.5), ("highlights", 1)):
        assert specs[tone + "Unbalance"]["default"] == [anchor, anchor, anchor, 1]
