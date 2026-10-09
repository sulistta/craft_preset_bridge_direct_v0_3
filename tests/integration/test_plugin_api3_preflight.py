"""Original runtime capability cases for API 3 plus revision-1 compatibility."""

import json

import pytest

from craft_bridge.core.safety import BridgeError
from craft_bridge.integrations.effectcraft import apply_plan
from craft_bridge.mappings.registry import Registry
from tests.integration.test_control import server
from tests.integration.test_plugin_api2_preflight import reply_for
from tests.unit.test_plugin_api2 import manifest, plan_for


def install(tmp_path, monkeypatch, api):
    monkeypatch.setenv("CRAFT_BRIDGE_CONFIG", str(tmp_path / "config"))
    definition = manifest()
    definition.update(api=api, bridge_host_revision=2 if api == 3 else 1)
    data = {
        "format": "craftbridge.mappings",
        "version": 2,
        "name": "timing-probe",
        "plugins": [definition],
        "mappings": [],
    }
    path = tmp_path / "package.json"
    path.write_text(json.dumps(data))
    registry = Registry()
    registry.install(path)
    return registry


def respond(api=3, fault=None):
    base = reply_for()

    def reply(request):
        result = base(request)
        if request["params"]["command"] == "effect.plugins.list":
            result["apis"] = [1, 2, 3]
            result["plugins"][0]["api"] = api
            result["bridge_host"] = {
                "revision": 2,
                "revisions": [1, 2],
                "layer_inputs": 4,
                "layer_timing": True,
            }
            host = result["bridge_host"]
            if fault == "api":
                result["apis"] = [1, 2]
            elif fault == "plugin_api":
                result["plugins"][0]["api"] = 2
            elif fault == "timing_missing":
                host.pop("layer_timing")
            elif fault == "timing_false":
                host["layer_timing"] = False
            elif fault == "timing_integer":
                host["layer_timing"] = 1
            elif fault == "revision1":
                host["revision"] = 1
            elif fault == "revisions_missing":
                host.pop("revisions")
            elif fault == "revisions_bool":
                host["revisions"] = [True, 2]
            elif fault == "revision_unknown":
                host["revision"] = 3
            elif fault == "missing_legacy_revision":
                host["revisions"] = [2]
        return result

    return reply


@pytest.mark.parametrize(
    "fault",
    [
        "api",
        "plugin_api",
        "timing_missing",
        "timing_false",
        "timing_integer",
        "revision1",
        "revisions_missing",
        "revisions_bool",
        "revision_unknown",
        "missing_legacy_revision",
    ],
)
def test_unproven_timing_never_mutates(tmp_path, monkeypatch, fault):
    registry = install(tmp_path, monkeypatch, 3)
    with server(respond(fault=fault)) as (port, requests):
        with pytest.raises(BridgeError):
            apply_plan(
                plan_for(registry),
                layer="Target",
                layer_bindings={"second": "Resource"},
                port=port,
                confirmed=True,
            )
    assert not any(r["params"]["command"] in ("effect.apply", "prop.set", "prop.addKey") for r in requests)


@pytest.mark.parametrize("api", [2, 3])
def test_revision2_explicitly_supports_legacy_and_timing_contracts(tmp_path, monkeypatch, api):
    registry = install(tmp_path, monkeypatch, api)
    with server(respond(api)) as (port, requests):
        result = apply_plan(
            plan_for(registry),
            layer="Target",
            layer_bindings={"second": "Resource"},
            port=port,
            confirmed=True,
        )
    assert result["bindings"]["fx0"] and any(r["params"]["command"] == "prop.set" for r in requests)
