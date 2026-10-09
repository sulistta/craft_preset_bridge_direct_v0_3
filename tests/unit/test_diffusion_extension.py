"""Original synthetic cases; no private preset data is distributed."""

import json

import pytest

from craft_bridge.core.pipeline import convert_file, inspect_file, preview
from craft_bridge.extensions import extension_paths
from craft_bridge.mappings.registry import Registry
from tests.helpers import ffx


@pytest.fixture
def diffusion(tmp_path, monkeypatch):
    monkeypatch.setenv('CRAFT_BRIDGE_CONFIG',str(tmp_path/'config'))
    mapping,module=extension_paths('diffusion')
    assert module.read_bytes().startswith(b'\0asm')
    Registry().install(mapping)
    return json.loads(mapping.read_text())


def test_seventeen_controls_and_strict_refuses_approximation(diffusion,tmp_path):
    manifest=diffusion['plugins'][0]
    specs={p['id']:p for p in manifest['params']}
    parameters=[]
    for source,rule in diffusion['mappings'][0]['params'].items():
        spec=specs[rule['target']]
        if spec['type']=='color':
            r,g,b,a=spec['default']
            parameters.append((source,[a*255,r*255,g*255,b*255],5,4,None,30720,7))
        else:
            kind=7 if spec['type']=='popup' and spec['id']=='direction' else 1 if spec['id'].startswith(('color_count','width_')) else 10
            value=spec['default']+1 if spec['type']=='popup' else spec['default']
            parameters.append((source,value,kind))
    file=tmp_path/'original-synthetic.ffx'
    file.write_bytes(ffx([('omino_diffusion',parameters)]))
    plan,report=preview(inspect_file(file))
    assert report.status=='PARTIAL' and report.effects[0].parameters_converted==17
    effect=plan['effects'][0]
    assert effect['effect']=='org.craftbridge.diffusion' and effect['plugin_fingerprint']
    values={p['id']:p['value'] for p in effect['properties']}
    assert values['color_count']==1 and values['direction']==0
    assert values['color_2']==[1,1,1,1]
    assert sum(w.code=='MAPPING_APPROXIMATION' for w in report.effects[0].warnings)==4
    output=tmp_path/'strict.json'
    result=convert_file(file,output,strict=True)
    assert result.status=='FAILED' and result.output is None and not output.exists()
    assert (tmp_path/'strict.json.report.json').exists()


@pytest.mark.parametrize('source,value,kind',[
    ('0003',5,7),('0016',7,1),('0016',2.5,1),('0016',0,1),
    ('0001',4.01,10),('0017',-4.01,10),('0005',0,1),('0015',4097,1),
])
def test_unmapped_options_and_limits_refused(diffusion,tmp_path,source,value,kind):
    file=tmp_path/'invalid.ffx'
    file.write_bytes(ffx([('omino_diffusion',[('omino_diffusion-'+source,value,kind)])]))
    plan,report=preview(inspect_file(file))
    assert not plan['effects']
    assert any(w.code=='PARAMETER_REJECTED' and w.path=='omino_diffusion-'+source for w in report.effects[0].warnings)


def test_manifest_and_map_contract(diffusion):
    mapping,module=extension_paths('diffusion')
    assert json.loads(mapping.with_name('manifest.json').read_text())==diffusion['plugins'][0]
    assert len(diffusion['plugins'][0]['params'])==len(diffusion['mappings'][0]['params'])==17
    assert module.stat().st_size<200_000
