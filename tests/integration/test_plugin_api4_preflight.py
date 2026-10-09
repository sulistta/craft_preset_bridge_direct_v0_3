"""Refuse unproven or different temporal host declarations before mutation."""

import pytest

from craft_bridge.core.safety import BridgeError
from craft_bridge.integrations.effectcraft import apply_plan
from craft_bridge.mappings.plugins import PluginManifest
from tests.integration.test_control import server
from tests.integration.test_layer_resources import response_for
from tests.unit.test_plugin_api4 import install, manifest, plan_for


def respond(fault=None):
    m = PluginManifest.model_validate(manifest())
    listing = {
        "api": 1,
        "apis": [1, 2, 3, 4],
        "wasm": True,
        "bridge_host": {
            "revision": 3,
            "revisions": [1, 2, 3],
            "layer_inputs": 4,
            "layer_timing": True,
            "temporal_sampling": True,
            "temporal_inputs": 4,
        },
        "plugins": [
            {
                "id": m.id,
                "api": 4,
                "version": m.version,
                "params": [p.id for p in m.params],
                "temporal_inputs": [r.model_dump() for r in m.temporal_inputs],
            }
        ],
    }
    host = listing["bridge_host"]
    if fault in ("sampling", "timing"):
        host["temporal_sampling" if fault == "sampling" else "layer_timing"] = False
    elif fault == "revision":
        host.update(revision=2, revisions=[1, 2])
    elif fault == "history":
        host["revisions"] = [3]
    elif fault == "limit":
        host["temporal_inputs"] = 3
    elif fault == "bool_limit":
        host["temporal_inputs"] = True
    elif fault == "api":
        listing["apis"] = [1, 2, 3]
    elif fault == "missing":
        listing["plugins"][0].pop("temporal_inputs")
    elif fault in ("declaration", "bool_multiple"):
        listing["plugins"][0]["temporal_inputs"][0]["multiple"] = 2 if fault == "declaration" else True
    base = response_for()
    values = {"skip": 0.0}

    def reply(request):
        command, params = request["params"]["command"], request["params"]["params"]
        if command == "effect.plugins.list":
            return listing
        if command == "effect.list":
            return [{"id": m.id, "params": [{"id": "skip", "default": 0.0}]}]
        if command == "effect.apply":
            return {"effects": [91], "paths": ["effects/#1"]}
        if command == "prop.set":
            values["skip"] = params["value"]
            return {"path": params["path"], "value": params["value"]}
        if command == "prop.get" and params["path"].endswith("/skip"):
            return {"value": values["skip"], "animated": False, "expression": None}
        return base(request)

    return reply


@pytest.mark.parametrize(
    "fault",
    [
        "sampling",
        "timing",
        "revision",
        "history",
        "limit",
        "bool_limit",
        "api",
        "missing",
        "declaration",
        "bool_multiple",
    ],
)
def test_unproven_temporal_sampling_never_mutates(tmp_path, monkeypatch, fault):
    registry = install(tmp_path, monkeypatch)
    with server(respond(fault)) as (port, requests):
        with pytest.raises(BridgeError):
            apply_plan(plan_for(registry), layer="Target", port=port, confirmed=True)
    assert not any(r["params"]["command"] in ("effect.apply", "prop.set", "prop.addKey") for r in requests)


def test_revision3_temporal_plan_is_applied(tmp_path, monkeypatch):
    registry = install(tmp_path, monkeypatch)
    with server(respond()) as (port, requests):
        result = apply_plan(plan_for(registry), layer="Target", port=port, confirmed=True)
    assert result["bindings"]["fx0"] and any(r["params"]["command"] == "prop.set" for r in requests)
