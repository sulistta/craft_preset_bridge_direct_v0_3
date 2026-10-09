import json
import socket
import socketserver
import threading
import time
from contextlib import contextmanager

import pytest

from craft_bridge.core.pipeline import inspect_file, preview
from craft_bridge.core.safety import BridgeError
from craft_bridge.core.validation import validate_plan
from craft_bridge.integrations.control import ControlClient
from craft_bridge.integrations.effectcraft import apply_plan


@contextmanager
def server(responder):
    requests = []

    class Handler(socketserver.StreamRequestHandler):
        def handle(self):
            for line in self.rfile:
                request = json.loads(line)
                requests.append(request)
                reply = responder(request)
                if reply is None:
                    return
                raw = (
                    reply
                    if isinstance(reply, bytes)
                    else json.dumps({"id": request["id"], "ok": True, "result": reply}).encode() + b"\n"
                )
                try:
                    self.wfile.write(raw)
                except (BrokenPipeError, ConnectionResetError):
                    return

    class Server(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
        daemon_threads = True

    app = Server(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=app.serve_forever, daemon=True)
    thread.start()
    try:
        yield app.server_address[1], requests
    finally:
        app.shutdown()
        app.server_close()
        thread.join()


def responder(req):
    command = req["params"]["command"]
    if command == "app.capabilities":
        return {"version": "test-only"}
    if command == "command.list":
        return [
            {"id": c}
            for c in [
                "effect.apply",
                "effect.toggle",
                "prop.set",
                "prop.addKey",
                "keys.select",
                "keys.interpolation",
                "keys.setEase",
            ]
        ]
    if command == "effect.list":
        return [{"id": "ec.blur.sharpen", "params": [{"id": "amount"}]}]
    if command == "layer.tree":
        return {"id": 17, "start": 0.0, "stretch": 100.0, "switches": {}}
    if command == "comp.info":
        return {"id": 3, "frameRate": 30.0}
    if command == "prop.get":
        return {"value": 15.0, "keys": []}
    if command == "effect.apply":
        return {"paths": ["effects/#7"], "effects": [321], "effect": "ec.blur.sharpen"}
    return True


def plan_for(ffx_file):
    return validate_plan(preview(inspect_file(ffx_file))[0])


def test_apply_resolves_returned_reference_and_comp(ffx_file):
    with server(responder) as (port, requests):
        result = apply_plan(plan_for(ffx_file), layer="#2", comp="Test", port=port, confirmed=True)
    assert result["bindings"]["fx0"]["path"] == "effects/#7"
    mutations = [r["params"] for r in requests if r["params"]["command"] == "prop.set"]
    assert mutations[0]["params"] == {
        "layer": "#2",
        "comp": "Test",
        "path": "effects/#7/amount",
        "value": 15.0,
    }


@pytest.mark.parametrize("invalid", [None, "wrong-effect", "wrong-index", "animated", "expression"])
def test_existing_effect_binding_preflight_and_application(ffx_file, invalid):
    from craft_bridge.exporters.effectcraft.exporter import preview_commands

    plan = plan_for(ffx_file)
    plan.effects[0].application = "existing"
    plan.effects[0].source_effect_index = 1
    plan.commands = preview_commands(plan)
    property_calls = 0

    def reply(req):
        nonlocal property_calls
        command = req["params"]["command"]
        if command == "layer.tree":
            return {
                **responder(req),
                "properties": {
                    "children": [
                        {
                            "match": "effects",
                            "children": [
                                {
                                    "effect": "ec.blur.sharpen"
                                    if invalid != "wrong-effect"
                                    else "ec.blur.gaussian",
                                    "path": "effects/#2" if invalid != "wrong-index" else "effects/#1",
                                    "uid": 741,
                                }
                            ],
                        }
                    ]
                },
            }
        if command == "prop.get":
            property_calls += 1
            if property_calls == 1 and invalid == "animated":
                return {"value": 4, "keys": [{"time": 0, "value": 4}]}
            if property_calls == 1 and invalid == "expression":
                return {"value": 4, "keys": [], "expression": "never execute this"}
            return {"value": 15, "keys": []}
        return responder(req)

    with server(reply) as (port, requests):
        if invalid is None:
            result = apply_plan(plan, layer="#1", port=port, confirmed=True)
            assert result["bindings"] == {"fx0": {"path": "effects/#2", "uid": 741}}
            assert property_calls == 2
        else:
            with pytest.raises(BridgeError):
                apply_plan(plan, layer="#1", port=port, confirmed=True)
    assert not any(
        r["params"]["command"] in ("effect.apply", "bridge.bindExistingEffect", "effect.toggle")
        for r in requests
    )
    if invalid is not None:
        assert not any(r["params"]["command"] in ("prop.set", "prop.addKey") for r in requests)


def test_confirmation_and_dry_run_never_connect(ffx_file):
    plan = plan_for(ffx_file)
    with pytest.raises(BridgeError, match="confirmação"):
        apply_plan(plan, layer="#1", port=1)
    result = apply_plan(plan, layer="#1", port=1, dry_run=True)
    assert result["dry_run"] and result["commands"]


def test_preflight_rejects_unavailable_effect_before_mutating(ffx_file):
    def reply(r):
        return [] if r["params"]["command"] == "effect.list" else responder(r)

    with server(reply) as (port, requests):
        with pytest.raises(BridgeError):
            apply_plan(plan_for(ffx_file), layer="#1", port=port, confirmed=True)
    assert not any(r["params"]["command"] == "effect.apply" for r in requests)


def test_postcheck_detects_value_divergence_and_does_not_save(ffx_file, tmp_path):
    def reply(r):
        return {"value": 14.0, "keys": []} if r["params"]["command"] == "prop.get" else responder(r)

    with server(reply) as (port, requests):
        with pytest.raises(BridgeError, match="Valor retornado diverge"):
            apply_plan(
                plan_for(ffx_file),
                layer="#1",
                port=port,
                confirmed=True,
                save_project=tmp_path / "new.ecproj",
            )
    assert any(r["params"]["command"] == "prop.set" for r in requests)
    assert not any(r["params"]["command"] == "file.saveAs" for r in requests)


def test_preflight_rejects_frame_snapping_before_mutation(ffx_file):
    from craft_bridge.core.models import Keyframe
    from craft_bridge.exporters.effectcraft.exporter import preview_commands

    plan = plan_for(ffx_file)
    plan.effects[0].properties[0].keyframes = [
        Keyframe(ticks=1, time_base=100, value=15.0, in_interp=["Linear"], out_interp=["Linear"])
    ]
    plan.commands = preview_commands(plan)
    with server(responder) as (port, requests):
        with pytest.raises(BridgeError, match="arredondaria"):
            apply_plan(plan, layer="#1", port=port, confirmed=True)
    assert not any(r["params"]["command"] == "effect.apply" for r in requests)


def test_nearby_ntsc_rate_is_rejected_before_any_mutation(ffx_file):
    from craft_bridge.core.models import Keyframe
    from craft_bridge.exporters.effectcraft.exporter import preview_commands

    plan = plan_for(ffx_file)
    plan.effects[0].properties[0].keyframes = [
        Keyframe(ticks=5000, time_base=23976, value=15, in_interp=["Linear"], out_interp=["Linear"])
    ]
    plan.commands = preview_commands(plan)

    def reply(req):
        return (
            {"id": 3, "frameRate": 24000 / 1001}
            if req["params"]["command"] == "comp.info"
            else responder(req)
        )

    with server(reply) as (port, requests):
        with pytest.raises(BridgeError, match="arredondaria"):
            apply_plan(plan, layer="#1", port=port, confirmed=True)
    assert not any(r["params"]["command"] in ("effect.apply", "prop.set", "prop.addKey") for r in requests)


@pytest.mark.parametrize(
    "reply", [b"not json\n", b'{"id":999,"ok":true}\n', b'{"id":1,"ok":false,"error":"nope"}\n', b""]
)
def test_protocol_errors(reply):
    with server(lambda req: reply) as (port, _):
        with ControlClient(port) as client, pytest.raises(BridgeError):
            client.execute("test")


def test_timeout_and_connection_failure():
    def slow(req):
        time.sleep(0.1)
        return True

    with server(slow) as (port, _):
        with ControlClient(port, timeout=0.01) as client, pytest.raises(BridgeError, match="timeout"):
            client.execute("test")
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    unused = sock.getsockname()[1]
    sock.close()
    with pytest.raises(BridgeError):
        with ControlClient(unused):
            pass


def test_plan_refuses_existing_project_output(ffx_file, tmp_path):
    p = tmp_path / "existing.ecproj"
    p.write_text("old")
    with pytest.raises(BridgeError):
        apply_plan(plan_for(ffx_file), layer="#1", confirmed=True, save_project=p)
    assert p.read_text() == "old"


def test_filmcraft_import_is_explicit_and_uses_api(premiere_file, tmp_path):
    from craft_bridge.core.pipeline import convert_file
    from craft_bridge.integrations.filmcraft import import_presets

    out = tmp_path / "native.json"
    convert_file(premiere_file, out)
    assert import_presets(out, dry_run=True)["dry_run"]
    with pytest.raises(BridgeError):
        import_presets(out)
    with server(lambda req: {"imported": ["Blur original"]}) as (port, requests):
        result = import_presets(out, port=port, confirmed=True)
    assert requests[0]["params"]["command"] == "presets.import"
    assert result["imported"] == {"imported": ["Blur original"]}


@pytest.mark.parametrize("fault", [None, "missing-command", "activation-failed"])
def test_animated_plan_activates_target_after_preflight_before_mutation(ffx_file, fault):
    from craft_bridge.core.models import Keyframe
    from craft_bridge.exporters.effectcraft.exporter import preview_commands

    plan = plan_for(ffx_file)
    plan.effects[0].properties[0].keyframes = [
        Keyframe(ticks=0, time_base=30, value=15, in_interp=["Linear"], out_interp=["Linear"]),
        Keyframe(ticks=30, time_base=30, value=25, in_interp=["Linear"], out_interp=["Linear"]),
    ]
    plan.commands = preview_commands(plan)
    active = 4
    def reply(req):
        nonlocal active
        command, params = req["params"]["command"], req["params"]["params"]
        if command == "command.list":
            commands = responder(req)
            return commands + ([] if fault == "missing-command" else [{"id": "comp.open"}])
        if command == "comp.info":
            return {"id": 3 if params.get("comp") == "Target" else active, "frameRate": 30}
        if command == "comp.open":
            assert params == {"comp": 3}
            if fault != "activation-failed":
                active = 3
            return True
        if command == "prop.get":
            return {"value": 15, "keys": [{"time": 0, "value": 15, "in": "Linear", "out": "Linear"},
                                          {"time": 1, "value": 25, "in": "Linear", "out": "Linear"}]}
        if command in ("effect.apply", "prop.set", "prop.addKey", "keys.select", "keys.interpolation"):
            assert active == 3
        return responder(req)
    with server(reply) as (port, requests):
        if fault is None:
            result = apply_plan(plan, layer="#1", comp="Target", port=port, confirmed=True)
            assert result["preflight"]["activate_comp"] == 3
        else:
            with pytest.raises(BridgeError, match="composição|comp.open"):
                apply_plan(plan, layer="#1", comp="Target", port=port, confirmed=True)
    commands = [r["params"]["command"] for r in requests]
    if fault is None:
        assert commands.index("comp.open") < commands.index("effect.apply")
    else:
        assert not any(c in commands for c in ("effect.apply", "prop.set", "prop.addKey"))
    if fault == "missing-command":
        assert "comp.open" not in commands


def test_animation_dry_run_exposes_context_activation_without_connecting(ffx_file):
    from craft_bridge.core.models import Keyframe
    from craft_bridge.exporters.effectcraft.exporter import preview_commands

    plan = plan_for(ffx_file)
    plan.effects[0].properties[0].keyframes = [Keyframe(ticks=0, time_base=30, value=15, in_interp=["Linear"], out_interp=["Linear"])]
    plan.commands = preview_commands(plan)
    result = apply_plan(plan, layer="#1", comp="Target", port=1, dry_run=True)
    assert result["context_commands"][0]["params"]["comp"] == "Target"
