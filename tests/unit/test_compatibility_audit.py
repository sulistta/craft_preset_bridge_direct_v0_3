"""Audit counts observed loss without exposing fixture contents or claiming renders."""

import hashlib
import json

import pytest

from craft_bridge.core.models import ConversionWarning, Parameter, ParameterValue
from craft_bridge.core.pipeline import inspect_file
from craft_bridge.core.safety import BridgeError
from craft_bridge.mappings.registry import Registry
from scripts import audit_compatibility as module
from tests.helpers import ffx


def test_audit_distinguishes_missing_map_instances_files_and_opaque_values(tmp_path):
    root = tmp_path / "presets"
    root.mkdir()
    path = root / "private-name.ffx"
    path.write_bytes(ffx([
        ("Test Missing", [("Test Missing-0001", 918273, 1)]),
        ("Test Missing", [("Test Missing-0001", 0, 0)]),
        ("ADBE Brightness & Contrast 2", [("ADBE Brightness & Contrast 2-0001", 15, 1)]),
    ]))
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    result = module.audit(root, Registry(packages=[]))
    missing, mapped = result["effects"]
    assert result["files"] == 1 and result["file_statuses"] == {"PARTIAL": 1}
    assert result["files_with_observation"] == {
        "effect_conversion_loss": 1, "missing_effect_map": 1, "unknown_source_parameter": 1,
    }
    assert missing["files"] == 1 and missing["instances"] == 2 and not missing["map_available"]
    assert missing["source_unknown_parameters"] == 1
    assert missing["source_parameter_loss_warnings"]["UNDECODED_VALUE"] == 1
    assert missing["conversion_loss_warnings"]["NO_MAPPING"] == 2
    assert mapped["map_available"] and mapped["parameters_converted"] == 1
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    serialized = json.dumps(result)
    assert "private-name" not in serialized and str(root) not in serialized and "918273" not in serialized
    assert not result["engine_contacted"] and not result["visual_equivalence_verified"]


def test_audit_excludes_administrative_unknown_but_counts_hidden_processing(tmp_path, monkeypatch):
    path = tmp_path / "case.ffx"
    path.write_bytes(ffx([("Test Missing", [])]))
    document = inspect_file(path)
    effect = document.presets[0].effects[0]
    effect.parameters = [
        Parameter(id="admin", name="Administrative", value=ParameterValue(kind="unknown"),
                  metadata={"administrative": True}, warnings=[ConversionWarning(code="ADMIN", message="UI")]),
        Parameter(id="hidden", name="Processing", value=ParameterValue(kind="unknown"),
                  metadata={"hidden": True}, warnings=[ConversionWarning(code="PROCESSING", message="Opaque")]),
    ]
    monkeypatch.setattr(module, "inspect_file", lambda _: document)
    row = module.audit(tmp_path, Registry(packages=[]))["effects"][0]
    assert row["source_unknown_parameters"] == 1
    assert row["source_parameter_loss_warnings"] == {"PROCESSING": 1}


def test_all_ffx_presets_are_audited_without_counting_file_twice(tmp_path, monkeypatch):
    path = tmp_path / "case.ffx"
    path.write_bytes(ffx([("Test Missing", [])]))
    document = inspect_file(path)
    document.presets.append(document.presets[0].model_copy(deep=True))
    monkeypatch.setattr(module, "inspect_file", lambda _: document)
    result = module.audit(tmp_path, Registry(packages=[]))
    assert result["files"] == 1 and result["file_statuses"] == {"UNSUPPORTED": 1}
    assert result["effects"][0]["files"] == 1 and result["effects"][0]["instances"] == 2


def test_changed_source_aborts_audit(tmp_path, monkeypatch):
    path = tmp_path / "case.ffx"
    path.write_bytes(ffx([("Test Missing", [])]))
    original = module.preview

    def change_during_preview(*args, **kwargs):
        result = original(*args, **kwargs)
        path.write_bytes(b"changed")
        return result

    monkeypatch.setattr(module, "preview", change_during_preview)
    with pytest.raises(BridgeError, match="mudou"):
        module.audit(tmp_path, Registry(packages=[]))


def test_output_inside_private_package_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr("sys.argv", ["audit", str(tmp_path), str(tmp_path / "report.json")])
    with pytest.raises(SystemExit) as error:
        module.main()
    assert error.value.code == 2 and not (tmp_path / "report.json").exists()
