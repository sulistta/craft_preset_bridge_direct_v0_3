"""Leitor PremiereData com resolução explícita de ObjectID/ObjectRef."""

import math
import re
from typing import cast
from xml.etree.ElementTree import Element, ParseError

from defusedxml.common import DefusedXmlException
from defusedxml.ElementTree import fromstring

from craft_bridge.core.models import (
    ConversionWarning,
    Effect,
    EffectIdentifier,
    Interpolation,
    Keyframe,
    KeyframeMode,
    Mask,
    Parameter,
    ParameterValue,
    Preset,
    PresetDocument,
    SourceMetadata,
    ValueKind,
)
from craft_bridge.core.safety import BridgeError, Budget, raw_summary

TICKS = 254_016_000_000


def warn(code: str, message: str, path: str = "", *, loss: bool = True) -> ConversionWarning:
    return ConversionWarning(code=code, message=message, path=path, loss=loss)


def value_of(raw: str, kind: str) -> float | int | bool | list[float] | str | None:
    raw = raw.strip()
    try:
        if kind == "boolean":
            return {"true": True, "false": False, "1": True, "0": False}[raw.lower()]
        if kind in ("enum", "integer"):
            number = float(raw)
            return int(number) if math.isfinite(number) and number.is_integer() else None
        if kind in ("point", "vector", "color"):
            numbers = [float(part) for part in raw.split(":")]
            return numbers if all(math.isfinite(x) for x in numbers) else None
        if kind == "number":
            number = float(raw)
            return number if math.isfinite(number) else None
        if kind == "text":
            return raw
    except (ValueError, KeyError):
        return None
    return None


