"""Cliente JSON/TCP loopback com respostas limitadas, IDs e timeout."""

import json
import socket
from types import TracebackType
from typing import Any, BinaryIO

from craft_bridge.core.safety import BridgeError


class ControlClient:
    def __init__(self, port: int = 9877, timeout: float = 10.0):
        if not 1 <= port <= 65535 or not 0 < timeout <= 60:
            raise BridgeError("Porta/timeout inválidos.")
        self.port, self.timeout = port, timeout
        self.socket: socket.socket | None = None
        self.reader: BinaryIO | None = None
        self.sequence = 0

    def __enter__(self) -> "ControlClient":
        try:
            self.socket = socket.create_connection(("127.0.0.1", self.port), timeout=self.timeout)
            self.reader = self.socket.makefile("rb")
        except OSError as exc:
            raise BridgeError(f"Não foi possível conectar à porta local {self.port}: {exc}") from exc
        return self

    def __exit__(self, typ: type | None, value: BaseException | None, tb: TracebackType | None) -> None:
        if self.reader:
            self.reader.close()
        if self.socket:
            self.socket.close()

    def execute(self, command: str, params: dict | None = None) -> Any:
        if self.socket is None or self.reader is None:
            raise BridgeError("Cliente não conectado.")
        self.sequence += 1
        request = {
            "id": self.sequence,
            "method": "engine.execute",
            "params": {"command": command, "params": params or {}},
        }
        payload = json.dumps(request, allow_nan=False).encode("utf-8") + b"\n"
        if len(payload) > 4 * 1024 * 1024:
            raise BridgeError("Comando excede o tamanho máximo.")
        try:
            self.socket.sendall(payload)
            line = self.reader.readline(4 * 1024 * 1024 + 1)
        except OSError as exc:
            raise BridgeError(f"Conexão interrompida/timeout em {command}: {exc}") from exc
        if not line.endswith(b"\n") or len(line) > 4 * 1024 * 1024:
            raise BridgeError("Resposta truncada, ausente ou excede o limite.")
        try:
            reply = json.loads(line)
        except (ValueError, UnicodeDecodeError) as exc:
            raise BridgeError("Resposta do protocolo não é JSON válido.") from exc
        if not isinstance(reply, dict) or reply.get("id") != self.sequence:
            raise BridgeError("ID de resposta divergente.")
        if reply.get("ok") is not True:
            raise BridgeError(f"{command}: {reply.get('error', 'resposta sem ok=true')}")
        return reply.get("result")
