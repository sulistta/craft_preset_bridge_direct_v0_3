"""Validação sintática e semântica separada da aplicação em engines."""

import json
from importlib.resources import files

from jsonschema import Draft202012Validator
from pydantic import ValidationError

from craft_bridge.core.models import Interpolation
from craft_bridge.core.safety import BridgeError
from craft_bridge.exporters.common import check_value, transform
from craft_bridge.exporters.effectcraft.exporter import (
    EffectCraftPlan,
    LayerReference,
    layer_references,
    preview_commands,
)
from craft_bridge.mappings.registry import Registry, Rule


def validate_filmcraft(data: dict, registry: Registry) -> None:
    schema = json.loads(files("craft_bridge.schemas").joinpath("filmcraft.json").read_text())
    errors = list(Draft202012Validator(schema).iter_errors(data))
    if errors:
        raise BridgeError(f"Schema FilmCraft inválido: {errors[0].message}")
    for preset in data["presets"]:
        for effect in preset["effects"]:
            specs = registry.catalog["filmcraft"]["effects"].get(effect["effect"])
            if specs is None:
                raise BridgeError("Efeito FilmCraft fora do catálogo verificado.")
            for name, param in effect["params"].items():
                if name not in specs:
                    raise BridgeError(f"Parâmetro FilmCraft desconhecido: {name}")
                spec = specs[name]
                if param.get("keyframes") and spec.get("animatable") is False:
                    raise BridgeError("Parâmetro FilmCraft não aceita animação.")
                if param.get("keyframes") and spec["kind"] == "Text":
                    raise BridgeError("Animação de texto/dados estruturados ainda não validada.")
                for wrapped in [param["value"], *(k["value"] for k in param.get("keyframes", []))]:
                    if set(wrapped) != {spec["kind"]}:
                        raise BridgeError("Tipo serde não corresponde ao parâmetro FilmCraft.")
                    value = wrapped[spec["kind"]]
                    if spec["kind"] == "Vec2":
                        value = [value["x"], value["y"]]
                    check_value(transform(value, Rule(target=name, kind=spec["kind"]), None), spec)


