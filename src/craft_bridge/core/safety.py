"""Limites compartilhados e operações de arquivo sem sobrescrita implícita."""

import base64
import hashlib
import json
import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class BridgeError(ValueError):
    """Erro controlado de entrada, conversão ou protocolo."""


@dataclass(frozen=True)
class Limits:
    max_file_bytes: int = 64 * 1024 * 1024
    max_chunks: int = 100_000
    max_depth: int = 48
    max_effects: int = 2048
    max_parameters: int = 50_000
    max_keyframes: int = 100_000
    max_diagnostic_bytes: int = 96
    max_diagnostics: int = 256
    max_seconds: float = 15.0

    def __post_init__(self) -> None:
        if any(value <= 0 for value in vars(self).values()):
            raise BridgeError("Todos os limites devem ser positivos.")


class Budget:
    def __init__(self, limits: Limits):
        self.limits = limits
        self.deadline = time.monotonic() + limits.max_seconds
        self.counts: dict[str, int] = {}

    def check(self, kind: str | None = None, count: int = 1) -> None:
        if time.monotonic() > self.deadline:
            raise BridgeError("Limite de tempo de processamento excedido.")
        if kind:
            self.counts[kind] = self.counts.get(kind, 0) + count
            if self.counts[kind] > getattr(self.limits, "max_" + kind):
                raise BridgeError(f"Limite de {kind} excedido.")


def read_bounded(path: Path, limits: Limits) -> bytes:
    if not path.is_file():
        raise BridgeError(f"Arquivo não encontrado: {path}")
    with path.open("rb") as stream:
        data = stream.read(limits.max_file_bytes + 1)
    if len(data) > limits.max_file_bytes:
        raise BridgeError("Arquivo excede o limite de tamanho.")
    return data


def raw_summary(data: bytes | memoryview, limits: Limits, offset: int | None = None) -> dict[str, Any]:
    return {
        "size": len(data),
        "offset": offset,
        "sha256": hashlib.sha256(data).hexdigest(),
        "sample_base64": base64.b64encode(data[: limits.max_diagnostic_bytes]).decode("ascii"),
        "truncated": len(data) > limits.max_diagnostic_bytes,
    }


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"


def atomic_write(path: Path, text: str, *, overwrite: bool = False) -> None:
    """Publica texto completo; por padrão recusa arquivos e symlinks existentes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".craft-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        if overwrite:
            os.replace(temp, path)
        else:
            try:
                os.link(temp, path)
            except FileExistsError as exc:
                raise BridgeError(f"Saída já existe; escolha outro caminho: {path}") from exc
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
