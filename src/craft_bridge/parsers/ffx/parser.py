"""Parsing FFX estruturado: índices, snapshots, descriptors e streams independentes."""

import json
import math
import struct
from collections import Counter
from functools import lru_cache
from importlib.resources import files
from pathlib import Path
from typing import cast

from craft_bridge.core.models import (
    ConversionWarning,
    Effect,
    EffectIdentifier,
    Parameter,
    ParameterValue,
    Preset,
    PresetDocument,
    SourceMetadata,
    UnsupportedFeature,
    ValueKind,
)
from craft_bridge.core.safety import BridgeError, Budget, raw_summary
from craft_bridge.parsers.ffx.arbitrary import (
    CHANNELS,
    CURVES,
    HUE,
    LEVELS,
    curve_lut_text,
    decode_curves,
    decode_numeric,
)
from craft_bridge.parsers.ffx.keyframes import decode_keyframes
from craft_bridge.parsers.ffx.mesh import LAYOUT as MESH_LAYOUT
from craft_bridge.parsers.ffx.mesh import MESH, decode_mesh
from craft_bridge.parsers.ffx.neutralizer import derive_neutralizer
from craft_bridge.parsers.ffx.optical_flares import OPTIONS, decode_ofp
from craft_bridge.parsers.ffx.rifx import Chunk, decode_string, parse_rifx

KINDS = {
    1: "number",
    2: "number",
    3: "number",
    4: "boolean",
    5: "color",
    6: "point",
    7: "enum",
    9: "number",
    10: "number",
}
INTRINSIC = {
    "ADBE Position": ("point", "px"),
    "ADBE Anchor Point": ("point", "px"),
    "ADBE Scale": ("vector", "ratio"),
    "ADBE Rotate Z": ("number", "degrees"),
    "ADBE Opacity": ("number", "ratio"),
    "ADBE Effect Mask Opacity": ("number", "%"),
}
ADMIN = {"ADBE Force CPU GPU", "ADBE Effect Mask Parade", "ADBE Group End"}


@lru_cache(maxsize=1)
def source_types() -> dict[str, dict]:
    return json.loads(files("craft_bridge.parsers.ffx").joinpath("parameter-types.json").read_text())[
        "parameters"
    ]


def warning(code: str, message: str, path: str = "", *, loss: bool = True) -> ConversionWarning:
    return ConversionWarning(code=code, message=message, path=path, loss=loss)


def text(node: Chunk, tag: str, default: str = "") -> str:
    leaf = node.leaf(tag)
    return decode_string(leaf.data) if leaf else default


def descriptors(snapshot: Chunk) -> dict[str, dict]:
    root = next((c for c in snapshot.children if c.form == "parT"), None)
    meta: dict[str, dict] = {}
    if root is None:
        return meta
    pending, last = "", ""
    for child in root.children:
        if child.id == "tdmn":
            pending, last = decode_string(child.data), ""
        elif child.id == "pard" and pending:
            if len(child.data) != 148:
                raise BridgeError("Descriptor pard desconhecido; esperado 148 bytes.")
            meta[pending] = {
                "kind": struct.unpack_from(">I", child.data, 12)[0],
                "flags": struct.unpack_from(">I", child.data, 4)[0],
                "name": decode_string(child.data[16:80]),
            }
            if meta[pending]["kind"] == 10:
                meta[pending]["display_flags"] = struct.unpack_from(">H", child.data, 0x7E)[0]
            last, pending = pending, ""
        elif child.id == "pdnm" and last:
            meta[last]["menu"] = decode_string(child.data).split("|")
    return meta


