"""Prepare an isolated EffectCraft checkout with the experimental Bridge host patch.

Reads the pinned Git object, never the research checkout's working files. Refuses
to replace a directory. This does not install plugins or modify the user's app.
"""

import argparse
import hashlib
import json
import subprocess
import tarfile
import tempfile
from pathlib import Path

COMMIT = "e38a92e792c07f1c57c5dcfcab37d91932b9e2b8"
ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "scripts/effectcraft-multi-input/host-api2.patch"


def prepare(source: Path, output: Path) -> dict[str, object]:
    source = source.resolve(strict=True)
    output = output.absolute()
    if output.exists() or output.is_symlink():
        raise ValueError("Use a new output directory; existing files will not be replaced.")
    forbidden = (ROOT / ".research", source)
    if any(output.resolve().is_relative_to(path) for path in forbidden):
        raise ValueError("The output must be outside research and source checkouts.")
    patch = PATCH.read_bytes()
    subprocess.run(["git", "-C", str(source), "cat-file", "-e", f"{COMMIT}^{{commit}}"], check=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    # Keep incomplete extraction/patching disposable; publish only on success.
    with tempfile.TemporaryDirectory(prefix="bridge-host-", dir=output.parent) as temporary:
        temporary_path = Path(temporary)
        archive = temporary_path / "source.tar"
        checkout = temporary_path / "checkout"
        subprocess.run(["git", "-C", str(source), "archive", COMMIT, "--output", str(archive)], check=True)
        checkout.mkdir()
        with tarfile.open(archive) as entries:
            entries.extractall(checkout, filter="data")
        # Otherwise Git discovers the parent Bridge repository and silently skips
        # patch paths outside this subdirectory. Give the exported tree its own root.
        subprocess.run(["git", "init", "--quiet", str(checkout)], check=True)
        subprocess.run(["git", "apply", "--check", str(PATCH)], cwd=checkout, check=True)
        subprocess.run(["git", "apply", str(PATCH)], cwd=checkout, check=True)
        subprocess.run(["git", "apply", "--reverse", "--check", str(PATCH)], cwd=checkout, check=True)
        audit: dict[str, object] = {
            "upstream_commit": COMMIT,
            "experimental_host_revision": 3,
            "official_upstream_abi": False,
            "patch_sha256": hashlib.sha256(patch).hexdigest(),
            "apis": [1, 2, 3, 4],
            "layer_timing": True,
            "temporal_sampling": True,
            "max_combined_inputs": 4,
            "temporal_tree_requests": 64,
            "temporal_nesting": 16,
            "max_layer_inputs": 4,
            "source_effect_support_added": False,
        }
        (checkout / "bridge-host-provenance.json").write_text(json.dumps(audit, indent=2) + "\n")
        checkout.rename(output)
    return audit


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / ".research/effectcraft")
    parser.add_argument("--out", type=Path, default=ROOT / "artifacts/effectcraft-multi-input")
    args = parser.parse_args()
    try:
        audit = prepare(args.source, args.out)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Host preparation failed: {error}\n")
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
