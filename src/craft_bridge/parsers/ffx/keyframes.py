"""Perfis lhd3/ldat verificados por tamanho, dimensões e metadados tdb4."""

import math
import struct

from craft_bridge.core.models import BezierHandles, Interpolation, Keyframe
from craft_bridge.core.safety import BridgeError, Budget

INTERP = {1: Interpolation.LINEAR, 2: Interpolation.BEZIER, 3: Interpolation.HOLD}


def decode_keyframes(
    header: memoryview,
    data: memoryview,
    *,
    dimensions: int,
    stream_flags: int,
    time_base: int,
    budget: Budget,
    value_kind: str = "unknown",
) -> list[Keyframe]:
    """Não faz fallback para layouts plausíveis; divergências exigem diagnóstico."""
    if len(header) != 52 or struct.unpack_from(">I", header)[0] != 0x00D00BEE:
        raise BridgeError("Layout lhd3 desconhecido (esperado magic D00BEE e 52 bytes).")
    _, _, count, field3, record_size, item_type = struct.unpack_from(">6I", header)
    budget.check("keyframes", count)
    if not 1 <= dimensions <= 8 or time_base <= 0 or item_type != 4 or count == 0:
        raise BridgeError("Metadados de keyframes não sustentados por evidência.")
    if stream_flags & 2:
        if value_kind == "color" and dimensions == 4 and stream_flags in (6, 7):
            return _color_keys(data, count, record_size, time_base, budget)
        raise BridgeError("Layout espacial/cor/single-ease ainda não decodificado.")
    if stream_flags & ~1:
        raise BridgeError("Flags de stream desconhecidas.")
    normal_size = 8 + 40 * dimensions
    interleaved = False
    if len(data) == count * record_size and record_size == normal_size:
        pass
    elif (
        dimensions > 1
        and field3 == dimensions
        and record_size == 48
        and len(data) == count * dimensions * record_size
    ):
        interleaved = True
    else:
        raise BridgeError("ldat não corresponde a um perfil de registros comprovado.")
    result = []
    for i in range(count):
        budget.check()
        offset = i * record_size * (dimensions if interleaved else 1)
        ticks = struct.unpack_from(">i", data, offset)[0]
        if ticks == -(2**31):
            raise BridgeError("Keyframe sem tempo (sentinela).")
        values, ins, outs, in_speed, in_inf, out_speed, out_inf = [], [], [], [], [], [], []
        continuous = []
        for dim in range(dimensions):
            o = offset + dim * 48 if interleaved else offset
            if struct.unpack_from(">i", data, o)[0] != ticks:
                raise BridgeError("Tempos divergentes entre componentes intercalados.")
            code_in, code_out = data[o + 4], data[o + 5]
            flags = struct.unpack_from(">H", data, o + 6)[0]
            if code_in not in INTERP or code_out not in INTERP or flags & ~0x7C8:
                raise BridgeError("Interpolação/flags de keyframe não suportadas (auto/roving/desconhecidas).")
            doubles = (
                [struct.unpack_from(">d", data, o + 8 + (j * dimensions + dim) * 8)[0] for j in range(5)]
                if not interleaved
                else list(struct.unpack_from(">5d", data, o + 8))
            )
            if not all(math.isfinite(v) for v in doubles):
                raise BridgeError("Valor ou tangente não finita.")
            value, si, ii, so, oi = doubles
            if flags & 8:
                # Continuous is an editing constraint, not permission to replace
                # the stored derivative. Endpoints have only one active side.
                # Interior mismatches need a separately verified resolution rule.
                if code_in != 2 or code_out != 2 or (0 < i < count - 1 and si != so):
                    raise BridgeError("Continuous Bezier exige lados Bezier e velocidades internas iguais.")
            if not (0 <= ii <= 1 and 0 <= oi <= 1):
                raise BridgeError("Influência fora de 0..1; não será normalizada por suposição.")
            values.append(value)
            ins.append(INTERP[code_in])
            outs.append(INTERP[code_out])
            in_speed.append(si)
            in_inf.append(ii)
            out_speed.append(so)
            out_inf.append(oi)
            continuous.append(bool(flags & 8))
        metadata: dict[str, str | list[bool]] = {"layout": "interleaved-48" if interleaved else "tdb4-nonspatial"}
        if any(continuous):
            metadata["source_temporal_continuous"] = continuous
        result.append(
            Keyframe(
                ticks=ticks,
                time_base=time_base,
                value=values[0] if dimensions == 1 else values,
                in_interp=ins,
                out_interp=outs,
                handles=BezierHandles(
                    in_speed=in_speed, in_influence=in_inf, out_speed=out_speed, out_influence=out_inf
                ),
                metadata=metadata,
            )
        )
    if any(a.ticks >= b.ticks for a, b in zip(result, result[1:], strict=False)):
        raise BridgeError("Keyframes fora de ordem ou duplicados: requerem interpretação adicional.")
    return result


def _color_keys(data: memoryview, count: int, size: int, base: int, budget: Budget) -> list[Keyframe]:
    """AE single-ease Color: 56-byte header + ARGB + eight zero tangents.

    Linear/Hold only. The single Bezier ease is not a per-component derivative.
    Source: pinned py-aep ldat; confirmed by real Tritone selected property.
    """
    if size != 152 or len(data) != count * size:
        raise BridgeError("Registro de keyframe Color exige 152 bytes por chave.")
    result = []
    for i in range(count):
        budget.check()
        o = i * size
        ticks, code_in, code_out, flags, spatial, reserved = struct.unpack_from(">iBBHII", data, o)
        if (
            ticks == -(2**31)
            or code_in not in (1, 3)
            or code_out not in (1, 3)
            or flags & 7 != 1
            or flags & ~0x7C1
            or spatial not in (0, 2)
            or reserved != 0
        ):
            raise BridgeError("Color: Bezier/auto/flags desconhecidas não têm tradução verificada.")
        ease = struct.unpack_from(">5d", data, o + 16)
        numbers = struct.unpack_from(">12d", data, o + 56)
        if (
            not all(math.isfinite(x) for x in (*ease, *numbers))
            or ease[0] < 0
            or not 0 <= ease[2] <= 1
            or not 0 <= ease[4] <= 1
            or any(x != 0 for x in numbers[4:])
        ):
            raise BridgeError("Color: ease inválido ou tangentes não nulas.")
        result.append(
            Keyframe(
                ticks=ticks,
                time_base=base,
                value=list(numbers[:4]),
                in_interp=[INTERP[code_in]] * 4,
                out_interp=[INTERP[code_out]] * 4,
                metadata={
                    "layout": "AE-color-single-ease-152",
                    "spatial_flags_ignored_for_color": spatial,
                    "stored_ease": list(ease),
                },
            )
        )
    if any(a.ticks >= b.ticks for a, b in zip(result, result[1:], strict=False)):
        raise BridgeError("Keyframes Color fora de ordem ou duplicados.")
    return result
