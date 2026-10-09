"""Original synthetic pixels through the official WASM loader, never Adobe pixels."""

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
    mapping, module = extension_paths('pixelsort')
    results = []

    def run(name, params, pixels=None, **extra):
        payload = {'params': params, 'strict_render': True, **extra}
        if pixels is not None:
            payload['pixels'] = pixels
        path = args.output / (name + '.json')
        path.write_text(json.dumps(payload))
        started = time.monotonic()
        process = subprocess.run([str(args.harness.resolve()), 'plugin-render', str(module), str(path.resolve())],
                                 capture_output=True, text=True, timeout=300, check=True)
        output = json.loads(process.stdout)
        (args.output / (name + '.result.json')).write_text(json.dumps(output))
        results.append({'case': name, 'seconds': time.monotonic() - started, 'strict_render': True})
        print(name, results[-1]['seconds'], flush=True)
        return output

    def close(a, b):
        assert len(a) == len(b)
        assert all(math.isclose(x, y, abs_tol=3e-6) for p, q in zip(a, b, strict=True) for x, y in zip(p, q, strict=True))

    image = [[.8,.1,0,1],[.2,.3,0,1],[.2,.5,0,1],[.6,.4,0,1]]
    neutral = {'sort_type':4,'threshold':-1,'restart':0,'soften':0}
    ordered = [image[1],image[2],image[3],image[0]]
    close(run('horizontal-stable-pixel-sort',neutral,image),ordered)
    close(run('reverse-stable-ties',{**neutral,'reverse':True},image),[image[0],image[3],image[1],image[2]])
    close(run('vertical',{**neutral,'sort_angle':90},image,width=1,height=4),ordered)
    close(run('mix-one-hdr-identity',{'mix':1},[[2,-1,.2,.5],[.1,.2,.3,1]]),[[2,-1,.2,.5],[.1,.2,.3,1]])
    close(run('half-mix',{**neutral,'mix':.5},image),[[(a+b)/2 for a,b in zip(p,q,strict=True)] for p,q in zip(image,ordered,strict=True)])
    close(run('maximum-restarts-identity',{**neutral,'restart':1000},image),image)
    intervals = [[.9,.9,.9,1],[.6,.6,.6,1],[.1,.1,.1,1],[.8,.8,.8,1],[.7,.7,.7,1]]
    close(run('threshold-regions',{**neutral,'sort_type':0,'threshold':.5},intervals),[intervals[1],intervals[0],intervals[2],intervals[4],intervals[3]])
    close(run('sort-below',{**neutral,'threshold':.5,'sort_direction':0},image),[image[0],image[1],image[2],image[3]])
    metric_input = [[.8,.4,.2,1]]
    metrics = [.4706,1.4/3,.2,.8,.8,.4,.2,1/18,.75,.8]
    for kind,value in enumerate(metrics):
        close(run('metric-'+str(kind),{'show':1,'sort_type':kind},metric_input),[[value,value,value,1]])
    close(run('normal-alpha-metric',{'show':1,'sort_type':4},[[.4,.1,.2,.5]]),[[.4,.4,.4,.5]])
    close(run('premult-alpha-metric',{'show':1,'sort_type':4,'opacity_mode':2},[[.4,.1,.2,.5]]),[[.2,.2,.2,.5]])
    close(run('all-opaque-alpha',{'show':1,'sort_type':4,'opacity_mode':0},[[.4,.1,.2,.5]]),[[.4,.4,.4,1]])
    close(run('threshold-mask',{'show':2,'sort_type':4,'threshold':.5},image),[[1,1,1,1],[0,0,0,1],[0,0,0,1],[1,1,1,1]])
    close(run('restart-mask-all',{'show':3,'restart':1000},image),[[1]*4 for _ in image])
    texture = [[((i*31)%79)/79,((i*19)%73)/73,((i*43)%71)/71,1] for i in range(81)]
    modes = {}
    for mode in range(3):
        params = {**neutral,'mode':mode,'radial_center':[4,4],'circular_center':[4,4],
                  'radial_inner':0,'ray_length':100,'vary_radius':0,'circular_inner':0,'thickness':100,
                  'circular_degrees':360,'vary_start':0,'sort_angle':37}
        output = run('pattern-'+str(mode),params,texture,width=9,height=9)
        assert output != texture
        close(sorted(output),sorted(texture))  # whole-pixel permutation in every mode, no resampling
        modes[mode] = (params,output)
    baseline = modes[0][1]
    assert run('fractional-seed-a',{**modes[0][0],'restart':300,'seed':.273},texture,width=9,height=9) != baseline
    a=run('fractional-seed-repeat',{**modes[0][0],'restart':300,'seed':.273},texture,width=9,height=9)
    b=run('fractional-seed-b',{**modes[0][0],'restart':300,'seed':.274},texture,width=9,height=9)
    assert a!=b
    close(a,run('fractional-seed-same',{**modes[0][0],'restart':300,'seed':.273},texture,width=9,height=9))
    for mode,name,value in [(1,'radial_start',90),(1,'radial_degrees',90),(1,'radial_inner',2),(1,'ray_length',3),
                            (1,'vary_radius',.7),(1,'radial_center',[3,5]),(2,'circular_start',90),
                            (2,'circular_degrees',90),(2,'circular_inner',2),(2,'thickness',3),
                            (2,'vary_start',.7),(2,'circular_center',[3,5])]:
        assert run(name,{**modes[mode][0],name:value},texture,width=9,height=9) != modes[mode][1]
    assert run('softened-mask',{'show':2,'sort_type':4,'threshold':.5,'soften':1},image) != [[1,1,1,1],[0,0,0,1],[0,0,0,1],[1,1,1,1]]
    close(run('combined-geometry-mask',{'mode':1,'radial_center':[0,0],'radial_degrees':0,'show':4},image),[[0,0,0,1] for _ in image])
    for mode in (1,2):
        close(run('full-scope-wrap-'+str(mode),{**neutral,'mode':mode,'show':4,
              'radial_center':[0,0],'circular_center':[0,0],'radial_start':1e-16,'circular_start':1e-16,
              'radial_inner':0,'ray_length':100,'vary_radius':0,'circular_inner':0,'thickness':100,
              'circular_degrees':360,'vary_start':0},image),[[1]*4 for _ in image])
    controls = []
    if args.corpus:
        registry = Registry(packages=[mapping])
        texture = [[((x*17+y*31)%113)/112,((x*37+y*19)%109)/108,((x*43+y*13)%107)/106,1] for y in range(49) for x in range(65)]
        for file in sorted(args.corpus.rglob('*.ffx')):
            doc=inspect_file(file)
            plan,_=preview(doc,registry=registry,source_size=(1920,1080))
            for effect in plan['effects']:
                if effect['source']!='S_PixelSort':
                    continue
                params={p['id']:p['value'] for p in effect['properties']}
                output=run('real-controls-'+str(len(controls)),params,texture,width=65,height=49)
                assert all(math.isfinite(v) for p in output for v in p)
                assert any(p!=q for p,q in zip(texture,output,strict=True))
                controls.append({'source_sha256':doc.source.sha256,'params':params})
        assert len(controls)==1
    if args.hd:
        run('full-hd-angle-37',{'sort_angle':37},fill=[.3,.5,.9,1],width=1920,height=1080,summary=True)
    audit={'cases':results,'real_control_sets':controls,'module_sha256':hashlib.sha256(module.read_bytes()).hexdigest(),
           'synthetic_pixels_only':True,'adobe_visual_comparison':False}
    (args.output/'summary.json').write_text(json.dumps(audit,indent=2))


if __name__=='__main__':
    main()
