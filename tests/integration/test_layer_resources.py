"""Synthetic native layer plans and transport; no Adobe fixture assumptions."""

import json
import subprocess
import sys

import pytest

from craft_bridge.core.safety import BridgeError
from craft_bridge.core.validation import validate_plan
from craft_bridge.exporters.effectcraft.exporter import (
    EffectCraftPlan,
    LayerReference,
    PlanEffect,
    PlanProperty,
    preview_commands,
)
from craft_bridge.integrations.effectcraft import apply_plan
from craft_bridge.mappings.registry import Registry
from tests.integration.test_control import server


def layer_plan(value=None, version=4):
    if value is None:
        value = LayerReference(layer_ref="map")
    plan = EffectCraftPlan(version=version, name="Original synthetic layer test",
                           catalog_commit=Registry(packages=[]).catalog["effectcraft"]["commit"],
                           source_sha256="0" * 64, effects=[PlanEffect(ref="fx0", effect="ec.distort.displacementmap",
                           source="original-synthetic", properties=[PlanProperty(id="displacementMapLayer", kind="Layer", value=value)])])
    plan.commands = preview_commands(plan)
    return plan


@pytest.mark.parametrize("value", [0, 17, 1.5, True, "#2", [17]])
def test_raw_transport_ids_selectors_and_coercions_refused(value):
    with pytest.raises(BridgeError, match="referência simbólica"):
        validate_plan(layer_plan(value).model_dump(mode="json"))


def test_v4_and_static_native_only():
    with pytest.raises(BridgeError, match="v4"):
        validate_plan(layer_plan(version=3).model_dump(mode="json"))
    plan = layer_plan().model_dump(mode="json")
    plan["effects"][0]["properties"][0]["keyframes"] = [{"ticks": 0, "time_base": 30, "value": 17}]
    with pytest.raises(BridgeError, match="animação"):
        validate_plan(plan)
    plan = layer_plan().model_dump(mode="json")
    plan["effects"][0]["properties"][0]["value"] = {"layer_ref": "map", "uid": 17}
    with pytest.raises(BridgeError):
        validate_plan(plan)


def response_for(*, resolved=29, members=None, default=None, readback=None, current_type="layer", post_override=None):
    state = {"value": None, "written": False}
    members = [17, 29] if members is None else members

    def respond(request):
        command = request["params"]["command"]
        p = request["params"]["params"]
        if command == "command.list":
            return [{"id": c} for c in ("effect.apply", "prop.set", "prop.get", "layer.tree", "comp.info")]
        if command == "app.capabilities":
            return {}
        if command == "effect.list":
            return [{"id": "ec.distort.displacementmap", "params": [{"id": "displacementMapLayer", "default": default}]}]
        if command == "comp.info":
            return {"id": 3, "layers": [{"id": uid} for uid in members]}
        if command == "layer.tree":
            return {"id": 17 if p["layer"] == "Target" else resolved, "start": 0, "stretch": 100, "switches": {}}
        if command == "effect.apply":
            return {"paths": ["effects/#7"], "effects": [321]}
        if command == "prop.set":
            state.update(value=p["value"], written=True)
            return True
        if command == "prop.get":
            value = state["value"] if readback is None or not state["written"] else readback
            result = {"value": value, "keys": [], "type": current_type}
            if state["written"] and post_override is not None:
                result.update(post_override)
                if post_override.get("drop_value"):
                    del result["value"]
            return result
        raise AssertionError(command)
    return respond


def test_layer_is_resolved_to_exact_uid_and_target_context_is_pinned():
    plan = validate_plan(layer_plan().model_dump(mode="json"))
    with server(response_for()) as (port, requests):
        result = apply_plan(plan, layer="Target", comp="Comp", layer_bindings={"map": "Map"}, port=port, confirmed=True)
    assert result["preflight"]["layer_resource_uids"] == {"map": 29}
    sets = [r["params"]["params"] for r in requests if r["params"]["command"] == "prop.set"]
    assert sets == [{"layer": 17, "comp": 3, "path": "effects/#7/displacementMapLayer", "value": 29}]
    commands = [r["params"]["command"] for r in requests]
    assert commands.index("layer.tree") < commands.index("effect.apply")
    assert all(r["params"]["command"] != "bridge.resolveLayer" for r in requests)


