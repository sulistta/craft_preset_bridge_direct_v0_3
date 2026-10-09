import json

import pytest

from craft_bridge.core.pipeline import convert_file, inspect_file, preview
from craft_bridge.extensions import extension_paths
from craft_bridge.mappings.registry import Registry
from tests.helpers import ffx
from tests.unit.test_selected_properties import selected_ffx


@pytest.fixture
def installed_stretch(tmp_path, monkeypatch):
    monkeypatch.setenv('CRAFT_BRIDGE_CONFIG',str(tmp_path/'config'))
    mapping,module=extension_paths('stretch')
    assert module.read_bytes().startswith(b'\0asm')
    Registry().install(mapping)
    return json.loads(mapping.read_text())


def test_twenty_typed_controls_have_explicit_approximation_and_strict_refuses(installed_stretch,tmp_path):
    manifest=installed_stretch['plugins'][0]
    specs={p['id']:p for p in manifest['params']}
    parameters=[]
    for source,rule in installed_stretch['mappings'][0]['params'].items():
        spec=specs[rule['target']]
        kind=7 if spec['type']=='popup' else 4 if spec['type']=='checkbox' else 3 if spec['type']=='angle' else 10
        value=spec['default']+1 if kind==7 else int(spec['default']) if kind==4 else spec['default']
        parameters.append((source,value,kind))
    file=tmp_path/'original-synthetic.ffx'
    file.write_bytes(ffx([('pixel_stretch',parameters)]))
    plan,report=preview(inspect_file(file))
    assert report.status=='PARTIAL' and report.effects[0].parameters_converted==20
    effect=plan['effects'][0]
    assert effect['effect']=='org.craftbridge.stretch' and effect['plugin_fingerprint']
    values={p['id']:p['value'] for p in effect['properties']}
    assert values['direction']==0 and values['channels']==0 and values['sync'] is True
    assert values['intensity']==100 and values['pixel_size']==1
    assert sum(w.code=='MAPPING_APPROXIMATION' for w in report.effects[0].warnings)==4
    output=tmp_path/'strict.json'
    result=convert_file(file,output,strict=True)
    assert result.status=='FAILED' and result.output is None and not output.exists()
    assert (tmp_path/'strict.json.report.json').exists()


@pytest.mark.parametrize('source,value,kind',[
    ('0001',5,7),('0022',9,7),('0004',7,7),('0016',5,7),
    ('0003',0,10),('0023',101,10),('1006',-1,10),
    ('0005',1e6+1,3),('0009',-1e6-1,3),('0013',1e6+1,3),
])
def test_unknown_options_and_out_of_range_numbers_are_refused(installed_stretch,tmp_path,source,value,kind):
    file=tmp_path/'invalid.ffx'
    file.write_bytes(ffx([('pixel_stretch',[('pixel_stretch-'+source,value,kind)])]))
    plan,report=preview(inspect_file(file))
    assert not plan['effects']
    assert any(w.code=='PARAMETER_REJECTED' and w.path=='pixel_stretch-'+source for w in report.effects[0].warnings)


def test_selected_controls_bind_existing_instance_and_preserve_animation(installed_stretch,tmp_path):
    file=tmp_path/'selected-original.ffx'
    file.write_bytes(selected_ffx([
        ('pixel_stretch','pixel_stretch-0002',0.5,10,[(0,0.5,1),(30720,1.5,1)]),
        ('pixel_stretch','pixel_stretch-0001',1,7,[(0,1,3),(30720,3,3)]),
        ('pixel_stretch','pixel_stretch-0010',1,4,[(0,1,3),(30720,0,3)]),
    ],indices=[2,2,2]))
    plan,report=preview(inspect_file(file))
    assert report.status=='PARTIAL' and report.effects[0].keyframes_preserved==6
    effect=plan['effects'][0]
    assert effect['application']=='existing' and effect['source_effect_index']==2
    values={p['id']:p for p in effect['properties']}
    assert values['direction']['keyframes'][1]['value']==2
    assert values['sync']['keyframes'][1]['value'] is False
    assert values['stretch']['keyframes'][1]['value']==1.5
    assert not any(c['command']=='effect.apply' for c in plan['commands'])


def test_module_manifest_and_rules_share_one_contract(installed_stretch):
    mapping,module=extension_paths('stretch')
    assert json.loads(mapping.with_name('manifest.json').read_text())==installed_stretch['plugins'][0]
    assert len(installed_stretch['plugins'][0]['params'])==len(installed_stretch['mappings'][0]['params'])==20
    assert module.stat().st_size<200_000
