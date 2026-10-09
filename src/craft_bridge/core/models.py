"""Modelo intermediário versionado; valores desconhecidos permanecem explícitos."""

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ValueKind = Literal["number", "boolean", "enum", "color", "point", "vector", "text", "unknown"]
SourceFormat = Literal["prfpset", "ffx"]
KeyframeMode = Literal["Scale", "AnchorToIn", "AnchorToOut"]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Interpolation(str, Enum):
    LINEAR = "Linear"
    HOLD = "Hold"
    BEZIER = "Bezier"
    UNKNOWN = "Unknown"


class BezierHandles(Model):
    in_speed: list[float] = Field(default_factory=list)
    in_influence: list[float] = Field(default_factory=list)
    out_speed: list[float] = Field(default_factory=list)
    out_influence: list[float] = Field(default_factory=list)


class Keyframe(Model):
    ticks: int
    time_base: int = Field(gt=0)
    value: float | int | bool | list[float] | str
    in_interp: list[Interpolation] = Field(default_factory=list)
    out_interp: list[Interpolation] = Field(default_factory=list)
    handles: BezierHandles | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def seconds(self) -> float:
        return self.ticks / self.time_base


class ConversionWarning(Model):
    code: str
    message: str
    path: str = ""
    loss: bool = True


class UnsupportedFeature(Model):
    feature: str
    reason: str
    path: str = ""
    raw: dict[str, Any] = Field(default_factory=dict)


class ParameterValue(Model):
    kind: ValueKind
    data: float | int | bool | list[float] | str | None = None
    unit: str | None = None


class Parameter(Model):
    id: str
    name: str
    value: ParameterValue
    keyframes: list[Keyframe] = Field(default_factory=list)
    group: list[str] = Field(default_factory=list)
    origin: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    warnings: list[ConversionWarning] = Field(default_factory=list)


class EffectIdentifier(Model):
    match_name: str
    source_id: str | None = None


class Mask(Model):
    name: str
    decoded: bool = False
    raw: dict[str, Any] = Field(default_factory=dict)


class Effect(Model):
    name: str
    identifier: EffectIdentifier
    order: int
    enabled: bool = True
    parameters: list[Parameter] = Field(default_factory=list)
    masks: list[Mask] = Field(default_factory=list)
    feature: str = "effect"
    metadata: dict[str, Any] = Field(default_factory=dict)
    warnings: list[ConversionWarning] = Field(default_factory=list)


class SourceMetadata(Model):
    path: str
    format: SourceFormat
    size: int
    sha256: str
    parser_version: str = "0.36.0"
    detected_version: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Preset(Model):
    name: str
    effects: list[Effect] = Field(default_factory=list)
    description: str = ""
    source_duration_ticks: int | None = None
    source_time_base: int | None = None
    source_size: tuple[int, int] | None = None
    keyframe_mode: KeyframeMode = "Scale"
    warnings: list[ConversionWarning] = Field(default_factory=list)


class PresetDocument(Model):
    format: Literal["craftbridge.intermediate"] = "craftbridge.intermediate"
    version: Literal[1] = 1
    source: SourceMetadata
    presets: list[Preset] = Field(default_factory=list)
    warnings: list[ConversionWarning] = Field(default_factory=list)
    unsupported: list[UnsupportedFeature] = Field(default_factory=list)
    diagnostics: dict[str, Any] = Field(default_factory=dict)


class EffectResult(Model):
    preset: str
    source: str
    target: str | None = None
    status: str
    parameters_found: int = 0
    parameters_converted: int = 0
    keyframes_found: int = 0
    keyframes_preserved: int = 0
    warnings: list[ConversionWarning] = Field(default_factory=list)
    transformations: list[str] = Field(default_factory=list)
    mapping_validation: str = ""
    mapping_evidence: str = ""


class ConversionReport(Model):
    format: Literal["craftbridge.conversion-report"] = "craftbridge.conversion-report"
    version: Literal[1] = 1
    source: SourceMetadata | None = None
    source_path: str
    input_sha256: str | None = None
    input_size: int | None = None
    target: str
    status: Literal["SUCCESS", "PARTIAL", "UNSUPPORTED", "FAILED"]
    catalog_commit: str = ""
    mapping_package: str = "builtin-1"
    effects: list[EffectResult] = Field(default_factory=list)
    warnings: list[ConversionWarning] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    output: str | None = None
    validation: str = "schema-and-pinned-catalog; engine not contacted"
    dry_run: bool = False
    strict: bool = False
