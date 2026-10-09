import json
from pathlib import Path

from craft_bridge.core.models import ConversionReport, PresetDocument
from craft_bridge.core.resources import SourceLayerBindings
from craft_bridge.exporters.effectcraft.exporter import EffectCraftPlan
from craft_bridge.mappings.registry import Package

ROOT = Path(__file__).resolve().parents[1] / "src/craft_bridge/schemas"
for name, model in [
    ("intermediate", PresetDocument),
    ("report", ConversionReport),
    ("mappings", Package),
    ("effectcraft-plan", EffectCraftPlan),
    ("source-layer-bindings", SourceLayerBindings),
]:
    (ROOT / (name + ".json")).write_text(json.dumps(model.model_json_schema(), indent=2) + "\n")
value = {
    "oneOf": [
        {"type": "object", "properties": {kind: typ}, "required": [kind], "additionalProperties": False}
        for kind, typ in [
            ("Float", {"type": "number"}),
            ("Bool", {"type": "boolean"}),
            ("Choice", {"type": "integer", "minimum": 0}),
            ("Text", {"type": "string", "maxLength": 65536}),
            ("Color", {"type": "array", "items": {"type": "number"}, "minItems": 4, "maxItems": 4}),
            (
                "Vec2",
                {
                    "type": "object",
                    "required": ["x", "y"],
                    "properties": {"x": {"type": "number"}, "y": {"type": "number"}},
                    "additionalProperties": False,
                },
            ),
        ]
    ]
}
key = {
    "type": "object",
    "required": ["time", "value", "interp"],
    "properties": {
        "time": {"type": "integer", "minimum": -(2**63), "maximum": 2**63 - 1},
        "value": value,
        "interp": {
            "enum": ["Linear", "Hold", "Bezier", "AutoBezier", "ContinuousBezier", "EaseIn", "EaseOut"]
        },
        "in_influence": {"type": "number", "minimum": 0, "maximum": 1},
        "out_influence": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "additionalProperties": False,
}
param = {
    "type": "object",
    "required": ["value"],
    "properties": {"value": value, "keyframes": {"type": "array", "items": key}},
    "additionalProperties": False,
}
effect = {
    "type": "object",
    "required": ["effect", "enabled", "params"],
    "properties": {
        "effect": {"type": "string"},
        "enabled": {"type": "boolean"},
        "params": {"type": "object", "additionalProperties": param},
    },
    "additionalProperties": False,
}
preset = {
    "type": "object",
    "required": ["name", "keyframes", "source_duration", "source_size", "effects"],
    "properties": {
        "name": {"type": "string"},
        "description": {"type": "string"},
        "keyframes": {"enum": ["Scale", "AnchorToIn", "AnchorToOut"]},
        "source_duration": {"type": "integer", "minimum": 0, "maximum": 2**63 - 1},
        "source_size": {
            "type": "array",
            "items": {"type": "integer", "minimum": 1, "maximum": 65536},
            "minItems": 2,
            "maxItems": 2,
        },
        "effects": {"type": "array", "items": effect, "minItems": 1},
    },
    "additionalProperties": False,
}
schema = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "FilmCraft effect-presets v1 subset (pinned commit)",
    "type": "object",
    "required": ["format", "version", "presets"],
    "properties": {
        "format": {"const": "filmcraft.effect-presets"},
        "version": {"const": 1},
        "presets": {"type": "array", "items": preset, "minItems": 1},
    },
    "additionalProperties": False,
}
(ROOT / "filmcraft.json").write_text(json.dumps(schema, indent=2) + "\n")
