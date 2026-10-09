"""Plano próprio, com referências simbólicas resolvidas pelo adaptador oficial."""

from typing import Any, Literal

from pydantic import Field

from craft_bridge.core.models import Keyframe, Model, PresetDocument
from craft_bridge.core.resources import LayerReference as LayerReference
from craft_bridge.core.resources import SourceLayerBindings
from craft_bridge.exporters.common import finalize, make_report, map_effect
from craft_bridge.mappings.registry import Registry


class PlanProperty(Model):
    id: str = Field(pattern=r"^[A-Za-z0-9_]+(/[A-Za-z0-9_]+)*$")
    kind: Literal["Float", "Bool", "Choice", "Vec2", "Color", "Text", "Layer"]
    value: float | int | bool | list[float] | str | LayerReference
    keyframes: list[Keyframe] = Field(default_factory=list, max_length=100_000)


class PlanEffect(Model):
    ref: str = Field(pattern=r"^fx[0-9]+$")
    effect: str
    source: str
    enabled: bool = True
    plugin_fingerprint: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    application: Literal["create", "existing"] = "create"
    source_effect_index: int | None = Field(default=None, ge=0, lt=0xFFFFFFFF)
    properties: list[PlanProperty] = Field(max_length=2048)


class EffectCraftPlan(Model):
    format: Literal["craftbridge.effectcraft-plan"] = "craftbridge.effectcraft-plan"
    version: Literal[2, 3, 4] = 3
    name: str
    catalog_commit: str
    source_sha256: str
    preset_index: int = 0
    effects: list[PlanEffect] = Field(default_factory=list, max_length=2048)
    commands: list[dict[str, Any]] = Field(default_factory=list)


def layer_references(plan: EffectCraftPlan) -> set[str]:
    return {
        prop.value.layer_ref for effect in plan.effects for prop in effect.properties
        if prop.kind == "Layer" and isinstance(prop.value, LayerReference) and prop.value.layer_ref is not None
    }


def preview_commands(plan: EffectCraftPlan) -> list[dict[str, Any]]:
    commands: list[dict[str, Any]] = [
        {"command": "bridge.resolveLayer", "params": {"ref": ref, "layer": f"$layerBinding.{ref}", "comp": "$comp"}}
        for ref in sorted(layer_references(plan))
    ]
    for effect in plan.effects:
        commands.append(
            {
                "command": "effect.apply" if effect.application == "create" else "bridge.bindExistingEffect",
                "params": {
                    "effect": effect.effect,
                    "layer": "$layer",
                    "comp": "$comp",
                    **(
                        {"source_effect_index": effect.source_effect_index}
                        if effect.application == "existing"
                        else {}
                    ),
                },
                "bind": effect.ref,
            }
        )
        if not effect.enabled and effect.application == "create":
            commands.append(
                {
                    "command": "effect.toggle",
                    "params": {
                        "effect": f"${effect.ref}.uid",
                        "value": False,
                        "layer": "$layer",
                        "comp": "$comp",
                    },
                }
            )
        for prop in effect.properties:
            path = f"${effect.ref}.path/{prop.id}"
            base = {"layer": "$layer", "comp": "$comp", "path": path}
            value = prop.value.model_dump(mode="json") if isinstance(prop.value, LayerReference) else prop.value
            commands.append({"command": "prop.set", "params": {**base, "value": value}})
            for key in prop.keyframes:
                commands.append(
                    {"command": "prop.addKey", "params": {**base, "value": key.value, "time": key.seconds}}
                )
                commands.append(
                    {
                        "command": "keys.select",
                        "params": {
                            "comp": "$comp",
                            "keys": [{"layer": "$layer", "path": path, "time": key.seconds}],
                        },
                    }
                )
                commands.append(
                    {
                        "command": "keys.interpolation",
                        "params": {
                            "in": key.in_interp[0].value.lower(),
                            "out": key.out_interp[0].value.lower(),
                        },
                    }
                )
                if key.handles:
                    for side, interp, speeds, influences in [
                        ("in", key.in_interp, key.handles.in_speed, key.handles.in_influence),
                        ("out", key.out_interp, key.handles.out_speed, key.handles.out_influence),
                    ]:
                        for dim, (code, speed, influence) in enumerate(
                            zip(interp, speeds, influences, strict=False)
                        ):
                            if code.value == "Bezier":
                                commands.append(
                                    {
                                        "command": "keys.setEase",
                                        "params": {
                                            **base,
                                            "time": key.seconds,
                                            "side": side,
                                            "dim": dim,
                                            "speed": speed,
                                            "influence": influence * 100,
                                        },
                                    }
                                )
    return commands


class EffectCraftExporter:
    def export(
        self,
        document: PresetDocument,
        registry: Registry,
        *,
        source_size=None,
        keyframe_mode=None,
        preset_index=0,
        source_layers: SourceLayerBindings | None = None,
    ):
        report = make_report(document, "effectcraft", registry)
        preset = document.presets[preset_index]
        plan = EffectCraftPlan(
            name=preset.name,
            catalog_commit=registry.catalog["effectcraft"]["commit"],
            source_sha256=document.source.sha256,
            preset_index=preset_index,
        )
        bindings = source_layers.resolve(document, registry, preset_index) if source_layers else {}
        for effect_index, effect in enumerate(preset.effects):
            mapped, result = map_effect(
                effect, preset, document, "effectcraft", registry, source_size or preset.source_size,
                {param: value for (index, param), value in bindings.items() if index == effect_index},
            )
            report.effects.append(result)
            if mapped:
                props = []
                for param in mapped["parameters"]:
                    keys = param["keyframes"]
                    # The protocol exposes one interpolation per side; mixed dimension codes require a different adapter.
                    if any(len(set(k.in_interp)) > 1 or len(set(k.out_interp)) > 1 for k in keys):
                        from craft_bridge.exporters.common import issue

                        result.warnings.append(
                            issue(
                                "COMPONENT_INTERP", "Interpolações divergentes por componente não aplicáveis."
                            )
                        )
                        result.parameters_converted -= 1
                        result.keyframes_preserved -= len(keys)
                        result.status = "Parcialmente compatível"
                        continue
                    props.append(PlanProperty(**param))
                if props:
                    if mapped["id"] in registry.plugins and registry.plugins[mapped["id"]].api >= 2:
                        plan.version = 4
                    plan.effects.append(
                        PlanEffect(
                            ref=f"fx{len(plan.effects)}",
                            effect=mapped["id"],
                            source=mapped["source"],
                            enabled=mapped["enabled"],
                            plugin_fingerprint=(registry.plugins[mapped["id"]].fingerprint()
                                                if mapped["id"] in registry.plugins else None),
                            application=effect.metadata.get("application", "create"),
                            source_effect_index=effect.metadata.get("source_effect_index"),
                            properties=props,
                        )
                    )
        plan.commands = preview_commands(plan)
        finalize(report)
        return plan.model_dump(mode="json"), report
