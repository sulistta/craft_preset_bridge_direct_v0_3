"""Original synthetic pixels through official WASM loader; no source plugin renders."""

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
    mapping, module = extension_paths('flicker')
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
        assert all(math.isclose(x, y, abs_tol=3e-6, rel_tol=1e-6) for p, q in zip(a, b, strict=True) for x, y in zip(p, q, strict=True))

    image = [[.2,.4,.1,.5], [4,-2,.3,1], [.1,-.3,.7,0]]
    close(run('zero-amplitude-hdr-identity', {'amplitude': 0}, image), image)
    close(run('brightness-two', {'amplitude': 0, 'brightness': 2}, image),
          [[2*p[0],2*p[1],2*p[2],p[3]] for p in image])
    close(run('brightness-zero', {'brightness': 0}, image), [[0,0,0,p[3]] for p in image])
    wave = {'amplitude': .5,'rand_luma_amp':0,'wave_amp':1,'wave_freq':1,
            'wave_g_phase':.25,'wave_b_phase':.5}
    for t in (0, .25, .5, .75, -.25, 1.25):
        factors = [max(0, 1+.5*math.sin(2*math.pi*(t+phase))) for phase in (0,.25,.5)]
        expected = [[p[ch]*factors[ch] for ch in range(3)]+[p[3]] for p in image]
        close(run('wave-' + str(t), wave, image, time=t), expected)
    # Channel amplitudes affect just their corresponding waveform.
    for ch, name in enumerate(('red_amp','green_amp','blue_amp')):
        factors = [max(0, 1+.5*math.sin(2*math.pi*(.25+phase))) for phase in (0,.25,.5)]
        factors[ch] = 1
        close(run(name, {**wave,name:0}, image, time=.25),
              [[p[c]*factors[c] for c in range(3)]+[p[3]] for p in image])
    close(run('negative-gain-floor', {'amplitude':2,'rand_luma_amp':0,'wave_amp':1,'wave_freq':1}, image, time=.75),
          [[0,0,0,p[3]] for p in image])
    baseline = run('shared-luma', {}, image, time=.123)
    factors = [baseline[0][ch]/image[0][ch] for ch in range(3)]
    assert max(factors)-min(factors) < 1e-6
    assert all(p[3] == q[3] for p,q in zip(image,baseline,strict=True))
    run('negative-time', {}, image, time=-.123)
    assert run('time-repeat-after-negative', {}, image, time=.123) == baseline
    assert run('fractional-seed', {'seed':.123001}, image,time=.123) != baseline
    assert run('frequency-change', {'rand_freq':15},image,time=.123) != baseline
    color = run('independent-color', {'rand_luma_amp':0,'rand_color_amp':1},image,time=.123)
    assert abs(color[0][0]/.2-color[0][1]/.4) > 1e-4
    assert run('color-and-luma', {'rand_color_amp':1},image,time=.123) != color
    static = run('zero-frequencies-first', {'rand_freq':0,'wave_freq':0},image,time=-100)
    assert run('zero-frequencies-second', {'rand_freq':0,'wave_freq':0},image,time=200) == static
    assert run('preview-scale-invariant', {},image,time=.123,scale=.5) == baseline
    left = run('lattice-left', {},image,time=1/30-1e-8)
    close(left, run('lattice-right', {},image,time=1/30+1e-8))
    extremes = {p['id']: p['max'] for p in json.loads(mapping.read_text())['plugins'][0]['params']}
    assert all(math.isfinite(v) for p in run('domain-upper-extremes',extremes,[[1e6,-1e6,1e6,1]],time=1e9) for v in p)
    real_controls = []
    if args.corpus:
        registry = Registry(packages=[mapping])
        texture = [[x/64,y/48,(x+y)/112,1] for y in range(49) for x in range(65)]
        for file in sorted(args.corpus.rglob('*.ffx')):
            doc = inspect_file(file)
            if not any(e.identifier.match_name == 'S_Flicker' for e in doc.presets[0].effects):
                continue
            plan, _ = preview(doc, registry=registry)
            for effect in plan['effects']:
                if effect['source'] != 'S_Flicker':
                    continue
                params = {p['id']:p['value'] for p in effect['properties']}
                first = run('real-controls-' + str(len(real_controls)),params,texture,width=65,height=49,time=.123)
                later = run('real-controls-later-' + str(len(real_controls)),params,texture,width=65,height=49,time=.223)
                assert all(math.isfinite(v) for p in first for v in p)
                assert first != later
                real_controls.append({'source_sha256':doc.source.sha256,'application':effect['application'],
                                      'params':params,'selected_unmapped_values_are_renderer_defaults':effect['application']=='existing'})
        assert len(real_controls) == 2
    if args.hd:
        hd = run('full-hd',{},fill=[.3,.5,.9,1],width=1920,height=1080,summary=True,time=.123)
        assert hd['pixels'] == 1920*1080
    audit = {'cases':results,'real_control_sets':real_controls,'module_sha256':hashlib.sha256(module.read_bytes()).hexdigest(),
             'synthetic_pixels_only':True,'adobe_visual_comparison':False}
    (args.output/'summary.json').write_text(json.dumps(audit,indent=2))


if __name__ == '__main__':
    main()
