"""Static Cycore RGB correction profile; never combine UI pickers with sliders.

Evidence and approximation limits: docs/decisions/006-neutralizer-rgb-transfer.md.
"""

import math
from typing import cast

from craft_bridge.core.models import ConversionWarning, Effect, Parameter, ParameterValue
from craft_bridge.core.safety import Budget

SOURCE = "CS Color Neutralizer"
TONES = (("shadows", 3, 1, 0.0), ("midtones", 9, 7, 0.5), ("highlights", 15, 13, 1.0))


def static_clean(param: Parameter) -> bool:
    return not param.keyframes and not param.metadata.get("animated") and not any(w.loss for w in param.warnings)


def derive_neutralizer(effect: Effect, budget: Budget) -> None:
    if effect.identifier.match_name != SOURCE or effect.feature != "effect":
        return
    effect.warnings.append(ConversionWarning(
        code="NEUTRALIZER_ALGORITHM",
        message="Transferência aproximada dos ajustes RGB: interpolação tonal, pinning e clipping do destino não têm equivalência visual Adobe comprovada.",
    ))
    for tone, first, picker_index, anchor in TONES:
        pickers = [p for p in effect.parameters if p.id == f"{SOURCE}-{picker_index:04}"]
        if len(pickers) != 1:
            continue
        picker = pickers[0]
        if not (
            picker.metadata.get("kind") == 5
            and picker.metadata.get("flags", 0) & 4
            and static_clean(picker)
        ):
            continue
        ids = [f"{SOURCE}-{i:04}" for i in range(first, first + 3)]
        channels = [[p for p in effect.parameters if p.id == source_id] for source_id in ids]
        if any(len(group) != 1 for group in channels):
            continue
        params = [group[0] for group in channels]
        if any(
            not static_clean(p)
            or p.value.kind != "number"
            or p.metadata.get("kind") != 10
            or p.metadata.get("display_flags") != 1
            or p.metadata.get("dimensions") != 1
            or p.metadata.get("stream_flags") not in (1, 7)
            or p.metadata.get("flags", 0) & 4
            or isinstance(p.value.data, bool)
            or not isinstance(p.value.data, (int, float))
            or not math.isfinite(p.value.data)
            or not -100 <= p.value.data <= 100
            for p in params
        ):
            effect.warnings.append(ConversionWarning(
                code="NEUTRALIZER_RGB_PROFILE",
                message=f"{tone}: trio RGB sem perfil estático e unidade percentual comprovada; valores originais preservados, sem inferir escala pelo intervalo.",
                path=ids[0],
            ))
            continue
        budget.check("parameters")
        derived_id = f"{SOURCE}/rgb/{tone}"
        # Native Balance - Unbalance is the additive RGB correction. Unbalance
        # stays at the verified native default anchor; the UI picker is unused.
        rgb = [anchor + cast(float, p.value.data) / 100 for p in params]
        effect.parameters.append(Parameter(
            id=derived_id, name=tone + " RGB", value=ParameterValue(kind="color", data=[*rgb, 1.0], unit="RGBA"),
            origin={"components": [p.origin.copy() for p in params]},
            metadata={"derived_from": ids, "layout": "Cycore-static-percent-RGB-v1", "native_anchor": anchor},
        ))
        for param in params:
            param.metadata.update(administrative=True, composed_into=derived_id)
        picker.metadata.update(administrative=True, ui_shadow_of=ids)
