"""Leitor RIFX com offsets e views, sem execução de conteúdo embutido."""

import struct
from collections.abc import Iterator
from dataclasses import dataclass, field

from craft_bridge.core.safety import BridgeError, Budget


@dataclass
class Chunk:
    id: str
    offset: int
    data: memoryview
    form: str | None = None
    children: list["Chunk"] = field(default_factory=list)

    def walk(self) -> Iterator["Chunk"]:
        yield self
        for child in self.children:
            yield from child.walk()

    def leaf(self, name: str) -> "Chunk | None":
        return next((c for c in self.children if c.id == name and c.form is None), None)


def parse_rifx(data: bytes, budget: Budget) -> tuple[Chunk, bytes]:
    if len(data) < 12 or data[:4] != b"RIFX" or data[8:12] != b"FaFX":
        raise BridgeError("FFX inválido: esperado RIFX big-endian com form FaFX.")
    if len(data) > budget.limits.max_file_bytes:
        raise BridgeError("Arquivo excede o limite de tamanho.")
    view = memoryview(data)

    def parse(offset: int, end: int, depth: int) -> tuple[Chunk, int]:
        budget.check("chunks")
        if depth > budget.limits.max_depth:
            raise BridgeError("Profundidade máxima de chunks excedida.")
        if offset + 8 > end:
            raise BridgeError(f"Cabeçalho de chunk truncado em {offset}.")
        tag = bytes(view[offset : offset + 4])
        if any(c < 32 or c > 126 for c in tag):
            raise BridgeError(f"FourCC inválido em {offset}.")
        size = struct.unpack_from(">I", view, offset + 4)[0]
        raw_end = offset + 8 + size
        padded_end = raw_end + size % 2
        if padded_end > end:
            raise BridgeError(f"Chunk {tag!r} em {offset} ultrapassa o limite do pai.")
        chunk = Chunk(tag.decode("ascii"), offset, view[offset + 8 : raw_end])
        if tag in (b"LIST", b"RIFX"):
            if size < 4:
                raise BridgeError(f"Container sem form em {offset}.")
            chunk.form = bytes(chunk.data[:4]).decode("latin1")
            if chunk.form == "btdk":
                # AEP text document exception: opaque payload, not a chunk tree.
                return chunk, padded_end
            pos = offset + 12
            while pos < raw_end:
                child, pos = parse(pos, raw_end, depth + 1)
                chunk.children.append(child)
        return chunk, padded_end

    top, end = parse(0, len(data), 0)
    return top, data[end:]


def decode_string(data: memoryview | bytes) -> str:
    raw = bytes(data)
    if raw[:4] == b"Utf8":
        if len(raw) < 8:
            raise BridgeError("String Utf8 sem comprimento.")
        size = int.from_bytes(raw[4:8], "big")
        if size > len(raw) - 8:
            raise BridgeError("String Utf8 truncada.")
        raw = raw[8 : 8 + size]
        try:
            return raw.rstrip(b"\0").decode("utf-8")
        except UnicodeDecodeError as exc:
            raise BridgeError("String Utf8 inválida.") from exc
    return raw.split(b"\0", 1)[0].decode("latin1")
