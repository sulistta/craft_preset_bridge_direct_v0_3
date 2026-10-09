"""Bounded declarative temporal requests; no Adobe maps or fixtures."""

import copy
import json

import pytest
from pydantic import ValidationError

from craft_bridge.core.models import Interpolation, Keyframe
from craft_bridge.core.safety import BridgeError
from craft_bridge.core.validation import validate_plan
from craft_bridge.exporters.effectcraft.exporter import (
    EffectCraftPlan,
    PlanEffect,
    PlanProperty,
    preview_commands,
)
from craft_bridge.mappings.plugins import PluginManifest
from craft_bridge.mappings.registry import Registry


def manifest():
    return {
        "api": 4,
        "bridge_host_revision": 3,
        "id": "org.craftbridge.test.temporal",
        "name": "Original temporal probe",
        "category": "Bridge Validation",
        "version": "0.1.0",
        "params": [
            {
                "id": "skip",
                "name": "Frames to skip",
                "type": "slider",
                "default": 0.0,
                "min": 0.0,
                "max": 1024.0,
            }
        ],
        "temporal_inputs": [{"id": "held", "mode": "frame_hold", "parameter": "skip"}],
    }


def install(tmp_path, monkeypatch):
    monkeypatch.setenv("CRAFT_BRIDGE_CONFIG", str(tmp_path / "config"))
    path = tmp_path / "package.json"
    path.write_text(
        json.dumps(
            {
                "format": "craftbridge.mappings",
                "version": 2,
                "name": "temporal-probe",
                "plugins": [manifest()],
                "mappings": [],
            }
        )
    )
    registry = Registry()
    registry.install(path)
    return registry


def plan_for(registry, value=2.0):
    definition = registry.plugins[manifest()["id"]]
    plan = EffectCraftPlan(
        version=4,
        name="Original temporal probe",
        catalog_commit=registry.catalog["effectcraft"]["commit"],
        source_sha256="0" * 64,
        effects=[
            PlanEffect(
                ref="fx0",
                effect=definition.id,
                source="original-synthetic",
                plugin_fingerprint=definition.fingerprint(),
                properties=[PlanProperty(id="skip", kind="Float", value=value)],
            )
        ],
    )
    plan.commands = preview_commands(plan)
    return plan


def test_roundtrip_preserves_temporal_declarations_and_fingerprint(tmp_path, monkeypatch):
    registry = install(tmp_path, monkeypatch)
    before = PluginManifest.model_validate(manifest())
    assert before.fingerprint() == registry.plugins[before.id].fingerprint()
    assert before.temporal_inputs[0].multiple == 1 and before.temporal_inputs[0].edge == "clamp"
    validate_plan(plan_for(registry).model_dump(mode="json"), registry)


@pytest.mark.parametrize(
    "fault",
    [
        "revision",
        "missing",
        "duplicate",
        "unknown_parameter",
        "range",
        "multiple",
        "bool_multiple",
        "unknown_field",
        "non_slider",
        "api3",
        "too_many",
    ],
)
def test_invalid_temporal_manifests_are_refused(fault):
    m = manifest()
    if fault == "revision":
        m["bridge_host_revision"] = 2
    elif fault == "missing":
        m.pop("temporal_inputs")
    elif fault == "duplicate":
        m["temporal_inputs"] *= 2
    elif fault == "unknown_parameter":
        m["temporal_inputs"][0]["parameter"] = "missing"
    elif fault == "range":
        m["params"][0]["max"] = 1025
    elif fault in ("multiple", "bool_multiple"):
        m["temporal_inputs"][0]["multiple"] = 2 if fault == "multiple" else True
    elif fault == "unknown_field":
        m["temporal_inputs"][0]["expression"] = "never execute"
    elif fault == "non_slider":
        m["params"][0] = {"id": "skip", "name": "Skip", "type": "angle", "default": 0.0}
    elif fault == "api3":
        m.update(api=3, bridge_host_revision=2)
    elif fault == "too_many":
        m["temporal_inputs"] = [dict(m["temporal_inputs"][0], id=str(i)) for i in range(5)]
    with pytest.raises((BridgeError, ValidationError)):
        PluginManifest.model_validate(m).specs()


def test_offsets_support_bounded_fractional_values_and_distinct_edges():
    for mode, limit in [("seconds_offset", 1000), ("frames_offset", 10000)]:
        m = manifest()
        m["params"][0].update(min=-limit, max=limit, default=-0.5)
        for edge in ["clamp", "wrap", "mirror"]:
            m["temporal_inputs"][0].update(mode=mode, multiple=16, edge=edge)
            assert PluginManifest.model_validate(m).specs()["skip"]["default"] == -0.5


def test_frame_hold_rejects_fractional_values_and_requires_integer_hold_animation(tmp_path, monkeypatch):
    registry = install(tmp_path, monkeypatch)
    with pytest.raises(BridgeError, match="inteiro"):
        validate_plan(plan_for(registry, 2.5).model_dump(mode="json"), registry)
    plan = plan_for(registry)
    p = plan.effects[0].properties[0]
    p.keyframes = [
        Keyframe(
            ticks=0, time_base=30, value=2.0, in_interp=[Interpolation.HOLD], out_interp=[Interpolation.HOLD]
        ),
        Keyframe(
            ticks=30, time_base=30, value=3.0, in_interp=[Interpolation.HOLD], out_interp=[Interpolation.HOLD]
        ),
    ]
    plan.commands = preview_commands(plan)
    validate_plan(plan.model_dump(mode="json"), registry)
    bad = copy.deepcopy(plan)
    bad.effects[0].properties[0].keyframes[1].value = 3.5
    bad.commands = preview_commands(bad)
    with pytest.raises(BridgeError, match="inteiros"):
        validate_plan(bad.model_dump(mode="json"), registry)
    p.keyframes[0].out_interp = [Interpolation.LINEAR]
    plan.commands = preview_commands(plan)
    with pytest.raises(BridgeError, match="Hold"):
        validate_plan(plan.model_dump(mode="json"), registry)
