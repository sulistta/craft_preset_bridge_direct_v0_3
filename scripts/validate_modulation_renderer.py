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
    mapping, module = extension_paths('modulation')
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

    neutral = {'distortion': 0, 'lowpass_1': False, 'lowpass_2': False, 'lowpass_3': False, 'ignore_alpha': True}
    image = [[0.4, 0.1, 0.2, 0.5], [0.1, 0.8, 0.3, 1], [0, 0, 0, 0], [0.8, 0.2, 0.7, 1]]
    expected = []
    for r, g, b, a in image:
        v = 0.2126*r + 0.7152*g + 0.0722*b
        expected.append([v, v, v, a])
    close(run('neutral-demodulation', neutral, image), expected)
    close(run('opacity-zero', {'opacity': 0}, image), image)
    close(run('half-opacity', {**neutral, 'opacity': 127.5}, image), [[(p[i] + q[i])/2 for i in range(4)] for p, q in zip(image, expected, strict=True)])
    inverse = run('invert', {**neutral, 'invert': True}, image)
    close(inverse, [[p[3] - v for v in q[:3]] + [p[3]] for p, q in zip(image, expected, strict=True)])
    textured = [[i%7/6, i%3/2, i%5/4, 1] for i in range(32)]
    forward = run('forward', {}, textured)
    close(run('backward', {'direction': 1}, textured[::-1])[::-1], forward)
    close(run('horizontal-waves', {'orientation': 1}, textured, width=1, height=32), forward)
    white = run('white-line', {**neutral, 'hide_white_line': False}, image)
    close(white[:1], [[0.5, 0.5, 0.5, 0.5]])
    baseline = run('controls-baseline', neutral, textured)
    for name in ['lowpass_1', 'lowpass_2', 'lowpass_3']:
        assert run(name, {**neutral, name: True}, textured) != baseline
    distorted = run('distortion', {**neutral, 'distortion': 36}, textured)
    assert distorted != baseline
    assert run('omega', {**neutral, 'distortion': 36, 'omega': 1.4}, textured) != distorted
    assert run('phase', {**neutral, 'distortion': 36, 'phase': .6}, textured) != distorted
    alpha_image = [[.2, .2, .2, 1], [0, 0, 0, 0], [.7, .7, .7, 1], [.3, .3, .3, .5]]
    respect = run('respect-alpha', {'ignore_alpha': False}, alpha_image)
    ignore = run('ignore-alpha', {'ignore_alpha': True}, alpha_image)
    assert respect != ignore
    close(respect[1:2], [[0]*4])
    assert run('preview-scale', {'distortion': 36}, textured, scale=.5) != run('reference-scale', {'distortion': 36}, textured)
    controls = []
    if args.corpus:
        registry = Registry(packages=[mapping])
        texture = [[x/64, y/48, (x+y)/112, 1] for y in range(49) for x in range(65)]
        for file in sorted(args.corpus.rglob('*.ffx')):
            doc = inspect_file(file)
            plan, _ = preview(doc, registry=registry, source_size=(1920, 1080))
            for effect in plan['effects']:
                if effect['source'] != 'ADBE Checkout':
                    continue
                params = {p['id']: p['value'] for p in effect['properties']}
                output = run('real-controls-' + str(len(controls)), params, texture, width=65, height=49)
                assert all(math.isfinite(v) for p in output for v in p)
                assert any(p != q for p, q in zip(texture, output, strict=True))
                controls.append({'source_sha256': doc.source.sha256, 'params': params})
    if args.hd:
        run('full-hd', {}, fill=[.3, .5, .7, 1], width=1920, height=1080, summary=True)
    audit = {'cases': results, 'real_control_sets': controls, 'module_sha256': hashlib.sha256(module.read_bytes()).hexdigest(),
             'synthetic_pixels_only': True, 'adobe_visual_comparison': False}
    (args.output / 'summary.json').write_text(json.dumps(audit, indent=2))


if __name__ == '__main__':
    main()
