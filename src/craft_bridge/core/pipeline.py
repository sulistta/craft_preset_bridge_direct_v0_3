"""API pública headless para inspeção, prévia, conversão e lotes."""

import csv
import hashlib
import html
import io
import logging
from collections.abc import Callable
from pathlib import Path
from threading import Event
from typing import cast

from pydantic import ValidationError

from craft_bridge.core.models import ConversionReport, PresetDocument, SourceFormat, SourceMetadata
from craft_bridge.core.resources import SourceLayerBindings
from craft_bridge.core.safety import BridgeError, Budget, Limits, atomic_write, json_text, read_bounded
from craft_bridge.core.validation import validate_filmcraft, validate_plan
from craft_bridge.exporters.effectcraft.exporter import EffectCraftExporter
from craft_bridge.exporters.filmcraft.exporter import FilmCraftExporter
from craft_bridge.mappings.registry import Registry
from craft_bridge.parsers.ffx.parser import FfxParser
from craft_bridge.parsers.prfpset.parser import PrfpsetParser

logger = logging.getLogger(__name__)


def inspect_file(path: str | Path, limits: Limits | None = None) -> PresetDocument:
    path, limits = Path(path), limits or Limits()
    logger.debug("Analisando %s", path)
    data = read_bounded(path, limits)
    budget = Budget(limits)
    parser: FfxParser | PrfpsetParser
    if data[:4] == b"RIFX":
        fmt, parser = "ffx", FfxParser()
    elif data.lstrip(b"\xef\xbb\xbf \r\n\t").startswith(b"<") or data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        fmt, parser = "prfpset", PrfpsetParser()
    else:
        raise BridgeError("Formato não reconhecido pelo conteúdo; esperado PremiereData ou RIFX/FaFX.")
    source = SourceMetadata(
        path=str(path.resolve()),
        format=cast(SourceFormat, fmt),
        size=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
    )
    try:
        return parser.parse(data, source, budget)
    except (ValueError, ValidationError) as exc:
        if isinstance(exc, BridgeError):
            raise
        raise BridgeError(f"Estrutura de preset inválida: {exc}") from exc


def preview(
    document: PresetDocument,
    *,
    target: str | None = None,
    registry: Registry | None = None,
    source_size: tuple[int, int] | None = None,
    keyframe_mode: str | None = None,
    source_layers: SourceLayerBindings | None = None,
) -> tuple[dict, ConversionReport]:
    target = target or ("filmcraft" if document.source.format == "prfpset" else "effectcraft")
    expected = "filmcraft" if document.source.format == "prfpset" else "effectcraft"
    if target != expected:
        raise BridgeError(f"O fluxo {document.source.format} exige destino {expected}.")
    if source_layers is not None and target != "effectcraft":
        raise BridgeError("Vínculos de origem são exclusivos do fluxo FFX → EffectCraft.")
    if source_size and (min(source_size) <= 0 or max(source_size) > 65536):
        raise BridgeError("Dimensões devem estar entre 1 e 65536 pixels.")
    if keyframe_mode not in (None, "Scale", "AnchorToIn", "AnchorToOut"):
        raise BridgeError("Modo de keyframe inválido.")
    registry = registry or Registry()
    exporter = FilmCraftExporter() if target == "filmcraft" else EffectCraftExporter()
    extra = {"source_layers": source_layers} if target == "effectcraft" else {}
    output, report = exporter.export(document, registry, source_size=source_size, keyframe_mode=keyframe_mode, **extra)
    if report.status in ("SUCCESS", "PARTIAL"):
        if target == "filmcraft":
            validate_filmcraft(output, registry)
        else:
            validate_plan(output, registry)
    return output, report


def html_report(report: ConversionReport) -> str:
    rows = "".join(
        f"<tr><td>{html.escape(e.source)}</td><td>{html.escape(e.target or '—')}</td>"
        f"<td>{html.escape(e.status)}</td><td>{e.parameters_converted}/{e.parameters_found}</td>"
        f"<td>{e.keyframes_preserved}/{e.keyframes_found}</td></tr>"
        for e in report.effects
    )
    messages = report.warnings + [w for e in report.effects for w in e.warnings]
    notices = "".join(f"<li>{html.escape(w.code)}: {html.escape(w.message)}</li>" for w in messages)
    errors = "".join(f"<li>{html.escape(e)}</li>" for e in report.errors)
    return f"""<!doctype html><html lang="pt-BR"><meta charset="utf-8"><title>Relatório Craft Preset Bridge</title>
<style>body{{font:16px system-ui;background:#151922;color:#e9edf3;margin:40px;line-height:1.6}}table{{border-collapse:collapse;width:100%}}td,th{{text-align:left;padding:12px;border-bottom:1px solid #414957}}code{{overflow-wrap:anywhere}}h1{{color:#83d9c2}}</style>
<h1>Craft Preset Bridge · {report.status}</h1><p>{html.escape(report.source_path)}</p>
<p>Destino: {report.target} · Validação: {html.escape(report.validation)}</p>
<p>SHA-256: <code>{report.input_sha256 or (report.source.sha256 if report.source else "indisponível")}</code></p>
<p>Parser: {report.source.parser_version if report.source else "indisponível"} · Catálogo: {report.catalog_commit}</p>
<table><tr><th>Origem</th><th>Destino</th><th>Compatibilidade</th><th>Parâmetros</th><th>Keyframes</th></tr>{rows}</table>
<h2>Avisos</h2><ul>{notices}</ul><h2>Erros</h2><ul>{errors}</ul></html>"""


