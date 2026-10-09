"""Aplica apenas planos tipados, usando paths/UIDs retornados por effect.apply."""

import math
import re
from pathlib import Path

from pydantic import ValidationError

from craft_bridge.core.safety import BridgeError, Limits, read_bounded
from craft_bridge.core.validation import validate_plan
from craft_bridge.exporters.effectcraft.exporter import (
    EffectCraftPlan,
    LayerReference,
    layer_references,
    preview_commands,
)
from craft_bridge.integrations.control import ControlClient
from craft_bridge.mappings.plugins import TemporalInput
from craft_bridge.mappings.registry import Registry


def _matches(actual, expected) -> bool:
    if isinstance(expected, bool):
        return actual is expected
    if isinstance(expected, (int, float)):
        return (
            not isinstance(actual, bool)
            and isinstance(actual, (int, float))
            and math.isclose(actual, expected, rel_tol=1e-7, abs_tol=1e-7)
        )
    if isinstance(expected, list):
        return (
            isinstance(actual, list)
            and len(actual) == len(expected)
            and all(_matches(a, b) for a, b in zip(actual, expected, strict=True))
        )
    return actual == expected


def _time_matches(actual: float, expected: float) -> bool:
    # Native Tick resolution is 1 / 254016000000 s. Compare times separately
    # from parameter values: a tolerance in frames admits nearby NTSC rates.
    return math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-9)


def load_plan(path: str | Path) -> EffectCraftPlan:
    import json

    try:
        data = json.loads(read_bounded(Path(path), Limits()))
    except ValueError as exc:
        raise BridgeError(f"Plano JSON inválido: {exc}") from exc
    return validate_plan(data)


def checked_layer_bindings(plan: EffectCraftPlan, bindings: dict[str, str] | None) -> dict[str, str]:
    bindings = {} if bindings is None else bindings
    if not isinstance(bindings, dict) or len(bindings) > 64 or any(
        not isinstance(key, str) or not isinstance(value, str) or not value.strip()
        or len(value.encode("utf-8")) > 256 or "\x00" in value
        for key, value in bindings.items()
    ):
        raise BridgeError("Vínculos Layer exigem até 64 seletores não vazios, UTF-8 de até 256 bytes sem NUL.")
    required = layer_references(plan)
    if required != set(bindings):
        raise BridgeError(f"Vínculos Layer divergentes: faltam {sorted(required - set(bindings))}; extras {sorted(set(bindings) - required)}.")
    return bindings.copy()


