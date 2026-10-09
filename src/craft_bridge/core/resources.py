"""Explicit replacements for opaque source references, pinned to one input file."""

from typing import Annotated, Literal

from pydantic import Field, StrictInt, model_validator

from craft_bridge.core.models import Model, PresetDocument
from craft_bridge.core.safety import BridgeError


class LayerReference(Model):
    layer_ref: str | None = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,79}$")


class SourceLayerBinding(LayerReference):
    preset_index: Annotated[StrictInt, Field(ge=0, le=2047)] = 0
    effect_index: Annotated[StrictInt, Field(ge=0, le=2047)]
    parameter: str = Field(min_length=1, max_length=256)


class SourceLayerBindings(Model):
    format: Literal["craftbridge.source-layer-bindings"] = "craftbridge.source-layer-bindings"
    version: Literal[1] = 1
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    bindings: list[SourceLayerBinding] = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def unique(self):
        keys = [(b.preset_index, b.effect_index, b.parameter) for b in self.bindings]
        if len(keys) != len(set(keys)):
            raise ValueError("Vínculo de origem duplicado.")
        return self

    def resolve(self, document: PresetDocument, registry, preset_index: int) -> dict[tuple[int, str], LayerReference]:
        if document.source.format != "ffx" or document.source.sha256 != self.source_sha256:
            raise BridgeError("Vínculos de origem exigem o SHA-256 exato do FFX analisado.")
        result = {}
        for binding in self.bindings:
            if binding.preset_index != preset_index:
                raise BridgeError("Vínculo refere-se a outro preset; nenhuma substituição implícita.")
            effects = document.presets[preset_index].effects
            if binding.effect_index >= len(effects):
                raise BridgeError("Índice de efeito do vínculo não existe na origem.")
            effect = effects[binding.effect_index]
            mapping = registry.find("ffx", "effectcraft", effect.identifier.match_name)
            rule = mapping.params.get(binding.parameter) if mapping else None
            if rule is None or rule.operation != "explicit_layer_binding":
                raise BridgeError("Vínculo exige parâmetro com mapa explícito de recurso Layer.")
            params = [p for p in effect.parameters if p.id == binding.parameter and not p.metadata.get("administrative")]
            if len(params) != 1:
                raise BridgeError("Vínculo exige uma propriedade de origem única presente no grupo.")
            result[binding.effect_index, binding.parameter] = LayerReference(layer_ref=binding.layer_ref)
        return result
