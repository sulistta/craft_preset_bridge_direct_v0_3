"""Mapeamento compartilhado com validação explícita de tipos, limites e perdas."""

import hashlib
import math
import re
from copy import deepcopy
from typing import Any

from craft_bridge.core.models import (
    ConversionReport,
    ConversionWarning,
    Effect,
    EffectResult,
    Keyframe,
    Parameter,
    Preset,
    PresetDocument,
)
from craft_bridge.core.resources import LayerReference
from craft_bridge.core.safety import BridgeError
from craft_bridge.mappings.registry import Registry, Rule


def issue(code: str, message: str, path: str = "") -> ConversionWarning:
    return ConversionWarning(code=code, message=message, path=path)


def parameter_issues(param: Parameter) -> list[ConversionWarning]:
    # Collect before any mapping refusal: missing maps/required data must not
    # conceal undecoded references, expressions or unsupported animation.
    warnings = deepcopy(param.warnings)
    for warning in warnings:
        warning.path = warning.path or param.id
        warning.message = f"{param.name} ({param.id}): {warning.message}"
    return warnings


def transform(value: Any, rule: Rule, size: tuple[int, int] | None) -> Any:
    if value is None:
        raise BridgeError("Valor desconhecido.")
    if rule.operation == "enum_map":
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value != int(value)
            or int(value) not in rule.choices
        ):
            raise BridgeError("Opção de origem sem equivalência verificada no menu de destino.")
        value = rule.choices[int(value)]
    if rule.operation == "normalized_to_pixels":
        if size is None or not isinstance(value, list) or len(value) != 2:
            raise BridgeError("Coordenada normalizada exige --size LARGURAxALTURA.")
        value = [value[0] * size[0], value[1] * size[1]]
    elif rule.operation in ("minus_one", "times_100", "times_255"):
        if isinstance(value, bool) or not isinstance(value, (float, int)):
            raise BridgeError("Conversão de escala exige número escalar.")
        value = value - 1 if rule.operation == "minus_one" else value * (255 if rule.operation == "times_255" else 100)
    elif rule.operation == "argb255_to_rgba":
        if (
            not isinstance(value, list)
            or len(value) != 4
            or any(
                isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in value
            )
        ):
            raise BridgeError("Cor AE exige quatro componentes ARGB finitos.")
        value = [value[1] / 255, value[2] / 255, value[3] / 255, value[0] / 255]
    if rule.kind == "Bool":
        if not isinstance(value, bool):
            raise BridgeError("Booleano esperado.")
    elif rule.kind in ("Float", "Choice"):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise BridgeError("Número finito esperado.")
        if rule.kind == "Choice":
            if value != int(value):
                raise BridgeError("Enum exige índice inteiro.")
            value = int(value)
    elif rule.kind in ("Vec2", "Color"):
        n = 2 if rule.kind == "Vec2" else 4
        if (
            not isinstance(value, list)
            or len(value) != n
            or any(
                isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in value
            )
        ):
            raise BridgeError(f"Vetor de {n} números finitos esperado.")
    elif rule.kind == "Text":
        if not isinstance(value, str) or len(value.encode("utf-8")) > 65536 or "\x00" in value:
            raise BridgeError("Texto estático exige string UTF-8 de até 65536 bytes sem NUL.")
    return value


def check_value(value: Any, spec: dict) -> None:
    if spec["kind"] in ("Float", "Choice") and not spec.get("min", -math.inf) <= value <= spec.get(
        "max", math.inf
    ):
        raise BridgeError(
            f"Valor {value} fora do intervalo {spec.get('min', '-inf')}..{spec.get('max', 'inf')}; não será limitado silenciosamente."
        )
    if spec.get("text_format") == "curve-points":
        # Native Curve::parse silently ignores invalid tokens and deduplicates x.
        # Reject those cases instead of accepting an unintended identity curve.
        try:
            if not isinstance(value, str) or not re.fullmatch(r"[0-9+eE.,\- \t\r\n]+", value):
                raise ValueError
            points = [tuple(map(float, token.split(","))) for token in value.split()]
            if not 2 <= len(points) <= 256 or any(
                len(pair) != 2 or any(not math.isfinite(v) or not 0 <= v <= 1 for v in pair)
                for pair in points
            ):
                raise ValueError
            if points[0][0] != 0 or points[-1][0] != 1 or any(
                b[0] - a[0] < 1e-6 for a, b in zip(points, points[1:], strict=False)
            ):
                raise ValueError
        except (AttributeError, ValueError, TypeError) as exc:
            raise BridgeError("Curva textual exige 2..256 pares x,y finitos em 0..1, x crescente de 0 a 1.") from exc


