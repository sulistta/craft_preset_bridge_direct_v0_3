"""Audit original diffusion pixels through the official WASM loader, with errors exposed.

Synthetic pixels are independent of Adobe. --corpus opts into local private controls.
"""

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path

from craft_bridge.core.pipeline import inspect_file, preview
from craft_bridge.extensions import extension_paths
from craft_bridge.mappings.registry import Registry


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    parser.add_argument('--corpus',type=Path)
    parser.add_argument('--hd',action='store_true')
    parser.add_argument('--harness',type=Path,default=Path('artifacts/native-target/debug/craft-bridge-native-validation'))
    parser.add_argument('--timeout',type=float,default=300)
    args=parser.parse_args()
    if args.output.exists() or not 0<args.timeout<=600 or args.corpus is not None and not args.corpus.is_dir():
        parser.error('New output, timeout (0,600], and existing optional corpus required')
    args.output.mkdir(parents=True)
    mapping,module=extension_paths('diffusion')
    results=[]
    def run(name,params,pixels=None,**extra):
        payload={'params':params,'strict_render':True,**extra}
        if pixels is not None:
            payload['pixels']=pixels
        path=args.output/(name+'.json')
        path.write_text(json.dumps(payload)+'\n')
        started=time.monotonic()
        process=subprocess.run([str(args.harness.resolve()),'plugin-render',str(module),str(path.resolve())],
                               capture_output=True,text=True,timeout=args.timeout,check=True)
        output=json.loads(process.stdout)
        (args.output/(name+'.result.json')).write_text(json.dumps(output)+'\n')
        results.append({'case':name,'seconds':time.monotonic()-started,'strict_render':True})
        print(name,results[-1]['seconds'],flush=True)
        return output
    def check(a,b):
        assert len(a)==len(b)
        assert all(abs(x-y)<3e-6 for p,q in zip(a,b,strict=True) for x,y in zip(p,q,strict=True))
    def gray(v):
        return [v,v,v,1]
    original=[gray(0.25)]*4
    expected=list(map(gray,[0,1,0,0]))
    check(run('along-error',{},original),expected)
    check(run('zero-error',{'error_across':0},original),[gray(0)]*4)
    check(run('left-direction',{'direction':1},original),expected[::-1])
    check(run('down-direction',{'direction':2},original,width=1,height=4),expected)
    check(run('up-direction',{'direction':3},original,width=1,height=4),expected[::-1])
    check(run('aside-error',{'error_across':0,'error_aside':1},[gray(0.25)]*2,width=1,height=2),list(map(gray,[0,1])))
    check(run('phase-error',{'error_across':0,'initial_phase':[0.5,0.5,0.5,1]},[gray(0.25)]),[gray(1)])
    check(run('fat-stripe',{'width_2':2},[gray(0.6)]*4),list(map(gray,[1,1,0,0])))
    check(run('preview-width',{'width_2':4},[gray(0.6)]*4,scale=0.5),list(map(gray,[1,1,0,0])))
    alpha=128/255*0.5
    check(run('palette-alpha',{'color_count':0,'color_1':[1,0,0,0.5]},[[0.25,0,0,0.5],[0]*4]),[[alpha,0,0,alpha],[0]*4])
    check(run('hdr-quantization',{'error_across':0},[[2,1,0.5,1]]),[gray(1)])
    for i in range(6):
        params={'color_count':i,'error_across':0}
        for j in range(i+1):
            params['color_'+str(j+1)]=[1,1,1,1] if j<i else [1,0,0,1]
        check(run('palette-slot-'+str(i),params,[[1,0,0,1]]),[[1,0,0,1]])
    controls=[]
    if args.corpus:
        registry=Registry(packages=[mapping])
        texture=[[x/64,y/48,(x+y)/112,1] for y in range(49) for x in range(65)]
        for file in sorted(args.corpus.rglob('*.ffx')):
            document=inspect_file(file)
            plan,_=preview(document,registry=registry,source_size=(1920,1080))
            for effect in plan['effects']:
                if effect['source']!='omino_diffusion':
                    continue
                assert all(not p['keyframes'] for p in effect['properties'])
                params={p['id']:p['value'] for p in effect['properties']}
                output=run('real-controls-'+str(len(controls)),params,texture,width=65,height=49)
                assert output!=texture
                controls.append({'source_sha256':document.source.sha256,'properties':len(params),
                                 'pixels_are_original_synthetic':True})
    if args.hd:
        output=run('fullhd-diffusion',{'error_across':1,'error_aside':0.2,'color_count':5},
                   width=1920,height=1080,fill=[0.5,0.25,0.125,1],summary=True)
        assert output['pixels']==1920*1080 and output['sum_rgb']>0
    summary={'cases':results,'real_control_sets':controls,'module_sha256':hashlib.sha256(module.read_bytes()).hexdigest(),
             'no_adobe_comparison':True,'original_synthetic_pixels':True}
    (args.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')


if __name__=='__main__':
    main()