def validate_plan(data: dict, registry: Registry | None = None) -> EffectCraftPlan:
    registry = registry or Registry()
    if (
        isinstance(data, dict)
        and data.get("format") == "craftbridge.effectcraft-plan"
        and data.get("version") == 1
    ):
        raise BridgeError(
            "Plano EffectCraft v1 obsoleto: reconverta o preset com a versão atual para corrigir unidades de pontos. Não altere apenas o número da versão."
        )
    try:
        plan = EffectCraftPlan.model_validate(data)
    except ValidationError as exc:
        raise BridgeError(f"Plano EffectCraft inválido: {exc}") from exc
    if plan.catalog_commit != registry.catalog["effectcraft"]["commit"]:
        raise BridgeError("Plano usa um catálogo não verificado.")
    if not plan.effects:
        raise BridgeError("Plano sem efeitos aplicáveis.")
    if len(layer_references(plan)) > 64:
        raise BridgeError("Plano suporta até 64 referências Layer distintas.")
    refs = set()
    existing_indices = set()
    for effect in plan.effects:
        plugin = registry.plugins.get(effect.effect)
        if plugin:
            if plan.version not in (3, 4) or effect.plugin_fingerprint != plugin.fingerprint():
                raise BridgeError("Plano de plugin exige v3/v4 e o mesmo manifesto instalado na conversão.")
            if plugin.api >= 2 and plan.version != 4:
                raise BridgeError("API 2/3/4 experimental exige plano v4.")
        elif effect.plugin_fingerprint is not None:
            raise BridgeError("Fingerprint de plugin não pertence a efeito nativo.")
        if (effect.application == "existing") != (effect.source_effect_index is not None):
            raise BridgeError(
                "Vínculo existente exige índice de origem; criação de efeito não aceita esse índice."
            )
        if effect.application == "existing":
            if not effect.enabled or effect.source_effect_index in existing_indices:
                raise BridgeError("Vínculo existente duplicado ou alteração de ativação indevida.")
            existing_indices.add(effect.source_effect_index)
        if effect.ref in refs:
            raise BridgeError("Referência de efeito duplicada.")
        refs.add(effect.ref)
        specs = registry.catalog["effectcraft"]["effects"].get(effect.effect)
        if specs is None or not effect.properties:
            raise BridgeError("Efeito sem propriedades ou fora do catálogo verificado.")
        if effect.application == "create":
            required = {
                mapping.params[source].target
                for mapping in registry.mappings.values() if mapping.effect == effect.effect
                for source in mapping.required_on_create
            }
            if not required.issubset({prop.id for prop in effect.properties}):
                raise BridgeError("Plano omite dados obrigatórios de criação; defaults não substituem a cena original.")
            if plugin and not {p.id for p in plugin.params if p.type == "layer"}.issubset({p.id for p in effect.properties}):
                raise BridgeError("Criação de plugin exige todos os vínculos Layer explícitos, inclusive null.")
        props = set()
        for prop in effect.properties:
            if prop.id not in specs or prop.kind != specs[prop.id]["kind"] or prop.id in props:
                raise BridgeError("Parâmetro/tipo inválido ou duplicado no plano.")
            props.add(prop.id)
            if prop.kind == "Layer":
                if plan.version != 4 or not isinstance(prop.value, LayerReference):
                    raise BridgeError("Layer exige plano v4 e referência simbólica; UID/índice bruto não é transportável.")
                if prop.keyframes:
                    raise BridgeError("Layer exige vínculo estático; animação de recursos ainda não validada.")
                if plugin is not None and plugin.api < 2:
                    raise BridgeError("Layer de plugin exige API 2/3/4 experimental.")
                continue
            rule = Rule(target=prop.id, kind=prop.kind)
            check_value(transform(prop.value, rule, None), specs[prop.id])
            if prop.kind == "Text" and prop.keyframes:
                raise BridgeError("Animação de texto/dados estruturados ainda não validada.")
            frame_hold = plugin is not None and any(
                r.mode == "frame_hold" and r.parameter == prop.id for r in plugin.temporal_inputs or []
            )
            if frame_hold and (isinstance(prop.value, bool) or not isinstance(prop.value, (int, float)) or not float(prop.value).is_integer()):
                raise BridgeError("frame_hold exige valor inteiro de frames a pular.")
            previous = None
            for key in prop.keyframes:
                if frame_hold and (isinstance(key.value, bool) or not isinstance(key.value, (int, float))
                    or not float(key.value).is_integer() or any(code != Interpolation.HOLD for code in key.in_interp + key.out_interp)):
                    raise BridgeError("Animação de frame_hold exige inteiros e Hold.")
                check_value(transform(key.value, rule, None), specs[prop.id])
                dims = len(key.value) if isinstance(key.value, list) else 1
                if previous is not None and key.seconds <= previous:
                    raise BridgeError("Keyframes devem ter tempos distintos e crescentes.")
                previous = key.seconds
                if (
                    len(key.in_interp) != dims
                    or len(key.out_interp) != dims
                    or len(set(key.in_interp)) != 1
                    or len(set(key.out_interp)) != 1
                    or Interpolation.UNKNOWN in key.in_interp + key.out_interp
                ):
                    raise BridgeError("Interpolações inválidas no plano.")
                if prop.kind in ("Bool", "Choice") and any(
                    code != Interpolation.HOLD for code in key.in_interp + key.out_interp
                ):
                    raise BridgeError("Animação discreta no destino exige Hold.")
                for side, codes in [("in", key.in_interp), ("out", key.out_interp)]:
                    if Interpolation.BEZIER in codes and key.handles is None:
                        raise BridgeError("Curva Bezier exige handles.")
                    if key.handles:
                        speeds = getattr(key.handles, side + "_speed")
                        influences = getattr(key.handles, side + "_influence")
                        if len(speeds) != dims or len(influences) != dims:
                            raise BridgeError("Tangentes não correspondem às dimensões.")
                        if any(
                            not 0.001 <= i <= 1
                            for i, code in zip(influences, codes, strict=False)
                            if code == Interpolation.BEZIER
                        ):
                            raise BridgeError("Influência Bezier fora do intervalo representável pela API.")
    if plan.commands != preview_commands(plan):
        raise BridgeError("Comandos do plano divergentes dos efeitos/propriedades auditados.")
    return plan
