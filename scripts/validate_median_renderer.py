"""Original synthetic pixels via official WASM loader; no BCC rendered fixtures."""

import argparse
import hashlib
import json
import math
import subprocess
import time
from pathlib import Path

from craft_bridge.core.pipeline import inspect_file, preview
from craft_bridge.extensions import extension_paths
from craft_bridge.mappings.registry import Registry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--corpus', type=Path)
    parser.add_argument('--hd', action='store_true')
    parser.add_argument('--harness', type=Path, default=Path('artifacts/native-target/debug/craft-bridge-native-validation'))
    args = parser.parse_args()
    if args.output.exists() or args.corpus is not None and not args.corpus.is_dir():
        parser.error('New output and existing optional authorized corpus required')
    args.output.mkdir(parents=True)
    mapping, module = extension_paths('median')
    results = []

    def run(name, params, pixels=None, **extra):
        payload = {'params': params, 'strict_render': True, **extra}
        if pixels is not None:
            payload['pixels'] = pixels
        path = args.output / (name + '.json')
        path.write_text(json.dumps(payload))
        start = time.monotonic()
        proc = subprocess.run([str(args.harness.resolve()), 'plugin-render', str(module), str(path.resolve())],
                              capture_output=True, text=True, check=True, timeout=300)
        output = json.loads(proc.stdout)
        (args.output / (name + '.result.json')).write_text(json.dumps(output))
        results.append({'case':name,'seconds':time.monotonic()-start,'strict_render':True})
        print(name,results[-1]['seconds'],flush=True)
        return output

    def close(a,b):
        assert len(a)==len(b)
        assert all(math.isclose(x,y,abs_tol=3e-6,rel_tol=1e-6) for p,q in zip(a,b,strict=True) for x,y in zip(p,q,strict=True))

    hdr=[[4,-2,-0.,.5],[.1,.2,.3,0]]
    for name,params in [('mix-identity',{'mix':100}),('level-identity',{'level':0}),('zero-radii',{'length':0,'width':0})]:
        close(run(name,params,hdr),hdr)
    line=[[.1,.2,.3,1],[.9,.8,.7,1],[.1,.2,.3,1]]
    base={'length':2,'width':0}
    close(run('horizontal-spike',base,line),[[.1,.2,.3,1]]*3)
    level=run('level-half',{**base,'level':50},line)
    close(level,[[.1,.2,.3,1],[.5,.5,.5,1],[.1,.2,.3,1]])
    close(run('mix-half',{**base,'mix':50},line),level)
    binary=[[0,0,0,1],[1,1,1,1],[0,0,0,1]]
    close(run('fractional-radius',{'length':1,'width':0,'fractional':True},binary),[[0,0,0,1],[.5,.5,.5,1],[0,0,0,1]])
    close(run('nonfractional-floor',{'length':1,'width':0},binary),binary)
    alpha=[[0,0,0,0],[.8,.4,.2,.5],[0,0,0,0]]
    assert run('alpha-preserved',base,alpha)[1][3]==.5
    close(run('alpha-filtered',{**base,'preserve_alpha':False},alpha),[[0]*4]*3)
    colors=[[.1,.8,.1,1],[.9,.2,.5,1],[.4,.6,.9,1]]
    close([run('selected-red-only',{**base,'mode':0,'channel':6},colors)[1]],[[.4,.2,.5,1]])
    close([run('whole-pixel-by-red',{**base,'mode':1,'channel':6},colors)[1]],[colors[2]])
    close(run('most-common',{**base,'mode':3},line),[[.1,.2,.3,1]]*3)
    repeated=[[0,0,0,1],[1,1,1,1],[0,0,0,1]]*3
    assert run('horizontal-direction',base,repeated,width=3,height=3)[4][0]==0
    assert run('vertical-angle',{**base,'angle':90},repeated,width=3,height=3)[4][0]==1
    assert run('vertical-width',{'length':0,'width':2},repeated,width=3,height=3)[4][0]==1
    image=[[(i*17+3)%29/29,(i*13+2)%31/31,(i*5+7)%23/23,1] for i in range(35)]
    actual=run('dense-rectangle-reference',{'length':4,'width':2},image,width=7,height=5)
    expected=[]
    for y in range(5):
        for x in range(7):
            values=[image[max(0,min(4,y+dy))*7+max(0,min(6,x+dx))] for dy in (-1,0,1) for dx in (-2,-1,0,1,2)]
            expected.append([sorted(p[ch] for p in values)[7] for ch in range(3)]+[1])
    close(actual,expected)
    assert run('softness-response',{**base,'softness':100},binary)[1][0] > 0
    assert run('preview-scale',{**base},binary,scale=.5) != run('preview-scale-reference',base,binary)
    texture=[[(x*17+y*43)%67/67,(x*33+y*71)%47/47,(x*19+y*23)%37/37,1] for y in range(49) for x in range(65)]
    for channel in range(9):
        output=run('channel-'+str(channel),{**base,'mode':0,'channel':channel},texture,width=65,height=49)
        assert all(math.isfinite(v) for p in output for v in p)
    large=[[(x*17+y*43)%67/67,(x*33+y*71)%47/47,(x*19+y*23)%37/37,1] for y in range(96) for x in range(128)]
    for mode in range(4):
        run('budget-mode-'+str(mode),{'mode':mode,'channel':3,'length':512,'width':512,'angle':138,'fractional':True},large,width=128,height=96,scale=.999)
    rgba=[[(x*17+y*43)%67/67*.75,(x*33+y*71)%47/47*.75,(x*19+y*23)%37/37*.75,
           .75+(x*29+y*17)%19/76] for y in range(180) for x in range(320)]
    for mode in range(4):
        run('budget-rgba-'+str(mode),{'mode':mode,'channel':3,'length':512,'width':512,'angle':138,
                                     'preserve_alpha':False},rgba,width=320,height=180)
    real_controls=[]
    if args.corpus:
        registry=Registry(packages=[mapping])
        for file in sorted(args.corpus.rglob('*.ffx')):
            doc=inspect_file(file)
            if not any(e.identifier.match_name=='BCC3Median' for e in doc.presets[0].effects):
                continue
            plan,_=preview(doc,registry=registry)
            for effect in plan['effects']:
                if effect['source']!='BCC3Median':
                    continue
                params={p['id']:p['value'] for p in effect['properties']}
                output=run('real-controls-'+str(len(real_controls)),params,large,width=128,height=96)
                assert all(math.isfinite(v) for p in output for v in p)
                assert any(p!=q for p,q in zip(large,output,strict=True))
                real_controls.append({'source_sha256':doc.source.sha256,'params':params})
        assert len(real_controls)==3
    if args.hd:
        hd=run('full-hd-actual-window-with-spike',{'length':100,'width':3,'angle':45},fill=[.3,.5,.9,1],width=1920,height=1080,
               replace=[{'index':540*1920+960,'pixel':[1,1,1,1]}],summary=True)
        assert hd['pixels']==1920*1080
        close([hd['center']],[[.3,.5,.9,1]])
    audit={'cases':results,'real_control_sets':real_controls,'module_sha256':hashlib.sha256(module.read_bytes()).hexdigest(),
           'synthetic_pixels_only':True,'adobe_visual_comparison':False,'max_taps_per_pixel':36,
           'full_hd_input_if_present':'uniform except one impulse; not general throughput benchmark'}
    (args.output/'summary.json').write_text(json.dumps(audit,indent=2))


if __name__=='__main__':
    main()
