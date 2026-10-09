"""Original impulse rays through Session; actual private controls opt-in."""

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
from craft_bridge.core.resources import SourceLayerBindings
from craft_bridge.core.validation import validate_plan
from craft_bridge.exporters.effectcraft.exporter import preview_commands
from craft_bridge.extensions import extension_paths
from craft_bridge.integrations.control import ControlClient
from craft_bridge.integrations.effectcraft import apply_plan
from craft_bridge.mappings.registry import Registry

ROOT = Path(__file__).resolve().parents[1]
SOURCE = 'OLM Directional Blur'


def impulse_module(path):
    """Original API1 fixture; creates a centered red pixel, not Adobe content."""
    manifest = json.dumps({'api': 1, 'id': 'org.craftbridge.test.olm.impulse', 'name': 'Original impulse fixture', 'category': 'Bridge test', 'version': '0.1.0', 'params': [{'id': 'enabled', 'name': 'Enabled', 'type': 'checkbox', 'default': True}]})
    escaped = manifest.replace('"', '\\"')
    path.write_text(f'''(module
      (memory (export "memory") 2)
      (data (i32.const 16) "{escaped}")
      (func (export "ec_api_version") (result i32) i32.const 1)
      (func (export "ec_manifest_ptr") (result i32) i32.const 16)
      (func (export "ec_manifest_len") (result i32) i32.const {len(manifest)})
      (func (export "ec_alloc") (param i32) (result i32) i32.const 65536)
      (func (export "ec_render") (param $px i32) (param $w i32) (param $h i32)
        (param $params i32) (param $np i32) (param $time f64) (param $scale f64) (result i32)
        (local $i i32) (local $ptr i32) (local $v f32)
        (loop $loop
          local.get $i local.get $w i32.rem_u local.get $w i32.const 2 i32.div_u i32.eq
          local.get $i local.get $w i32.div_u local.get $h i32.const 2 i32.div_u i32.eq i32.and
          if (result f32) f32.const 1 else f32.const 0 end local.set $v
          local.get $px local.get $i i32.const 16 i32.mul i32.add local.set $ptr
          local.get $ptr local.get $v f32.store
          local.get $ptr f32.const 0 f32.store offset=4
          local.get $ptr f32.const 0 f32.store offset=8
          local.get $ptr local.get $v f32.store offset=12
          local.get $i i32.const 1 i32.add local.tee $i local.get $w local.get $h i32.mul i32.lt_u br_if $loop)
        i32.const 0))''')


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
    fixture = out / 'original-impulse.wat'
    impulse_module(fixture)
    mapping, module = extension_paths('olmdirectional')
    package = json.loads(mapping.read_text())
    registry = Registry()
    registry.install(mapping)
    builder = runpy.run_path(str(ROOT / 'scripts/validate_pixelencoder_renderer.py'))['document']
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
                assert client.execute('effect.plugins.load', {'path': str(fixture)})['loaded'][0]['api'] == 1
                client.execute('file.projectSettings', {'bitDepth': 32})
                client.execute('comp.new', {'width': 16, 'height': 8, 'frameRate': 30, 'duration': 2, 'name': 'Original OLM-style rays'})
                cid = client.execute('comp.info')['id']
                for name, color in [('white', '#ffffff'), ('black', '#000000'), ('gray', '#808080')]:
                    layer = client.execute('layer.newSolid', {'color': color, 'name': name})['layer']
                    client.execute('layer.setSwitch', {'layers': [layer], 'switch': 'guide', 'value': True})
                target = client.execute('layer.newSolid', {'color': '#808080', 'name': 'Original source'})['layer']

            def plan_for(changes, reference=None):
                doc = builder(package)
                doc.presets[0].effects[0].identifier.match_name = SOURCE
                for p in doc.presets[0].effects[0].parameters:
                    rule = package['mappings'][0]['params'][p.id]
                    if rule['target'] in changes:
                        value = changes[rule['target']]
                        p.value.data = value + 1 if rule['operation'] == 'minus_one' else value
                explicit = SourceLayerBindings(source_sha256=doc.source.sha256, bindings=[{'effect_index': 0, 'parameter': SOURCE + '-0017', 'layer_ref': reference}]) if reference else None
                raw, report = preview(doc, registry=registry, source_layers=explicit)
                assert report.status == 'PARTIAL' and report.effects[0].parameters_converted == 15
                return validate_plan(raw, registry)

            def apply(plan, reference=None, impulse=True):
                with ControlClient(port) as client:
                    client.execute('effect.removeAll', {'comp': cid, 'layer': target})
                    if impulse:
                        client.execute('effect.apply', {'comp': cid, 'layer': target, 'effect': 'org.craftbridge.test.olm.impulse'})
                return apply_plan(plan, layer=target, comp=cid, port=port, confirmed=True, layer_bindings={reference: reference} if reference else {})

            def image(client, scale=1., time=0.):
                frame = client.execute('bridge.probe.render', {'comp': cid, 'time': time, 'scale': scale})
                assert (frame['width'], frame['height']) == ((16, 8) if scale == 1. else (8, 4))
                assert all(math.isfinite(v) for p in frame['pixels'] for v in p)
                return frame['pixels']

            cases = [
                ('front', {'angle': 0., 'front': 2.}, None, 1., 0, 2., 0.),
                ('back', {'angle': 0., 'front': 0., 'back': 2.}, None, -1., 0, 2., 0.),
                ('vertical', {'angle': 90., 'front': 2.}, None, 1., 1, 2., 0.),
                ('fade', {'angle': 0., 'front': 2., 'front_fade': 100.}, None, 1., 0, 2., 100.),
                ('layer-white', {'angle': 0., 'front': 2., 'noise_type': 2, 'noise_variation': 100.}, 'white', 1., 0, 2., 0.),
                ('layer-black', {'angle': 0., 'front': 2., 'noise_type': 2, 'noise_variation': 100.}, 'black', 1., 0, 0., 0.),
                ('layer-gray', {'angle': 0., 'front': 2., 'noise_type': 2, 'noise_variation': 100.}, 'gray', 1., 0, 2 * 128 / 255, 0.),
                ('smallest-group-size', {'angle': 0., 'front': 2., 'size_variation': 100.}, None, 1., 0, 0., 0.),
            ]
            for name, changes, reference, sign, axis, length, fade in cases:
                apply(plan_for(changes, reference), reference)
                with ControlClient(port) as client:
                    for scale in [1., .5]:
                        width, height = (16, 8) if scale == 1. else (8, 4)
                        expected = [[0.] * 4 for _ in range(width * height)]
                        x, y = width // 2, height // 2
                        expected[y * width + x] = [1., 0., 0., 1.]
                        for distance in range(1, 3):
                            if distance / scale > length + 1e-9:
                                continue
                            xx = x + int(sign * distance) if axis == 0 else x
                            yy = y + int(sign * distance) if axis == 1 else y
                            alpha = 1 - fade / 100 * (distance / scale / length)
                            expected[yy * width + xx] = [alpha, 0., 0., alpha]
                        actual = image(client, scale)
                        assert all(all(math.isclose(v, e, abs_tol=1e-6) for v, e in zip(px, exp, strict=True)) for px, exp in zip(actual, expected, strict=True)), (name, scale)
                audit.append({'case': name, 'full_half': True})
            for mode in [0, 1]:
                apply(plan_for({'angle': 0., 'front': 6., 'noise_type': mode, 'noise_variation': 100., 'thickness': 1.}))
                with ControlClient(port) as client:
                    first = image(client, time=0.)
                    assert image(client, time=1.) == first and image(client, time=0.) == first
                audit.append({'case': 'original-noise-time-order', 'noise_type': mode})
            with ControlClient(port) as client:
                before = image(client)
                client.execute('file.saveAs', {'path': str(out / 'original.ecproj')})
                client.execute('file.open', {'path': str(out / 'original.ecproj')})
                assert image(client) == before
            audit.append({'case': 'original-reopened'})
            if args.real_presets:
                count = 0
                for file in sorted(args.real_presets.rglob('*.ffx')):
                    before = hashlib.sha256(file.read_bytes()).hexdigest()
                    doc = inspect_file(file)
                    indices = [i for i, e in enumerate(doc.presets[0].effects) if e.identifier.match_name == SOURCE]
                    if not indices:
                        continue
                    raw, report = preview(doc, registry=registry)
                    real = validate_plan(raw, registry)
                    real.effects = [e for e in real.effects if e.source == SOURCE]
                    real.commands = preview_commands(real)
                    assert len(real.effects) == 1 and len(real.effects[0].properties) == 15
                    result = apply(real, impulse=False)
                    path = result['bindings'][real.effects[0].ref]['path']
                    with ControlClient(port) as client:
                        for reopened in [False, True]:
                            if reopened:
                                client.execute('file.saveAs', {'path': str(out / 'real-controls.ecproj')})
                                client.execute('file.open', {'path': str(out / 'real-controls.ecproj')})
                            for p in real.effects[0].properties:
                                expected = None if p.kind == 'Layer' else p.value
                                assert client.execute('prop.get', {'comp': cid, 'layer': target, 'path': path + '/' + p.id})['value'] == expected
                            assert all(all(math.isclose(v, 128 / 255, abs_tol=1e-6) for v in px[:3]) and px[3] == 1. for px in image(client))
                    assert hashlib.sha256(file.read_bytes()).hexdigest() == before
                    assert any(w.code == 'SOURCE_LAYER_INACTIVE' and w.loss for w in report.effects[indices[0]].warnings)
                    audit.append({'case': 'real-controls-original-pixels', 'source_sha256': before, 'processing_values': 14, 'inactive_resource': True, 'reopened': True})
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