def preflight(client: ControlClient, plan: EffectCraftPlan, layer: str | int, comp: str | int | None,
              layer_bindings: dict[str, str] | None = None) -> dict:
    layer_bindings = checked_layer_bindings(plan, layer_bindings)
    capabilities = client.execute("app.capabilities")
    commands = client.execute("command.list", {"schemas": True})
    ids = {c.get("id") for c in commands if isinstance(c, dict)} if isinstance(commands, list) else set()
    required = {c["command"] for c in plan.commands} - {"bridge.bindExistingEffect", "bridge.resolveLayer"}
    has_layers = any(p.kind == "Layer" for e in plan.effects for p in e.properties)
    if has_layers:
        required |= {"layer.tree", "comp.info", "prop.get"}
    if required - ids:
        raise BridgeError(f"Aplicativo não oferece comandos: {sorted(required - ids)}")
    catalog = client.execute("effect.list")
    registry = Registry()
    if any(e.plugin_fingerprint is not None for e in plan.effects):
        listing = client.execute("effect.plugins.list")
        if not isinstance(listing, dict) or type(listing.get("api")) is not int or listing["api"] != 1 or not isinstance(listing.get("plugins"), list):
            raise BridgeError("Catálogo conectado não oferece a API de plugins v1.")
        for effect in plan.effects:
            if effect.plugin_fingerprint is None:
                continue
            manifest = registry.plugins.get(effect.effect)
            if manifest is None or manifest.fingerprint() != effect.plugin_fingerprint:
                raise BridgeError("Manifesto de plugin mudou antes da aplicação.")
            if manifest.api >= 2:
                apis, host = listing.get("apis"), listing.get("bridge_host")
                revision_ok = (isinstance(host, dict) and type(host.get("revision")) is int
                    and (host["revision"] == 1 and manifest.bridge_host_revision == 1
                         or host["revision"] in (2, 3) and isinstance(host.get("revisions"), list)
                         and all(type(v) is int for v in host["revisions"])
                         and host["revisions"] == list(range(1, host["revision"] + 1))
                         and manifest.bridge_host_revision in host["revisions"]))
                if (not isinstance(apis, list) or any(type(v) is not int for v in apis) or manifest.api not in apis
                    or not isinstance(host, dict) or type(host.get("revision")) is not int
                    or not revision_ok
                    or type(host.get("layer_inputs")) is not int or host["layer_inputs"] != 4
                    or manifest.api >= 3 and host.get("layer_timing") is not True
                    or manifest.api == 4 and (host.get("temporal_sampling") is not True
                        or type(host.get("temporal_inputs")) is not int or host["temporal_inputs"] != 4)
                    or listing.get("wasm") is not True):
                    raise BridgeError(f"Host conectado não comprova API {manifest.api} experimental/revisão {manifest.bridge_host_revision}, recursos e contexto exigidos.")
            matches = [p for p in listing["plugins"] if isinstance(p, dict) and p.get("id") == effect.effect]
            native = [p for p in catalog if isinstance(p, dict) and p.get("id") == effect.effect] if isinstance(catalog, list) else []
            if len(matches) != 1 or matches[0].get("version") != manifest.version or matches[0].get("params") != [p.id for p in manifest.params] or len(native) != 1:
                raise BridgeError("Plugin ausente ou versão/parâmetros diferentes do manifesto instalado.")
            if (manifest.api >= 2 or "api" in matches[0]) and (type(matches[0].get("api")) is not int or matches[0]["api"] != manifest.api):
                raise BridgeError("Versão de API do plugin carregado diverge do manifesto instalado.")
            if manifest.api == 4:
                try:
                    raw_requests = matches[0].get("temporal_inputs")
                    if not isinstance(raw_requests, list):
                        raise BridgeError("Host não comprova as entradas temporais do módulo carregado.")
                    actual_requests = [TemporalInput.model_validate(r) for r in raw_requests]
                except ValidationError as error:
                    raise BridgeError("Declaração temporal carregada inválida.") from error
                if actual_requests != manifest.temporal_inputs:
                    raise BridgeError("Entradas temporais carregadas divergem do manifesto instalado.")
            params = native[0].get("params")
            specs = manifest.specs()
            if not isinstance(params, list) or len(params) != len(specs) or any(
                not isinstance(p, dict) or p.get("id") != expected.id or "default" not in p
                or not _matches(p.get("default"), specs[expected.id]["default"])
                for p, expected in zip(params, manifest.params, strict=True)
            ):
                raise BridgeError("Defaults nativos do plugin divergem do manifesto instalado.")
    catalog_ids = (
        {c.get("id") for c in catalog if isinstance(c, dict)} if isinstance(catalog, list) else set()
    )
    if {e.effect for e in plan.effects} - catalog_ids:
        raise BridgeError("Efeitos do plano ausentes no aplicativo conectado.")
    available = {
        e["id"]: {p.get("id") for p in e.get("params", []) if isinstance(p, dict)}
        for e in catalog
        if isinstance(e, dict) and isinstance(e.get("params"), list)
    }
    for effect in plan.effects:
        if {p.id for p in effect.properties} - available.get(effect.effect, set()):
            raise BridgeError("Parâmetros do plano ausentes no catálogo conectado.")
    target = {"layer": layer, **({"comp": comp} if comp else {})}
    tree = client.execute("layer.tree", {**target, "depth": 2})
    info = client.execute("comp.info", {"comp": comp} if comp else {})
    if not isinstance(tree, dict) or not isinstance(info, dict):
        raise BridgeError("Consulta de camada/composição inválida.")
    resource_uids: dict[str, int] = {}
    resource_target = None
    if has_layers:
        # Native Value::Layer.coerce_json accepts invalid strings as None.
        # Never send a symbolic selector/raw transport UID to that coercion.
        cid, lid = info.get("id"), tree.get("id")
        if any(isinstance(v, bool) or not isinstance(v, int) or not 0 < v <= 0xFFFFFFFFFFFFFFFF for v in (cid, lid)):
            raise BridgeError("UID de composição/camada inválido para recursos Layer.")
        members = info.get("layers")
        if not isinstance(members, list) or any(not isinstance(m, dict) for m in members):
            raise BridgeError("Lista de camadas da composição ausente para conferir recursos.")
        member_ids = [m.get("id") for m in members]
        if any(isinstance(v, bool) or not isinstance(v, int) or not 0 < v <= 0xFFFFFFFFFFFFFFFF for v in member_ids) or len(set(member_ids)) != len(member_ids) or lid not in member_ids:
            raise BridgeError("Camadas da composição inválidas ou destino fora da composição.")
        resource_target = {"comp": cid, "layer": lid}
        for ref, selector in layer_bindings.items():
            resource = client.execute("layer.tree", {"comp": cid, "layer": selector, "depth": 0})
            uid = resource.get("id") if isinstance(resource, dict) else None
            if isinstance(uid, bool) or not isinstance(uid, int) or uid not in member_ids:
                raise BridgeError(f"Layer {ref} não resolve uma camada da composição de destino.")
            if uid == lid:
                raise BridgeError(f"Layer {ref} referencia a própria camada; o host nativo não oferece essa leitura recursiva.")
            resource_uids[ref] = uid
        for effect in plan.effects:
            matches_native = [e for e in catalog if isinstance(e, dict) and e.get("id") == effect.effect]
            if len(matches_native) != 1:
                raise BridgeError("Catálogo conectado contém efeito Layer ambíguo.")
            connected_params = matches_native[0].get("params")
            if not isinstance(connected_params, list) or any(not isinstance(p, dict) for p in connected_params):
                raise BridgeError("Catálogo de parâmetros Layer inválido.")
            for prop in effect.properties:
                if prop.kind == "Layer":
                    native_props = [p for p in connected_params if p.get("id") == prop.id]
                    if len(native_props) != 1 or "default" not in native_props[0] or native_props[0]["default"] is not None:
                        raise BridgeError("Default conectado não corresponde ao tipo Layer nativo verificado.")
    existing = {}
    activate_comp = None
    if any(e.application == "existing" for e in plan.effects):
        properties = tree.get("properties")
        groups = properties.get("children") if isinstance(properties, dict) else None
        if not isinstance(groups, list) or any(not isinstance(g, dict) for g in groups):
            raise BridgeError("Árvore de efeitos existentes inválida.")
        effect_groups = [g for g in groups if g.get("match") == "effects"]
        effects: list[dict] | None = effect_groups[0].get("children") if len(effect_groups) == 1 else None
        if not isinstance(effects, list) or any(not isinstance(e, dict) for e in effects):
            raise BridgeError("Lista de efeitos existentes ausente ou ambígua.")
        for effect in plan.effects:
            if effect.application != "existing":
                continue
            prefix = (
                f"effects/#{effect.source_effect_index + 1}" if effect.source_effect_index is not None else ""
            )
            matches = [e for e in effects if e.get("path") == prefix and e.get("effect") == effect.effect]
            if (
                len(matches) != 1
                or not isinstance(matches[0].get("uid"), int)
                or isinstance(matches[0]["uid"], bool)
                or matches[0]["uid"] <= 0
            ):
                raise BridgeError(
                    f"Propriedades selecionadas exigem {effect.effect} na posição {effect.source_effect_index} (índice de origem, começa em zero). Nenhum efeito será criado."
                )
            existing[effect.ref] = {"path": prefix, "uid": matches[0]["uid"]}
            for prop in effect.properties:
                actual = client.execute("prop.get", {**target, "path": prefix + "/" + prop.id})
                if (
                    not isinstance(actual, dict)
                    or not isinstance(actual.get("keys"), list)
                    or actual["keys"]
                    or actual.get("expression")
                ):
                    raise BridgeError(
                        "Propriedade existente animada/com expressão: substituição ainda não validada; aplicação recusada antes de mutação."
                    )
                if prop.kind == "Layer" and actual.get("type") != "layer":
                    raise BridgeError("Propriedade existente não tem tipo Layer na engine; aplicação recusada antes de mutação.")
    if any(p.keyframes for e in plan.effects for p in e.properties):
        # keys.select/interpolation operate on active_comp, ignoring a comp field.
        # Resolve context before mutation rather than selecting keys in another comp.
        active = client.execute("comp.info")
        if (
            not isinstance(active, dict)
            or not isinstance(active.get("id"), int)
            or isinstance(active["id"], bool)
            or not isinstance(info.get("id"), int)
            or isinstance(info["id"], bool)
        ):
            raise BridgeError("Não foi possível conferir a composição ativa para os keyframes.")
        if active["id"] != info["id"]:
            if "comp.open" not in ids:
                raise BridgeError("Ative a composição de destino: a API não oferece comp.open para aplicar os keyframes nela.")
            activate_comp = info["id"]
        start, stretch, fps = tree.get("start"), tree.get("stretch"), info.get("frameRate")
        if not (
            isinstance(start, (int, float))
            and isinstance(stretch, (int, float))
            and isinstance(fps, (int, float))
        ):
            raise BridgeError("Metadados temporais do destino inválidos.")
        if not all(math.isfinite(v) for v in (start, stretch, fps)):
            raise BridgeError("Metadados temporais do destino inválidos.")
        start, stretch, fps = float(start), float(stretch), float(fps)
        if stretch <= 0 or fps <= 0:
            raise BridgeError("Metadados temporais do destino inválidos.")
        for effect in plan.effects:
            for prop in effect.properties:
                for key in prop.keyframes:
                    frame = (start + key.seconds * stretch / 100) * fps
                    if not math.isfinite(frame) or not _time_matches(
                        (round(frame) / fps - start) * 100 / stretch, key.seconds
                    ):
                        raise BridgeError(
                            "O destino arredondaria um keyframe para outro frame; escolha uma composição compatível."
                        )
        if tree.get("switches", {}).get("time_remap", False):
            raise BridgeError("Time remapping do destino não suportado.")
    return {
        "capabilities": capabilities,
        "layer": tree.get("id"),
        "comp": info.get("id"),
        "existing_bindings": existing,
        "activate_comp": activate_comp,
        "layer_resource_uids": resource_uids,
        "layer_resource_target": resource_target,
    }


