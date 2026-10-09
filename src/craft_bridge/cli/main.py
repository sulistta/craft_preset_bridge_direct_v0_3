"""CLI em português, headless; códigos de saída documentados no README."""

import argparse
import importlib.util
import logging
import platform
import shutil
import sys
from pathlib import Path

from pydantic import ValidationError

from craft_bridge import __version__
from craft_bridge.core.pipeline import batch_convert, batch_csv, convert_file, inspect_file, preview
from craft_bridge.core.resources import SourceLayerBindings
from craft_bridge.core.safety import BridgeError, Limits, atomic_write, json_text, read_bounded
from craft_bridge.integrations.effectcraft import apply_plan, load_plan
from craft_bridge.integrations.filmcraft import import_presets
from craft_bridge.mappings.registry import Registry

EXIT = {"SUCCESS": 0, "PARTIAL": 2, "UNSUPPORTED": 3, "FAILED": 1}


def size_arg(value: str) -> tuple[int, int]:
    try:
        width, height = [int(x) for x in value.lower().split("x")]
        if not (0 < width <= 65536 and 0 < height <= 65536):
            raise ValueError
        return width, height
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Use LARGURAxALTURA, por exemplo 1920x1080.") from exc


def conversion_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--strict", action="store_true", help="Rejeitar conversões com perdas relevantes")
    parser.add_argument("--dry-run", action="store_true", help="Simular sem escrever arquivos nem conectar")
    parser.add_argument("--size", type=size_arg, help="Resolução de referência para pontos normalizados")
    parser.add_argument("--keyframe-mode", choices=["Scale", "AnchorToIn", "AnchorToOut"])
    parser.add_argument("--max-mib", type=int, default=64, help="Limite por arquivo, em MiB")
    parser.add_argument("--timeout", type=float, default=15, help="Limite cooperativo de parsing em segundos")
    parser.add_argument("--json", action="store_true", help="Relatório estruturado")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog="craft-bridge", description="Conversão local de presets para FilmCraft e EffectCraft."
    )
    root.add_argument("--version", action="version", version=__version__)
    root.add_argument("--verbose", action="store_true")
    commands = root.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect", help="Analisar conteúdo e compatibilidade")
    inspect.add_argument("file", type=Path)
    inspect.add_argument("--json", action="store_true")
    inspect.add_argument("--size", type=size_arg)
    inspect.add_argument("--source-layers", help="JSON de vínculos manuais fixado ao SHA-256 do FFX")
    inspect.add_argument("--max-mib", type=int, default=64)
    inspect.add_argument("--timeout", type=float, default=15)
    convert = commands.add_parser("convert", help="Converter e gerar relatórios JSON/HTML")
    convert.add_argument("file", type=Path)
    convert.add_argument("--out", type=Path, required=True)
    convert.add_argument("--target", choices=["filmcraft", "effectcraft"])
    convert.add_argument("--source-layers", help="JSON de vínculos manuais fixado ao SHA-256 do FFX")
    conversion_options(convert)
    batch = commands.add_parser("batch", help="Converter uma pasta recursivamente")
    batch.add_argument("folder", type=Path)
    batch.add_argument("--out", type=Path, required=True)
    batch.add_argument("--preserve-folders", action="store_true")
    conversion_options(batch)
    doctor = commands.add_parser("doctor", help="Diagnóstico do ambiente")
    doctor.add_argument("--json", action="store_true")
    maps = commands.add_parser("mappings", help="Listar/instalar mapas declarativos")
    maps_sub = maps.add_subparsers(dest="mapping_command", required=True)
    maps_sub.add_parser("list")
    install = maps_sub.add_parser("install")
    install.add_argument("package", type=Path)
    extensions = commands.add_parser("extensions", help="Renderers próprios com conversão aproximada")
    extension_sub = extensions.add_subparsers(dest="extension_command", required=True)
    extension_sub.add_parser("list")
    extension_install = extension_sub.add_parser("install", help="Instalar mapa; não carrega o renderer")
    from craft_bridge.extensions import NAMES
    extension_install.add_argument("name", choices=NAMES)
    flare = extension_sub.add_parser("build-flare", help="Gerar renderer/mapa aproximados com cenas locais de Optical Flares")
    flare.add_argument("folder", type=Path)
    flare.add_argument("--out", type=Path, required=True, help="Pasta de saída nova; contém cenas privadas do usuário")
    apply = commands.add_parser("apply", help="Prévia/aplicação pela API local do EffectCraft")
    apply.add_argument("plan", type=Path)
    apply.add_argument("--target", choices=["effectcraft", "filmcraft"], default="effectcraft")
    apply.add_argument("--layer")
    apply.add_argument("--comp")
    apply.add_argument("--port", type=int)
    apply.add_argument("--timeout", type=float, default=10)
    apply.add_argument("--yes", action="store_true", help="Confirmar explicitamente mudanças no projeto")
    apply.add_argument("--dry-run", action="store_true")
    apply.add_argument("--save-project", type=Path, help="Salvar novo .ecproj pela engine")
    apply.add_argument("--json", action="store_true")
    apply.add_argument("--bind-layer", action="append", default=[], metavar="REF=SELETOR",
                       help="Vínculo Layer explícito de plano v4; exemplo map=#2 (repetível)")
    commands.add_parser("gui", help="Abrir a interface gráfica opcional")
    return root


