"""Original typed controls, atomic refusal and fill-color transport."""

import pytest

from craft_bridge.core.pipeline import convert_file, inspect_file, preview
from craft_bridge.extensions import extension_paths
from craft_bridge.mappings.registry import Registry
from tests.helpers import ffx

PREFIX = "com.FXHOME.HitFilm.Hotspots-"


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv("CRAFT_BRIDGE_CONFIG", str(tmp_path / "config"))
    registry = Registry(packages=[extension_paths("hfhotspots")[0]])
    source = tmp_path / "original.ffx"
    source.write_bytes(ffx([("com.FXHOME.HitFilm.Hotspots", [
        (PREFIX + "0001", 0.75, 10),
        (PREFIX + "0002", [128., 255., 64., 0.], 5, 4, None, 30720, 7),
        (PREFIX + "0003", 0.5, 10),
        (PREFIX + "0004", 2., 10),
        (PREFIX + "0006", 12., 10),
        (PREFIX + "0005", 0., 1),
        (PREFIX + "1985", 1, 7),
    ])]))
    return source, inspect_file(source), registry


def test_five_visible_controls_and_subthreshold_color_are_preserved(setup):
    _, doc, registry = setup
    original = doc.model_dump()
    plan, report = preview(doc, registry=registry)
    assert doc.model_dump() == original
    assert report.status == "PARTIAL" and report.effects[0].parameters_converted == 5
    values = {p["id"]: p["value"] for p in plan["effects"][0]["properties"]}
    assert values == {"threshold": 0.75, "fill_color": [1., 64 / 255, 0., 128 / 255], "saturation": 0.5, "brightness": 2., "smooth_source": 12.}
    for suffix in ["0005", "1985"]:
        assert any(w.path == PREFIX + suffix and w.loss for w in report.effects[0].warnings)
    assert registry.plugins["org.craftbridge.hfhotspots"].api == 2


def test_strict_does_not_publish_approximate_preset(setup, tmp_path):
    source, _, registry = setup
    output = tmp_path / "strict.json"
    assert convert_file(source, output, strict=True, registry=registry).status == "FAILED"
    assert not output.exists()


@pytest.mark.parametrize("suffix,value", [("0001", -1), ("0003", 65), ("0004", -1), ("0006", 8193)])
def test_invalid_visible_control_refuses_whole_creation(setup, suffix, value):
    _, doc, registry = setup
    next(p for p in doc.presets[0].effects[0].parameters if p.id == PREFIX + suffix).value.data = value
    plan, report = preview(doc, registry=registry)
    assert not plan["effects"] and report.effects[0].parameters_converted == 0


def test_missing_visible_smooth_source_does_not_use_hidden_shadow(setup):
    _, doc, registry = setup
    doc.presets[0].effects[0].parameters = [p for p in doc.presets[0].effects[0].parameters if p.id != PREFIX + "0006"]
    plan, report = preview(doc, registry=registry)
    assert not plan["effects"] and report.effects[0].parameters_converted == 0
    assert any(w.code == "REQUIRED_SOURCE_DATA" for w in report.effects[0].warnings)
