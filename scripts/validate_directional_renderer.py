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
    mapping, module = extension_paths('directional')
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
    for name,params in [('mix-identity',{'mix':100}),('zero-length',{'amount':0})]:
        close(run(name,params,hdr),hdr)
    ramp=[[i/8,.2,.1,1] for i in range(9)]
    expected=[[sum(max(0,min(8,i+d))/8 for d in range(-2,3))/5,.2,.1,1] for i in range(9)]
    close(run('horizontal-independent-box',{'amount':4},ramp),expected)
    image=[[x/8,y/6,(x+y)/14,1] for y in range(7) for x in range(9)]
    expected=[[x/8,sum(max(0,min(6,y+d))/6 for d in range(-2,3))/5,
               sum((x+max(0,min(6,y+d)))/14 for d in range(-2,3))/5,1] for y in range(7) for x in range(9)]
    close(run('vertical-independent-box',{'amount':4,'angle':90},image,width=9,height=7),expected)
    line=[[0,0,0,1],[1,1,1,1],[0,0,0,1]]
    base={'amount':2}
    baseline=run('spike-removal',base,line)
    close(baseline,[[1/3]*3+[1]]*3)
    close(run('fractional-length',{'amount':1},line),[[1/6]*3+[1],[2/3]*3+[1],[1/6]*3+[1]])
    half=run('mix-half',{**base,'mix':50},line)
    close(half,[[1/6]*3+[1],[2/3]*3+[1],[1/6]*3+[1]])
    close(run('apply-mix-zero',{**base,'apply_mode':12,'apply_mix':0},line),baseline)
    close(run('apply-add',{**base,'apply_mode':12},line),[[1/3]*3+[1],[4/3]*3+[1],[1/3]*3+[1]])
    close(run('apply-add-zero-blur',{'amount':0,'apply_mode':12},[[.2,.3,.4,1]]),[[.4,.6,.8,1]])
    close([run('threshold-half',{**base,'threshold':127.5},line)[1]],[[5/6]*3+[1]])
    close([run('deviation-limit',{**base,'deviation':25.5},line)[1]],[[.9]*3+[1]])
    solid=[[.2,.3,.4,1]]*5
    close(run('replicated-edge',{'amount':4},solid),solid)
    close([run('transparent-edge',{'amount':4,'avoid_clipping':True},solid)[0]],[[.12,.18,.24,.6]])
    impulse=[[0,0,0,1] for _ in range(17)]
    impulse[8]=[1]*4
    assert run('thin',{'amount':4,'thin':100},impulse)[8][0] > .3
    close([run('spread',{'amount':4,'thin':100,'spread':100},impulse)[6]],[[.5,.5,.5,1]])
    assert run('displace-right',{'amount':4,'displace':True},impulse)[12][0] > .19
    assert run('preview-scale',{'amount':4},impulse,scale=.5)[8][0] > .3
    rgba=[[.1,.2,.3,.5],[.8,.7,.6,1],[.1,.2,.3,.5]]
    masks=[(True,True,True,True),(True,True,True,False),(False,False,False,True),
           (True,False,False,False),(False,True,False,False),(False,False,True,False),
           (True,True,False,False),(True,False,True,False),(False,True,True,False)]
    for channel,mask in enumerate(masks):
        output=run('channels-'+str(channel),{**base,'channels':channel},rgba)
        for i,(original,filtered) in enumerate(zip(rgba,output,strict=True)):
            for c,enabled in enumerate(mask):
                if not enabled:
                    assert math.isclose(filtered[c],original[c],abs_tol=3e-6), (i,c)
    colored=[[.1,.2,.3,.5],[4,-2,.1,1],[.1,.4,.2,.5]]
    for mode in range(27):
        output=run('apply-mode-'+str(mode),{'amount':4,'apply_mode':mode,'avoid_clipping':True},colored)
        assert all(math.isfinite(v) for p in output for v in p)
    texture=[[(x*17+y*43)%67/67*.5,(x*33+y*71)%47/47*.5,(x*19+y*23)%37/37*.5,
              .5+(x*29+y*17)%19/38] for y in range(180) for x in range(320)]
    for mode in range(27):
        output=run('budget-mode-'+str(mode),{'amount':96.7,'angle':137.3,'apply_mode':mode},
                   texture,width=320,height=180)
        assert all(math.isfinite(v) for p in output for v in p)
    run('maximum-length-transparent-displace',{'amount':8192,'angle':137.3,'displace':True,
                                               'avoid_clipping':True,'thin':100,'spread':100},
        texture,width=320,height=180)
    controls=[]
    if args.corpus:
        registry=Registry(packages=[mapping])
        for file in sorted(args.corpus.rglob('*.ffx')):
            doc=inspect_file(file)
            if not any(e.identifier.match_name=='BCC3Directional Blur' for e in doc.presets[0].effects):
                continue
            plan,_=preview(doc,registry=registry)
            for effect in plan['effects']:
                if effect['source']!='BCC3Directional Blur':
                    continue
                params={p['id']:p['value'] for p in effect['properties']}
                output=run('real-controls-'+str(len(controls)),params,texture,width=320,height=180)
                assert all(math.isfinite(v) for p in output for v in p)
                assert any(p!=q for p,q in zip(texture,output,strict=True))
                controls.append({'source_sha256':doc.source.sha256,'params':params})
        assert len(controls)==3
    if args.hd:
        output=run('full-hd-nonuniform-checker',{'amount':96.7,'angle':137.3},fill=[0,0,0,0],
                   width=1920,height=1080,checker={'cell':13,'first':[.3,.5,.7,1],'second':[.4,.1,.2,.5]},summary=True)
        assert output['pixels']==1920*1080
        assert any(not math.isclose(v,o,abs_tol=3e-6) for v,o in zip(output['center'],[.3,.5,.7,1],strict=True))
    audit={'cases':results,'real_control_sets':controls,'module_sha256':hashlib.sha256(module.read_bytes()).hexdigest(),
           'synthetic_pixels_only':True,'adobe_visual_comparison':False,'max_taps_per_pixel':31,
           'full_hd_input_if_present':'nonuniform original checker; 31 taps, angle 137.3 degrees, amount 96.7'}
    (args.output/'summary.json').write_text(json.dumps(audit,indent=2))


if __name__=='__main__':
    main()
