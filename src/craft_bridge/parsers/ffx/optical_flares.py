"""Original bounded OFP v3 structural decoder; no renderer or external asset access.

Envelope/field grammar corroborated by pinned Nuaj research and 38 real blobs.
Preserves raw field/object-name bytes for lossless data roundtrip. Field IDs and
auxiliary flags are not mapped to renderer semantics; labels remain raw bytes.
"""

import math
import struct
from dataclasses import dataclass

from craft_bridge.core.safety import BridgeError, Budget

OPTIONS = "VIDEOCOPILOT OpticalFlares-0024"
MAX_BYTES = 2 * 1024 * 1024
MAX_FIELDS = 20_000
MAX_OBJECTS = 1024


@dataclass
class Reader:
    data: memoryview
    offset: int = 4
    fields: int = 0
    budget: Budget | None = None

    def atom(self, expected: int, size: int) -> bytes:
        if self.offset + 4 > len(self.data):
            raise BridgeError("OFP: cabeçalho de átomo truncado.")
        tag, length = struct.unpack_from("<HH", self.data, self.offset)
        if tag != expected or length != size or self.offset + 4 + length > len(self.data):
            raise BridgeError("OFP: tag, tamanho ou limite de átomo incompatível.")
        self.offset += 4
        value = bytes(self.data[self.offset : self.offset + length])
        self.offset += length
        return value

    def marker(self, tag: int) -> None:
        if self.atom(tag, 1) != b"\0":
            raise BridgeError("OFP: payload de marcador desconhecido.")

    def block(self, end: int) -> list[dict]:
        fields: list[dict] = []
        while True:
            if self.budget:
                self.budget.check()
            if self.offset + 4 > len(self.data):
                raise BridgeError("OFP: bloco sem marcador final.")
            tag = struct.unpack_from("<H", self.data, self.offset)[0]
            if tag == end:
                self.marker(end)
                return fields
            id = struct.unpack("<I", self.atom(0x32, 4))[0]
            kind = struct.unpack("<I", self.atom(0x33, 4))[0]
            raw = self.atom(0x34, 32)
            self.marker(2000)
            self.fields += 1
            if self.fields > MAX_FIELDS:
                raise BridgeError("OFP: limite de campos excedido.")
            if self.budget:
                self.budget.check("parameters")
            value: object
            if kind == 0:
                number = struct.unpack_from("<f", raw)[0]
                finite(number)
                value = number
            elif kind == 1:
                x, y = struct.unpack_from("<2f", raw)
                finite(x)
                finite(y)
                value = {"x": x, "y": y, "flag_byte": raw[8]}
            elif kind == 2:
                # Packed little-endian ABGR: raw bytes are R,G,B,A.
                value = {"rgba8": list(raw[:4]), "flag_byte": raw[4]}
            elif kind == 3:
                value = struct.unpack_from("<i", raw)[0]
            elif kind == 4:
                value = bool(raw[0])
            elif kind == 5:
                value = {
                    "code": struct.unpack_from("<i", raw)[0],
                    "label_bytes": raw[4:].split(b"\0", 1)[0].hex(),
                }
            elif kind == 6:
                value = None  # Separator, not a rendering control.
            else:
                raise BridgeError("OFP: tipo de campo desconhecido.")
            fields.append({"id": id, "kind": kind, "value": value, "raw_hex": raw.hex()})


def finite(value: float) -> None:
    if not math.isfinite(value):
        raise BridgeError("OFP: valor de campo não finito.")


def flag(value: int) -> bool:
    if value not in (0, 1):
        raise BridgeError("OFP: flag booleano desconhecido.")
    return bool(value)


def decode_ofp(data: bytes | memoryview, budget: Budget | None = None) -> dict:
    if len(data) > MAX_BYTES or len(data) < 9 or bytes(data[:4]) != b"OFP\3":
        raise BridgeError("OFP: assinatura, versão ou tamanho não suportado.")
    reader = Reader(memoryview(data), budget=budget)
    reader.marker(3000)
    globals = reader.block(4000)
    objects: list[dict] = []
    while reader.offset < len(data):
        if budget:
            budget.check()
        if len(objects) >= MAX_OBJECTS:
            raise BridgeError("OFP: limite de objetos excedido.")
        type = struct.unpack("<I", reader.atom(1, 4))[0]
        name = reader.atom(2, 64)
        hidden = flag(reader.atom(3, 1)[0])
        solo = flag(reader.atom(4, 1)[0])
        fields = reader.block(1000)
        # Unknown object types retain their complete fields, but have no renderer.
        objects.append(
            {"type": type, "name_bytes": name.hex(), "hidden": hidden, "solo": solo, "fields": fields}
        )
    return {
        "format": "craftbridge.ofp-scene",
        "version": 3,
        "globals": globals,
        "objects": objects,
        "field_count": reader.fields,
        "render_semantics_verified": False,
    }


def encode_ofp(scene: dict) -> bytes:
    """Reconstruct validated original data for maintainer roundtrip verification.

    This is an exact raw-data roundtrip, not a certified OFP preset editor.
    Edits inconsistent with the raw bytes are rejected.
    """

    def atom(tag, raw):
        return struct.pack("<HH", tag, len(raw)) + raw

    def block(fields, end):
        result = bytearray()
        for f in fields:
            result += atom(0x32, struct.pack("<I", f["id"])) + atom(0x33, struct.pack("<I", f["kind"]))
            result += atom(0x34, bytes.fromhex(f["raw_hex"])) + atom(2000, b"\0")
        return bytes(result) + atom(end, b"\0")

    try:
        if scene.get("format") != "craftbridge.ofp-scene" or scene.get("version") != 3:
            raise ValueError("scene format")
        objects = scene["objects"]
        globals = scene["globals"]
        if not isinstance(objects, list) or not isinstance(globals, list):
            raise ValueError("scene arrays")
        if len(objects) > MAX_OBJECTS:
            raise ValueError("scene objects")
        # Validate lengths before decoding hexadecimal or allocating output. A field
        # is 57 bytes, each object envelope 91 bytes, and global framing 14 bytes.
        count = len(globals)
        for obj in objects:
            if not isinstance(obj["fields"], list) or len(obj["name_bytes"]) != 128:
                raise ValueError("scene object layout")
            count += len(obj["fields"])
        if count > MAX_FIELDS or 14 + 91 * len(objects) + 57 * count > MAX_BYTES:
            raise ValueError("scene limits")
        for fields in [globals, *(obj["fields"] for obj in objects)]:
            if any(not isinstance(f["raw_hex"], str) or len(f["raw_hex"]) != 64 for f in fields):
                raise ValueError("scene field layout")
        result = bytearray(b"OFP\3" + atom(3000, b"\0") + block(scene["globals"], 4000))
        for obj in objects:
            result += atom(1, struct.pack("<I", obj["type"])) + atom(2, bytes.fromhex(obj["name_bytes"]))
            result += atom(3, bytes([int(obj["hidden"])])) + atom(4, bytes([int(obj["solo"])]))
            result += block(obj["fields"], 1000)
            if len(result) > MAX_BYTES:
                raise ValueError("scene size")
        # Roundtrip structures must agree with all decoded fields, not just raw bytes.
        if decode_ofp(result) != scene:
            raise ValueError("scene fields differ from raw data")
        return bytes(result)
    except (KeyError, TypeError, ValueError, OverflowError, struct.error) as exc:
        raise BridgeError("OFP: estrutura inválida para roundtrip.") from exc
