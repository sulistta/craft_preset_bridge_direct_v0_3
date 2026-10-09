"""Audit original stretch pixels through the official WASM loader, with errors exposed.

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
    mapping,module=extension_paths('stretch')
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
    original=list(map(gray,[0,1,0.5,0]))
    check(run('cumulative-brightness',{'stretch':1},original),list(map(gray,[0,1,1,0.5])))
    check(run('down-direction',{'stretch':1,'direction':2},original,width=1,height=4),list(map(gray,[0,1,1,0.5])))
    # Reversed segment widths: 1,1.5,2,1; the crossing footprint averages 0.5/1.
    check(run('left-direction',{'stretch':1,'direction':1},original),list(map(gray,[1,0.75,0.5,0])))
    check(run('up-direction',{'stretch':1,'direction':3},original,width=1,height=4),list(map(gray,[1,0.75,0.5,0])))
    check(run('subpixel-wrap',{'pixel_size':0.5},original),list(map(gray,[0.5,0.25,0.5,0.25])))
    check(run('subpixel-mirror',{'pixel_size':0.5,'edge':1},original),list(map(gray,[0.5,0.25,0.25,0.5])))
    check(run('subpixel-clamp',{'pixel_size':0.5,'edge':2},original),list(map(gray,[0.5,0.25,0,0])))
    check(run('subpixel-transparent',{'pixel_size':0.5,'edge':3},original),[gray(0.5),gray(0.25),[0]*4,[0]*4])
    hdr=[[2,1,0.5,0.5],[0]*4,gray(0.25)]
    check(run('hdr-neutral-preview',{},hdr,scale=0.5),hdr)
    check(run('zero-intensity',{'intensity':0,'stretch':100,'shift_phase':200,'shade_opacity':80},hdr),hdr)
    check(run('alpha-shading',{'shading':3,'shade_size':4,'shade_opacity':100},[gray(1)]*4),[[1-i/4]*4 for i in range(4)])
    check(run('rgb-shading',{'shading':3,'shade_size':4,'shade_opacity':100,'shade_channels':1},[gray(1)]*4),[[1-i/4]*3+[1] for i in range(4)])
    controls=[]
    if args.corpus:
        registry=Registry(packages=[mapping])
        texture=[[x/64,y/48,(x+y)/112,1] for y in range(49) for x in range(65)]
        for file in sorted(args.corpus.rglob('*.ffx')):
            document=inspect_file(file)
            plan,_=preview(document,registry=registry,source_size=(1920,1080))
            for effect in plan['effects']:
                if effect['source']!='pixel_stretch':
                    continue
                assert all(not p['keyframes'] for p in effect['properties'])
                params={p['id']:p['value'] for p in effect['properties']}
                output=run('real-controls-'+str(len(controls)),params,texture,width=65,height=49)
                assert output!=texture
                controls.append({'source_sha256':document.source.sha256,'properties':len(params),
                                 'pixels_are_original_synthetic':True})
    if args.hd:
        output=run('fullhd-rgba-subpixel',{'channels':1,'pixel_size':0.01,'stretch':0.7,'curve':3,'smoothness':60,'shading':1,'shade_opacity':50},
                   width=1920,height=1080,fill=[0.5,0.25,0.125,1],summary=True)
        assert output['pixels']==1920*1080 and output['sum_rgb']>0
    summary={'cases':results,'real_control_sets':controls,'module_sha256':hashlib.sha256(module.read_bytes()).hexdigest(),
             'no_adobe_comparison':True,'original_synthetic_pixels':True}
    (args.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')


if __name__=='__main__':
    main()
