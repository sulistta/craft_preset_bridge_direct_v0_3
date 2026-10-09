"""Bounded structural Mesh Warp reader; record semantics remain unverified.

Evidence: one authorized snapshot, both default and instance, plus py-aep's
aRbs ownership documentation. This is not a renderer or a control-point map.
"""

import math
import struct

from craft_bridge.core.safety import BridgeError, Budget

MESH = "ADBE MESH WARP-0004"
LAYOUT = "AE-MeshWarp-8x8-10f32-structural"
HEADER = (8, 8, 0, 0, 0x0D0D)
RECORDS = 64
SIZE = 20 + RECORDS * 40


def decode_mesh(data: bytes | memoryview, budget: Budget | None = None) -> dict:
    """Preserve all ten float32 fields per record, including signed zero.

    Accept only the observed header/size. No interpretation of pair ordering,
    tangents, normalized coordinates, or undocumented header fields is implied.
    """
    if len(data) != SIZE or struct.unpack_from(">5I", data) != HEADER:
        raise BridgeError("Mesh Warp: cabeçalho/tamanho fora do perfil estrutural observado.")
    records = []
    for i in range(RECORDS):
        if budget is not None:
            budget.check("parameters")
        record = list(struct.unpack_from(">10f", data, 20 + i * 40))
        if not all(math.isfinite(v) for v in record):
            raise BridgeError("Mesh Warp: registro com float32 não finito.")
        records.append(record)
    return {"layout": LAYOUT, "header_words": list(HEADER), "record_count": RECORDS, "records": records}


def encode_mesh(decoded: dict) -> bytes:
    """Diagnostic serializer only; require a complete, exact float32 representation."""
    if (
        set(decoded) != {"layout", "header_words", "record_count", "records"}
        or decoded["layout"] != LAYOUT
        or decoded["header_words"] != list(HEADER)
        or not isinstance(decoded["header_words"], list)
        or any(type(v) is not int for v in decoded["header_words"])
        or type(decoded["record_count"]) is not int
        or decoded["record_count"] != RECORDS
        or not isinstance(decoded["records"], list)
        or len(decoded["records"]) != RECORDS
    ):
        raise BridgeError("Mesh Warp: representação estrutural inconsistente.")
    output = bytearray(struct.pack(">5I", *HEADER))
    for record in decoded["records"]:
        if (
            not isinstance(record, list)
            or len(record) != 10
            or any(type(v) not in (int, float) for v in record)
        ):
            raise BridgeError("Mesh Warp: esperado registro de dez números finitos.")
        try:
            raw = struct.pack(">10f", *record)
        except (OverflowError, struct.error) as exc:
            raise BridgeError("Mesh Warp: número fora da representação float32.") from exc
        unpacked = list(struct.unpack(">10f", raw))
        if not all(math.isfinite(v) for v in unpacked) or unpacked != record:
            raise BridgeError("Mesh Warp: número não representável exatamente em float32.")
        output.extend(raw)
    return bytes(output)
