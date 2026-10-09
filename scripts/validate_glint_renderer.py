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
    mapping, module = extension_paths('glint')
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

    image = [[.4, .1, .2, .5], [4, -2, .3, 1], [.1, 0, 0, 0]]
    close(run('zero-brightness-identity', {'brightness': 0}, image), image)
    # Independent direct convolution of the selected horizontal exponential kernel.
    width = 9
    impulse = [[0, 0, 0, 0] for _ in range(width)]
    impulse[width//2] = [1, 1, 1, 1]
    horizontal = {'brightness_y': 0, 'brightness_diag1': 0, 'brightness_diag2': 0,
                  'source_opacity': 0, 'size': 3, 'size_red': 1, 'size_green': 1, 'size_blue': 1}
    result = run('horizontal-direct-convolution', horizontal, impulse)
    q = math.exp(-1/3)
    expected = []
    for i in range(width):
        value = .3*(1-q)/(1+q)*q**abs(i-width//2)
        expected.append([value, value, value, value])
    close(result, expected)
    hue_input = [[1, 0, 0, 1]]
    isolated = {**horizontal, 'size': 0}
    close(run('hue-third-cycle', {**isolated, 'hue_shift': 1/3}, hue_input), [[0, .3, 0, .3]])
    close(run('threshold-add-red', {**isolated, 'threshold_add_color': [1,0,0,1]}, hue_input), [[0]*4])
    close(run('from-alpha', {**isolated, 'glint_from_alpha': 1}, [[0,0,0,1]]), [[.3]*4])
    close(run('scale-colors', {**isolated, 'scale_colors': [.5,.2,0,1]}, [[1]*4]), [[.15,.06,0,.15]])
    alpha_input = [[.4,.4,.4,.5]]
    normal = run('normal-opacity', {**isolated, 'source_opacity': 1}, alpha_input)
    close(normal, [[.45,.45,.45,.525]])
    close(run('under-source', {**isolated, 'source_opacity': 1, 'glint_under_source': 1}, alpha_input), [[.425,.425,.425,.525]])
    close(run('as-premult', {**isolated, 'source_opacity': 1, 'opacity_mode': 2}, alpha_input), alpha_input)
    close(run('all-opaque', {**isolated, 'source_opacity': 1, 'opacity_mode': 0}, alpha_input), [[.4,.4,.4,1]])
    close(run('affect-alpha-zero', {**isolated, 'source_opacity': 1, 'affect_alpha': 0}, alpha_input), [[.45,.45,.45,.5]])
    close(run('background-brightness', {**isolated, 'source_opacity': 1, 'bg_brightness': .5}, alpha_input), [[.25,.25,.25,.525]])
    # Original impulse supports each axis and channel independently.
    impulse2 = [[0]*4 for _ in range(9*9)]
    impulse2[40] = [1]*4
    baseline = run('four-axes', {'size': 3, 'source_opacity': 0}, impulse2, width=9, height=9)
    for name in ('brightness_x','brightness_y','brightness_diag1','brightness_diag2'):
        assert run(name, {'size': 3, 'source_opacity': 0, name: 0}, impulse2, width=9, height=9) != baseline
    for name in ('size_x','size_y','size_diag1','size_diag2','size_red','size_green','size_blue'):
        assert run(name, {'size': 3, 'source_opacity': 0, name: 0}, impulse2, width=9, height=9) != baseline
    for name in ('threshold_blur','blur_glint'):
        assert run(name, {'size': 3, 'source_opacity': 0, name: 1}, impulse2, width=9, height=9) != baseline
    assert run('preview-scale', {'size':3,'source_opacity':0}, impulse2, width=9,height=9,scale=.5) != baseline
    controls = []
    if args.corpus:
        registry = Registry(packages=[mapping])
        texture = [[x/64, y/48, (x+y)/112, 1] for y in range(49) for x in range(65)]
        for file in sorted(args.corpus.rglob('*.ffx')):
            doc = inspect_file(file)
            plan, _ = preview(doc, registry=registry, source_size=(1920, 1080))
            for effect in plan['effects']:
                if effect['source'] != 'S_Glint':
                    continue
                params = {p['id']: p['value'] for p in effect['properties']}
                output = run('real-controls-' + str(len(controls)), params, texture, width=65, height=49)
                assert all(math.isfinite(v) for p in output for v in p)
                assert any(p != q for p, q in zip(texture, output, strict=True))
                controls.append({'source_sha256': doc.source.sha256, 'params': params})
        assert len(controls) == 2
    if args.hd:
        run('full-hd', {}, fill=[.3, .5, .9, 1], width=1920, height=1080, summary=True)
    audit = {'cases': results, 'real_control_sets': controls, 'module_sha256': hashlib.sha256(module.read_bytes()).hexdigest(),
             'synthetic_pixels_only': True, 'adobe_visual_comparison': False}
    (args.output / 'summary.json').write_text(json.dumps(audit, indent=2))


if __name__ == '__main__':
    main()
