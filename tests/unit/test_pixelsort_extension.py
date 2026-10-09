"""Original synthetic profiles; actual private presets are opt-in and not distributed."""

import json

import pytest

from craft_bridge.core.pipeline import convert_file, inspect_file, preview
from craft_bridge.extensions import extension_paths
from craft_bridge.mappings.registry import Registry
from tests.helpers import ffx


@pytest.fixture
def pixelsort(tmp_path, monkeypatch):
    monkeypatch.setenv('CRAFT_BRIDGE_CONFIG', str(tmp_path / 'config'))
    mapping, module = extension_paths('pixelsort')
    assert module.read_bytes().startswith(b'\0asm')
    Registry().install(mapping)
    return json.loads(mapping.read_text())


def test_twenty_four_controls_points_menus_losses_and_strict(pixelsort, tmp_path):
    manifest = pixelsort['plugins'][0]
    specs = {p['id']: p for p in manifest['params']}
    params = []
    for source, rule in pixelsort['mappings'][0]['params'].items():
        spec = specs[rule['target']]
        kind = {'slider': 2, 'point': 6, 'popup': 7, 'checkbox': 4}[spec['type']]
        value = spec['default'] + 1 if kind == 7 else spec['default']
        params.append((source, value, kind, 2, None, 30720, 3) if kind == 6 else (source, value, kind))
    params.append(('S_PixelSort-0001', 0, 0))
    file = tmp_path / 'original-synthetic.ffx'
    file.write_bytes(ffx([('S_PixelSort', params)]))
    out, report = preview(inspect_file(file), source_size=(1920, 1080))
    assert report.status == 'PARTIAL' and report.effects[0].parameters_converted == 24
    effect = out['effects'][0]
    assert effect['effect'] == 'org.craftbridge.pixelsort' and effect['plugin_fingerprint']
    values = {p['id']: p['value'] for p in effect['properties']}
    assert values['radial_center'] == values['circular_center'] == [960, 540]
    assert values['mode'] == values['sort_type'] == values['show'] == 0
    assert values['sort_direction'] == values['opacity_mode'] == 1
    assert values['seed'] == .273
    assert sum(w.code == 'MAPPING_APPROXIMATION' for w in report.effects[0].warnings) == 4
    assert any(w.path == 'S_PixelSort-0001' and w.loss for w in report.effects[0].warnings)
    _, no_size = preview(inspect_file(file))
    assert no_size.effects[0].parameters_converted == 22
    assert sum(w.code == 'PARAMETER_REJECTED' for w in no_size.effects[0].warnings) == 2
    output = tmp_path / 'strict.json'
    assert convert_file(file, output, strict=True, source_size=(1920, 1080)).status == 'FAILED'
    assert not output.exists()
    mapping, module = extension_paths('pixelsort')
    assert json.loads(mapping.with_name('manifest.json').read_text()) == manifest
    assert module.stat().st_size < 200_000
    assert (mapping.parent / 'licenses/Rust-1.98.1-COPYRIGHT-library.html').is_file()


@pytest.mark.parametrize('source,value,kind', [
    ('0045', 4, 7), ('0066', 11, 7), ('0064', 0, 7), ('0071', 6, 7), ('0075', 4, 7),
    ('0067', 1001, 2), ('0068', 4097, 2), ('0069', -0.1, 2), ('0070', 1.1, 2),
    ('0053', 361, 2), ('0055', 65537, 2), ('0065', .5, 2),
])
def test_invalid_menu_range_or_boolean_refused(pixelsort, tmp_path, source, value, kind):
    file = tmp_path / 'invalid.ffx'
    file.write_bytes(ffx([('S_PixelSort', [('S_PixelSort-' + source, value, kind)])]))
    out, report = preview(inspect_file(file))
    assert not out['effects'] and report.status == 'UNSUPPORTED'


def test_scalar_bezier_seed_preserves_fraction_and_eases(pixelsort, tmp_path):
    file = tmp_path / 'animated.ffx'
    file.write_bytes(ffx([('S_PixelSort', [
        ('S_PixelSort-0069', .273, 2, 1, [(0, .273, 2), (30720, .274, 2)], 30720, 0),
    ])]))
    out, report = preview(inspect_file(file))
    prop = out['effects'][0]['properties'][0]
    assert prop['id'] == 'seed' and len(prop['keyframes']) == 2
    assert prop['keyframes'][0]['value'] == .273
    assert prop['keyframes'][1]['value'] == .274
    assert prop['keyframes'][1]['handles']['in_influence'] == [1 / 3]
    assert report.effects[0].keyframes_preserved == 2
