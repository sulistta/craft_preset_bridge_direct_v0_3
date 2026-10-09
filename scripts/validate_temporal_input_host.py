"""Prove API 4 reads different source pixels through an isolated native Session."""

import argparse
import json
import os
import select
import subprocess
from pathlib import Path

from craft_bridge.core.validation import validate_plan
from craft_bridge.exporters.effectcraft.exporter import (
    EffectCraftPlan,
    PlanEffect,
    PlanProperty,
    preview_commands,
)
from craft_bridge.integrations.control import ControlClient
from craft_bridge.integrations.effectcraft import apply_plan
from craft_bridge.mappings.registry import Registry

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
    os.environ["CRAFT_BRIDGE_CONFIG"] = str(out / "config")
    registry = Registry()
    registry.install(ROOT / "docs/examples/plugin-temporal-package.json")
    definition = registry.plugins["org.craftbridge.test.temporal"]
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
                client.execute("file.projectSettings", {"bitDepth": 32})
                client.execute(
                    "comp.new",
                    {
                        "width": 4,
                        "height": 2,
                        "frameRate": 30,
                        "duration": 2,
                        "name": "Original source-time proof",
                    },
                )
                cid = client.execute("comp.info")["id"]
                target = client.execute(
                    "layer.newSolid", {"color": "#404040", "name": "Original animated image"}
                )["layer"]
                path = client.execute(
                    "effect.apply", {"comp": cid, "layer": target, "effect": "ec.color.brightnesscontrast"}
                )["paths"][0]
                for time, value in [(0.0, 0.0), (1.0, 100.0)]:
                    client.execute(
                        "prop.addKey",
                        {
                            "comp": cid,
                            "layer": target,
                            "path": path + "/brightness",
                            "time": time,
                            "value": value,
                        },
                    )
                client.execute(
                    "effect.plugins.load", {"path": str(ROOT / "docs/examples/plugin-temporal-probe.wat")}
                )
                listing = client.execute("effect.plugins.list")
                assert listing["apis"] == [1, 2, 3, 4] and listing["bridge_host"]["revision"] == 3

                def image(time, scale):
                    return client.execute("bridge.probe.render", {"comp": cid, "time": time, "scale": scale})

                def independent_reference(cases):
                    return {(time, scale): image(time, scale) for time, scale in cases}

                expected = independent_reference(
                    [(t, s) for s in [1.0, 0.5] for t in [0.0, 0.1, 0.2, 0.3, 0.5, 0.6]]
                )
                assert expected[(0.0, 1.0)] != expected[(0.1, 1.0)] != expected[(0.2, 1.0)]
            plan = EffectCraftPlan(
                version=4,
                name="Original temporal transport",
                catalog_commit=registry.catalog["effectcraft"]["commit"],
                source_sha256="0" * 64,
                effects=[
                    PlanEffect(
                        ref="fx0",
                        effect=definition.id,
                        source="original-synthetic",
                        plugin_fingerprint=definition.fingerprint(),
                        properties=[PlanProperty(id="skip", kind="Float", value=2.0)],
                    )
                ],
            )
            plan.commands = preview_commands(plan)
            validate_plan(plan.model_dump(mode="json"), registry)
            applied = apply_plan(plan, layer=target, comp=cid, port=port, confirmed=True)
            temporal_path = applied["bindings"]["fx0"]["path"]
            with ControlClient(port) as client:
                for scale in [1.0, 0.5]:
                    for current, source in [
                        (0.0, 0.0),
                        (2 / 30, 0.0),
                        (3 / 30, 0.1),
                        (5 / 30, 0.1),
                        (6 / 30, 0.2),
                        (9 / 30, 0.3),
                        (2 / 30, 0.0),
                    ]:
                        frame = image(current, scale)
                        assert frame == expected[(source, scale)], (
                            current,
                            source,
                            frame,
                            expected[(source, scale)],
                        )
                        audit.append(
                            {
                                "case": "source-frame-held",
                                "comp_time": current,
                                "source_time": source,
                                "scale": scale,
                            }
                        )
                client.execute("file.saveAs", {"path": str(out / "held-source.ecproj")})
                client.execute("file.open", {"path": str(out / "held-source.ecproj")})
                assert image(5 / 30, 1.0) == expected[(0.1, 1.0)]
                audit.append({"case": "reopened-source-hold"})
                # Trim shifts the actual visible-frame anchor to .5, not zero.
                client.execute("layer.timing", {"comp": cid, "layer": target, "in": 0.5, "out": 31 / 30})
                for scale in [1.0, 0.5]:
                    assert image(17 / 30, scale) == expected[(0.5, scale)]
                    audit.append(
                        {
                            "case": "trimmed-source-anchor",
                            "comp_time": 17 / 30,
                            "source_time": 0.5,
                            "scale": scale,
                        }
                    )
                client.execute("layer.timing", {"comp": cid, "layer": target, "in": 0.0, "out": 31 / 30})
                client.execute("layer.timeReverse", {"comp": cid, "layer": target})
                for scale in [1.0, 0.5]:
                    assert image(25 / 30, scale) == expected[(0.1, scale)]
                    audit.append(
                        {
                            "case": "reverse-source-time",
                            "comp_time": 25 / 30,
                            "local_source_time": 0.1,
                            "scale": scale,
                        }
                    )
                client.execute("layer.timeReverse", {"comp": cid, "layer": target})
                # Hold animation only: integer changes preserve preceding native keyframes.
                for time, value in [(0.0, 0.0), (0.5, 2.0)]:
                    client.execute(
                        "prop.addKey",
                        {
                            "comp": cid,
                            "layer": target,
                            "path": temporal_path + "/skip",
                            "time": time,
                            "value": value,
                        },
                    )
                    client.execute(
                        "keys.select",
                        {
                            "keys": [
                                {"comp": cid, "layer": target, "path": temporal_path + "/skip", "time": time}
                            ]
                        },
                    )
                    client.execute("keys.interpolation", {"in": "hold", "out": "hold"})
                for current, source in [(0.2, 0.2), (17 / 30, 0.5), (18 / 30, 0.6)]:
                    assert image(current, 1.0) == expected[(source, 1.0)]
                    audit.append({"case": "animated-held-input", "comp_time": current, "source_time": source})
                client.execute("file.saveAs", {"path": str(out / "animated-source-hold.ecproj")})
                client.execute("file.open", {"path": str(out / "animated-source-hold.ecproj")})
                assert image(17 / 30, 0.5) == expected[(0.5, 0.5)]
                audit.append({"case": "reopened-animated-source-hold"})
            (out / "summary.json").write_text(
                json.dumps(
                    {
                        "samples": audit,
                        "api": 4,
                        "host_revision": 3,
                        "images_from_real_different_times": True,
                        "source": "original synthetic images only",
                        "source_effect_support_added": False,
                        "adobe_visual_comparison": False,
                    },
                    indent=2,
                )
                + "\n"
            )
            print(f"{len(audit)} original source-time samples verified", flush=True)
        finally:
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=10)


if __name__ == "__main__":
    main()
