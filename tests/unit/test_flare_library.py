"""Original synthetic OFP/FFX data; no vendor presets or images."""

import hashlib
import json
import struct
from pathlib import Path

import pytest

from craft_bridge.core.pipeline import inspect_file, preview
from craft_bridge.core.safety import BridgeError
from craft_bridge.extensions.flare.library import (
    MAGIC,
    SCENE_CAPACITY,
    _active_segments,
    build_library,
    manifest_for,
    pack_scenes,
    patch_template,
    unpack_scenes,
)
from craft_bridge.mappings.registry import Registry
from tests.helpers import chunk, container, path, stream
from tests.unit.test_optical_flares import atom, field, marker

ROOT = Path(__file__).resolve().parents[2]


def scene(brightness=100):
    return (
        b"OFP\3" + marker(3000) + field(0x70, 0, struct.pack("<f", 100)) + marker(4000)
        + atom(1, struct.pack("<I", 1)) + atom(2, b"Original glow".ljust(64, b"\0"))
        + atom(3, b"\0") + atom(4, b"\0")
        + field(0, 0, struct.pack("<f", brightness)) + field(1, 0, struct.pack("<f", 20)) + marker(1000)
    )


def write_ffx(folder, data=None, multiple=False, options=True):
    from craft_bridge.parsers.ffx.optical_flares import OPTIONS

    meta, node = stream(OPTIONS, 0, 11, flags=7)
    brightness_meta, brightness = stream("VIDEOCOPILOT OpticalFlares-0003", 40, 10)
    arbs = container("aRbs", chunk("aRbp", data or scene()), *([chunk("aRbp", scene(20))] if multiple else []))
    contents = [node, arbs, brightness] if options else [brightness]
    folder.mkdir(exist_ok=True)
    file = folder / "synthetic.ffx"
    file.write_bytes(container("FaFX", container("besc",
        path(["ADBE Effect Parade", "VIDEOCOPILOT OpticalFlares"]),
        container("sspc", container("parT", meta, brightness_meta), container("tdgp", *contents))), tag="RIFX"))
    return file


def test_scene_library_is_exact_ordered_and_bounded():
    first, second = scene(), scene(30)
    library = pack_scenes([first, second])
    assert unpack_scenes(library) == [first, second]
    with pytest.raises(BridgeError):
        pack_scenes([])
    with pytest.raises(BridgeError):
        pack_scenes([first] * 257)
    for broken in (library[:-1], library + b"extra", library[:8] + struct.pack("<II",len(library),257) + library[16:],
                   MAGIC + struct.pack("<II", SCENE_CAPACITY+1, 1) + b"\0" * 8):
        with pytest.raises(BridgeError):
            unpack_scenes(broken)
    broken = bytearray(library)
    struct.pack_into("<I", broken, 24, 24)
    with pytest.raises(BridgeError, match="sobreposta"):
        unpack_scenes(broken)


def test_template_data_patching_keeps_code_and_size_and_refuses_untrusted_binary():
    folder = ROOT / "src/craft_bridge/extensions/flare"
    template = (folder / "bridge_flare_template.wasm").read_bytes()
    digest = json.loads((folder / "template.json").read_text())["sha256"]
    library = pack_scenes([scene()])
    manifest = manifest_for([hashlib.sha256(scene()).hexdigest()], hashlib.sha256(library).hexdigest(), digest)
    data = manifest.model_dump_json(exclude_none=True).encode()
    module = patch_template(template, library, data, digest)
    assert len(module) == len(template) and library in module and data in module
    # Independently compare all bytes outside active payloads, including code,
    # segment expressions/lengths, exports and tables.
    segments = _active_segments(template)
    assert _active_segments(module) == segments
    cursor = 0
    for start, end in segments:
        assert module[cursor:start] == template[cursor:start]
        cursor = end
    assert module[cursor:] == template[cursor:]
    with pytest.raises(BridgeError):
        patch_template(module, library, data, digest)
    with pytest.raises(BridgeError):
        patch_template(template[:-1], library, data, hashlib.sha256(template[:-1]).hexdigest())


