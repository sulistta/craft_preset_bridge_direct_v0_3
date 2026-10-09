"""Layouts first-party documentados de aRbp; nenhum blob é executado.

Evidência: py-aep/docs/file_format.md, aRbp, no commit de references.json.
IDs derivados descrevem os valores do blob, não os campos temporários da UI.
"""

import math
import struct

from craft_bridge.core.safety import BridgeError

HUE = "ADBE HUE SATURATION-0003"
LEVELS = "ADBE Easy Levels2-0002"
CURVES = "ADBE CurvesCustom-0001"
RANGES = ("reds", "yellows", "greens", "cyans", "blues", "magentas")
CHANNELS = ("", "red", "green", "blue", "alpha")
LEVEL_VALUES = ("inBlack", "inWhite", "gamma", "outBlack", "outWhite")


def decode_numeric(match: str, data: bytes | memoryview) -> dict[str, float]:
    """Valida o blob inteiro antes de retornar qualquer valor para conversão."""
    if match == HUE:
        if len(data) != 180:
            raise BridgeError("Hue/Saturation aRbp exige exatamente 180 bytes.")
        values = struct.unpack(">45i", data)
        result = dict(zip(("hue", "saturation", "lightness"), map(float, values[:3]), strict=True))
        for i, prefix in enumerate(RANGES):
            outer_start, start, end, outer_end, hue, sat, light = values[3 + 7 * i : 10 + 7 * i]
            # Windows are circular, e.g. reds: 315,345,15,45. Keep their actual
            # angles; the native renderer uses rem_euclid for both start and end.
            if any(not -360 <= x <= 720 for x in (outer_start, start, end, outer_end)):
                raise BridgeError("Janela de matiz fora do perfil documentado.")
            fall_start, width, fall_end = (
                (start - outer_start) % 360,
                (end - start) % 360,
                (outer_end - end) % 360,
            )
            if fall_start > 180 or fall_end > 180 or fall_start + width + fall_end > 360:
                raise BridgeError("Janela de matiz ambígua ou com falloff sobreposto.")
            result.update(
                {
                    prefix + "RangeStart": float(start),
                    prefix + "RangeEnd": float(end),
                    prefix + "StartFalloff": float(fall_start),
                    prefix + "EndFalloff": float(fall_end),
                    prefix + "Hue": float(hue),
                    prefix + "Saturation": float(sat),
                    prefix + "Lightness": float(light),
                }
            )
        return result
    if match == LEVELS:
        if len(data) != 108 or struct.unpack_from(">2I", data) != (0x000F10A7, 1):
            raise BridgeError("Versão/tamanho de Levels aRbp não reconhecido.")
        numbers = struct.unpack_from(">25f", data, 8)
        if not all(math.isfinite(x) for x in numbers):
            raise BridgeError("Levels aRbp contém valor não finito.")
        return {
            (prefix + suffix[0].upper() + suffix[1:] if prefix else suffix): float(numbers[5 * i + j])
            for i, prefix in enumerate(CHANNELS)
            for j, suffix in enumerate(LEVEL_VALUES)
        }
    raise BridgeError("Layout aRbp sem decoder numérico verificado.")


def decode_curves(data: bytes | memoryview) -> dict:
    """Preserva LUT e pontos, sem presumir equivalência de interpolação no destino."""
    if len(data) != 1644 or struct.unpack_from(">2H", data) != (1, 1):
        raise BridgeError("Versão/tamanho de Curves aRbp não reconhecido.")
    channels = []
    for i, name in enumerate(("rgb", "red", "green", "blue", "alpha")):
        start = 1284 + i * 72
        count, flag = struct.unpack_from(">2I", data, start + 64)
        if not 0 <= count <= 16 or flag not in (1, 0xFFFFFFFF):
            raise BridgeError("Registro de Curves fora do perfil documentado.")
        pairs = [list(struct.unpack_from(">2H", data, start + j * 4)) for j in range(count)]
        if any(x > 255 for pair in pairs for x in pair):
            raise BridgeError("Ponto de Curves fora do intervalo 0..255.")
        channels.append(
            {"channel": name, "lut": list(data[4 + i * 256 : 260 + i * 256]), "points": pairs, "flag": flag}
        )
    return {"layout": "AE-Curves-v1", "channels": channels}


def curve_lut_text(channel: dict) -> str:
    """Transfer every stored 8-bit LUT sample; no guessed source spline.

    Native interpolation between samples differs and must be reported as loss.
    Keep the original control points/flag separately for diagnosis and future fidelity.
    """
    lut = channel["lut"]
    if len(lut) != 256 or any(type(v) is not int or not 0 <= v <= 255 for v in lut):
        raise BridgeError("Curves exige uma LUT de 256 inteiros 0..255.")
    return " ".join(f"{x / 255:.17g},{y / 255:.17g}" for x, y in enumerate(lut))
