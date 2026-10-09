"""Original pattern images through native Session; real FFX controls opt-in."""

import argparse
import hashlib
import json
import math
import os
import runpy
import select
import subprocess
from pathlib import Path

from craft_bridge.core.pipeline import inspect_file, preview
from craft_bridge.core.validation import validate_plan
from craft_bridge.exporters.effectcraft.exporter import preview_commands
from craft_bridge.extensions import extension_paths
from craft_bridge.integrations.control import ControlClient
from craft_bridge.integrations.effectcraft import apply_plan
from craft_bridge.mappings.registry import Registry

ROOT = Path(__file__).resolve().parents[1]


def document(package):
    original = json.loads(json.dumps(package))
    for spec in original['plugins'][0]['params']:
        if spec['type'] == 'color':
            spec['type'] = 'point'
    doc = runpy.run_path(str(ROOT / 'scripts/validate_signal_renderer.py'))['document'](original)
    effect = doc.presets[0].effects[0]
    effect.identifier.match_name = 'ADBE PixelEncoder - AEPlugins'
    rules = package['mappings'][0]['params']
    for p in effect.parameters:
        if rules[p.id]['kind'] == 'Color':
            c = p.value.data
            p.value.kind = 'color'
            p.value.unit = 'AE-ARGB-255'
            p.value.data = [c[3] * 255, *(v * 255 for v in c[:3])]
    return doc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--real-presets', type=Path)
    parser.add_argument('--harness', type=Path, default=ROOT / 'artifacts/native-target/debug/craft-bridge-multi-input-probe')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Use a new output directory')
    out = args.output.resolve()
    out.mkdir(parents=True)
    os.environ['CRAFT_BRIDGE_CONFIG'] = str(out / 'config')
    mapping, module = extension_paths('pixelencoder')
    package = json.loads(mapping.read_text())
    registry = Registry()
    registry.install(mapping)
    audit = []
    with (out / 'host.log').open('w') as log:
        process = subprocess.Popen([str(args.harness.resolve()), '--serve'], stdout=subprocess.PIPE, stderr=log, text=True)
        try:
            assert process.stdout is not None and select.select([process.stdout], [], [], 20)[0]
            ready = process.stdout.readline().strip()
            assert ready.startswith('Bridge experimental host ready: '), ready
            port = int(ready.rsplit(' ', 1)[1])
            with ControlClient(port) as client:
                assert client.execute('effect.plugins.load', {'path': str(module)})['loaded'][0]['api'] == 2
                client.execute('file.projectSettings', {'bitDepth': 32})
                client.execute('comp.new', {'width': 64, 'height': 64, 'frameRate': 30, 'duration': 2, 'name': 'Original tile proof'})
                cid = client.execute('comp.info')['id']
                target = client.execute('layer.newSolid', {'color': '#808080', 'name': 'Original source'})['layer']

            def plan_for(changes):
                doc = document(package)
                for p in doc.presets[0].effects[0].parameters:
                    rule = package['mappings'][0]['params'][p.id]
                    if rule['target'] in changes:
                        v = changes[rule['target']]
                        p.value.data = v + 1 if rule['operation'] == 'minus_one' else [v[3] * 255, *(c * 255 for c in v[:3])] if rule['kind'] == 'Color' else v
                raw, report = preview(doc, registry=registry)
                assert report.status == 'PARTIAL' and report.effects[0].parameters_converted == 16
                return validate_plan(raw, registry)

            def image(client, time=0., scale=1.):
                frame = client.execute('bridge.probe.render', {'comp': cid, 'time': time, 'scale': scale})
                assert frame['width'] == frame['height'] == int(64 * scale)
                assert all(math.isfinite(v) for px in frame['pixels'] for v in px)
                return frame['pixels']

            def apply(plan):
                with ControlClient(port) as client:
                    client.execute('effect.removeAll', {'comp': cid, 'layer': target})
                return apply_plan(plan, layer=target, comp=cid, port=port, confirmed=True)

            neutral = {'brightness': 0., 'contrast': 100., 'size': 16., 'detail_x': 100., 'detail_y': 100., 'lock': False, 'chaos': False, 'foreground': [1., 0., 0., 1.], 'background': [0., 0., 1., 1.]}
            full = []
            for pattern in range(10):
                apply(plan_for(neutral | {'pattern': pattern}))
                with ControlClient(port) as client:
                    for scale in [1., 0.5]:
                        pixels = image(client, scale=scale)
                        assert [1., 0., 0., 1.] in pixels and [0., 0., 1., 1.] in pixels, pattern
                        if scale == 1.:
                            full.append(pixels)
                audit.append({'case': 'original-pattern', 'pattern': pattern, 'full_half': True})
            assert len({json.dumps(p) for p in full}) == 10
            apply(plan_for(neutral | {'pattern': 7, 'transparent': True, 'original_color': True}))
            with ControlClient(port) as client:
                pixels = image(client)
                assert [0., 0., 0., 0.] in pixels
                assert any(math.isclose(p[0], 128 / 255, abs_tol=1e-6) and p[3] == 1. for p in pixels)
            audit.append({'case': 'original-color-transparent'})
            plan = plan_for(neutral | {'pattern': 7, 'chaos': True, 'intensity': 90., 'speed': 3., 'seed': 1.25})
            apply(plan)
            with ControlClient(port) as client:
                first = image(client, time=0.)
                assert first != image(client, time=1.)
                assert first == image(client, time=0.)
                client.execute('file.saveAs', {'path': str(out / 'original.ecproj')})
                client.execute('file.open', {'path': str(out / 'original.ecproj')})
                assert first == image(client, time=0.)
            audit.append({'case': 'original-chaos-time-out-of-order-reopened'})
            if args.real_presets:
                count = 0
                for file in sorted(args.real_presets.rglob('*.ffx')):
                    before = hashlib.sha256(file.read_bytes()).hexdigest()
                    doc = inspect_file(file)
                    if not any(e.identifier.match_name == 'ADBE PixelEncoder - AEPlugins' for e in doc.presets[0].effects):
                        continue
                    raw, _ = preview(doc, registry=registry)
                    real = validate_plan(raw, registry)
                    real.effects = [e for e in real.effects if e.source == 'ADBE PixelEncoder - AEPlugins']
                    real.commands = preview_commands(real)
                    assert len(real.effects) == 1 and len(real.effects[0].properties) == 16
                    result = apply(real)
                    path = result['bindings'][real.effects[0].ref]['path']
                    with ControlClient(port) as client:
                        for reopened in [False, True]:
                            if reopened:
                                client.execute('file.saveAs', {'path': str(out / 'real-controls.ecproj')})
                                client.execute('file.open', {'path': str(out / 'real-controls.ecproj')})
                            for p in real.effects[0].properties:
                                assert client.execute('prop.get', {'comp': cid, 'layer': target, 'path': path + '/' + p.id})['value'] == p.value
                            image(client)
                    assert hashlib.sha256(file.read_bytes()).hexdigest() == before
                    audit.append({'case': 'real-controls-original-pixels', 'source_sha256': before, 'values': 16, 'reopened': True})
                    count += 1
                assert count == 1
            (out / 'summary.json').write_text(json.dumps({'cases': audit, 'adobe_visual_comparison': False}, indent=2) + '\n')
            print(f'{len(audit)} native cases verified')
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)


if __name__ == '__main__':
    main()
