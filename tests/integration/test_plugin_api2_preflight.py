"""Runtime capability refusals before any mutation, using an original TCP peer."""

import copy

import pytest

from craft_bridge.core.safety import BridgeError
from craft_bridge.integrations.effectcraft import apply_plan
from tests.integration.test_control import server
from tests.integration.test_layer_resources import response_for
from tests.unit.test_plugin_api2 import install, manifest, plan_for


def reply_for(fault=None, uid=29, readback=None):
    definition = manifest()
    listing = {
        "api": 1,
        "apis": [1, 2],
        "wasm": True,
        "bridge_host": {"revision": 1, "layer_inputs": 4},
        "plugins": [
            {
                "id": definition["id"],
                "api": 2,
                "version": definition["version"],
                "params": [p["id"] for p in definition["params"]],
            }
        ],
    }
    catalog = [
        {
            "id": definition["id"],
            "params": [{"id": p["id"], "default": p["default"]} for p in definition["params"]],
        }
    ]
    if fault == "legacy":
        listing.pop("bridge_host")
        listing.pop("apis")
    elif fault == "host_missing":
        listing.pop("bridge_host")
    elif fault == "api_missing":
        listing["apis"] = [1]
    elif fault == "float_api":
        listing["apis"] = [1, 2.0]
    elif fault == "legacy_bool_api":
        listing["api"] = True
    elif fault == "float_plugin_api":
        listing["plugins"][0]["api"] = 2.0
    elif fault == "float_limit":
        listing["bridge_host"]["layer_inputs"] = 4.0
    elif fault == "bool_revision":
        listing["bridge_host"]["revision"] = True
    elif fault == "revision":
        listing["bridge_host"]["revision"] = 2
    elif fault == "layer_limit":
        listing["bridge_host"]["layer_inputs"] = 3
    elif fault == "wasm":
        listing["wasm"] = False
    elif fault == "plugin_api":
        listing["plugins"][0]["api"] = 1
    elif fault == "plugin_api_missing":
        listing["plugins"][0].pop("api")
    elif fault == "version":
        listing["plugins"][0]["version"] = "other"
    elif fault == "duplicate":
        listing["plugins"].append(copy.deepcopy(listing["plugins"][0]))
    elif fault == "null_missing":
        catalog[0]["params"][0].pop("default")
    elif fault == "default":
        catalog[0]["params"][0]["default"] = 0
    base = response_for(resolved=uid, members=[17, uid], readback=readback)
    values = {"source": None, "sourceSource": 0, "mix": 1.0}

    def respond(request):
        command, params = request["params"]["command"], request["params"]["params"]
        if command == "effect.plugins.list":
            return listing
        if command == "effect.list":
            return catalog
        if command == "prop.set":
            values[params["path"].rsplit("/", 1)[1]] = params["value"]
        if command == "prop.get" and params["path"].endswith("/source"):
            return base(request)
        if command == "prop.get":
            return {"value": values[params["path"].rsplit("/", 1)[1]], "keys": []}
        return base(request)

    return respond


@pytest.mark.parametrize(
    "fault",
    [
        "legacy",
        "host_missing",
        "api_missing",
        "float_api",
        "legacy_bool_api",
        "float_plugin_api",
        "float_limit",
        "bool_revision",
        "revision",
        "layer_limit",
        "wasm",
        "plugin_api",
        "plugin_api_missing",
        "version",
        "duplicate",
        "null_missing",
        "default",
    ],
)
def test_unproven_runtime_never_creates_or_writes(tmp_path, monkeypatch, fault):
    registry = install(tmp_path, monkeypatch)
    with server(reply_for(fault)) as (port, requests):
        with pytest.raises(BridgeError):
            apply_plan(
                plan_for(registry),
                layer="Target",
                layer_bindings={"second": "Resource"},
                port=port,
                confirmed=True,
            )
    assert not any(r["params"]["command"] in ("effect.apply", "prop.set", "prop.addKey") for r in requests)


def test_plugin_layer_binding_preserves_u64_and_never_sends_internal_commands(tmp_path, monkeypatch):
    registry = install(tmp_path, monkeypatch)
    uid = 2**63 + 17
    with server(reply_for(uid=uid)) as (port, requests):
        result = apply_plan(
            plan_for(registry),
            layer="Target",
            layer_bindings={"second": "Resource"},
            port=port,
            confirmed=True,
        )
    assert result["preflight"]["layer_resource_uids"] == {"second": uid}
    assert not any(r["params"]["command"].startswith("bridge.") for r in requests)
    writes = [r["params"]["params"] for r in requests if r["params"]["command"] == "prop.set"]
    assert writes[0] == {"layer": 17, "comp": 3, "path": "effects/#7/source", "value": uid}


def test_rounded_neighboring_plugin_layer_uid_is_not_accepted(tmp_path, monkeypatch):
    registry = install(tmp_path, monkeypatch)
    uid = 2**63 + 17
    with server(reply_for(uid=uid, readback=uid + 1)) as (port, _):
        with pytest.raises(BridgeError, match="diverge"):
            apply_plan(
                plan_for(registry),
                layer="Target",
                layer_bindings={"second": "Resource"},
                port=port,
                confirmed=True,
            )
