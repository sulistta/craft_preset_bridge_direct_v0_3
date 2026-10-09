"""Exporta o formato nativo do FilmCraft no commit auditado."""

from typing import Any

from craft_bridge.core.models import PresetDocument
from craft_bridge.core.safety import BridgeError
from craft_bridge.exporters.common import (
    film_key,
    film_value,
    finalize,
    issue,
    make_report,
    map_effect,
)
from craft_bridge.mappings.registry import Registry


class FilmCraftExporter:
    def export(self, document: PresetDocument, registry: Registry, *, source_size=None, keyframe_mode=None):
        report = make_report(document, "filmcraft", registry)
        out: dict[str, Any] = {"format": "filmcraft.effect-presets", "version": 1, "presets": []}
        for preset in document.presets:
            size = source_size or preset.source_size
            effects = []
            for effect in preset.effects:
                mapped, result = map_effect(effect, preset, document, "filmcraft", registry, size)
                report.effects.append(result)
                if mapped is None:
                    continue
                params: dict[str, Any] = {}
                for item in mapped["parameters"]:
                    try:
                        keys = [film_key(k, item["kind"]) for k in item["keyframes"]]
                        if keys and not preset.source_duration_ticks:
                            raise BridgeError("Animação sem duração de referência.")
                    except BridgeError as exc:
                        result.warnings.append(issue("FILM_KEYFRAMES", str(exc), item["id"]))
                        result.parameters_converted -= 1
                        result.keyframes_preserved -= len(item["keyframes"])
                        result.status = "Parcialmente compatível"
                        continue
                    params[item["id"]] = {"value": film_value(item["kind"], item["value"])}
                    if keys:
                        params[item["id"]]["keyframes"] = keys
                if params:
                    effects.append({"effect": mapped["id"], "enabled": mapped["enabled"], "params": params})
            if effects:
                duration = (
                    (preset.source_duration_ticks or 0)
                    * 254_016_000_000
                    // (preset.source_time_base or 254_016_000_000)
                )
                out["presets"].append(
                    {
                        "name": preset.name,
                        "description": preset.description,
                        "keyframes": keyframe_mode or preset.keyframe_mode,
                        "source_duration": duration,
                        "source_size": list(size or (1920, 1080)),
                        "effects": effects,
                    }
                )
        if keyframe_mode:
            report.warnings = [w for w in report.warnings if w.code != "KEYFRAME_MODE"]
        finalize(report)
        return out, report