def check_requirements(effect: Effect, rule: Rule) -> None:
    for source, expected in rule.requires.items():
        matches = [p for p in effect.parameters if p.id == source]
        if len(matches) != 1:
            raise BridgeError(f"Condição exige uma propriedade de origem única: {source}.")
        param = matches[0]
        actual = param.value.data
        if (
            param.keyframes
            or param.metadata.get("animated")
            or any(w.loss for w in param.warnings)
            or isinstance(actual, bool) != isinstance(expected, bool)
            or actual != expected
        ):
            raise BridgeError(f"Condição não comprovada: {source} deve ser estático e igual a {expected}.")


def source_layer_inactive(effect: Effect, rule: Rule) -> bool:
    """Prove a documented unused input; never infer the original opaque binding."""
    if not rule.inactive_when:
        return False
    for source, values in rule.inactive_when.items():
        matches = [p for p in effect.parameters if p.id == source and not p.metadata.get("administrative")]
        if len(matches) != 1:
            return False
        param = matches[0]
        if (param.value.kind != "enum" or type(param.value.data) is not int or param.value.data not in values
            or param.keyframes or param.metadata.get("animated") is not False or param.metadata.get("keyframes_declared", 0)
            or any(w.loss for w in param.warnings)):
            return False
    return True


def mapped_parameter(param: Parameter, rule: Rule, spec: dict, size: tuple[int, int] | None,
                     binding: LayerReference | None = None) -> dict:
    if rule.operation == "explicit_layer_binding":
        if binding is None:
            raise BridgeError("Referência de origem opaca exige vínculo explícito; None não será inferido.")
        if (param.keyframes or param.metadata.get("animated") is not False or param.metadata.get("keyframes_declared", 0)
            or any(w.code in ("EXPRESSION", "KEYFRAME_LAYOUT", "KEYFRAME_DECODE") for w in param.warnings)):
            raise BridgeError("Vínculo estático não substitui animação ou expressão de origem.")
        return {"id": rule.target, "kind": "Layer", "value": binding, "keyframes": [],
                "adaptations": [f"{param.id}: referência de origem substituída explicitamente por {binding.layer_ref!r}"]}
    if rule.operation == "ofp_scene_lookup":
        from craft_bridge.parsers.ffx.optical_flares import OPTIONS, encode_ofp

        if (param.id != OPTIONS or param.metadata.get("arbitrary_layout") != "OFP-v3-structural"
            or param.metadata.get("kind") != 11 or param.metadata.get("dimensions") != 1
            or param.metadata.get("stream_flags") != 7 or param.metadata.get("animated") is not False
            or param.keyframes or param.metadata.get("keyframes_declared", 0)
            or any(w.code != "OFP_RENDER_UNSUPPORTED" for w in param.warnings)):
            raise BridgeError("Cena OFP exige associação estática íntegra, sem recursos adicionais.")
        scene = param.metadata.get("decoded_arbitrary")
        if not isinstance(scene, dict):
            raise BridgeError("Cena OFP não foi decodificada.")
        digest = hashlib.sha256(encode_ofp(scene)).hexdigest()
        if digest != param.origin.get("aRbp", {}).get("sha256") or digest not in rule.scenes:
            raise BridgeError("Hash da cena não corresponde à biblioteca instalada; nenhuma cena default será escolhida.")
        value = rule.scenes[digest]
        check_value(value, spec)
        return {"id": rule.target, "kind": rule.kind, "value": value, "keyframes": [],
                "adaptations": [f"{param.id}: cena OFP integral vinculada pelo SHA-256 {digest}"]}
    if any(w.loss for w in param.warnings):
        raise BridgeError("Propriedade tem recursos não decodificados; não será aplicada parcialmente.")
    if param.keyframes and spec.get("animatable") is False:
        raise BridgeError("Parâmetro de destino não aceita animação.")
    if rule.kind == "Text" and (param.keyframes or param.metadata.get("animated")):
        raise BridgeError("Animação de texto/dados estruturados ainda não validada.")
    value = transform(param.value.data, rule, size)
    check_value(value, spec)
    keys = []
    adaptations = []
    for original in param.keyframes:
        key = original.model_copy(deep=True)
        key.value = transform(key.value, rule, size)
        check_value(key.value, spec)
        if rule.kind == "Vec2" and any(i.value == "Bezier" for i in key.in_interp + key.out_interp):
            raise BridgeError(
                "Curva temporal por componente não equivale ao easing espacial único do destino."
            )
        if rule.kind in ("Bool", "Choice"):
            codes = key.in_interp + key.out_interp
            if not codes or any(code.value not in ("Linear", "Hold") for code in codes):
                raise BridgeError("Keyframe discreto exige Hold; uma chave isolada também aceita Linear.")
            if any(code.value != "Hold" for code in codes):
                if len(param.keyframes) != 1:
                    raise BridgeError("Animação discreta com várias chaves exige Hold explícito.")
                key.in_interp = key.out_interp = [type(codes[0]).HOLD]
                key.metadata["source_discrete_interpolation"] = [c.value for c in codes]
                adaptations.append(f"{param.id}: chave discreta isolada Linear → Hold (valor constante)")
            key.handles = None
        if (
            not key.in_interp
            or not key.out_interp
            or any(i.value == "Unknown" for i in key.in_interp + key.out_interp)
        ):
            raise BridgeError("Interpolação de origem desconhecida.")
        if rule.operation != "identity" and key.handles:
            for side in ("in", "out"):
                speeds = getattr(key.handles, side + "_speed")
                if rule.operation == "argb255_to_rgba":
                    order = [1, 2, 3, 0]
                    speeds = [speeds[i] / 255 for i in order]
                    influences = getattr(key.handles, side + "_influence")
                    setattr(key.handles, side + "_influence", [influences[i] for i in order])
                    codes = getattr(key, side + "_interp")
                    setattr(key, side + "_interp", [codes[i] for i in order])
                elif rule.operation == "normalized_to_pixels":
                    if size is None or len(speeds) != 2:
                        raise BridgeError("Tangentes 2D exigem resolução de referência.")
                    speeds = [speed * factor for speed, factor in zip(speeds, size, strict=True)]
                else:
                    factor = {"times_100": 100, "times_255": 255}.get(rule.operation, 1)
                    speeds = [s * factor for s in speeds]
                setattr(key.handles, side + "_speed", speeds)
        keys.append(key)
    return {
        "id": rule.target,
        "kind": rule.kind,
        "value": value,
        "keyframes": keys,
        "adaptations": adaptations,
    }


