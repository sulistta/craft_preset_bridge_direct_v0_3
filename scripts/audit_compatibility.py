"""Diagnóstico agregado local; não exporta valores, caminhos ou presets privados."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from craft_bridge.core.pipeline import candidate_files, inspect_file, preview
from craft_bridge.core.safety import BridgeError, Limits, atomic_write, read_bounded
from craft_bridge.extensions import NAMES, extension_paths
from craft_bridge.mappings.registry import Registry


def audit(root: Path, registry: Registry, source_size: tuple[int, int] | None = None) -> dict:
    statuses: Counter[str] = Counter()
    observations: Counter[str] = Counter()
    rows: dict[tuple[str, str, str], dict] = {}
    files = candidate_files(root)
    rank = {"SUCCESS": 0, "PARTIAL": 1, "UNSUPPORTED": 2, "FAILED": 3}
    for path in files:
        document = inspect_file(path)
        before = document.source.sha256
        target = "effectcraft" if document.source.format == "ffx" else "filmcraft"
        # EffectCraft exports one selected preset; audit every preset explicitly.
        documents = [document]
        if document.source.format == "ffx":
            documents = [document.model_copy(update={"presets": [p]}) for p in document.presets]
        file_statuses = []
        seen = set()
        file_observations = set()
        for selected in documents:
            _, report = preview(selected, registry=registry, source_size=source_size)
            file_statuses.append(report.status)
            sources = [e for p in selected.presets for e in p.effects]
            for source, result in zip(sources, report.effects, strict=True):
                key = (document.source.format, target, source.identifier.match_name)
                if key not in rows:
                    rows[key] = {
                        "source_format": key[0], "target": key[1], "effect": key[2],
                        "map_available": registry.find(*key) is not None,
                        "files": 0, "instances": 0, "instances_without_converted_parameters": 0,
                        "parameters_converted": 0, "keyframes_preserved": 0,
                        "source_unknown_parameters": 0,
                        "source_parameter_loss_warnings": Counter(),
                        "conversion_loss_warnings": Counter(),
                    }
                row = rows[key]
                if key not in seen:
                    row["files"] += 1
                    seen.add(key)
                row["instances"] += 1
                if not row["map_available"]:
                    file_observations.add("missing_effect_map")
                if any(w.loss for w in result.warnings):
                    file_observations.add("effect_conversion_loss")
                row["instances_without_converted_parameters"] += result.parameters_converted == 0
                row["parameters_converted"] += result.parameters_converted
                row["keyframes_preserved"] += result.keyframes_preserved
                params = [p for p in source.parameters if not p.metadata.get("administrative")]
                if any(p.value.kind == "unknown" for p in params):
                    file_observations.add("unknown_source_parameter")
                row["source_unknown_parameters"] += sum(p.value.kind == "unknown" for p in params)
                row["source_parameter_loss_warnings"].update(w.code for p in params for w in p.warnings if w.loss)
                row["conversion_loss_warnings"].update(w.code for w in result.warnings if w.loss)
        after = hashlib.sha256(read_bounded(path, Limits())).hexdigest()
        if before != after:
            raise BridgeError("Arquivo de origem mudou durante a auditoria; relatório não publicado.")
        statuses[max(file_statuses, key=rank.__getitem__) if file_statuses else "UNSUPPORTED"] += 1
        observations.update(file_observations)
    effects = sorted(rows.values(), key=lambda r: (r["map_available"], -r["files"], r["source_format"], r["effect"]))
    for row in effects:
        for field in ("source_parameter_loss_warnings", "conversion_loss_warnings"):
            row[field] = dict(sorted(row[field].items()))
    return {
        "format": "craftbridge.compatibility-audit", "version": 1,
        "files": len(files), "file_statuses": dict(sorted(statuses.items())),
        "files_with_observation": dict(sorted(observations.items())),
        "mapping_count": len(registry.mappings),
        "source_size": list(source_size) if source_size else None,
        "all_original_hashes_unchanged": True,
        "engine_contacted": False, "visual_equivalence_verified": False,
        "effects": effects,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--bundled", action="store_true", help="Incluir mapas das extensões originais empacotadas.")
    parser.add_argument("--map", action="append", default=[], type=Path, dest="maps")
    parser.add_argument("--size", nargs=2, type=int, metavar=("WIDTH", "HEIGHT"))
    args = parser.parse_args()
    if args.output.resolve().is_relative_to(args.root.resolve()):
        parser.error("A saída deve ficar fora da pasta dos presets.")
    try:
        packages = [extension_paths(name)[0] for name in NAMES] if args.bundled else []
        registry = Registry(packages=packages + args.maps)
        result = audit(args.root, registry, tuple(args.size) if args.size else None)
        atomic_write(args.output, json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    except (BridgeError, OSError) as exc:
        parser.exit(1, f"Auditoria interrompida: {exc}\n")
    print(f"{result['files']} arquivos; {len(result['effects'])} identificadores de efeito. Relatório: {args.output}")


if __name__ == "__main__":
    main()