def convert_file(
    path: str | Path,
    out: str | Path,
    *,
    strict: bool = False,
    dry_run: bool = False,
    limits: Limits | None = None,
    **options,
) -> ConversionReport:
    path, out = Path(path), Path(out)
    if out.resolve() == path.resolve():
        raise BridgeError("Não é permitido sobrescrever a origem.")
    document = None
    try:
        document = inspect_file(path, limits)
        output, report = preview(document, **options)
    except (BridgeError, OSError) as exc:
        report = ConversionReport(
            source_path=str(path.resolve()),
            source=document.source if document else None,
            target=options.get("target")
            or ("filmcraft" if path.suffix.lower() == ".prfpset" else "effectcraft"),
            status="FAILED",
            errors=[str(exc)],
        )
        output = None
    report.strict, report.dry_run = strict, dry_run
    logger.debug("Conversão %s: %s (%s)", path, report.status, report.target)
    if report.source:
        report.input_sha256 = report.source.sha256
        report.input_size = report.source.size
    else:
        try:
            failed_input = read_bounded(path, limits or Limits())
            report.input_sha256 = hashlib.sha256(failed_input).hexdigest()
            report.input_size = len(failed_input)
        except (BridgeError, OSError):
            pass  # The original error is already preserved; do not bypass size limits to hash it.
    if strict and report.status == "PARTIAL":
        report.status = "FAILED"
        report.errors.append("Modo strict: perda de recursos relevantes; saída não publicada.")
    publish = report.status in ("SUCCESS", "PARTIAL")
    report.output = str(out.resolve()) if publish and not dry_run else None
    if not dry_run:
        json_report = Path(str(out) + ".report.json")
        web_report = Path(str(out) + ".report.html")
        destinations = [json_report, web_report, *([out] if publish else [])]
        for dest in destinations:
            if dest.resolve() == path.resolve() or dest.exists() or dest.is_symlink():
                raise BridgeError(f"Destino já existe ou coincide com a origem: {dest}")
        if publish:
            atomic_write(out, json_text(output))
        atomic_write(json_report, report.model_dump_json(indent=2) + "\n")
        atomic_write(web_report, html_report(report))
    return report


def candidate_files(root: Path, output: Path | None = None) -> list[Path]:
    if not root.is_dir():
        raise BridgeError(f"Pasta não encontrada: {root}")
    return sorted(
        p
        for p in root.rglob("*")
        if p.is_file()
        and not p.is_symlink()
        and p.suffix.lower() in (".ffx", ".prfpset")
        and not (output and p.resolve().is_relative_to(output.resolve()))
    )


def batch_convert(
    root: str | Path,
    out: str | Path,
    *,
    preserve_folders: bool = False,
    cancel: Event | None = None,
    progress: Callable | None = None,
    **options,
) -> list[ConversionReport]:
    root, out = Path(root), Path(out)
    if options.get("source_layers") is not None:
        raise BridgeError("Vínculos de origem são específicos de um arquivo; use convert, não batch.")
    if root.resolve() == out.resolve():
        raise BridgeError("A saída do lote deve ser uma pasta diferente da origem.")
    files = candidate_files(root, out)
    reports = []
    for index, path in enumerate(files):
        if cancel and cancel.is_set():
            break
        relative = path.relative_to(root)
        token = hashlib.sha256(str(relative).encode()).hexdigest()[:10]
        name = path.name + ("" if preserve_folders else "." + token) + ".json"
        dest = (out / relative.parent / name) if preserve_folders else out / name
        try:
            report = convert_file(path, dest, **options)
        except (BridgeError, OSError) as exc:
            report = ConversionReport(
                source_path=str(path.resolve()), target="auto", status="FAILED", errors=[str(exc)]
            )
        reports.append(report)
        if progress:
            progress(index + 1, len(files), report)
    return reports


def batch_csv(reports: list[ConversionReport]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(["arquivo", "estado", "destino", "efeitos_convertidos", "erros"])
    for report in reports:
        # Prevent spreadsheet formula execution in exported user-controlled names.
        values = [
            report.source_path,
            report.status,
            report.target,
            str(sum(e.parameters_converted > 0 for e in report.effects)),
            "; ".join(report.errors),
        ]
        writer.writerow(["'" + v if v.startswith(("=", "+", "-", "@")) else v for v in values])
    return buffer.getvalue()
