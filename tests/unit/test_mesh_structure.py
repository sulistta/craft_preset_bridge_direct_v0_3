"""Original synthetic structural records, not Adobe/private mesh fixtures."""

import json
import struct

import pytest

from craft_bridge.core.pipeline import convert_file, inspect_file, preview
from craft_bridge.core.safety import BridgeError, Budget, Limits
from craft_bridge.parsers.ffx.mesh import HEADER, MESH, decode_mesh, encode_mesh
from tests.unit.test_arbitrary import arbitrary_ffx


def original_blob():
    # Independent arbitrary binary fractions test lossless fields without
    # assuming any private grid/control-point geometry or semantic pair order.
    records = [struct.pack(">10f", -0.0, *[(i - j) / 16 for j in range(9)]) for i in range(64)]
    return struct.pack(">5I", *HEADER) + b"".join(records)


def test_all_fields_survive_json_and_byte_roundtrip():
    blob = original_blob()
    decoded = decode_mesh(blob)
    assert decoded["record_count"] == 64 and len(decoded["records"]) == 64
    assert all(len(r) == 10 for r in decoded["records"])
    assert encode_mesh(json.loads(json.dumps(decoded))) == blob
    assert struct.pack(">f", decoded["records"][0][0]) == b"\x80\0\0\0"


@pytest.mark.parametrize("cut", [0, 19, 20, 40, -1])
def test_truncation_and_trailing_bytes_refused(cut):
    with pytest.raises(BridgeError):
        decode_mesh(original_blob()[:cut])
    with pytest.raises(BridgeError):
        decode_mesh(original_blob() + b"\0")


@pytest.mark.parametrize("word,value", [(0, 9), (1, 9), (2, 1), (3, 1), (4, 0)])
def test_unknown_headers_are_not_inferred(word, value):
    blob = bytearray(original_blob())
    struct.pack_into(">I", blob, word * 4, value)
    with pytest.raises(BridgeError):
        decode_mesh(blob)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_record_rejected(value):
    blob = bytearray(original_blob())
    struct.pack_into(">f", blob, 20 + 63 * 40 + 36, value)
    with pytest.raises(BridgeError):
        decode_mesh(blob)


def test_shared_deadline_and_record_budget():
    budget = Budget(Limits())
    budget.deadline = 0
    with pytest.raises(BridgeError, match="tempo"):
        decode_mesh(original_blob(), budget)
    with pytest.raises(BridgeError, match="parameters"):
        decode_mesh(original_blob(), Budget(Limits(max_parameters=63)))


@pytest.mark.parametrize("value", [True, "0", 1e100, 10**400, 1/3, float("inf"), float("nan")])
def test_encoder_refuses_nonexact_or_invalid_fields(value):
    decoded = decode_mesh(original_blob())
    decoded["records"][63][9] = value
    with pytest.raises(BridgeError):
        encode_mesh(decoded)


def test_encoder_refuses_incomplete_structure_before_building_output():
    decoded = decode_mesh(original_blob())
    for altered in [
        {**decoded, "record_count": True},
        {**decoded, "header_words": [8, 8, False, 0, 0x0D0D]},
        {**decoded, "records": decoded["records"][:-1]},
        {**decoded, "layout": "unknown"},
        {**decoded, "extra": 1},
    ]:
        with pytest.raises(BridgeError):
            encode_mesh(altered)


def test_instance_association_preserves_diagnostics_without_fake_conversion(tmp_path):
    file = tmp_path / "original.ffx"
    file.write_bytes(arbitrary_ffx(MESH, original_blob()))
    doc = inspect_file(file)
    parameter = next(p for p in doc.presets[0].effects[0].parameters if p.id == MESH)
    assert parameter.value.kind == "unknown" and parameter.value.data is None
    assert parameter.metadata.get("administrative") is not True
    assert encode_mesh(parameter.metadata["decoded_arbitrary"]) == original_blob()
    assert parameter.origin["aRbp"]["size"] == len(original_blob())
    assert {w.code for w in parameter.warnings} == {"MESH_RENDER_UNSUPPORTED"}
    plan, report = preview(doc)
    assert not plan["effects"] and report.status == "UNSUPPORTED"
    output = tmp_path / "strict.json"
    strict = convert_file(file, output, strict=True)
    assert strict.status == "UNSUPPORTED" and not output.exists()


def test_definition_default_never_replaces_instance_payload(tmp_path):
    from tests.helpers import chunk, container, path, stream

    default = bytearray(original_blob())
    struct.pack_into(">f", default, 20, 16.0)
    meta, node = stream(MESH, 0, 11, flags=7)
    source = "ADBE MESH WARP"
    snapshot = container(
        "sspc",
        container("parT", meta, chunk("aRbp", default)),
        container("tdgp", node, container("aRbs", chunk("aRbp", original_blob()))),
    )
    file = tmp_path / "definition-and-instance.ffx"
    file.write_bytes(container("FaFX", container("besc", path(["ADBE Effect Parade", source]), snapshot), tag="RIFX"))
    parameter = inspect_file(file).presets[0].effects[0].parameters[0]
    assert encode_mesh(parameter.metadata["decoded_arbitrary"]) == original_blob()


@pytest.mark.parametrize("animated,copies", [(True, 1), (False, 2), (False, 0)])
def test_animation_and_ambiguous_association_remain_opaque(tmp_path, animated, copies):
    file = tmp_path / "unsupported.ffx"
    file.write_bytes(arbitrary_ffx(MESH, original_blob(), animated=animated, copies=copies))
    doc = inspect_file(file)
    parameter = next(p for p in doc.presets[0].effects[0].parameters if p.id == MESH)
    assert "decoded_arbitrary" not in parameter.metadata
    assert any(w.code == "ARBITRARY_LAYOUT" for w in parameter.warnings)
