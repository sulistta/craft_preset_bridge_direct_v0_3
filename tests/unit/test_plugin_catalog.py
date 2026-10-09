import copy
import json

import pytest
from pydantic import ValidationError

from craft_bridge.core.pipeline import inspect_file, preview
from craft_bridge.core.safety import BridgeError
from craft_bridge.core.validation import validate_plan
from craft_bridge.mappings.plugins import PluginManifest, PluginParam
from craft_bridge.mappings.registry import Registry
from tests.helpers import ffx


def manifest():
    return {
        "api": 1, "id": "org.craftbridge.test.gain", "name": "Bridge Gain Probe",
        "category": "Bridge Validation", "version": "1.0.0",
        "params": [
            {"id": "gain", "name": "Gain", "type": "slider", "default": 1.0, "min": 0, "max": 4},
            {"id": "enabled", "name": "Enabled", "type": "checkbox", "default": True},
            {"id": "channel", "name": "Channel", "type": "popup", "default": 0, "options": ["All", "Red"]},
        ],
    }


def package():
    return {
        "format": "craftbridge.mappings", "version": 2, "name": "gain-probe", "plugins": [manifest()],
        "mappings": [{
            "source": "Bridge Gain Probe", "source_format": "ffx", "target": "effectcraft",
            "effect": manifest()["id"],
            "params": {
                "Bridge Gain Probe-0001": {"target": "gain", "kind": "Float"},
                "Bridge Gain Probe-0002": {"target": "enabled", "kind": "Bool"},
                "Bridge Gain Probe-0003": {"target": "channel", "kind": "Choice", "operation": "minus_one"},
            },
            "evidence": "Fully synthetic probe; official native API v1; no Adobe fixture",
            "validation": "synthetic-only", "target_commit": Registry(packages=[]).catalog["effectcraft"]["commit"],
        }],
    }


def plugin_plan(tmp_path, monkeypatch):
    monkeypatch.setenv("CRAFT_BRIDGE_CONFIG", str(tmp_path / "config"))
    source = tmp_path / "package.json"
    source.write_text(json.dumps(package()))
    Registry().install(source)
    f = tmp_path / "gain.ffx"
    f.write_bytes(ffx([("Bridge Gain Probe", [
        ("Bridge Gain Probe-0001", 2.0, 10),
        ("Bridge Gain Probe-0002", 1, 4),
        ("Bridge Gain Probe-0003", 2, 7),
    ])]))
    return preview(inspect_file(f))[0]


def test_new_plugin_ids_map_and_plan_pins_manifest(tmp_path, monkeypatch):
    payload = plugin_plan(tmp_path, monkeypatch)
    plan = validate_plan(payload)
    assert plan.version == 3
    assert plan.effects[0].plugin_fingerprint == PluginManifest.model_validate(manifest()).fingerprint()
    assert {p.id: p.value for p in plan.effects[0].properties} == {"gain": 2, "enabled": True, "channel": 1}
    assert len(Registry().catalog["effectcraft"]["effects"]) == 307


@pytest.mark.parametrize("edit", ["missing", "altered", "v2"])
def test_plugin_plan_requires_original_manifest_and_v3(tmp_path, monkeypatch, edit):
    payload = plugin_plan(tmp_path, monkeypatch)
    if edit == "missing":
        payload["effects"][0]["plugin_fingerprint"] = None
    elif edit == "altered":
        payload["effects"][0]["plugin_fingerprint"] = "0" * 64
    else:
        payload["version"] = 2
    with pytest.raises(BridgeError, match="manifesto"):
        validate_plan(payload)


def test_manifest_removed_or_changed_after_conversion_is_refused(tmp_path, monkeypatch):
    payload = plugin_plan(tmp_path, monkeypatch)
    installed = tmp_path / "config/mappings/gain-probe.json"
    original = json.loads(installed.read_text())
    changed = copy.deepcopy(original)
    changed["plugins"][0]["params"][0]["max"] = 5
    installed.write_text(json.dumps(changed))
    with pytest.raises(BridgeError, match="manifesto"):
        validate_plan(payload)
    installed.unlink()
    with pytest.raises(BridgeError):
        validate_plan(payload)


