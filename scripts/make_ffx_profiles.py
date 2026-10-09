"""Extrai IDs/tipos de todos os descriptors reais, sem dados privados de presets.

Execute sobre um corpus real autorizado. Tipos não dependem de mapas instalados.
Propriedades derivadas pelo Bridge e streams selecionados sem parT não são evidência.
"""

import argparse
import json
from collections.abc import Iterable
from pathlib import Path

from craft_bridge.core.models import PresetDocument
from craft_bridge.core.pipeline import inspect_file

ROOT = Path(__file__).resolve().parents[1]


def extract_profiles(documents: Iterable[PresetDocument]) -> tuple[dict[str, dict], set[str]]:
    observed: dict[str, dict] = {}
    conflicts: set[str] = set()
    for document in documents:
        for preset in document.presets:
            for effect in preset.effects:
                if effect.feature != "effect":
                    continue
                for param in effect.parameters:
                    kind, dims = param.metadata.get("kind"), param.metadata.get("dimensions")
                    if (
                        param.metadata.get("derived_from")
                        or not isinstance(param.origin.get("tdb4"), dict)
                        or kind not in (1, 2, 3, 4, 5, 6, 7, 9, 10)
                        or dims not in (1, 2, 3, 4)
                    ):
                        continue
                    entry = {"kind": kind, "expected_dimensions": dims, "evidence": "real-parT-and-tdb4"}
                    if param.id in observed and observed[param.id] != entry:
                        conflicts.add(param.id)
                    observed[param.id] = entry
    for match in conflicts:
        observed.pop(match, None)
    # Only scalar, two-dimensional Point and four-dimensional Color profiles audited
    # by this parser; an unsupported shape cannot promote selected properties.
    observed = {id: entry for id, entry in observed.items() if entry["expected_dimensions"] == (
        4 if entry["kind"] == 5 else 2 if entry["kind"] == 6 else 1
    )}
    return dict(sorted(observed.items())), conflicts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "src/craft_bridge/parsers/ffx/parameter-types.json")
    args = parser.parse_args()
    if not args.corpus.is_dir():
        parser.error("Corpus local ausente")
    observed, conflicts = extract_profiles(inspect_file(file) for file in sorted(args.corpus.rglob("*.ffx")))
    args.output.write_text(json.dumps({
        "format": "craftbridge.ffx-parameter-types", "version": 1,
        "evidence": "Private real corpus; all exact raw parT kinds/tdb4 shapes; no derived IDs, UI names or preset values",
        "parameters": observed,
    }, ensure_ascii=False, indent=2) + "\n")
    print(f"{len(observed)} tipos reais; {len(conflicts)} conflitos excluídos")


if __name__ == "__main__":
    main()
