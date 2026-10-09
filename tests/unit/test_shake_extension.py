import json

import pytest

from craft_bridge.core.pipeline import convert_file, inspect_file, preview
from craft_bridge.extensions import extension_paths
from craft_bridge.mappings.registry import Registry
from tests.helpers import ffx
from tests.unit.test_selected_properties import selected_ffx


@pytest.fixture
def installed_shake(tmp_path, monkeypatch):
    monkeypatch.setenv("CRAFT_BRIDGE_CONFIG", str(tmp_path / "config"))
    mapping, module = extension_paths("shake")
    assert module.read_bytes().startswith(b"\0asm")
    Registry().install(mapping)
    return json.loads(mapping.read_text())


def all_controls(package):
    manifest = package["plugins"][0]
    specs = {p["id"]: p for p in manifest["params"]}
    result = []
    for source, rule in package["mappings"][0]["params"].items():
        spec = specs[rule["target"]]
        value = spec["default"]
        kind = 2
        if spec["type"] == "popup":
            value += 1
            kind = 7
        elif spec["type"] == "checkbox":
            value = int(value)
            kind = 4
        result.append((source, value, kind))
    return result


def test_every_original_control_has_a_typed_rule_and_approximation_is_reported(installed_shake, tmp_path):
    source = tmp_path / "original-synthetic.ffx"
    source.write_bytes(ffx([("S_Shake", all_controls(installed_shake))]))
    payload, report = preview(inspect_file(source))
    assert report.status == "PARTIAL"
    effect = payload["effects"][0]
    props = {p["id"]: p["value"] for p in effect["properties"]}
    assert len(props) == 43 and effect["effect"] == "org.craftbridge.shake"
    assert props["style"] == 0 and props["opacity"] == 1 and props["wrap_x"] == 2
    assert props["motion_blur"] is False
    assert sum(w.code == "MAPPING_APPROXIMATION" for w in report.effects[0].warnings) == 4
    out = tmp_path / "strict.json"
    assert convert_file(source, out, strict=True).status == "FAILED"
    assert not out.exists()


@pytest.mark.parametrize(
    "source,value,kind",
    [("S_Shake-0001", 4, 7), ("S_Shake-0057", 0, 7), ("S_Shake-0053", 0, 2), ("S_Shake-0050", -1, 2)],
)
def test_invalid_controls_are_lost_instead_of_clamped(installed_shake, tmp_path, source, value, kind):
    file = tmp_path / "invalid.ffx"
    file.write_bytes(ffx([("S_Shake", [(source, value, kind)])]))
    payload, report = preview(inspect_file(file))
    assert not payload["effects"]
    assert any(w.code == "PARAMETER_REJECTED" and w.path == source for w in report.effects[0].warnings)


def test_selected_motion_seed_and_hold_use_the_original_instance(installed_shake, tmp_path):
    file = tmp_path / "selected.ffx"
    file.write_bytes(
        selected_ffx(
            [
                ("S_Shake", "S_Shake-0050", 2, 2, [(0, 2, 1), (30720, 0, 1)]),
                ("S_Shake", "S_Shake-0056", 0.25, 2, [(0, 0.25, 1), (30720, 0.5, 1)]),
                ("S_Shake", "S_Shake-0054", 1, 4, [(0, 1, 3), (30720, 0, 3)]),
            ],
            indices=[4, 4, 4],
        )
    )
    payload, report = preview(inspect_file(file))
    assert report.status == "PARTIAL" and report.effects[0].keyframes_preserved == 6
    effect = payload["effects"][0]
    assert effect["application"] == "existing" and effect["source_effect_index"] == 4
    props = {p["id"]: p for p in effect["properties"]}
    assert props["seed"]["value"] == 0.25 and props["seed"]["keyframes"][1]["value"] == 0.5
    assert props["motion_blur"]["keyframes"][1]["value"] is False
    assert not any(c["command"] in ("effect.apply", "effect.toggle") for c in payload["commands"])


def test_manifest_module_and_mapping_agree(installed_shake):
    mapping, module = extension_paths("shake")
    manifest = json.loads(mapping.with_name("manifest.json").read_text())
    assert installed_shake["plugins"] == [manifest]
    assert len(manifest["params"]) == len(installed_shake["mappings"][0]["params"]) == 43
    assert module.stat().st_size < 200_000
