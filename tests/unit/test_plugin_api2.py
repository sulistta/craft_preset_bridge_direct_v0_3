"""Experimental manifests/plans with original data, no source Layer decoder."""

import copy
import json

import pytest
from pydantic import ValidationError

from craft_bridge.core.safety import BridgeError
from craft_bridge.core.validation import validate_plan
from craft_bridge.exporters.effectcraft.exporter import (
    EffectCraftPlan,
    LayerReference,
    PlanEffect,
    PlanProperty,
    preview_commands,
)
from craft_bridge.mappings.plugins import PluginManifest
from craft_bridge.mappings.registry import Registry


def manifest():
    return {
        "api": 2,
        "bridge_host_revision": 1,
        "id": "org.craftbridge.test.layer_mix",
        "name": "Bridge Layer Mix Probe",
        "category": "Bridge Validation",
        "version": "0.1.0",
        "params": [
            {"id": "source", "name": "Source", "type": "layer", "default": None},
            {
                "id": "sourceSource",
                "name": "Source mode",
                "type": "popup",
                "default": 0,
                "options": ["Source", "Masks", "Effects & Masks"],
            },
            {"id": "mix", "name": "Mix", "type": "slider", "default": 1.0, "min": 0, "max": 1},
        ],
    }


def install(tmp_path, monkeypatch):
    monkeypatch.setenv("CRAFT_BRIDGE_CONFIG", str(tmp_path / "config"))
    package = {
        "format": "craftbridge.mappings",
        "version": 2,
        "name": "layer-probe",
        "plugins": [manifest()],
        "mappings": [],
    }
    path = tmp_path / "package.json"
    path.write_text(json.dumps(package))
    Registry().install(path)
    return Registry()


def plan_for(registry, value=None):
    if value is None:
        value = LayerReference(layer_ref="second")
    definition = registry.plugins[manifest()["id"]]
    plan = EffectCraftPlan(
        version=4,
        name="Original synthetic multi-input probe",
        catalog_commit=registry.catalog["effectcraft"]["commit"],
        source_sha256="0" * 64,
        effects=[
            PlanEffect(
                ref="fx0",
                effect=definition.id,
                source="original-synthetic",
                plugin_fingerprint=definition.fingerprint(),
                properties=[
                    PlanProperty(id="source", kind="Layer", value=value),
                    PlanProperty(id="sourceSource", kind="Choice", value=0),
                    PlanProperty(id="mix", kind="Float", value=0.5),
                ],
            )
        ],
    )
    plan.commands = preview_commands(plan)
    return plan


def test_explicit_layer_null_and_fingerprint_survive_install(tmp_path, monkeypatch):
    registry = install(tmp_path, monkeypatch)
    before = PluginManifest.model_validate(manifest())
    assert registry.plugins[before.id].fingerprint() == before.fingerprint()
    assert registry.plugins[before.id].specs()["source"] == {
        "kind": "Layer",
        "default": None,
        "animatable": False,
    }
    stored = json.loads((tmp_path / "config/mappings/layer-probe.json").read_text())
    assert stored["plugins"][0]["params"][0]["default"] is None
    plan = validate_plan(plan_for(registry).model_dump(mode="json"), registry)
    assert plan.commands[0]["command"] == "bridge.resolveLayer"


@pytest.mark.parametrize(
    "fault",
    [
        "api1",
        "revision_missing",
        "revision2",
        "bool_api",
        "float_api",
        "bool_revision",
        "float_revision",
        "missing_null",
        "uid_default",
        "bool_default",
        "options",
        "limits",
        "five_layers",
    ],
)
def test_incompatible_manifests_are_refused(fault):
    data = copy.deepcopy(manifest())
    if fault == "api1":
        data["api"] = 1
    elif fault == "revision_missing":
        del data["bridge_host_revision"]
    elif fault == "revision2":
        data["bridge_host_revision"] = 2
    elif fault == "bool_api":
        data["api"] = True
    elif fault == "float_api":
        data["api"] = 2.0
    elif fault == "bool_revision":
        data["bridge_host_revision"] = True
    elif fault == "float_revision":
        data["bridge_host_revision"] = 1.0
    elif fault == "missing_null":
        del data["params"][0]["default"]
    elif fault == "uid_default":
        data["params"][0]["default"] = 9
    elif fault == "bool_default":
        data["params"][0]["default"] = False
    elif fault == "options":
        data["params"][0]["options"] = ["Source"]
    elif fault == "limits":
        data["params"][0]["min"] = 0
    else:
        for i in range(4):
            data["params"].append({**data["params"][0], "id": f"other{i}"})
    with pytest.raises((BridgeError, ValidationError)):
        PluginManifest.model_validate(data).specs()


