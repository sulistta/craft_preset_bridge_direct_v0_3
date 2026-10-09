"""Declarative legacy/experimental manifests; no module loading or execution."""

import hashlib
import json
import math
from typing import Any, Literal

from pydantic import (
    Field,
    SerializerFunctionWrapHandler,
    StrictBool,
    StrictFloat,
    StrictInt,
    field_validator,
    model_serializer,
)

from craft_bridge.core.models import Model
from craft_bridge.core.safety import BridgeError


class PluginParam(Model):
    id: str = Field(pattern=r"^[A-Za-z0-9_]{1,128}$")
    name: str = Field(min_length=1, max_length=256)
    type: Literal["slider", "angle", "checkbox", "popup", "point", "color", "layer"]
    default: StrictBool | StrictFloat | StrictInt | list[StrictFloat] | None = None
    min: float | None = None
    max: float | None = None
    sliderMin: float | None = None
    sliderMax: float | None = None
    decimals: int | None = Field(default=None, ge=0, le=255)
    options: list[str] | None = Field(default=None, min_length=1, max_length=256)

    @model_serializer(mode="wrap")
    def serialize(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        result: dict[str, Any] = handler(self)
        if self.type == "layer":
            # Registry packages normally omit None. This null is a declared
            # resource default and must survive installation/fingerprinting.
            result["default"] = self.default
        return result

    def spec(self) -> dict:
        value = self.default
        if self.type == "layer":
            if "default" not in self.model_fields_set or value is not None:
                raise BridgeError("Layer de plugin exige default null explícito; UID não é portátil.")
            if self.options is not None or any(v is not None for v in (self.min, self.max, self.sliderMin, self.sliderMax, self.decimals)):
                raise BridgeError("Layer de plugin não aceita menu ou limites de slider.")
            return {"kind": "Layer", "default": None, "animatable": False}
        if value is None:
            if "default" in self.model_fields_set or self.type == "slider":
                raise BridgeError("Default de plugin ausente ou nulo; slider exige default explícito.")
            # Defaults declared by PluginParamKind's official serde contract.
            defaults: dict[str, bool | float | int | list[float]] = {
                "angle": 0.0, "checkbox": False, "popup": 0, "point": [0.5, 0.5], "color": [1.0] * 4,
            }
            value = defaults[self.type]
        result: dict[str, Any] = {"default": value}
        if self.type == "checkbox":
            if not isinstance(value, bool):
                raise BridgeError("Default de checkbox deve ser booleano.")
            result["kind"] = "Bool"
        elif self.type == "popup":
            if isinstance(value, bool) or not isinstance(value, int) or not self.options or not 0 <= value < len(self.options):
                raise BridgeError("Popup exige opções e default inteiro dentro do menu.")
            if any(not option or len(option) > 1024 for option in self.options):
                raise BridgeError("Opção de plugin inválida.")
            result.update(kind="Choice", min=0, max=len(self.options) - 1, options=self.options)
        elif self.type in ("point", "color"):
            if not isinstance(value, list) or len(value) != (2 if self.type == "point" else 4) or any(not math.isfinite(v) for v in value):
                raise BridgeError("Default vetorial de plugin inválido.")
            result["kind"] = "Vec2" if self.type == "point" else "Color"
        else:
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise BridgeError("Default numérico de plugin inválido.")
            result.update(kind="Float", default=float(value))
            if self.type == "slider":
                lo, hi = (0.0 if self.min is None else self.min), (100.0 if self.max is None else self.max)
                slo, shi = (lo if self.sliderMin is None else self.sliderMin), (hi if self.sliderMax is None else self.sliderMax)
                if not lo <= value <= hi or not slo <= shi:
                    raise BridgeError("Slider de plugin exige min ≤ default ≤ max e sliderMin ≤ sliderMax.")
                result.update(min=lo, max=hi)
        if self.type != "popup" and self.options is not None:
            raise BridgeError("Opções somente para popup de plugin.")
        if self.type != "slider" and any(v is not None for v in (self.min, self.max, self.sliderMin, self.sliderMax, self.decimals)):
            raise BridgeError("Limites de slider não pertencem a este tipo de plugin.")
        return result


class TemporalInput(Model):
    id: str = Field(pattern=r"^[A-Za-z0-9_]{1,128}$")
    mode: Literal["frame_hold", "seconds_offset", "frames_offset"]
    parameter: str = Field(pattern=r"^[A-Za-z0-9_]{1,128}$")
    multiple: StrictInt = Field(default=1, ge=1, le=16)
    edge: Literal["clamp", "wrap", "mirror"] = "clamp"


class PluginManifest(Model):
    api: Literal[1, 2, 3, 4]
    bridge_host_revision: Literal[1, 2, 3] | None = None
    id: str = Field(pattern=r"^[A-Za-z0-9_.-]{1,256}$")
    name: str = Field(min_length=1, max_length=256)
    category: str = Field(min_length=1, max_length=256)
    version: str = Field(default="", max_length=128)
    author: str = Field(default="", max_length=256)
    description: str = Field(default="", max_length=4096)
    params: list[PluginParam] = Field(min_length=1, max_length=256)
    temporal_inputs: list[TemporalInput] | None = Field(default=None, min_length=1, max_length=4)

    @field_validator("api", "bridge_host_revision", mode="before")
    @classmethod
    def exact_versions(cls, value: Any) -> Any:
        if value is not None and type(value) is not int:
            raise ValueError("Versão de API/host deve ser inteiro exato.")
        return value

    def specs(self) -> dict:
        if self.id.startswith("ec."):
            raise BridgeError("ec. é reservado ao catálogo nativo; use o ID declarado pelo plugin.")
        if len({p.id for p in self.params}) != len(self.params):
            raise BridgeError("Parâmetros de plugin duplicados.")
        layers = sum(p.type == "layer" for p in self.params)
        if self.api == 2 and self.bridge_host_revision != 1:
            raise BridgeError("API 2 exige bridge_host_revision=1; contrato experimental, não ABI upstream.")
        if self.api == 3 and self.bridge_host_revision != 2:
            raise BridgeError("API 3 exige bridge_host_revision=2 e contexto temporal real do host.")
        if self.api == 1 and (layers or self.bridge_host_revision is not None):
            raise BridgeError("API 1 não oferece Layer nem revisão experimental do host.")
        if layers > 4:
            raise BridgeError("Host experimental suporta até quatro Layer por plugin.")
        specs = {p.id: p.spec() for p in self.params}
        if self.api == 4:
            if self.bridge_host_revision != 3 or not self.temporal_inputs:
                raise BridgeError("API 4 exige revisão 3 e temporal_inputs explícitos.")
            if layers + len(self.temporal_inputs) > 4:
                raise BridgeError("API 4 aceita até quatro entradas auxiliares combinadas.")
            if len({r.id for r in self.temporal_inputs}) != len(self.temporal_inputs):
                raise BridgeError("Entradas temporais duplicadas.")
            for request in self.temporal_inputs:
                param = next((p for p in self.params if p.id == request.parameter), None)
                if param is None or param.type != "slider":
                    raise BridgeError("Entrada temporal exige referência a slider declarado.")
                lo, hi = {"frame_hold": (0, 1024), "seconds_offset": (-1000, 1000), "frames_offset": (-10000, 10000)}[request.mode]
                spec = specs[param.id]
                if spec["min"] < lo or spec["max"] > hi or request.mode == "frame_hold" and (
                    request.multiple != 1 or float(spec["default"]).is_integer() is False
                ):
                    raise BridgeError("Slider temporal excede os limites ou frame_hold não tem default inteiro.")
        elif self.temporal_inputs is not None:
            raise BridgeError("temporal_inputs exige API 4 experimental.")
        return specs

    def fingerprint(self) -> str:
        self.specs()
        data = self.model_dump(mode="json", exclude_none=True)
        return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