class PrfpsetParser:
    def parse(self, data: bytes, source: SourceMetadata, budget: Budget) -> PresetDocument:
        if len(data) > budget.limits.max_file_bytes:
            raise BridgeError("XML excede o limite de tamanho.")
        try:
            root = fromstring(data, forbid_dtd=True, forbid_entities=True, forbid_external=True)
        except (ParseError, DefusedXmlException) as exc:
            raise BridgeError(f"XML inválido ou inseguro: {exc}") from exc
        if root.tag != "PremiereData":
            raise BridgeError("XML não é um preset PremiereData.")
        budget.check()
        objects: dict[str, Element] = {}
        nodes: list[Element] = []
        stack = [(root, 0)]
        while stack:
            node, depth = stack.pop()
            budget.check("chunks")
            if depth > budget.limits.max_depth:
                raise BridgeError("Profundidade máxima de XML excedida.")
            nodes.append(node)
            if "ObjectID" in node.attrib:
                identifier = node.attrib["ObjectID"]
                if identifier in objects:
                    raise BridgeError(f"ObjectID duplicado: {identifier}")
                objects[identifier] = node
            stack.extend((child, depth + 1) for child in reversed(list(node)))
        for node in nodes:
            if "ObjectRef" in node.attrib and node.attrib["ObjectRef"] not in objects:
                raise BridgeError(f"ObjectRef não resolvido: {node.attrib['ObjectRef']}")

        def resolve(node: Element | None) -> Element:
            if node is None:
                raise BridgeError("Referência obrigatória ausente.")
            seen = set()
            while "ObjectRef" in node.attrib:
                ref = node.attrib["ObjectRef"]
                if ref in seen:
                    raise BridgeError("Referência XML cíclica.")
                seen.add(ref)
                node = objects[ref]
            return node

        source.detected_version = root.get("Version")
        document = PresetDocument(
            source=source, diagnostics={"objects": len(objects), "xml_elements": len(nodes)}
        )
        groups = [n for n in nodes if n.tag == "FilterPresetItem" and "ObjectID" in n.attrib]
        if not groups:
            raise BridgeError("PremiereData sem FilterPresetItem (não é um preset suportado).")
        names = {}
        for node in nodes:
            if node.tag == "TreeItemBase":
                ref = node.find("Data")
                if ref is not None and ref.get("ObjectRef"):
                    names[ref.get("ObjectRef")] = node.findtext("Name") or "Preset"
        for group in groups:
            preset = Preset(name=names.get(group.get("ObjectID"), source.path.rsplit("/", 1)[-1]))
            document.presets.append(preset)
            refs = list(group.findall("./FilterPresets/FilterPreset"))
            refs.sort(key=lambda n: int(n.get("Index", "0")))
            signatures = []
            for index, ref in enumerate(refs):
                budget.check("effects")
                filter_node = resolve(ref)
                if filter_node.tag != "FilterPreset":
                    raise BridgeError("FilterPreset referencia objeto de tipo incorreto.")
                component = resolve(filter_node.find("Component"))
                comp = component.find("Component")
                if comp is None:
                    raise BridgeError("VideoFilterComponent sem Component.")
                match = filter_node.findtext("FilterMatchName") or component.findtext("MatchName") or ""
                effect = Effect(
                    name=comp.findtext("DisplayName") or match,
                    identifier=EffectIdentifier(match_name=match, source_id=filter_node.get("ObjectID")),
                    order=index,
                    enabled=comp.findtext("Bypass") != "true",
                )
                preset.effects.append(effect)
                start = int(filter_node.findtext("AnchorInPoint") or "0")
                end_text = filter_node.findtext("AnchorOutPoint")
                end = int(end_text) if end_text else None
                mode = filter_node.findtext("Type")
                signatures.append((start, end, mode))
                if end is not None and end > start:
                    preset.source_duration_ticks = end - start
                    preset.source_time_base = TICKS
                preset.keyframe_mode = cast(
                    KeyframeMode,
                    {"0": "Scale", "1": "AnchorToIn", "2": "AnchorToOut"}.get(mode or "", "Scale"),
                )
                effect.metadata.update(anchor_in=start, anchor_out=end, preset_type=mode)
                effect.metadata["description"] = filter_node.findtext("Description") or ""
                if filter_node.findtext("Speed", "1.") not in ("1", "1.", "1.0"):
                    effect.warnings.append(
                        warn("SPEED", "Retiming de origem diferente de 1 não implementado.")
                    )
                param_refs = list(comp.findall("./Params/Param"))
                param_refs.sort(key=lambda n: int(n.get("Index", "0")))
                for param_ref in param_refs:
                    node = resolve(param_ref)
                    effect.parameters.append(self._parameter(node, param_ref.get("Index", ""), start, budget))
                if any(p.keyframes for p in effect.parameters):
                    preset.warnings.append(
                        warn(
                            "KEYFRAME_MODE",
                            "Type 0/1/2 → Scale/In/Out exige validação rotulada ou override explícito.",
                        )
                    )
                subrefs = component.findall("./SubComponents/SubComponent")
                for subref in subrefs:
                    sub = resolve(subref)
                    raw = {}
                    for subp in sub.findall("./Component/Params/Param")[: budget.limits.max_diagnostics]:
                        target = resolve(subp)
                        raw[subp.get("Index", "")] = self._raw_xml(target, budget)
                    effect.masks.append(
                        Mask(name=sub.findtext("./Component/DisplayName") or "Subcomponente", raw=raw)
                    )
                    effect.warnings.append(
                        warn("MASK", "Subcomponente/máscara preservado; geometria Base64 não decodificada.")
                    )
            if len(set(signatures)) > 1:
                preset.warnings.append(
                    warn("MIXED_TIMING", "Efeitos do preset têm referências temporais diferentes.")
                )
            if not refs:
                preset.warnings.append(warn("EMPTY_PRESET", "Nenhum efeito encontrado no preset."))
        return document

    def _raw_xml(self, node: Element, budget: Budget) -> dict:
        # Preserve field-level bounded samples, not unbounded XML copies.
        entries = {}
        for child in list(node)[: budget.limits.max_diagnostics]:
            raw = (child.text or "").encode("utf-8")
            if raw:
                entries[child.tag] = {**raw_summary(raw, budget.limits), "encoding": child.get("Encoding")}
        return entries

    def _parameter(self, node: Element, index: str, anchor: int, budget: Budget) -> Parameter:
        budget.check("parameters")
        control = node.findtext("ParameterControlType")
        kind = {
            "1": "number",
            "2": "number",
            "3": "number",
            "4": "boolean",
            "5": "color",
            "6": "point",
            "7": "enum",
            "8": "number",
        }.get(control or "", "unknown")
        if node.tag == "PointComponentParam":
            kind = "point"
        if node.tag == "ArbVideoComponentParam":
            kind = "unknown"
        decode_kind = "integer" if control == "1" and kind == "number" else kind
        record = node.findtext("StartKeyframe") or ""
        fields = record.split(",")
        # CurrentValue can be a stale preview. StartKeyframe contains the saved constant.
        constant = fields[1] if len(fields) >= 2 else node.findtext("CurrentValue") or ""
        value = value_of(constant, decode_kind)
        param = Parameter(
            id=node.findtext("ParameterID") or index,
            name=node.findtext("Name") or f"Parâmetro {index}",
            value=ParameterValue(
                kind=cast(ValueKind, kind),
                data=value,
                unit="normalized-frame" if kind == "point" else node.findtext("UnitsString") or None,
            ),
            origin={
                "object_id": node.get("ObjectID"),
                "index": index,
                "StartKeyframe": record[:512],
                "CurrentValue": (node.findtext("CurrentValue") or "")[:512],
            },
            metadata={"control_type": control, "source_tag": node.tag},
        )
        key_text = node.findtext("Keyframes") or ""
        records = key_text.split(";") if key_text.strip() else []
        for raw in records:
            if not raw.strip():
                continue
            budget.check("keyframes")
            items = raw.strip().split(",")
            try:
                ticks = int(items[0])
                decoded = value_of(items[1], decode_kind)
            except (ValueError, IndexError) as exc:
                param.warnings.append(warn("XML_KEYFRAME", f"Registro de keyframe desconhecido: {exc}"))
                continue
            if decoded is None:
                param.warnings.append(warn("XML_KEYFRAME_VALUE", "Valor animado não decodificado."))
                continue
            param.keyframes.append(
                Keyframe(
                    ticks=ticks - anchor,
                    time_base=TICKS,
                    value=decoded,
                    in_interp=[Interpolation.UNKNOWN],
                    out_interp=[Interpolation.UNKNOWN],
                    metadata={"raw": raw[:512]},
                )
            )
        if records:
            param.warnings.append(
                warn(
                    "XML_INTERPOLATION",
                    "Tempos/valores extraídos; códigos de curvas Premiere ainda não verificados.",
                )
            )
        binary_fields = [
            c for c in node if c.get("Encoding") == "base64" or re.match(r"kf\.\d+\.value", c.tag)
        ]
        if binary_fields or kind == "unknown":
            param.origin["raw_fields"] = self._raw_xml(node, budget)
            param.warnings.append(
                warn("OPAQUE_XML", "Dados arbitrários/Base64 ou tipo desconhecido; não convertidos.")
            )
        if node.findtext("IsTimeVarying") == "true" and not param.keyframes:
            param.warnings.append(
                warn("UNDECODED_ANIMATION", "Propriedade animada sem keyframes decodificados.")
            )
        if value is None:
            param.warnings.append(warn("UNDECODED_VALUE", "Valor desconhecido não substituído por zero."))
        return param
