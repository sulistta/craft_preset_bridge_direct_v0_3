"""Original local scene-library builder. Patches data only in a trusted WASM template.

No compiler, plugin loading, expression evaluation or asset access at runtime.
Only statically associated Options scenes enter the library.
"""

import hashlib
import json
import math
import struct
from importlib.resources import files
from pathlib import Path

from craft_bridge.core.pipeline import inspect_file
from craft_bridge.core.safety import BridgeError, atomic_write, json_text
from craft_bridge.mappings.plugins import PluginManifest
from craft_bridge.mappings.registry import Mapping, Package, Registry
from craft_bridge.parsers.ffx.optical_flares import OPTIONS, decode_ofp, encode_ofp

SCENE_TAG = b"CBFLARE_SCENE_01"
MANIFEST_TAG = b"CBFLARE_MANIF_01"
SCENE_CAPACITY = 2 * 1024 * 1024
MANIFEST_CAPACITY = 16 * 1024
MAX_SCENES = 256
MAGIC = b"CBFLIB01"
OBJECT_TYPES = {1, 2, 4, 5, 6, 7, 8, 9, 11, 12, 14, 15}


def validate_render_profile(scene: dict) -> None:
    """Reject structural profiles that cannot be processed by the original kernel.

    This is data/type/complexity validation, not a claim of visual equivalence.
    """
    global_kinds = {0x70: 0, 8: 0, 4: 2, 0x12: 0, 9: 3}
    object_kinds = {0: 0, 1: 0, 8: 0, 5: 0, 0x12: 0, 0x1D: 0, 0x34: 0,
                    0x0C: 0, 0x31: 0, 0x0F: 0, 0x55: 1, 3: 1, 0x17: 1,
                    4: 2, 0x0B: 3, 6: 3, 7: 3, 0x29: 3, 0x1B: 4, 0x16: 4,
                    0x1A: 4, 0x6E: 4, 0x6C: 0}
    blocks = [(scene['globals'], global_kinds)]
    primitives = 0
    for obj in scene['objects']:
        if obj['type'] not in OBJECT_TYPES:
            raise BridgeError("Tipo de objeto OFP sem renderer próprio; biblioteca não publicada.")
        kinds = {**object_kinds, (0x67 if obj['type']==7 else 2): (0 if obj['type']==7 else 1),
                 (0x43 if obj['type'] in (2,9) else 0x38): 0}
        if obj['type'] in (4,14):
            kinds[0x0E] = 0
            kinds[0x0D if obj['type']==4 else 0x3F] = 0
        blocks.append((obj['fields'], kinds))
        counts = [f for f in obj['fields'] if f['id']==0x0E and f['kind']!=6]
        count = math.floor(counts[0]['value'] + 0.5) if counts and obj['type'] in (4,14) and counts[0]['kind']==0 else 1
        if not 0 <= count <= 128:
            raise BridgeError("Quantidade de objetos replicados fora do perfil 0..128.")
        primitives += count
    if primitives > 4096:
        raise BridgeError("Cena excede 4096 primitivas procedurais.")
    for fields, expected in blocks:
        seen = set()
        for field in fields:
            if field['kind']==6:
                continue
            if field['id'] in seen or field['id'] in expected and field['kind'] != expected[field['id']]:
                raise BridgeError("Campo OFP repetido ou com tipo fora do perfil do renderer.")
            seen.add(field['id'])
            values = [field['value']] if field['kind']==0 else [field['value']['x'],field['value']['y']] if field['kind']==1 else []
            if any(abs(value)>1e6 for value in values):
                raise BridgeError("Campo OFP fora do intervalo numérico do renderer.")
    # Keep builder acceptance within the renderer's implemented enum profile.
    for fields, menus in [(scene['globals'], {9:{0,1}}), *(
        (obj['fields'], {6:{0,1,2,3,4}, 7:{0,1,2,3}, 0x29:{0,1,2},
                         **({0x0B:{0,1,2}} if obj['type'] in (4,14,15) else {})})
        for obj in scene['objects']
    )]:
        for field in fields:
            if field['kind']!=6 and field['id'] in menus and field['value'] not in menus[field['id']]:
                raise BridgeError("Enum OFP fora do perfil implementado; biblioteca não publicada.")


