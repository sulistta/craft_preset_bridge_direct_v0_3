"""Original synthetic controls; private presets are opt-in, never redistributed."""

import json

import pytest

from craft_bridge.core.pipeline import convert_file, inspect_file, preview
from craft_bridge.extensions import extension_paths
from craft_bridge.mappings.registry import Registry
from tests.helpers import ffx


@pytest.fixture
def glint(tmp_path, monkeypatch):
    monkeypatch.setenv('CRAFT_BRIDGE_CONFIG', str(tmp_path / 'config'))
    mapping, module = extension_paths('glint')
    assert module.read_bytes().startswith(b'\0asm')
    Registry().install(mapping)
    return json.loads(mapping.read_text())


def test_twenty_five_controls_colors_contract_losses_and_strict(glint, tmp_path):
    manifest = glint['plugins'][0]
    specs = {p['id']: p for p in manifest['params']}
    params = []
    for source, rule in glint['mappings'][0]['params'].items():
        spec = specs[rule['target']]
        kind = {'slider': 2, 'color': 5, 'popup': 7}[spec['type']]
        value = spec['default']
        if kind == 7:
            value += 1
        elif kind == 5:
            value = [value[3] * 255, *(v * 255 for v in value[:3])]
        params.append((source, value, kind, 4, None, 30720, 7) if kind == 5 else (source, value, kind))
    params.append(('S_Glint-0001', 0, 0))  # unresolved background is not assumed empty
    file = tmp_path / 'original-synthetic.ffx'
    file.write_bytes(ffx([('S_Glint', params)]))
    out, report = preview(inspect_file(file))
    assert report.status == 'PARTIAL' and report.effects[0].parameters_converted == 25
    effect = out['effects'][0]
    assert effect['plugin_fingerprint'] and effect['effect'] == 'org.craftbridge.glint'
    values = {p['id']: p['value'] for p in effect['properties']}
    assert values['opacity_mode'] == 1
    assert values['scale_colors'] == [1, 1, 1, 1]
    assert values['threshold_add_color'] == [0, 0, 0, 1]
    warnings = report.effects[0].warnings
    assert sum(w.code == 'MAPPING_APPROXIMATION' for w in warnings) == 4
    assert any(w.path == 'S_Glint-0001' and w.loss for w in warnings)
    output = tmp_path / 'strict.json'
    assert convert_file(file, output, strict=True).status == 'FAILED'
    assert not output.exists()
    mapping, module = extension_paths('glint')
    assert json.loads(mapping.with_name('manifest.json').read_text()) == manifest
    assert module.stat().st_size < 200_000
    assert (mapping.parent / 'licenses/Rust-1.98.1-COPYRIGHT-library.html').is_file()


@pytest.mark.parametrize('source,value,kind', [
    ('0050', -0.1, 2), ('0050', 65, 2), ('0100', 1.1, 2),
    ('0059', 4097, 2), ('0060', 9, 2), ('0068', 1.1, 2),
    ('0074', 4, 7), ('0074', 0, 7), ('0074', 1.5, 7),
])
def test_out_of_profile_range_or_menu_is_refused(glint, tmp_path, source, value, kind):
    file = tmp_path / 'invalid.ffx'
    file.write_bytes(ffx([('S_Glint', [('S_Glint-' + source, value, kind)])]))
    out, report = preview(inspect_file(file))
    assert not out['effects'] and report.status == 'UNSUPPORTED'


def test_scalar_bezier_preserves_speed_and_influence(glint, tmp_path):
    file = tmp_path / 'animated.ffx'
    file.write_bytes(ffx([('S_Glint', [
        ('S_Glint-0050', .8, 2, 1, [(0, .8, 2), (30720, 1.2, 2)], 30720, 0),
    ])]))
    out, report = preview(inspect_file(file))
    prop = out['effects'][0]['properties'][0]
    assert prop['id'] == 'brightness' and len(prop['keyframes']) == 2
    assert prop['keyframes'][1]['handles']['in_influence'] == [1 / 3]
    assert report.effects[0].keyframes_preserved == 2