class FfxParser:
    """Aceita FaFX; estruturas desconhecidas ficam no modelo e nos avisos."""

    def parse(self, data: bytes, source: SourceMetadata, budget: Budget) -> PresetDocument:
        tree, trailer = parse_rifx(data, budget)
        document = PresetDocument(source=source)
        all_nodes = list(tree.walk())
        consumed_arbitrary: set[int] = set()
        head = tree.leaf("head")
        if head and len(head.data) >= 12:
            words = struct.unpack_from(">3I", head.data)
            source.detected_version = f"{words[1]}.{words[2]} (head schema {words[0]})"
        document.diagnostics["chunk_counts"] = dict(Counter(c.form or c.id for c in all_nodes))
        if trailer:
            document.diagnostics["trailer"] = raw_summary(trailer, budget.limits)
            document.warnings.append(
                warning(
                    "TRAILER", "Dados após RIFX preservados como diagnóstico (não executados).", loss=False
                )
            )
        besc = next((c for c in tree.children if c.form == "besc"), None)
        if besc is None:
            raise BridgeError("FaFX sem LIST besc.")
        preset = Preset(name=Path(source.path).stem)
        document.presets.append(preset)
        paths = []
        for child in besc.children:
            if child.form != "tdsp":
                continue
            entries = [c for c in child.children if c.form == "tdsi"]
            names = [text(c, "tdmn") for c in entries]
            if names == ["ADBE End of path sentinel"]:
                continue
            if not names or any(not n for n in names):
                raise BridgeError("Entrada tdsp sem cadeia de match names.")
            if any((leaf := c.leaf("tdix")) is not None and len(leaf.data) != 4 for c in entries):
                raise BridgeError("Índice tdix exige exatamente quatro bytes.")
            indices = [
                int.from_bytes(leaf.data, "big") if (leaf := c.leaf("tdix")) else None for c in entries
            ]
            paths.append((names, indices, child.offset))
        snapshots = [c for c in besc.children if c.form == "sspc"]
        blocks = snapshots or [c for c in besc.children if c.form in ("tdgp", "tdbs")]
        effect_path_positions = [
            i for i, (names, _, _) in enumerate(paths) if len(names) == 2 and names[0] == "ADBE Effect Parade"
        ]
        snapshot_ordinals = {position: ordinal for ordinal, position in enumerate(effect_path_positions)}
        expected_blocks = len(effect_path_positions) if snapshots else len(paths)
        if expected_blocks != len(blocks):
            document.warnings.append(
                warning(
                    "BLOCK_COUNT",
                    f"{expected_blocks} caminhos aplicáveis e {len(blocks)} blocos; associações incompletas.",
                )
            )
        cache: dict[str, dict[str, dict]] = {}
        source_indices = [
            indices[-1] for names, indices, _ in paths if len(names) == 2 and names[0] == "ADBE Effect Parade"
        ]
        ordered_effect_paths = (
            len(source_indices) == len(blocks)
            and all(isinstance(index, int) and 0 <= index < 0xFFFFFFFF for index in source_indices)
            and all(
                a is not None and b is not None and a < b
                for a, b in zip(source_indices, source_indices[1:], strict=False)
            )
            and all(
                len(paths[position][1]) == 2 and paths[position][1][0] == 0xFFFFFFFF
                for position in effect_path_positions
            )
        )
        for i, (names, indices, offset) in enumerate(paths):
            budget.check("effects")
            match = names[1] if names[0] == "ADBE Effect Parade" and len(names) > 1 else names[0]
            feature = (
                "effect"
                if snapshots and i in snapshot_ordinals
                else ("transform" if not snapshots and names[0] == "ADBE Transform Group" else "property")
            )
            if names[0] == "ADBE Text Properties":
                feature = "text"
            elif names[0] == "ADBE Root Vectors Group":
                feature = "shape"
            elif names[0] == "ADBE Mask Parade":
                feature = "mask"
            effect = Effect(
                name=match,
                identifier=EffectIdentifier(match_name=match),
                order=i,
                feature=feature,
                metadata={"target_path": names, "tdix": indices, "offset": offset},
            )
            preset.effects.append(effect)
            if snapshots and i not in snapshot_ordinals:
                effect.warnings.append(
                    warning(
                        "PROPERTY_SNAPSHOT",
                        "Caminho de propriedade em preset misto; não consome um snapshot de efeito.",
                    )
                )
                continue
            block_index = snapshot_ordinals[i] if snapshots else i
            if snapshots and indices[-1] != block_index:
                effect.warnings.append(
                    warning(
                        "INDEX", "Índice/caminho de efeito não corresponde ao perfil sequencial comprovado."
                    )
                )
            if block_index >= len(blocks):
                effect.warnings.append(warning("MISSING_BLOCK", "Bloco de propriedades ausente."))
                continue
            block = blocks[block_index]
            try:
                meta = descriptors(block) if snapshots else source_types()
                if not meta:
                    meta = cache.get(match, {})
                else:
                    cache[match] = meta
                effect.name = text(block, "fnam", match)
                roots = [c for c in block.children if c.form == "tdgp"] if snapshots else [block]
                for root in roots:
                    state = root.leaf("tdsb")
                    if state and len(state.data) == 4:
                        effect.enabled = bool(int.from_bytes(state.data, "big") & 1)
                    if root.form == "tdbs":
                        effect.parameters.append(self._parameter(root, names[-1], meta, [], budget))
                    else:
                        self._group(root, effect, meta, [], budget, consumed_arbitrary)
                self._arbitrary_shadows(effect, budget)
                derive_neutralizer(effect, budget)
                if not roots:
                    effect.warnings.append(
                        warning("NO_PROPERTIES", "Nenhuma árvore de propriedades decodificada.")
                    )
                if snapshots and indices[-1] != block_index and ordered_effect_paths:
                    namespaced = [
                        p
                        for p in effect.parameters
                        if not p.metadata.get("administrative") and p.id != "ADBE Effect Mask Opacity"
                    ]
                    if namespaced and all(p.id.startswith(match + "-") for p in namespaced):
                        effect.warnings = [w for w in effect.warnings if w.code != "INDEX"]
                        effect.warnings.append(
                            warning(
                                "INDEX_REBASED",
                                "Índices originais com lacunas: associação por ordem e namespace de parâmetros verificados.",
                                loss=False,
                            )
                        )
                        effect.metadata["association"] = "ordered-paths-and-parameter-namespace"
            except BridgeError as exc:
                effect.warnings.append(warning("EFFECT_DECODE", str(exc)))
        if not preset.effects:
            document.warnings.append(
                warning("NO_EFFECTS", "Cabeçalho reconhecido, mas nenhum efeito ou propriedade interpretado.")
            )
        if not snapshots and len(paths) == len(blocks):
            self._selected_effects(preset)
        self._unassociated_ofp(all_nodes, document, budget, consumed_arbitrary)
        known = {
            "head",
            "beso",
            "tdot",
            "tdpl",
            "tdix",
            "tdmn",
            "tdsn",
            "fnam",
            "parn",
            "pard",
            "pdnm",
            "tdsb",
            "tdb4",
            "cdat",
            "tdum",
            "tduM",
            "lhd3",
            "ldat",
            "pgui",
            "tdpi",
            "tdps",
            "tdli",
        }
        unknown = [
            n
            for n in all_nodes
            if ((n.form is None and n.id not in known) or n.form == "btdk")
            and n.offset not in consumed_arbitrary
        ]
        document.diagnostics["opaque_chunks"] = [
            {"id": n.form or n.id, **raw_summary(n.data, budget.limits, n.offset)}
            for n in unknown[: budget.limits.max_diagnostics]
        ]
        document.diagnostics["opaque_count"] = len(unknown)
        if unknown:
            document.warnings.append(
                warning(
                    "OPAQUE_CHUNKS",
                    f"{len(unknown)} chunks opacos; dados privados/expressões não são convertidos.",
                )
            )
        if any(e.feature not in ("effect", "transform", "effect-properties") for e in preset.effects):
            document.unsupported.append(
                UnsupportedFeature(
                    feature="property/text/shape/mask",
                    reason="Semântica de aplicação complexa não implementada.",
                )
            )
        return document

    def _unassociated_ofp(
        self,
        nodes: list[Chunk],
        document: PresetDocument,
        budget: Budget,
        consumed: set[int],
    ) -> None:
        """Read scene data without selecting a current value or guessing its owner."""
        candidates = [
            node for node in nodes
            if node.id == "aRbp" and node.offset not in consumed and bytes(node.data[:3]) == b"OFP"
        ]
        if not candidates:
            return
        scenes = []
        for node in candidates[: budget.limits.max_diagnostics]:
            budget.check()
            entry = {"origin": raw_summary(node.data, budget.limits, node.offset), "associated": False}
            try:
                entry["scene"] = decode_ofp(node.data, budget)
            except BridgeError as exc:
                entry["error"] = str(exc)
            scenes.append(entry)
        document.diagnostics["unassociated_ofp_scenes"] = scenes
        document.diagnostics["unassociated_ofp_count"] = len(candidates)
        document.warnings.append(warning(
            "OFP_ASSOCIATION_UNSUPPORTED",
            f"{len(candidates)} blocos OFP sem associação estática comprovada; inspeção preserva dados, sem escolher estado atual nem exportar.",
        ))

    def _selected_effects(self, preset: Preset) -> None:
        groups: dict[tuple[str, int], Effect] = {}
        result: list[Effect] = []
        for effect in preset.effects:
            names, indices = effect.metadata["target_path"], effect.metadata["tdix"]
            if not (
                len(names) == len(indices) == 3
                and names[0] == "ADBE Effect Parade"
                and indices[0] == 0xFFFFFFFF
                and isinstance(indices[1], int)
                and 0 <= indices[1] < 0xFFFFFFFF
                and isinstance(indices[2], int)
                and 0 <= indices[2] < 0xFFFFFFFF
                and names[2].startswith(names[1] + "-")
                and len(effect.parameters) == 1
                and effect.parameters[0].id == names[2]
                and effect.parameters[0].metadata.get("evidence") == "real-parT-and-tdb4"
                and not effect.warnings
            ):
                result.append(effect)
                continue
            key = (names[1], indices[1])
            if key not in groups:
                effect.feature = "effect-properties"
                effect.enabled = True  # tdsb here belongs to the property, not the effect.
                effect.metadata.update(
                    application="existing",
                    source_effect_index=indices[1],
                    selected_paths=[effect.metadata["target_path"]],
                )
                groups[key] = effect
                result.append(effect)
            else:
                grouped = groups[key]
                grouped.parameters.extend(effect.parameters)
                grouped.metadata["selected_paths"].append(names)
        preset.effects = result

    def _group(
        self,
        node: Chunk,
        effect: Effect,
        meta: dict,
        group: list[str],
        budget: Budget,
        consumed: set[int],
    ) -> None:
        pending = ""
        previous: Parameter | None = None
        for child in node.children:
            budget.check()
            if child.id == "tdmn":
                pending = decode_string(child.data)
                previous = None
            elif child.form == "tdgp":
                label = text(child, "tdsn", pending)
                pending = ""
                previous = None
                self._group(child, effect, meta, [*group, label] if label else group, budget, consumed)
            elif child.form == "tdbs":
                param = self._parameter(child, pending, meta, group, budget)
                pending = ""
                effect.parameters.append(param)
                previous = param
            elif child.form == "aRbs" and previous is not None:
                self._arbitrary(child, previous, effect, budget, consumed)
                previous = None
            else:
                previous = None

    def _arbitrary(
        self,
        node: Chunk,
        param: Parameter,
        effect: Effect,
        budget: Budget,
        consumed: set[int],
    ) -> None:
        if param.id not in (HUE, LEVELS, CURVES, OPTIONS, MESH):
            return
        try:
            if (
                len(node.children) != 1
                or node.children[0].id != "aRbp"
                or node.children[0].form is not None
                or param.metadata.get("kind") != 11
                or param.metadata.get("stream_flags") != 7
                or param.metadata.get("dimensions") != 1
                or param.metadata.get("animated") is not False
                or param.keyframes
                or param.metadata.get("keyframes_declared", 0)
                or any(w.code not in ("UNDECODED_VALUE", "COMPLEX_PARAMETER") for w in param.warnings)
            ):
                raise BridgeError(
                    "aRbp animado, múltiplo ou com metadados desconhecidos; leitura estática recusada."
                )
            leaf = node.children[0]
            origin = {**param.origin, "aRbp": raw_summary(leaf.data, budget.limits, leaf.offset)}
            if param.id == MESH:
                mesh = decode_mesh(leaf.data, budget)
                param.metadata.update(decoded_arbitrary=mesh, arbitrary_layout=MESH_LAYOUT)
                param.origin = origin
                param.warnings = [warning(
                    "MESH_RENDER_UNSUPPORTED",
                    "Registros Mesh Warp preservados estruturalmente; unidades, pares de controle, tangentes e interpolação ainda não têm tradução verificada. Nenhum controle é descartado para gerar uma malha bilinear.",
                    param.id,
                )]
            elif param.id == OPTIONS:
                scene = decode_ofp(leaf.data, budget)
                param.metadata.update(decoded_arbitrary=scene, arbitrary_layout="OFP-v3-structural")
                param.origin = origin
                param.warnings = [warning(
                    "OFP_RENDER_UNSUPPORTED",
                    "Estrutura OFP lida; campos, objetos e texturas ainda não têm renderer certificado no destino.",
                    param.id,
                )]
            elif param.id == CURVES:
                decoded = decode_curves(leaf.data)
                # Validate all channels before deriving any runtime value.
                curve_values = {c["channel"]: curve_lut_text(c) for c in decoded["channels"]}
                budget.check("parameters", len(curve_values))
                effect.parameters.extend(
                    Parameter(
                        id=param.id + "/" + name,
                        name=name,
                        group=param.group,
                        value=ParameterValue(kind="text", data=value),
                        origin=origin,
                        metadata={"derived_from": param.id, "arbitrary_layout": "AE-Curves-v1-LUT"},
                    ) for name, value in curve_values.items()
                )
                param.metadata.update(administrative=True, decoded_arbitrary=decoded)
                param.origin = origin
                param.warnings = []
                effect.warnings.append(
                    warning(
                        "CURVES_INTERPOLATION",
                        "Curves transfere os 256 samples por canal da LUT de 8 bits; o destino reamostra com spline monotônica/LUT de 1025 entradas. Interpolação, precisão 16/32bpc e valores HDR não equivalem à origem.",
                        param.id,
                    )
                )
            else:
                values = decode_numeric(param.id, leaf.data)
                budget.check("parameters", len(values))
                effect.parameters.extend(
                    Parameter(
                        id=param.id + "/" + name,
                        name=name,
                        group=param.group,
                        value=ParameterValue(kind="number", data=value),
                        origin=origin,
                        metadata={"derived_from": param.id, "arbitrary_layout": "AE-first-party-v1"},
                    )
                    for name, value in values.items()
                )
                param.metadata.update(administrative=True, decoded_arbitrary=True)
                param.warnings = []
                param.origin = origin
            consumed.add(leaf.offset)
        except BridgeError as exc:
            param.warnings.append(warning("ARBITRARY_LAYOUT", str(exc), param.id))

    def _arbitrary_shadows(self, effect: Effect, budget: Budget) -> None:
        for blob_id, shadow_numbers in ((HUE, range(4, 7)), (LEVELS, range(3, 8))):
            blobs = [p for p in effect.parameters if p.id == blob_id and p.metadata.get("decoded_arbitrary")]
            if len(blobs) != 1:
                continue
            prefix = blob_id.rsplit("-", 1)[0]
            shadows = {prefix + "-" + str(i).zfill(4) for i in shadow_numbers}
            for param in effect.parameters:
                if param.id not in shadows:
                    continue
                if param.keyframes or param.metadata.get("animated") or param.warnings:
                    effect.warnings.append(
                        warning(
                            "ARBITRARY_SHADOW_ANIMATION",
                            "Campo de interface animado ou desconhecido conflita com o blob estático.",
                            param.id,
                        )
                    )
                else:
                    param.metadata.update(administrative=True, ui_shadow_of=blob_id)
            if blob_id == LEVELS:
                # These two source switches apply to every channel, whereas the
                # native engine stores one pair per channel. Duplicate explicitly.
                clips = [p for p in effect.parameters if p.id in (prefix + "-0008", prefix + "-0009")]
                for clip in clips:
                    for channel in CHANNELS[1:]:
                        budget.check("parameters")
                        derived = clip.model_copy(deep=True)
                        derived.id += "/" + channel
                        derived.metadata["derived_from"] = clip.id
                        effect.parameters.append(derived)

    def _parameter(self, node: Chunk, match: str, meta: dict, group: list[str], budget: Budget) -> Parameter:
        budget.check("parameters")
        desc = meta.get(match, {})
        kind = KINDS.get(desc.get("kind"), "unknown")
        unit = "degrees" if desc.get("kind") == 3 else "AE-ARGB-255" if kind == "color" else None
        if match in INTRINSIC:
            kind, unit = INTRINSIC[match]
        admin = match in ADMIN or match.endswith("-0000") or desc.get("kind") in (13, 14, 15)
        param = Parameter(
            id=match,
            name=text(node, "tdsn", desc.get("name", match)),
            value=ParameterValue(kind=cast(ValueKind, kind), unit=unit),
            group=group,
            origin={"offset": node.offset},
            metadata={**desc, "administrative": admin},
        )
        stream = node.leaf("tdb4")
        dims, flags, base = 1, 0, 0
        if stream:
            param.origin["tdb4"] = raw_summary(stream.data, budget.limits, stream.offset)
            if len(stream.data) == 124 and bytes(stream.data[:2]) == b"\xdb\x99":
                dims, flags = struct.unpack_from(">HH", stream.data, 2)
                base = struct.unpack_from(">I", stream.data, 12)[0]
                param.metadata.update(
                    dimensions=dims,
                    stream_flags=flags,
                    time_base=base,
                    spatial=bool(flags & 8),
                    animated=bool(stream.data[68]),
                )
                if "expected_dimensions" in desc and dims != desc["expected_dimensions"]:
                    param.warnings.append(
                        warning(
                            "PROFILE_DIMENSIONS", "Dimensões divergentes do descriptor real deste ID.", match
                        )
                    )
                if any(stream.data[120:124]):
                    param.warnings.append(
                        warning("EXPRESSION", "Expressão preservada como bytes, sem execução.")
                    )
            else:
                param.warnings.append(warning("TDB4", "Metadados de stream não reconhecidos."))
        else:
            param.warnings.append(warning("NO_TDB4", "Stream sem metadados de tipo e tempo."))
        value = node.leaf("cdat")
        if value:
            param.origin["cdat"] = raw_summary(value.data, budget.limits, value.offset)
            if kind != "unknown" and 1 <= dims <= 4 and len(value.data) >= dims * 8:
                numbers = list(struct.unpack_from(">" + "d" * dims, value.data))
                if all(math.isfinite(x) for x in numbers):
                    if kind == "boolean" and dims == 1 and numbers[0] in (0, 1):
                        param.value.data = bool(numbers[0])
                    elif kind == "enum" and dims == 1 and numbers[0].is_integer():
                        param.value.data = int(numbers[0])
                    elif kind in ("point", "color", "vector"):
                        param.value.data = numbers
                        if kind == "color":
                            param.value.unit = "AE-ARGB-255"
                    elif kind == "number" and dims == 1:
                        param.value.data = numbers[0]
        for child in node.children:
            if child.form != "list":
                continue
            header, records = child.leaf("lhd3"), child.leaf("ldat")
            if not header or not records:
                param.warnings.append(warning("KEYFRAME_STREAM", "Lista de keyframes incompleta."))
                continue
            param.origin["lhd3"] = raw_summary(header.data, budget.limits, header.offset)
            if len(header.data) == 52 and struct.unpack_from(">I", header.data)[0] == 0x00D00BEE:
                param.metadata["keyframes_declared"] = struct.unpack_from(">I", header.data, 8)[0]
            param.origin["ldat"] = raw_summary(records.data, budget.limits, records.offset)
            try:
                param.keyframes = decode_keyframes(
                    header.data,
                    records.data,
                    dimensions=dims,
                    stream_flags=flags,
                    time_base=base,
                    budget=budget,
                    value_kind=kind,
                )
                if param.keyframes:
                    for key in param.keyframes:
                        if kind == "boolean":
                            if not isinstance(key.value, (int, float)) or key.value not in (0, 1):
                                raise BridgeError("Keyframe booleano exige 0 ou 1.")
                            key.value = bool(key.value)
                        elif kind == "enum":
                            if not isinstance(key.value, (int, float)) or not float(key.value).is_integer():
                                raise BridgeError("Keyframe enum exige índice inteiro.")
                            key.value = int(key.value)
                    param.value.data = param.keyframes[0].value
            except BridgeError as exc:
                param.warnings.append(warning("KEYFRAME_LAYOUT", str(exc)))
        if param.value.data is None and not admin:
            param.warnings.append(
                warning("UNDECODED_VALUE", "Valor não decodificado; bytes limitados no diagnóstico.")
            )
        if desc.get("kind") in (0, 11, 12) and not admin:
            param.warnings.append(
                warning("COMPLEX_PARAMETER", "Referência de camada/path ou dados privados não suportados.")
            )
        if desc.get("flags", 0) & 0x208:
            param.metadata["hidden"] = True  # hidden does not mean semantically disposable
        return param
