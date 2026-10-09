import copy

import pytest

from craft_bridge.core.safety import BridgeError
from craft_bridge.core.validation import validate_plan
from craft_bridge.integrations.control import ControlClient
from craft_bridge.integrations.effectcraft import apply_plan, preflight
from tests.integration.test_control import responder, server
from tests.unit.test_plugin_catalog import manifest, plugin_plan


def plugin_responder(fault=None):
    definition = manifest()
    listing = {"api": 1, "wasm": True, "plugins": [{
        "id": definition["id"], "version": definition["version"],
        "params": [p["id"] for p in definition["params"]],
    }]}
    catalog = [{"id": definition["id"], "params": [{"id": p["id"], "default": p["default"]} for p in definition["params"]]}]
    if fault == "api":
        listing["api"] = 2
    elif fault == "version":
        listing["plugins"][0]["version"] = "2.0"
    elif fault == "missing":
        listing["plugins"] = []
    elif fault == "duplicate":
        listing["plugins"].append(copy.deepcopy(listing["plugins"][0]))
    elif fault == "params":
        listing["plugins"][0]["params"] = ["other"]
    elif fault == "defaults":
        catalog[0]["params"][0]["default"] = 0.5
    elif fault == "duplicate_catalog":
        catalog.append(copy.deepcopy(catalog[0]))

    def reply(request):
        command = request["params"]["command"]
        if command == "effect.plugins.list":
            return listing
        if command == "effect.list":
            return catalog
        return responder(request)
    return reply


@pytest.mark.parametrize("fault", ["api", "version", "missing", "duplicate", "params", "defaults", "duplicate_catalog"])
def test_mismatched_runtime_plugin_is_refused_before_any_mutation(tmp_path, monkeypatch, fault):
    plan = validate_plan(plugin_plan(tmp_path, monkeypatch))
    with server(plugin_responder(fault)) as (port, requests):
        with pytest.raises(BridgeError):
            apply_plan(plan, layer="#1", port=port, confirmed=True)
    assert not any(r["params"]["command"] in ("effect.apply", "prop.set", "prop.addKey") for r in requests)


def test_matching_runtime_plugin_passes_readonly_preflight(tmp_path, monkeypatch):
    plan = validate_plan(plugin_plan(tmp_path, monkeypatch))
    with server(plugin_responder()) as (port, requests), ControlClient(port) as client:
        result = preflight(client, plan, "#1", None)
    assert result["layer"] == 17
    assert any(r["params"]["command"] == "effect.plugins.list" for r in requests)