@pytest.mark.parametrize("bindings", [{}, {"map": "Map", "extra": "Map"}, {"map": ""}, {"map": 29}, {"map": "a\0b"}])
def test_binding_errors_refused_without_connecting(bindings):
    with server(response_for()) as (port, requests):
        with pytest.raises(BridgeError):
            apply_plan(layer_plan(), layer="Target", layer_bindings=bindings, port=port, confirmed=True)
    assert requests == []


@pytest.mark.parametrize("kwargs", [
    {"resolved": 17}, {"resolved": 99}, {"resolved": True}, {"resolved": 29.},
    {"members": [17, 17, 29]}, {"members": [17, True]}, {"default": 0},
])
def test_invalid_resolution_and_catalog_refused_before_mutation(kwargs):
    with server(response_for(**kwargs)) as (port, requests):
        with pytest.raises(BridgeError):
            apply_plan(layer_plan(), layer="Target", layer_bindings={"map": "Map"}, port=port, confirmed=True)
    assert not any(r["params"]["command"] in ("effect.apply", "prop.set") for r in requests)


def test_wrong_native_property_type_never_writes_a_layer():
    with server(response_for(current_type="float")) as (port, requests):
        with pytest.raises(BridgeError, match="tipada"):
            apply_plan(layer_plan(), layer="Target", layer_bindings={"map": "Map"}, port=port, confirmed=True)
    assert not any(r["params"]["command"] == "prop.set" for r in requests)


def test_large_uid_comparison_does_not_round_neighboring_integers():
    uid = 2**63 + 1
    with server(response_for(resolved=uid, members=[17, uid], readback=uid + 1)) as (port, _):
        with pytest.raises(BridgeError, match="diverge"):
            apply_plan(layer_plan(), layer="Target", layer_bindings={"map": "Map"}, port=port, confirmed=True)


@pytest.mark.parametrize("post", [
    {"type": "float"}, {"keys": [{"time": 0}]}, {"expression": "unexecuted text"},
    {"value": True}, {"value": 29.0}, {"value": None}, {"drop_value": True},
])
def test_corrupt_layer_readback_is_reported_as_partial_mutation(post):
    with server(response_for(post_override=post)) as (port, _):
        with pytest.raises(BridgeError, match="mudanças parciais"):
            apply_plan(layer_plan(), layer="Target", layer_bindings={"map": "Map"}, port=port, confirmed=True)


def test_null_unbind_does_not_accept_a_missing_value_field():
    with server(response_for(post_override={"drop_value": True})) as (port, _):
        with pytest.raises(BridgeError, match="diverge"):
            apply_plan(layer_plan(LayerReference(layer_ref=None)), layer="Target", port=port, confirmed=True)


def test_explicit_null_unbind_and_dry_run():
    plan = layer_plan(LayerReference(layer_ref=None))
    with server(response_for()) as (port, requests):
        result = apply_plan(plan, layer="Target", port=port, confirmed=True)
    assert result["preflight"]["layer_resource_uids"] == {}
    assert next(r for r in requests if r["params"]["command"] == "prop.set")["params"]["params"]["value"] is None
    dry = apply_plan(layer_plan(), layer="Target", layer_bindings={"map": "#2"}, dry_run=True)
    assert dry["layer_bindings_resolved"] is False
    assert dry["commands"][0]["command"] == "bridge.resolveLayer"


def test_cli_binding_preview_and_duplicate_refusal(tmp_path):
    path = tmp_path / "original-synthetic.json"
    path.write_text(layer_plan().model_dump_json())
    cmd = [sys.executable, "-m", "craft_bridge", "apply", str(path), "--layer", "Target", "--dry-run"]
    success = subprocess.run([*cmd, "--bind-layer", "map=#2"], capture_output=True, text=True, check=True)
    assert json.loads(success.stdout)["layer_bindings"] == {"map": "#2"}
    duplicate = subprocess.run([*cmd, "--bind-layer", "map=#2", "--bind-layer", "map=#3"], capture_output=True, text=True)
    assert duplicate.returncode != 0 and "únicas" in duplicate.stderr