def map_effect(
    effect: Effect,
    preset: Preset,
    document: PresetDocument,
    target: str,
    registry: Registry,
    size: tuple[int, int] | None,
    bindings: dict[str, LayerReference] | None = None,
) -> tuple[dict | None, EffectResult]:
    relevant = [p for p in effect.parameters if not p.metadata.get("administrative")]
    result = EffectResult(
        preset=preset.name,
        source=effect.identifier.match_name,
        status="Não suportado",
        parameters_found=len(relevant),
        keyframes_found=sum(max(len(p.keyframes), p.metadata.get("keyframes_declared", 0)) for p in relevant),
        warnings=deepcopy(effect.warnings) + [w for p in relevant for w in parameter_issues(p)],
    )
    mapping = registry.find(document.source.format, target, effect.identifier.match_name)
    if mapping is None or effect.feature not in ("effect", "transform", "effect-properties"):
        result.warnings.append(issue("NO_MAPPING", "Efeito/recurso sem mapeamento verificado."))
        return None, result
    result.target = mapping.effect
    result.mapping_validation = mapping.validation
    result.mapping_evidence = mapping.evidence
    result.warnings.extend(issue("MAPPING_APPROXIMATION", message) for message in mapping.limitations)
    if "synthetic-only" in mapping.validation:
        result.warnings.append(
            issue(
                "MAPPING_UNVERIFIED",
                "Mapa experimental: ainda sem fixture real para confirmar os IDs de parâmetros de origem.",
            )
        )
    if any(
        w.code in ("INDEX", "MISSING_BLOCK", "EFFECT_DECODE", "ARBITRARY_SHADOW_ANIMATION")
        for w in effect.warnings
    ):
        result.status = "Não decodificado"
        return None, result
    creating = effect.feature != "effect-properties"
    if creating and any(sum(p.id == id for p in relevant) != 1 for id in mapping.required_on_create):
        result.warnings.append(issue("REQUIRED_SOURCE_DATA", "Dados obrigatórios de criação ausentes ou ambíguos; efeito não criado."))
        result.status = "Não decodificado"
        return None, result
    converted = []
    seen = set()
    accepted_sources = set()
    for param in relevant:
        if (
            param.id == "ADBE Effect Mask Opacity"
            and param.value.data == 100
            and not param.keyframes
            and not param.warnings
        ):
            result.parameters_found -= 1  # verified neutral compositing default
            continue
        rule = mapping.params.get(param.id)
        if rule is None:
            result.warnings.append(
                issue("PARAMETER_UNSUPPORTED", f"Parâmetro sem mapa: {param.name} ({param.id}).", param.id)
            )
            continue
        try:
            check_requirements(effect, rule)
            if rule.target in seen:
                raise BridgeError("Parâmetro duplicado na origem.")
            binding = (bindings or {}).get(param.id)
            inactive = binding is None and source_layer_inactive(effect, rule)
            if inactive:
                binding = LayerReference(layer_ref=None)
            item = mapped_parameter(
                param, rule, registry.catalog[target]["effects"][mapping.effect][rule.target], size,
                binding,
            )
            if inactive:
                item["adaptations"] = [f"{param.id}: recurso inativo pelo seletor estático comprovado; vínculo original não decodificado"]
        except BridgeError as exc:
            result.warnings.append(issue("PARAMETER_REJECTED", f"{param.name}: {exc}", param.id))
            continue
        seen.add(rule.target)
        accepted_sources.add(param.id)
        result.transformations.extend(item.pop("adaptations"))
        converted.append(item)
        result.parameters_converted += 1
        result.keyframes_preserved += len(item["keyframes"])
        if rule.operation == "explicit_layer_binding":
            result.warnings.append(issue(
                "SOURCE_LAYER_INACTIVE" if inactive else "SOURCE_LAYER_REPLACED",
                "Recurso inativo pelo seletor estático comprovado; None é entrada de transporte, não vínculo original decodificado." if inactive else
                "Referência opaca substituída por vínculo manual estático; vínculo original não decodificado.", param.id,
            ))
        if any(k.metadata.get("source_temporal_continuous") for k in item["keyframes"]):
            result.warnings.append(issue(
                "KEYFRAME_CONTINUITY",
                "Velocidades/influências Continuous Bezier preservadas em curva manual; vínculo de edição entre lados não reproduzido.",
                param.id,
            ))
        if rule.operation != "identity":
            result.transformations.append(f"{param.id} → {rule.target}: {rule.operation}")
    if not converted:
        return None, result
    if creating and any(id not in accepted_sources for id in mapping.required_on_create):
        result.warnings.append(issue("REQUIRED_SOURCE_DATA", "Dados obrigatórios recusados; efeito não criado nem substituído por defaults."))
        result.parameters_converted = result.keyframes_preserved = 0
        result.transformations = []
        result.status = "Não decodificado"
        return None, result
    result.status = (
        "Parcialmente compatível"
        if any(w.loss for w in result.warnings)
        else "Compatível com adaptação"
        if result.transformations
        else "Compatível"
    )
    return {
        "id": mapping.effect,
        "enabled": effect.enabled,
        "parameters": converted,
        "source": mapping.source,
    }, result