def pack_scenes(scenes: list[bytes]) -> bytes:
    if not 1 <= len(scenes) <= MAX_SCENES:
        raise BridgeError("Biblioteca exige 1..256 cenas.")
    offset = 16 + 8 * len(scenes)
    entries = []
    for data in scenes:
        if offset + len(data) > SCENE_CAPACITY:
            raise BridgeError("Biblioteca de cenas excede 2 MiB.")
        decode_ofp(data)
        entries.append(struct.pack("<II", offset, len(data)))
        offset += len(data)
    return MAGIC + struct.pack("<II", offset, len(scenes)) + b"".join(entries) + b"".join(scenes)


def unpack_scenes(data: bytes) -> list[bytes]:
    if len(data) > SCENE_CAPACITY or len(data) < 24 or data[:8] != MAGIC:
        raise BridgeError("Envelope de biblioteca de cenas inválido.")
    size, count = struct.unpack_from("<II", data, 8)
    if size != len(data) or not 1 <= count <= MAX_SCENES or 16 + 8 * count > size:
        raise BridgeError("Tamanho ou contagem de biblioteca inválida.")
    offset = 16 + 8 * count
    result = []
    for index in range(count):
        start, length = struct.unpack_from("<II", data, 16 + 8 * index)
        if start != offset or length == 0 or start + length > size:
            raise BridgeError("Entrada de biblioteca truncada, sobreposta ou fora de ordem.")
        scene = data[start : start + length]
        decode_ofp(scene)
        result.append(scene)
        offset += length
    if offset != size:
        raise BridgeError("Dados não associados no final da biblioteca.")
    return result


def _uleb(data: bytes, offset: int, end: int) -> tuple[int, int]:
    value = 0
    for index in range(5):
        if offset >= end:
            break
        byte = data[offset]
        offset += 1
        value |= (byte & 127) << (7 * index)
        if not byte & 128:
            if value > 0xFFFFFFFF:
                break
            return value, offset
    raise BridgeError("WASM: inteiro u32 truncado ou fora do intervalo.")


def _active_segments(module: bytes) -> list[tuple[int, int]]:
    if module[:8] != b"\0asm\1\0\0\0" or len(module) > 4 * 1024 * 1024:
        raise BridgeError("Template WASM inválido ou excessivo.")
    offset = 8
    data_sections = 0
    segments = []
    while offset < len(module):
        id = module[offset]
        size, start = _uleb(module, offset + 1, len(module))
        end = start + size
        if end > len(module):
            raise BridgeError("WASM: seção truncada.")
        if id == 11:
            data_sections += 1
            if data_sections != 1:
                raise BridgeError("WASM: seção de dados duplicada.")
            count, cursor = _uleb(module, start, end)
            if count > 1024:
                raise BridgeError("WASM: excesso de segmentos.")
            for _ in range(count):
                mode, cursor = _uleb(module, cursor, end)
                if mode not in (0, 2):
                    raise BridgeError("WASM: somente segmentos ativos comprovados.")
                if mode == 2:
                    memory, cursor = _uleb(module, cursor, end)
                    if memory != 0:
                        raise BridgeError("WASM: índice de memória não comprovado.")
                if cursor >= end or module[cursor] != 0x41:
                    raise BridgeError("WASM: expressão de offset não comprovada.")
                cursor += 1
                # Skip the bounded signed LEB i32 offset; it is never changed.
                for _index in range(5):
                    if cursor >= end:
                        raise BridgeError("WASM: offset truncado.")
                    byte = module[cursor]
                    cursor += 1
                    if not byte & 128:
                        break
                else:
                    raise BridgeError("WASM: offset excessivo.")
                if cursor >= end or module[cursor] != 0x0B:
                    raise BridgeError("WASM: expressão de offset sem fim.")
                length, cursor = _uleb(module, cursor + 1, end)
                if cursor + length > end:
                    raise BridgeError("WASM: segmento truncado.")
                segments.append((cursor, cursor + length))
                cursor += length
            if cursor != end:
                raise BridgeError("WASM: bytes adicionais na seção de dados.")
        offset = end
    return segments