@pytest.mark.parametrize("param", [
    {"type": "slider", "default": True}, {"type": "slider", "default": "1"},
    {"type": "slider", "default": 5, "min": 0, "max": 4},
    {"type": "slider", "default": 1, "sliderMin": 5, "sliderMax": 4},
    {"type": "slider", "default": 1, "max": float("inf")},
    {"type": "popup", "default": 0.5, "options": ["A"]},
    {"type": "popup", "default": 1, "options": ["A"]},
    {"type": "checkbox", "default": 1},
    {"type": "point", "default": [0.5, True]},
    {"type": "color", "default": [1, 1, 1]},
    {"type": "angle", "default": 30, "min": 0},
    {"type": "text", "default": "code"},
])
def test_invalid_native_plugin_types_bounds_and_defaults_are_refused(param):
    with pytest.raises((BridgeError, ValidationError)):
        PluginParam.model_validate({"id": "probe", "name": "Probe", **param}).spec()


def test_plugin_cannot_override_native_catalog_and_install_is_atomic(tmp_path, monkeypatch):
    monkeypatch.setenv("CRAFT_BRIDGE_CONFIG", str(tmp_path / "config"))
    registry = Registry()
    source = tmp_path / "package.json"
    data = package()
    data["plugins"][0]["id"] = "ec.blur.sharpen"
    source.write_text(json.dumps(data))
    with pytest.raises(BridgeError):
        registry.install(source)
    assert not registry.plugins and len(registry.catalog["effectcraft"]["effects"]) == 306
    assert not (tmp_path / "config").exists()
    source.write_text(json.dumps(package()))
    destination = registry.install(source)
    data = package()
    data["name"] = "gain-probe"  # Existing destination must not be overwritten.
    data["mappings"][0]["source"] = "New Source"
    source.write_text(json.dumps(data))
    before = destination.read_bytes()
    with pytest.raises(BridgeError):
        registry.install(source)
    assert destination.read_bytes() == before
    assert registry.find("ffx", "effectcraft", "New Source") is None


@pytest.mark.parametrize("kind,default,extra,expected", [
    ("point", [0.25, 0.75], {}, "Vec2"), ("color", [0.1, 0.2, 0.3, 1], {}, "Color"),
    ("angle", 45, {}, "Float"), ("checkbox", False, {}, "Bool"),
])
def test_other_official_parameter_kinds(kind, default, extra, expected):
    spec = PluginParam.model_validate({"id": "probe", "name": "Probe", "type": kind, "default": default, **extra}).spec()
    assert spec["kind"] == expected


@pytest.mark.parametrize("kind,default", [("angle", 0.0), ("checkbox", False), ("popup", 0), ("point", [0.5, 0.5]), ("color", [1.0] * 4)])
def test_omitted_defaults_follow_official_serde_contract(kind, default):
    param = {"id": "_0", "name": "Probe", "type": kind}
    if kind == "popup":
        param["options"] = ["A"]
    assert PluginParam.model_validate(param).spec()["default"] == default


def test_native_ascii_ids_with_leading_digits_or_underscores_are_valid():
    from craft_bridge.exporters.effectcraft.exporter import PlanProperty

    data = manifest()
    data["id"] = "1_gain"
    data["params"][0]["id"] = "_gain"
    assert "_gain" in PluginManifest.model_validate(data).specs()
    assert PlanProperty(id="0gain", kind="Float", value=1).id == "0gain"


@pytest.mark.parametrize("param", [{"type": "angle", "default": None}, {"type": "slider"}])
def test_null_or_missing_required_default_is_refused(param):
    with pytest.raises(BridgeError):
        PluginParam.model_validate({"id": "probe", "name": "Probe", **param}).spec()


def test_omitted_native_defaults_survive_install_and_reload(tmp_path, monkeypatch):
    monkeypatch.setenv("CRAFT_BRIDGE_CONFIG", str(tmp_path / "config"))
    data = package()
    del data["plugins"][0]["params"][1]["default"]
    source = tmp_path / "package.json"
    source.write_text(json.dumps(data))
    before = PluginManifest.model_validate(data["plugins"][0]).fingerprint()
    Registry().install(source)
    loaded = Registry().plugins[data["plugins"][0]["id"]]
    assert loaded.specs()["enabled"]["default"] is False
    assert loaded.fingerprint() == before


def test_shared_manifest_is_resolved_independently_of_package_filename_order(tmp_path, monkeypatch):
    monkeypatch.setenv("CRAFT_BRIDGE_CONFIG", str(tmp_path / "config"))
    definition = package()
    definition.update(name="z-manifest", mappings=[])
    source = tmp_path / "definition.json"
    source.write_text(json.dumps(definition))
    Registry().install(source)
    mapping = package()
    mapping.update(name="a-map", plugins=[])
    source.write_text(json.dumps(mapping))
    Registry().install(source)
    assert Registry().find("ffx", "effectcraft", "Bridge Gain Probe") is not None
