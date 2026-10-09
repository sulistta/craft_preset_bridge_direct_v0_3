import json
import subprocess
import sys
from pathlib import Path

import pytest

from craft_bridge.mappings.registry import Registry


@pytest.mark.parametrize("name,source", [("glow","PEDG"),("shake","S_Shake"),("stretch","pixel_stretch"),("diffusion","omino_diffusion"),("modulation","ADBE Checkout"),("glint","S_Glint"),("pixelsort","S_PixelSort"),("flicker","S_Flicker"),("median","BCC3Median"),("directional","BCC3Directional Blur"),("sharpen","S_Sharpen"),("colorize","BCC3Colorize")])
def test_packaged_renderer_installs_without_loading_module_or_adobe(tmp_path, monkeypatch, name, source):
    monkeypatch.setenv("CRAFT_BRIDGE_CONFIG", str(tmp_path / "config"))
    def cli(*args):
        result = subprocess.run([sys.executable, "-m", "craft_bridge", "extensions", *args], capture_output=True, text=True, timeout=20)
        assert result.returncode == 0, result.stderr
        return next(item for item in json.loads(result.stdout) if item["name"] == name)
    listed = cli("list")
    assert not (tmp_path / "config").exists()
    assert Path(listed["module"]).read_bytes().startswith(b"\0asm")
    assert listed["installed"] is None and listed["renderer_loaded"] is False
    installed = cli("install", name)
    assert Path(installed["installed"]).is_file()
    assert installed["renderer_loaded"] is False and installed["approximate"] is True
    assert Registry().find("ffx", "effectcraft", source) is not None
