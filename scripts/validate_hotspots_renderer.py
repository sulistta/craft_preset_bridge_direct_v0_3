"""Original masked highlights through an isolated Session; real controls opt-in."""

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
    mapping, module = extension_paths('hotspots')
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
                client.execute('file.projectSettings', {'bitDepth': 32})
                client.execute('comp.new', {'width': 8, 'height': 4, 'frameRate': 30, 'duration': 2, 'name': 'Original highlights'})
                cid = client.execute('comp.info')['id']
                for name, color in [('white', '#ffffff'), ('black', '#000000'), ('gray', '#808080')]:
                    client.execute('layer.newSolid', {'color': color, 'name': name})
                target = client.execute('layer.newSolid', {'color': '#808080', 'name': 'Original source'})['layer']

            def explicit(doc, index, reference):
                return SourceLayerBindings(source_sha256=doc.source.sha256, bindings=[{'effect_index': index, 'parameter': 'S_Hotspots-0001', 'layer_ref': reference}])

            def plan_for(changes, reference):
                doc = builder(package)
                doc.presets[0].effects[0].identifier.match_name = 'S_Hotspots'
                for p in doc.presets[0].effects[0].parameters:
                    rule = package['mappings'][0]['params'][p.id]
                    if rule['target'] in changes:
                        v = changes[rule['target']]
                        p.value.data = v + 1 if rule['operation'] == 'minus_one' else v
                raw, report = preview(doc, registry=registry, source_layers=explicit(doc, 0, reference))
                assert report.status == 'PARTIAL' and report.effects[0].parameters_converted == 10
                return validate_plan(raw, registry)

            def apply(plan, reference):
                with ControlClient(port) as client:
                    client.execute('effect.removeAll', {'comp': cid, 'layer': target})
                return apply_plan(plan, layer=target, comp=cid, port=port, confirmed=True, layer_bindings={reference: reference} if reference else {})

            def image(client, scale=1.):
                frame = client.execute('bridge.probe.render', {'comp': cid, 'time': 0., 'scale': scale})
                assert (frame['width'], frame['height']) == ((8, 4) if scale == 1. else (4, 2))
                assert all(math.isfinite(v) for p in frame['pixels'] for v in p)
                return frame['pixels']

            g = 128 / 255
            for name, reference, invert, mask_use, amount in [('null', None, False, 0, 1.), ('white', 'white', False, 0, 1.), ('black', 'black', False, 0, 0.), ('inverted-black', 'black', True, 0, 1.), ('gray-luma', 'gray', False, 0, g), ('black-alpha', 'black', False, 1, 1.)]:
                plan = plan_for({'threshold': 0.125, 'invert_mask': invert, 'mask_use': mask_use, 'blur_input': 0., 'blur_mask': 12.}, reference)
                apply(plan, reference)
                with ControlClient(port) as client:
                    for scale in [1., 0.5]:
                        expected = g - 0.125 * amount
                        assert all(all(math.isclose(v, expected, abs_tol=1e-6) for v in p[:3]) and p[3] == 1. for p in image(client, scale))
                audit.append({'case': name, 'full_half': True, 'explicit_replacement': reference})
            for opacity in range(3):
                plan = plan_for({'threshold': 0.125, 'opacity': opacity}, None)
                apply(plan, None)
                with ControlClient(port) as client:
                    assert all(math.isclose(p[0], g - 0.125, abs_tol=1e-6) for p in image(client))
                audit.append({'case': 'original-opacity', 'opacity': opacity})
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
                    indices = [i for i, e in enumerate(doc.presets[0].effects) if e.identifier.match_name == 'S_Hotspots']
                    if not indices:
                        continue
                    assert len(indices) == 1
                    raw, report = preview(doc, registry=registry, source_layers=explicit(doc, indices[0], None))
                    real = validate_plan(raw, registry)
                    real.effects = [e for e in real.effects if e.source == 'S_Hotspots']
                    real.commands = preview_commands(real)
                    assert len(real.effects) == 1 and len(real.effects[0].properties) == 10
                    result = apply(real, None)
                    path = result['bindings'][real.effects[0].ref]['path']
                    with ControlClient(port) as client:
                        for reopened in [False, True]:
                            if reopened:
                                client.execute('file.saveAs', {'path': str(out / 'real-controls.ecproj')})
                                client.execute('file.open', {'path': str(out / 'real-controls.ecproj')})
                            for p in real.effects[0].properties:
                                expected = None if p.kind == 'Layer' else p.value
                                assert client.execute('prop.get', {'comp': cid, 'layer': target, 'path': path + '/' + p.id})['value'] == expected
                            image(client)
                    assert hashlib.sha256(file.read_bytes()).hexdigest() == before
                    assert any(w.code == 'SOURCE_LAYER_REPLACED' and w.loss for w in report.effects[indices[0]].warnings)
                    audit.append({'case': 'real-processing-original-pixels', 'source_sha256': before, 'processing_values': 9, 'explicit_null_replacement': True, 'reopened': True})
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
