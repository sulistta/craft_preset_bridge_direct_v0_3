"""Real Git regression checks for the optional host preparer, with original data."""

import importlib.util
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/prepare_effectcraft_multi_input.py"
SPEC = importlib.util.spec_from_file_location("bridge_host_preparation", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
preparer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preparer)


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True)


def fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, parent_git: bool) -> tuple[Path, Path]:
    if parent_git:
        git(tmp_path, "init", "--quiet")
    source = tmp_path / "source"
    source.mkdir()
    git(source, "init", "--quiet")
    (source / "probe.txt").write_text("before\n")
    git(source, "add", "probe.txt")
    git(source, "-c", "user.name=Bridge Test", "-c", "user.email=bridge-test@example.invalid",
        "-c", "commit.gpgsign=false", "commit", "--quiet", "-m", "Original synthetic source")
    patch = tmp_path / "probe.patch"
    patch.write_text("diff --git a/probe.txt b/probe.txt\n--- a/probe.txt\n+++ b/probe.txt\n@@ -1 +1 @@\n-before\n+after\n")
    monkeypatch.setattr(preparer, "COMMIT", git(source, "rev-parse", "HEAD").strip())
    monkeypatch.setattr(preparer, "ROOT", tmp_path)
    monkeypatch.setattr(preparer, "PATCH", patch)
    return source, tmp_path / "artifacts/output"


@pytest.mark.parametrize("parent_git", [False, True])
def test_patch_really_changes_exported_tree_inside_or_outside_parent_git(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, parent_git: bool,
) -> None:
    source, output = fixture(tmp_path, monkeypatch, parent_git)
    audit = preparer.prepare(source, output)
    assert (output / "probe.txt").read_text() == "after\n"
    assert (source / "probe.txt").read_text() == "before\n"
    assert git(source, "status", "--porcelain") == ""
    assert audit["official_upstream_abi"] is False
    with pytest.raises(ValueError, match="existing"):
        preparer.prepare(source, output)
    assert (output / "probe.txt").read_text() == "after\n"


def test_refuses_research_and_source_destinations(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source, _ = fixture(tmp_path, monkeypatch, True)
    for output in [source / "new", tmp_path / ".research/new"]:
        with pytest.raises(ValueError, match="outside"):
            preparer.prepare(source, output)
        assert not output.exists()


def test_failed_patch_never_publishes_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source, output = fixture(tmp_path, monkeypatch, True)
    preparer.PATCH.write_text(preparer.PATCH.read_text().replace("-before", "-wrong"))
    with pytest.raises(subprocess.CalledProcessError):
        preparer.prepare(source, output)
    assert not output.exists()
    assert (source / "probe.txt").read_text() == "before\n"
    assert list(output.parent.iterdir()) == []