def test_build_and_map_exact_scene_without_default_fallback(tmp_path):
    corpus, output = tmp_path / "corpus", tmp_path / "library"
    file = write_ffx(corpus)
    library = build_library(corpus, output)
    assert library['associated_snapshots'] == 1 and len(library['scene_ids']) == 1
    assert library['renderer_loaded'] is False and library['mapping_installed'] is False
    registry = Registry(packages=[output / "mapping.json"])
    doc = inspect_file(file)
    plan, report = preview(doc, registry=registry)
    assert report.status == "PARTIAL" and len(plan["effects"]) == 1
    props = {p['id']:p['value'] for p in plan['effects'][0]['properties']}
    assert props == {'scene':0,'brightness':40}
    assert plan['effects'][0]['plugin_fingerprint'] == library['manifest_fingerprint']
    assert any(w.code == 'MAPPING_APPROXIMATION' for w in report.effects[0].warnings)
    from craft_bridge.core.validation import validate_plan
    from craft_bridge.exporters.effectcraft.exporter import EffectCraftPlan, preview_commands
    incomplete = EffectCraftPlan.model_validate(plan)
    incomplete.effects[0].properties = [p for p in incomplete.effects[0].properties if p.id!='scene']
    incomplete.commands = preview_commands(incomplete)
    with pytest.raises(BridgeError, match='obrigatórios'):
        validate_plan(incomplete.model_dump(mode='json'), registry)
    # This perfectly valid scene is absent from this library. Brightness alone
    # must not create an effect using the unrelated Scene 0 default.
    file = write_ffx(corpus, scene(20))
    plan, report = preview(inspect_file(file), registry=registry)
    assert report.status == 'UNSUPPORTED' and not plan['effects']
    assert report.effects[0].parameters_converted == 0
    assert any(w.code == 'REQUIRED_SOURCE_DATA' for w in report.effects[0].warnings)


@pytest.mark.parametrize('kind', ['missing','multiple','edited','extra_warning'])
def test_ambiguous_missing_or_inconsistent_source_cannot_create_generic_flare(tmp_path, kind):
    from craft_bridge.core.models import ConversionWarning
    from craft_bridge.parsers.ffx.optical_flares import OPTIONS

    corpus, output = tmp_path / 'corpus', tmp_path / 'library'
    file = write_ffx(corpus)
    build_library(corpus, output)
    registry = Registry(packages=[output / 'mapping.json'])
    file = write_ffx(corpus, multiple=kind=='multiple', options=kind!='missing')
    doc = inspect_file(file)
    if kind in ('edited','extra_warning'):
        parameter = next(p for p in doc.presets[0].effects[0].parameters if p.id==OPTIONS)
        if kind=='edited':
            parameter.metadata['decoded_arbitrary']['objects'][0]['fields'][0]['value']=20
        else:
            parameter.warnings.append(ConversionWarning(code='EXPRESSION',message='Unsupported'))
    plan, report = preview(doc, registry=registry)
    assert not plan['effects'] and report.status=='UNSUPPORTED'
    assert report.effects[0].parameters_converted==0


def test_builder_cannot_infer_multiple_state_association_or_overwrite(tmp_path):
    corpus, output = tmp_path / 'corpus', tmp_path / 'library'
    write_ffx(corpus, multiple=True)
    with pytest.raises(BridgeError):
        build_library(corpus, output)
    assert not output.exists()
    write_ffx(corpus)
    build_library(corpus, output)
    with pytest.raises(BridgeError):
        build_library(corpus, output)


@pytest.mark.parametrize('data', [
    scene().replace(atom(1, struct.pack('<I',1)), atom(1, struct.pack('<I',16))),
    scene().replace(field(1,0,struct.pack('<f',20)), field(1,0,struct.pack('<f',1e8))),
    scene().replace(marker(1000), field(6,3,struct.pack('<i',99))+marker(1000)),
])
def test_builder_refuses_structurally_valid_but_unrenderable_profiles(tmp_path, data):
    corpus, output = tmp_path/'corpus',tmp_path/'library'
    write_ffx(corpus,data)
    with pytest.raises(BridgeError):
        build_library(corpus,output)
    assert not output.exists()


def test_scene_map_menu_hashes_and_creation_requirement_are_validated(tmp_path):
    corpus, output = tmp_path / 'corpus', tmp_path / 'library'
    write_ffx(corpus)
    build_library(corpus, output)
    data = json.loads((output/'mapping.json').read_text())
    data['mappings'][0]['required_on_create']=[]
    (output/'bad.json').write_text(json.dumps(data))
    with pytest.raises(BridgeError):
        Registry(packages=[output/'bad.json'])


def test_approximate_flare_strict_writes_reports_without_publishing_preset(tmp_path):
    from craft_bridge.core.pipeline import convert_file

    corpus, library = tmp_path/'corpus', tmp_path/'library'
    source = write_ffx(corpus)
    original = source.read_bytes()
    build_library(corpus, library)
    registry = Registry(packages=[library/'mapping.json'])
    output = tmp_path/'converted.json'
    report = convert_file(source, output, registry=registry, strict=True)
    assert report.status == 'FAILED' and report.output is None
    assert not output.exists() and source.read_bytes() == original
    assert Path(str(output)+'.report.json').is_file()
    assert Path(str(output)+'.report.html').is_file()
    assert report.effects[0].parameters_converted == 2
    assert any(w.code == 'MAPPING_APPROXIMATION' for w in report.effects[0].warnings)


@pytest.mark.parametrize('index', [False, 0.0, '0', 256])
def test_scene_indices_require_bounded_exact_integers(tmp_path, index):
    from pydantic import ValidationError

    from craft_bridge.mappings.registry import Rule

    with pytest.raises(ValidationError):
        Rule(target='scene',kind='Choice',operation='ofp_scene_lookup',scenes={'a'*64:index})
