"""Importação opcional de presets pela API oficial do FilmCraft."""

import json
from pathlib import Path

from craft_bridge.core.safety import BridgeError, Limits, read_bounded
from craft_bridge.core.validation import validate_filmcraft
from craft_bridge.integrations.control import ControlClient
from craft_bridge.mappings.registry import Registry


def import_presets(
    path: str | Path, *, port: int = 9876, timeout: float = 10, confirmed: bool = False, dry_run: bool = False
) -> dict:
    path = Path(path).resolve()
    try:
        document = json.loads(read_bounded(path, Limits()))
    except ValueError as exc:
        raise BridgeError(f"JSON FilmCraft inválido: {exc}") from exc
    validate_filmcraft(document, Registry())
    command = {"command": "presets.import", "params": {"path": str(path)}}
    if dry_run:
        return {"dry_run": True, "commands": [command]}
    if not confirmed:
        raise BridgeError("Importação altera a biblioteca e exige confirmação (--yes).")
    with ControlClient(port, timeout) as client:
        result = client.execute("presets.import", {"path": str(path)})
    return {"imported": result, "file": str(path)}
