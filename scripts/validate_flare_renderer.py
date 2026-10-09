"""Verify a generated private library using the official, disposable WASM harness.

Scene bytes never enter fixtures/distribution. No desktop Session or source writes.
"""

import argparse
import hashlib
import json
import math
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('library', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--hd', action='store_true')
    parser.add_argument('--timeout', type=float, default=300)
    args = parser.parse_args()
    if args.output.exists() or not args.library.is_dir() or not 0 < args.timeout <= 600:
        parser.error('Existing generated library, new output and timeout (0,600] required')
    summary = json.loads((args.library/'library.json').read_text())
    module = args.library/'bridge_flare_library.wasm'
    assert hashlib.sha256(module.read_bytes()).hexdigest()==summary['module_sha256']
    args.output.mkdir(parents=True)
    results = []
    cases = [(f'scene-{index}', 65, 65, {'scene':index}, [0,0,0,0], None)
             for index in sorted(summary['scene_ids'].values())]
    fill = [0.05,0.1,0.15,0.25]
    for mode, expected in [(0,[0,0,0,1]),(1,[0,0,0,0]),(2,fill)]:
        cases.append((f'zero-alpha-mode-{mode}', 33,33, {'scene':0,'color':[1,1,1,0],'render_mode':mode},fill,expected))
    if args.hd:
        cases.append(('fullhd-scene-0',1920,1080,{'scene':0},[0,0,0,0],None))
    for name,w,h,params,fill,expected in cases:
        params.update({'position':[w//2,h//2],'center':[w//2,h//2]})
        payload = {'width':w,'height':h,'fill':fill,'params':params,'strict_render':True,'summary':True}
        input_path = args.output/(name+'.json')
        input_path.write_text(json.dumps(payload)+'\n')
        started = time.monotonic()
        process = subprocess.run([str(ROOT/'artifacts/native-target/debug/craft-bridge-native-validation'),
                                  'plugin-render',str(module.resolve()),str(input_path.resolve())],
                                 capture_output=True,text=True,timeout=args.timeout,check=True)
        rendered = json.loads(process.stdout)
        assert rendered['pixels']==w*h and math.isfinite(rendered['sum_rgb'])
        if expected is not None:
            assert all(math.isclose(a,b,rel_tol=1e-6,abs_tol=1e-7) for a,b in zip(rendered['center'],expected,strict=True))
            assert math.isclose(rendered['sum_rgb'],sum(expected[:3])*w*h,rel_tol=1e-6,abs_tol=1e-7)
        result = {'case':name,'result':rendered,'seconds':time.monotonic()-started}
        results.append(result)
        print(json.dumps(result),flush=True)
    result = {'cases':results,'module_sha256':summary['module_sha256'],
              'native_errors_exposed':True,'adobe_visual_comparison':False}
    (args.output/'summary.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':
    main()
