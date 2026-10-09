import json
import subprocess
import sys
from pathlib import Path

from craft_bridge.mappings.registry import Registry
from tests.unit.test_flare_library import write_ffx


def test_cli_builds_local_library_without_installing_or_loading(tmp_path, monkeypatch):
    monkeypatch.setenv('CRAFT_BRIDGE_CONFIG', str(tmp_path/'config'))
    corpus, output = tmp_path/'corpus', tmp_path/'library'
    source = write_ffx(corpus)
    original = source.read_bytes()
    command = [sys.executable, '-m', 'craft_bridge', 'extensions', 'build-flare', str(corpus), '--out', str(output)]
    result = subprocess.run(command, text=True, capture_output=True, timeout=20)
    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary['associated_snapshots']==1 and summary['approximate']
    assert summary['renderer_loaded'] is False and summary['mapping_installed'] is False
    assert not (tmp_path/'config').exists() and source.read_bytes()==original
    assert Path(summary['module']).read_bytes().startswith(b'\0asm')
    assert Registry().find('ffx','effectcraft','VIDEOCOPILOT OpticalFlares') is None
    assert Registry(packages=[Path(summary['mapping'])]).find('ffx','effectcraft','VIDEOCOPILOT OpticalFlares')
    duplicate = subprocess.run(command, text=True, capture_output=True, timeout=20)
    assert duplicate.returncode==1 and 'nova' in duplicate.stderr