def options(args) -> dict:
    return {
        "strict": args.strict,
        "dry_run": args.dry_run,
        "source_size": args.size,
        "keyframe_mode": args.keyframe_mode,
        "limits": Limits(max_file_bytes=args.max_mib * 1024 * 1024, max_seconds=args.timeout),
        "source_layers": load_source_layers(getattr(args, "source_layers", None)),
    }


def load_source_layers(path: str | None) -> SourceLayerBindings | None:
    if path is None:
        return None
    try:
        return SourceLayerBindings.model_validate_json(read_bounded(Path(path), Limits(max_file_bytes=65536)))
    except ValidationError as exc:
        raise BridgeError(f"Vínculos de origem inválidos: {exc}") from exc


def run(args) -> int:
    if args.command == "gui":
        if importlib.util.find_spec("PySide6") is None:
            raise BridgeError("GUI opcional ausente. Instale: uv sync --extra gui")
        from craft_bridge.gui.app import main as gui_main

        return gui_main()
    if args.command == "doctor":
        result = {
            "version": __version__,
            "python": platform.python_version(),
            "platform": platform.platform(),
            "gui_installed": importlib.util.find_spec("PySide6") is not None,
            "filmcraft_cli": shutil.which("filmcraft-cli"),
            "effectcraft_cli": shutil.which("effectcraft-cli"),
            "adobe_required": False,
            "mappings": len(Registry().mappings),
            "local_ports": {"filmcraft": 9876, "effectcraft": 9877},
            "validation": "Nenhuma engine consultada por doctor; presença de binário não prova compatibilidade.",
        }
        print(json_text(result))
        return 0
    if args.command == "mappings":
        registry = Registry()
        if args.mapping_command == "install":
            print(registry.install(args.package))
        else:
            print(json_text([m.model_dump(mode="json") for m in registry.mappings.values()]))
        return 0
    if args.command == "extensions":
        if args.extension_command == "build-flare":
            from craft_bridge.extensions.flare.library import build_library
            print(json_text(build_library(args.folder, args.out)))
            return 0
        from craft_bridge.extensions import NAMES, extension_paths

        names = NAMES if args.extension_command == "list" else (args.name,)
        extensions_result = []
        for name in names:
            mapping, module = extension_paths(name)
            installed = Registry().install(mapping) if args.extension_command == "install" else None
            extensions_result.append({"name": name, "mapping": str(mapping), "module": str(module),
                           "installed": str(installed) if installed else None,
                           "renderer_loaded": False, "approximate": True,
                           "notice": "Carregue o módulo no EffectCraft por effect.plugins.load. Conversão sempre parcial; sem equivalência visual Adobe."})
        print(json_text(extensions_result))
        return 0
    if args.command == "inspect":
        doc = inspect_file(
            args.file, Limits(max_file_bytes=args.max_mib * 1024 * 1024, max_seconds=args.timeout)
        )
        _, report = preview(doc, source_size=args.size, source_layers=load_source_layers(args.source_layers))
        if args.json:
            print(
                json_text(
                    {
                        "inspection": doc.model_dump(mode="json"),
                        "compatibility": report.model_dump(mode="json"),
                    }
                )
            )
        else:
            print(
                f"{doc.source.format.upper()} · {doc.source.size:,} bytes · {report.status}\nSHA-256: {doc.source.sha256}"
            )
            for preset in doc.presets:
                print(f"\n{preset.name}")
                for effect in preset.effects:
                    print(
                        f"  {effect.order + 1}. {effect.name} [{effect.identifier.match_name}] · {len(effect.parameters)} parâmetros"
                    )
            for effect_result in report.effects:
                print(
                    f"  {effect_result.source}: {effect_result.status} ({effect_result.parameters_converted}/{effect_result.parameters_found} parâmetros)"
                )
            for message in [*report.warnings, *(w for e in report.effects for w in e.warnings)]:
                print(f"  Aviso {message.code}: {message.message}")
        return 0
    if args.command == "convert":
        report = convert_file(args.file, args.out, target=args.target, **options(args))
        print(
            report.model_dump_json(indent=2)
            if args.json
            else f"{report.status}: {report.output or 'sem saída de preset'}"
            + ("\n" + "\n".join(report.errors) if report.errors else "")
        )
        return EXIT[report.status]
    if args.command == "batch":
        reports = batch_convert(
            args.folder, args.out, preserve_folders=args.preserve_folders, **options(args)
        )
        if not args.dry_run:
            atomic_write(args.out / "batch-report.csv", batch_csv(reports))
            atomic_write(
                args.out / "batch-report.json", json_text([r.model_dump(mode="json") for r in reports])
            )
        if args.json:
            print(json_text([r.model_dump(mode="json") for r in reports]))
        else:
            for report in reports:
                print(f"{report.status}: {report.source_path}")
        return max((EXIT[r.status] for r in reports), default=0)
    if args.command == "apply":
        layer_bindings = {}
        for item in args.bind_layer:
            ref, separator, selector = item.partition("=")
            if not separator or ref in layer_bindings:
                raise BridgeError("--bind-layer exige REF=SELETOR e referências únicas.")
            layer_bindings[ref] = selector
        if args.target == "filmcraft":
            if layer_bindings:
                raise BridgeError("Vínculos Layer desta versão exigem plano EffectCraft v4.")
            result = import_presets(
                args.plan,
                port=args.port or 9876,
                timeout=args.timeout,
                confirmed=args.yes,
                dry_run=args.dry_run,
            )
            print(json_text(result))
            return 0
        if not args.layer:
            raise BridgeError("Selecione uma camada com --layer para aplicar ao EffectCraft.")
        plan = load_plan(args.plan)
        from craft_bridge.integrations.effectcraft import checked_layer_bindings
        checked_layer_bindings(plan, layer_bindings)
        confirmed = args.yes
        if not args.dry_run and not confirmed:
            print(json_text(plan.commands), file=sys.stderr)
            if any(p.keyframes for e in plan.effects for p in e.properties):
                print("Para aplicar os keyframes, a composição de destino será ativada.", file=sys.stderr)
            if not sys.stdin.isatty():
                raise BridgeError("Sem confirmação interativa: use --dry-run ou --yes.")
            confirmed = (
                input("Aplicar estes comandos no projeto aberto? Digite APLICAR: ").strip() == "APLICAR"
            )
        result = apply_plan(
            plan,
            layer=args.layer,
            comp=args.comp,
            port=args.port or 9877,
            timeout=args.timeout,
            confirmed=confirmed,
            dry_run=args.dry_run,
            save_project=args.save_project,
            layer_bindings=layer_bindings,
        )
        print(json_text(result))
        return 0
    return 1


def main() -> int:
    args = parser().parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING)
    try:
        return run(args)
    except (BridgeError, OSError) as exc:
        if getattr(args, "json", False):
            print(json_text({"status": "FAILED", "errors": [str(exc)]}))
        else:
            print(f"Erro: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Operação cancelada.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