def patch_template(template: bytes, library: bytes, manifest: bytes, expected_sha256: str) -> bytes:
    if hashlib.sha256(template).hexdigest() != expected_sha256:
        raise BridgeError("Template WASM não coincide com o build auditado.")
    unpack_scenes(library)
    declared = PluginManifest.model_validate_json(manifest)
    declared.specs()
    if len(manifest) + 4 > MANIFEST_CAPACITY:
        raise BridgeError("Manifesto de biblioteca excede o slot reservado.")
    output = bytearray(template)
    segments = _active_segments(template)
    for tag, capacity, fill, replacement in (
        (SCENE_TAG, SCENE_CAPACITY, 0xA5, library),
        (MANIFEST_TAG, MANIFEST_CAPACITY, 0xB7, struct.pack("<I", len(manifest)) + manifest),
    ):
        matches = []
        for start, end in segments:
            found = template.find(tag, start, end)
            while found >= 0:
                data_start = found + len(tag)
                if data_start + capacity <= end and template[data_start : data_start + capacity] == bytes([fill]) * capacity:
                    matches.append(data_start)
                found = template.find(tag, found + 1, end)
        if len(matches) != 1:
            raise BridgeError("Template sem slot único, íntegro e ativo.")
        start = matches[0]
        output[start : start + capacity] = replacement.ljust(capacity, b"\0")
    return bytes(output)


def manifest_for(hashes: list[str], digest: str, renderer_digest: str) -> PluginManifest:
    params = [
        {"id": "scene", "name": "Scene (exact data hash)", "type": "popup", "default": 0,
         "options": [f"{index + 1}: {hash[:12]}" for index, hash in enumerate(hashes)]},
        {"id": "position", "name": "Light position", "type": "point"},
        {"id": "center", "name": "Optical center", "type": "point"},
        {"id": "brightness", "name": "Brightness (%)", "type": "slider", "default": 100.0, "min": 0, "max": 100000},
        {"id": "scale", "name": "Scale (%)", "type": "slider", "default": 100.0, "min": 0, "max": 10000},
        {"id": "rotation", "name": "Rotation (degrees)", "type": "angle"},
        {"id": "color", "name": "Color", "type": "color"},
        {"id": "color_mode", "name": "Color mode", "type": "popup", "options": ["Tint", "Multiply"]},
        {"id": "evolution", "name": "Evolution (approximate)", "type": "angle"},
        {"id": "render_mode", "name": "Render mode", "type": "popup", "options": ["On Black", "Transparent", "Over Input"]},
    ]
    return PluginManifest.model_validate({
        "api": 1, "id": "org.craftbridge.flare.lib_" + digest[:24],
        "name": "Bridge Flare Library (Approximate)", "category": "Craft Bridge",
        "version": "0.1.0+" + renderer_digest[:32] + "." + digest,
        "author": "Craft Preset Bridge contributors",
        "description": "Original procedural scene renderer. Exact embedded source data; approximate calibration/kernels. No vendor assets, textures, 3D, tracking or certified Optical Flares equivalence.",
        "params": params,
    })