@pytest.mark.parametrize("fault", ["v3", "missing_binding", "raw_uid", "animated_binding", "fingerprint"])
def test_v4_resources_are_explicit_static_and_pinned(tmp_path, monkeypatch, fault):
    registry = install(tmp_path, monkeypatch)
    data = plan_for(registry).model_dump(mode="json")
    if fault == "v3":
        data["version"] = 3
    elif fault == "missing_binding":
        data["effects"][0]["properties"].pop(0)
    elif fault == "raw_uid":
        data["effects"][0]["properties"][0]["value"] = 17
    elif fault == "animated_binding":
        data["effects"][0]["properties"][0]["keyframes"] = [{"ticks": 0, "time_base": 30, "value": 17}]
    else:
        data["effects"][0]["plugin_fingerprint"] = "0" * 64
    with pytest.raises(BridgeError):
        validate_plan(data, registry)


def test_explicit_unbind_existing_plugin_leaves_unselected_properties(tmp_path, monkeypatch):
    registry = install(tmp_path, monkeypatch)
    plan = plan_for(registry, LayerReference(layer_ref=None))
    effect = plan.effects[0]
    effect.application = "existing"
    effect.source_effect_index = 0
    effect.properties = effect.properties[:1]
    plan.commands = preview_commands(plan)
    assert (
        validate_plan(plan.model_dump(mode="json"), registry).effects[0].properties[0].value.layer_ref is None
    )


def test_api1_fingerprint_remains_unchanged():
    from tests.unit.test_plugin_catalog import manifest as legacy

    # Verified against the installed 0.24.0 headless wheel, including normalization.
    expected = "8100e537c4dd73dcaa31cd8efd18f182c328233da9369a0be2ead345e78933e2"
    assert PluginManifest.model_validate(legacy()).fingerprint() == expected


def test_scalar_api2_conversion_uses_v4_without_inventing_resources(tmp_path, monkeypatch):
    from craft_bridge.core.pipeline import inspect_file, preview
    from tests.helpers import ffx
    from tests.unit.test_plugin_catalog import package

    monkeypatch.setenv("CRAFT_BRIDGE_CONFIG", str(tmp_path / "config"))
    data = package()
    data["plugins"][0].update(api=2, bridge_host_revision=1)
    source = tmp_path / "package.json"
    source.write_text(json.dumps(data))
    Registry().install(source)
    preset = tmp_path / "original.ffx"
    preset.write_bytes(ffx([("Bridge Gain Probe", [("Bridge Gain Probe-0001", 2.0, 10)])]))
    output, _ = preview(inspect_file(preset))
    assert output["version"] == 4
    assert validate_plan(output).effects[0].properties[0].value == 2.0


def test_v4_plan_can_mix_legacy_and_experimental_plugins(tmp_path, monkeypatch):
    from tests.unit.test_plugin_catalog import package

    registry = install(tmp_path, monkeypatch)
    source = tmp_path / "legacy.json"
    source.write_text(json.dumps(package()))
    registry.install(source)
    plan = plan_for(registry)
    legacy = registry.plugins[package()["plugins"][0]["id"]]
    plan.effects.append(
        PlanEffect(
            ref="fx1",
            effect=legacy.id,
            source="original-legacy-probe",
            plugin_fingerprint=legacy.fingerprint(),
            properties=[PlanProperty(id="gain", kind="Float", value=1.0)],
        )
    )
    plan.commands = preview_commands(plan)
    assert len(validate_plan(plan.model_dump(mode="json"), registry).effects) == 2
