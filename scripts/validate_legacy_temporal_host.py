"""Original API 1 wave proves native Session cache respects time and layer mapping."""

import argparse
import json
import math
import select
import subprocess
from pathlib import Path

from craft_bridge.extensions import extension_paths
from craft_bridge.integrations.control import ControlClient

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--harness", type=Path, default=ROOT / "artifacts/native-target/debug/craft-bridge-multi-input-probe"
    )
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Use a new output directory")
    out = args.output.resolve()
    out.mkdir(parents=True)
    audit = []
    with (out / "host.log").open("w") as log:
        process = subprocess.Popen(
            [str(args.harness.resolve()), "--serve"], stdout=subprocess.PIPE, stderr=log, text=True
        )
        try:
            assert process.stdout is not None and select.select([process.stdout], [], [], 20)[0]
            ready = process.stdout.readline().strip()
            assert ready.startswith("Bridge experimental host ready: "), ready
            port = int(ready.rsplit(" ", 1)[1])
            with ControlClient(port) as client:
                assert (
                    client.execute("effect.plugins.load", {"path": str(extension_paths("flicker")[1])})[
                        "loaded"
                    ][0]["api"]
                    == 1
                )
                client.execute("file.projectSettings", {"bitDepth": 32})
                client.execute(
                    "comp.new",
                    {
                        "width": 2,
                        "height": 2,
                        "frameRate": 30,
                        "duration": 2,
                        "name": "Original temporal audit",
                    },
                )
                cid = client.execute("comp.info")["id"]
                target = client.execute("layer.newSolid", {"color": "#ff0000", "name": "Original target"})[
                    "layer"
                ]
                path = client.execute(
                    "effect.apply", {"comp": cid, "layer": target, "effect": "org.craftbridge.flicker"}
                )["paths"][0]
                for id, value in [
                    ("amplitude", 0.2),
                    ("rand_luma_amp", 0.0),
                    ("wave_amp", 1.0),
                    ("wave_freq", 1.0),
                ]:
                    client.execute(
                        "prop.set", {"comp": cid, "layer": target, "path": path + "/" + id, "value": value}
                    )

                def check(time, gain, scale):
                    result = client.execute(
                        "bridge.probe.render", {"comp": cid, "time": time, "scale": scale}
                    )
                    expected = [gain, 0.0, 0.0, 1.0]
                    assert all(
                        math.isclose(a, b, abs_tol=3e-6, rel_tol=3e-6)
                        for pixel in result["pixels"]
                        for a, b in zip(pixel, expected, strict=True)
                    ), (time, scale, result, expected)
                    audit.append(
                        {
                            "comp_time": time,
                            "scale": scale,
                            "pixel": result["pixels"][0],
                            "expected_original_wave": gain,
                        }
                    )

                # Controls have no keyframes; independently known original sine peaks/troughs.
                for scale in [1.0, 0.5]:
                    for time, gain in [(0.0, 1.0), (0.25, 1.2), (0.5, 1.0), (0.75, 0.8), (0.25, 1.2)]:
                        check(time, gain, scale)
                project = out / "original-wave.ecproj"
                client.execute("file.saveAs", {"path": str(project)})
                client.execute("file.open", {"path": str(project)})
                check(0.25, 1.2, 1.0)
                # Reverse a one-second visible span; layer time .75 at comp time .25.
                client.execute("layer.timing", {"comp": cid, "layer": target, "in": 0.0, "out": 31 / 30})
                client.execute("layer.timeReverse", {"comp": cid, "layer": target})
                for scale in [1.0, 0.5]:
                    check(0.25, 0.8, scale)
                    check(0.75, 1.2, scale)
            (out / "summary.json").write_text(
                json.dumps(
                    {
                        "samples": audit,
                        "api": 1,
                        "static_controls_time_respected": True,
                        "layer_time_reverse_respected": True,
                        "reopen_verified": True,
                        "source": "original synthetic only",
                        "official_upstream_host_changed": False,
                        "adobe_visual_comparison": False,
                    },
                    indent=2,
                )
                + "\n"
            )
            print("15 original API 1 temporal samples verified", flush=True)
        finally:
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=10)


if __name__ == "__main__":
    main()