def make_report(document: PresetDocument, target: str, registry: Registry) -> ConversionReport:
    warnings = deepcopy(document.warnings)
    for preset in document.presets:
        warnings.extend(preset.warnings)
    for feature in document.unsupported:
        warnings.append(issue("UNSUPPORTED_FEATURE", feature.reason, feature.path))
    return ConversionReport(
        source=document.source,
        source_path=document.source.path,
        target=target,
        status="UNSUPPORTED",
        warnings=warnings,
        catalog_commit=registry.catalog[target]["commit"],
    )


def finalize(report: ConversionReport) -> None:
    converted = sum(e.parameters_converted for e in report.effects)
    loss = any(w.loss for w in report.warnings) or any(w.loss for e in report.effects for w in e.warnings)
    report.status = "UNSUPPORTED" if not converted else "PARTIAL" if loss else "SUCCESS"


def film_value(kind: str, value: Any) -> dict:
    return {kind: {"x": value[0], "y": value[1]} if kind == "Vec2" else value}


def film_key(key: Keyframe, kind: str) -> dict:
    if len(set(key.out_interp)) != 1 or key.out_interp[0].value == "Bezier":
        raise BridgeError("Curva Bezier/componente separado não representável com precisão pelo FilmCraft.")
    return {
        "time": key.ticks * 254_016_000_000 // key.time_base,
        "value": film_value(kind, key.value),
        "interp": key.out_interp[0].value,
        "in_influence": 1 / 3,
        "out_influence": 1 / 3,
    }
