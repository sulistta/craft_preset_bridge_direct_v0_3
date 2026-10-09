import json
from importlib.resources import files

import pytest

from craft_bridge.core.pipeline import convert_file, inspect_file, preview
from craft_bridge.extensions import extension_paths
from craft_bridge.mappings.registry import Registry
from tests.helpers import ffx


def source_file(tmp_path, *, edits=None, keys=None):
    params = [
        ("PEDG-0001", 1500.0, 10, 1, keys), ("PEDG-0002", 3.0, 10),
        ("PEDG-0004", 120.0, 10), ("PEDG-0005", 50.0, 10),
        ("PEDG-0008", 2, 7), ("PEDG-0010", 0.0, 10),
        ("PEDG-0037", 1, 4), ("PEDG-0038", [255.0, 255.0, 64.0, 0.0], 5, 4),
        ("PEDG-0039", 3, 7), ("PEDG-0041", 25.0, 10),
        ("PEDG-0023", 2, 7), ("PEDG-0024", 100.0, 10), ("PEDG-0025", 1, 4),
    ]
    params = [edits.get(p[0], p) if edits else p for p in params]
    f = tmp_path / "glow.ffx"
    f.write_bytes(ffx([("PEDG", params)]))
    return f


@pytest.fixture
def installed(tmp_path, monkeypatch):
    monkeypatch.setenv("CRAFT_BRIDGE_CONFIG", str(tmp_path / "config"))
    mapping, module = extension_paths("glow")
    assert module.read_bytes()[:4] == b"\0asm"
    Registry().install(mapping)
    return Registry()


def test_optional_map_preserves_hdr_threshold_menus_and_linear_exposure(installed, tmp_path):
    payload, report = preview(inspect_file(source_file(tmp_path)))
    props = {p["id"]: p["value"] for p in payload["effects"][0]["properties"]}
    assert len(props) == 13
    assert props["threshold"] == 120.0 and props["exposure"] == 3.0
    assert props["blend"] == 1 and props["tint_mode"] == 2 and props["view"] == 1
    assert props["tint"] == [1.0, 64 / 255, 0.0, 1.0]
    assert props["unmult"] is True and props["aspect"] == 0.0
    assert payload["effects"][0]["effect"] == "org.craftbridge.glow"
    assert payload["effects"][0]["plugin_fingerprint"] == installed.plugins["org.craftbridge.glow"].fingerprint()
    assert report.status == "PARTIAL"  # Even when all 13 source controls are transferred.
    assert sum(w.code == "MAPPING_APPROXIMATION" for w in report.effects[0].warnings) == 4


def test_strict_never_publishes_approximate_glow(installed, tmp_path):
    out = tmp_path / "strict.json"
    report = convert_file(source_file(tmp_path), out, strict=True)
    assert report.status == "FAILED" and not out.exists()


@pytest.mark.parametrize("id,value,kind", [("PEDG-0001", 2001, 10), ("PEDG-0002", -1, 10), ("PEDG-0008", 3, 7), ("PEDG-0039", 0, 7), ("PEDG-0023", 3, 7)])
def test_unknown_menus_and_out_of_range_values_are_reported_not_clamped(installed, tmp_path, id, value, kind):
    f = source_file(tmp_path, edits={id: (id, value, kind)})
    payload, report = preview(inspect_file(f))
    assert len(payload["effects"][0]["properties"]) == 12
    assert any(w.code == "PARAMETER_REJECTED" and w.path == id for w in report.effects[0].warnings)


def test_radius_keys_keep_original_times_and_values(installed, tmp_path):
    payload, report = preview(inspect_file(source_file(tmp_path, keys=[(0, 200.0, 1), (30720, 1600.0, 1)])))
    prop = next(p for p in payload["effects"][0]["properties"] if p["id"] == "radius")
    assert [(k["ticks"] / k["time_base"], k["value"]) for k in prop["keyframes"]] == [(0.0, 200.0), (1.0, 1600.0)]
    assert report.effects[0].keyframes_preserved == 2


def test_renderer_manifest_and_package_have_identical_parameter_contract():
    mapping, _ = extension_paths("glow")
    data = json.loads(mapping.read_text())
    manifest = json.loads(files("craft_bridge.extensions").joinpath("glow/manifest.json").read_text())
    assert data["plugins"] == [manifest]
    assert len(manifest["params"]) == 13
    assert data["mappings"][0]["limitations"]


def test_selected_glow_properties_group_one_existing_instance_and_keep_keys(installed, tmp_path):
    from tests.unit.test_selected_properties import selected_ffx

    f = tmp_path / "selected.ffx"
    f.write_bytes(selected_ffx([
        ("PEDG", "PEDG-0001", 200, 10, [(0, 200, 1), (30720, 1600, 1)]),
        ("PEDG", "PEDG-0002", 1, 10, [(0, 1, 1), (30720, 3, 1)]),
        ("PEDG", "PEDG-0025", 1, 4, [(0, 1, 3), (30720, 0, 3)]),
    ], indices=[2, 2, 2]))
    payload, report = preview(inspect_file(f))
    assert report.status == "PARTIAL" and len(payload["effects"]) == 1
    effect = payload["effects"][0]
    assert effect["application"] == "existing" and effect["source_effect_index"] == 2
    assert {p["id"] for p in effect["properties"]} == {"radius", "exposure", "unmult"}
    assert report.effects[0].keyframes_preserved == 6
    assert not any(c["command"] in ("effect.apply", "effect.toggle") for c in payload["commands"])
    bool_prop = next(p for p in effect["properties"] if p["id"] == "unmult")
    assert [k["value"] for k in bool_prop["keyframes"]] == [True, False]


def test_proven_plugin_types_decode_without_installing_renderer_maps(tmp_path, monkeypatch):
    from tests.unit.test_selected_properties import selected_ffx

    monkeypatch.setenv("CRAFT_BRIDGE_CONFIG", str(tmp_path / "empty-config"))
    f = tmp_path / "selected.ffx"
    f.write_bytes(selected_ffx([("PEDG", "PEDG-0002", 1, 10, [(0, 1, 1), (30720, 3, 1)])]))
    document = inspect_file(f)
    assert document.presets[0].effects[0].feature == "effect-properties"
    parameter = document.presets[0].effects[0].parameters[0]
    assert parameter.value.kind == "number" and parameter.value.data == 1
    assert [k.value for k in parameter.keyframes] == [1, 3]
    payload, report = preview(document)
    assert report.status == "UNSUPPORTED" and payload["effects"] == []
