"""Compare source Curves LUT samples to the official native Curve evaluator.

Uses the disposable development harness's curve-eval mode. Corpus payloads are private;
all raw inputs and per-channel measurements stay in a new explicitly supplied directory.
This measures sample transfer, not Adobe visual equivalence or high-bit-depth behavior.
"""

import argparse
import json
import subprocess
from collections import defaultdict
from pathlib import Path

from craft_bridge.core.pipeline import inspect_file
from craft_bridge.parsers.ffx.arbitrary import CURVES, curve_lut_text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--harness", type=Path, default=Path("artifacts/native-target/debug/craft-bridge-native-validation"))
    args = parser.parse_args()
    if not args.corpus.is_dir() or args.output.exists() or not args.harness.is_file():
        parser.error("Existing corpus/harness and a new output directory are required")
    entries, references = [], {}
    for file in sorted(args.corpus.rglob("*.ffx")):
        document = inspect_file(file)
        for index, effect in enumerate(document.presets[0].effects):
            for param in effect.parameters:
                if param.id != CURVES:
                    continue
                decoded = param.metadata.get("decoded_arbitrary")
                if not isinstance(decoded, dict):
                    continue
                for channel in decoded["channels"]:
                    id = document.source.sha256 + ":" + str(index) + ":" + channel["channel"]
                    references[id] = channel["lut"]
                    for mode, points in [
                        ("points", " ".join(f"{x / 255:.17g},{y / 255:.17g}" for x, y in channel["points"])),
                        ("lut", curve_lut_text(channel)),
                    ]:
                        entries.append({"id": id + ":" + mode, "points": points, "channel": channel["channel"],
                                        "inputs": [x / 255 for x in range(256)]})
    if not entries:
        raise ValueError("No decoded Curves channels; no evidence claimed")
    args.output.mkdir(parents=True)
    input_file = args.output / "input.json"
    input_file.write_text(json.dumps(entries))
    evaluated = subprocess.run([str(args.harness.resolve()), "curve-eval", str(input_file.resolve())],
                               capture_output=True, text=True, check=True, timeout=60)
    native = json.loads(evaluated.stdout)
    expected_ids = [e["id"] for e in entries]
    if [e["id"] for e in native] != expected_ids:
        raise AssertionError("Native evaluator omitted/reordered channels")
    modes = defaultdict(list)
    results = []
    for entry in native:
        id, mode = entry["id"].rsplit(":", 1)
        if entry["rendered_values"] != entry["values"]:
            raise AssertionError("Native Curves renderer differs from Curve evaluator")
        errors = [abs(a - v / 255) for a, v in zip(entry["values"], references[id], strict=True)]
        error = max(errors)
        modes[mode].append(error)
        results.append({"id": id, "mode": mode, "max_abs_error": error, "max_error_8bit_units": error * 255})
    summary = {k: {"channels": len(v), "maximum_error_8bit_units": max(v) * 255,
                   "nonzero_channels": sum(e > 1e-7 for e in v)} for k, v in modes.items()}
    (args.output / "native.json").write_text(evaluated.stdout)
    (args.output / "comparison.json").write_text(json.dumps({"summary": summary, "channels": results,
                                                           "native_renderer_verified": True}, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