def apply_plan(
    plan: EffectCraftPlan,
    *,
    layer: str | int,
    comp: str | int | None = None,
    port: int = 9877,
    timeout: float = 10,
    confirmed: bool = False,
    dry_run: bool = False,
    save_project: str | Path | None = None,
    layer_bindings: dict[str, str] | None = None,
) -> dict:
    validate_plan(plan.model_dump(mode="json"))
    layer_bindings = checked_layer_bindings(plan, layer_bindings)
    if dry_run:
        return {
            "dry_run": True,
            "commands": preview_commands(plan),
            "layer": layer,
            "comp": comp,
            "save_project": str(save_project) if save_project else None,
            "layer_bindings": layer_bindings,
            "layer_bindings_resolved": False,
            "context_commands": ([{"command": "comp.open", "params": {"comp": comp or "$activeComp"},
                                   "when": "destino diferente da composição ativa"}]
                                 if any(p.keyframes for e in plan.effects for p in e.properties) else []),
        }
    if not confirmed:
        raise BridgeError("Aplicação requer confirmação explícita (--yes ou confirmação da interface).")
    if save_project:
        save_project = Path(save_project).resolve()
        if save_project.suffix.lower() != ".ecproj" or save_project.exists():
            raise BridgeError("Escolha um caminho .ecproj novo para salvar pela engine.")
    with ControlClient(port, timeout) as client:
        discovered = preflight(client, plan, layer, comp, layer_bindings)
        if discovered["activate_comp"] is not None:
            client.execute("comp.open", {"comp": discovered["activate_comp"]})
            active = client.execute("comp.info")
            if not isinstance(active, dict) or active.get("id") != discovered["activate_comp"]:
                raise BridgeError("A engine não ativou a composição de destino; efeitos e propriedades não foram aplicados.")
        target = discovered["layer_resource_target"] or {"layer": layer, **({"comp": comp} if comp else {})}
        bindings = {}
        for effect in plan.effects:
            result = (
                {
                    "paths": [discovered["existing_bindings"][effect.ref]["path"]],
                    "effects": [discovered["existing_bindings"][effect.ref]["uid"]],
                }
                if effect.application == "existing"
                else client.execute("effect.apply", {**target, "effect": effect.effect})
            )
            if (
                not isinstance(result, dict)
                or not isinstance(result.get("paths"), list)
                or len(result["paths"]) != 1
                or not isinstance(result.get("effects"), list)
                or len(result["effects"]) != 1
                or not isinstance(result["effects"][0], int)
                or isinstance(result["effects"][0], bool)
                or result["effects"][0] <= 0
                or not isinstance(result["paths"][0], str)
                or not re.fullmatch(r"effects/#[1-9][0-9]*", result["paths"][0])
            ):
                raise BridgeError(
                    "effect.apply não retornou path/UID único; efeito pode ter sido criado. Operação interrompida."
                )
            prefix, uid = result["paths"][0], result["effects"][0]
            bindings[effect.ref] = {"path": prefix, "uid": uid}
            if not effect.enabled and effect.application == "create":
                client.execute("effect.toggle", {**target, "effect": uid, "value": False})
            for prop in effect.properties:
                base = {**target, "path": prefix + "/" + prop.id}
                if prop.kind == "Layer":
                    current = client.execute("prop.get", base)
                    if not isinstance(current, dict) or current.get("type") != "layer" or current.get("keys") != [] or current.get("expression"):
                        raise BridgeError("Propriedade Layer não é estática/tipada na engine; vínculo não foi alterado. Um efeito recém-criado pode permanecer no projeto.")
                value = (
                    discovered["layer_resource_uids"][prop.value.layer_ref] if prop.value.layer_ref is not None else None
                ) if isinstance(prop.value, LayerReference) else prop.value
                client.execute("prop.set", {**base, "value": value})
                for key in prop.keyframes:
                    client.execute("prop.addKey", {**base, "time": key.seconds, "value": key.value})
                    client.execute(
                        "keys.select",
                        {
                            **({"comp": target["comp"]} if "comp" in target else {}),
                            "keys": [{"layer": target["layer"], "path": base["path"], "time": key.seconds}],
                        },
                    )
                    client.execute(
                        "keys.interpolation",
                        {"in": key.in_interp[0].value.lower(), "out": key.out_interp[0].value.lower()},
                    )
                    if key.handles:
                        for side, codes in [("in", key.in_interp), ("out", key.out_interp)]:
                            for dim, code in enumerate(codes):
                                if code.value == "Bezier":
                                    client.execute(
                                        "keys.setEase",
                                        {
                                            **base,
                                            "time": key.seconds,
                                            "side": side,
                                            "dim": dim,
                                            "speed": getattr(key.handles, side + "_speed")[dim],
                                            "influence": getattr(key.handles, side + "_influence")[dim] * 100,
                                        },
                                    )
                actual = client.execute("prop.get", base)
                if not isinstance(actual, dict):
                    raise BridgeError(
                        "Não foi possível conferir a propriedade aplicada; o projeto pode ter mudanças parciais."
                    )
                if prop.keyframes:
                    keys = actual.get("keys", [])
                    if (
                        not isinstance(keys, list)
                        or len(keys) != len(prop.keyframes)
                        or any(not isinstance(a, dict) for a in keys)
                    ):
                        raise BridgeError(
                            "Resposta de keyframes inválida; o projeto pode ter mudanças parciais."
                        )
                    if any(
                        not (
                            isinstance(a.get("time"), (int, float))
                            and _time_matches(a["time"], k.seconds)
                            and _matches(a.get("value"), k.value)
                            and str(a.get("in", "")).lower() == k.in_interp[0].value.lower()
                            and str(a.get("out", "")).lower() == k.out_interp[0].value.lower()
                        )
                        for a, k in zip(keys, prop.keyframes, strict=True)
                    ):
                        raise BridgeError(
                            "Keyframes retornados divergem do plano; o projeto pode ter mudanças parciais."
                        )
                elif prop.kind == "Layer" and (
                    actual.get("type") != "layer" or actual.get("keys") != [] or actual.get("expression")
                    or "value" not in actual or (actual["value"] is not None if value is None else
                    isinstance(actual["value"], bool) or not isinstance(actual["value"], int) or actual["value"] != value)
                ):
                    raise BridgeError("Referência Layer retornada diverge do UID resolvido; o projeto pode ter mudanças parciais.")
                elif prop.kind != "Layer" and not _matches(actual.get("value"), value):
                    raise BridgeError(
                        "Valor retornado diverge do plano; o projeto pode ter mudanças parciais."
                    )
        if save_project:
            client.execute("file.saveAs", {"path": str(save_project)})
    return {
        "applied": True,
        "effects": len(plan.effects),
        "bindings": bindings,
        "preflight": discovered,
        "save_project": str(save_project) if save_project else None,
    }