def build_library(folder: Path, output: Path) -> dict:
    if not folder.is_dir():
        raise BridgeError("Pasta de presets não encontrada.")
    if output.exists():
        raise BridgeError("Escolha uma pasta de saída nova para a biblioteca.")
    # Read/validate everything before writing. Never infer an Options association
    # from diagnostic blobs, including multiple aRbp payloads.
    scenes: dict[str, bytes] = {}
    associated = 0
    for file in sorted(folder.rglob("*.ffx")):
        if file.is_symlink():
            continue
        document = inspect_file(file)
        for preset in document.presets:
            for effect in preset.effects:
                for param in effect.parameters:
                    if param.id != OPTIONS or not param.metadata.get("decoded_arbitrary"):
                        continue
                    data = encode_ofp(param.metadata["decoded_arbitrary"])
                    validate_render_profile(param.metadata["decoded_arbitrary"])
                    hash = hashlib.sha256(data).hexdigest()
                    if hash != param.origin.get("aRbp", {}).get("sha256"):
                        raise BridgeError("Cena decodificada não coincide com o hash original.")
                    scenes[hash] = data
                    associated += 1
    hashes = sorted(scenes)
    library = pack_scenes([scenes[hash] for hash in hashes])
    digest = hashlib.sha256(library).hexdigest()
    resources = files(__package__)
    metadata = json.loads(resources.joinpath("template.json").read_text())
    template = resources.joinpath("bridge_flare_template.wasm").read_bytes()
    manifest = manifest_for(hashes, digest, metadata["sha256"])
    manifest.specs()
    encoded_manifest = json.dumps(manifest.model_dump(mode="json", exclude_none=True), separators=(",", ":")).encode()
    module = patch_template(template, library, encoded_manifest, metadata["sha256"])
    index = {hash: index for index, hash in enumerate(hashes)}
    prefix = "VIDEOCOPILOT OpticalFlares-"
    params = {
        OPTIONS: {"target": "scene", "kind": "Choice", "operation": "ofp_scene_lookup", "scenes": index},
        prefix + "0001": {"target": "position", "kind": "Vec2", "operation": "normalized_to_pixels"},
        prefix + "0002": {"target": "center", "kind": "Vec2", "operation": "normalized_to_pixels"},
        prefix + "0003": {"target": "brightness"}, prefix + "0004": {"target": "scale"},
        prefix + "0005": {"target": "rotation"},
        prefix + "0006": {"target": "color", "kind": "Color", "operation": "argb255_to_rgba"},
        prefix + "0094": {"target": "color_mode", "kind": "Choice", "operation": "enum_map", "choices": {1: 0, 2: 1}},
        prefix + "0073": {"target": "evolution"},
        prefix + "0025": {"target": "render_mode", "kind": "Choice", "operation": "enum_map", "choices": {1: 0, 2: 1, 3: 2}},
    }
    mapping = Mapping.model_validate({
        "source": "VIDEOCOPILOT OpticalFlares", "source_format": "ffx", "target": "effectcraft", "effect": manifest.id,
        "params": params, "required_on_create": [OPTIONS],
        "target_commit": Registry(packages=[]).catalog["effectcraft"]["commit"],
        "evidence": "Nine authorized real static Options snapshots and exact parT/tdb4 kinds/menus; exact OFP binary hashes; original API v1 scene renderer.",
        "validation": "real-source-structure; original-approximate-renderer; no-adobe-visual-comparison",
        "limitations": [
            "Cena OFP preservada integralmente, mas calibração espacial, distribuição de objetos, cores, kernels, animação e blending são implementações próprias aproximadas; sem equivalência Optical Flares comprovada.",
            "Texturas/sprites proprietários não são carregados; objetos Texture são omitidos. Gradientes avançados, triggers, matte box, aberração/correção e controles de forma ainda têm perdas.",
            "Não são reproduzidos 3D, máscaras, tracking, camadas de origem, flicker, motion blur ou sampling do plugin. Outros parâmetros permanecem recusados individualmente.",
            "A biblioteca exige o módulo gerado e a cena pelo hash exato. Fingerprint do manifesto não constitui atestação binária do módulo carregado.",
        ],
    })
    package = Package(version=2, name="flare-library-" + digest[:20], plugins=[manifest], mappings=[mapping])
    candidate = Registry(packages=[])
    candidate._add(package)
    output.mkdir(parents=True)
    # These are user-derived private outputs. They are never added to the package.
    module_path = output / "bridge_flare_library.wasm"
    module_path.write_bytes(module)
    atomic_write(output / "manifest.json", json_text(manifest.model_dump(mode="json", exclude_none=True)))
    mapping_path = output / "mapping.json"
    atomic_write(mapping_path, json_text(package.model_dump(mode="json", exclude_none=True)))
    summary = {"format": "craftbridge.flare-library", "version": 1, "effect_id": manifest.id,
               "module": str(module_path.resolve()), "module_sha256": hashlib.sha256(module).hexdigest(),
               "mapping": str(mapping_path.resolve()),
               "library_sha256": digest, "manifest_fingerprint": manifest.fingerprint(),
               "associated_snapshots": associated, "scene_ids": index, "renderer_loaded": False,
               "mapping_installed": False, "approximate": True, "adobe_visual_equivalence_verified": False}
    atomic_write(output / "library.json", json_text(summary))
    return summary
