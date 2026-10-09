"""Registros originais sintéticos; sem copiar velocidades do corpus privado."""

import struct

import pytest

from craft_bridge.core.pipeline import convert_file, inspect_file, preview
from craft_bridge.core.safety import BridgeError, Budget, Limits
from craft_bridge.parsers.ffx.keyframes import decode_keyframes
from tests.helpers import chunk, container, path, stream


def raw_keys(records, dims=1):
    size = 8 + 40 * dims
    header = memoryview(struct.pack(">13I", 0xD00BEE, 0, len(records), 1, size, 4, *([0] * 7)))
    data = memoryview(b"".join(struct.pack(">iBBH", t, ci, co, flags) + struct.pack(">" + "d" * (5 * dims), *values) for t, ci, co, flags, values in records))
    return header, data


def decode(records, dims=1, flags=0):
    header, data = raw_keys(records, dims)
    return decode_keyframes(header, data, dimensions=dims, stream_flags=flags, time_base=30720, budget=Budget(Limits()))


def examples():
    return [(0, 2, 2, 8, [8, 0, .75, -13, .2]), (30720, 2, 2, 8, [1, -2, .65, 0, .1])]


def test_endpoint_stored_speeds_never_equalized_or_zeroed():
    keys = decode(examples())
    assert keys[0].handles.in_speed == [0]
    assert keys[0].handles.out_speed == [-13]
    assert keys[1].handles.in_speed == [-2]
    assert keys[1].handles.out_speed == [0]
    assert keys[0].handles.out_influence == [.2]
    assert keys[1].handles.in_influence == [.65]
    assert all(k.metadata["source_temporal_continuous"] == [True] for k in keys)


def test_equal_interior_derivatives_preserved():
    records = examples()
    records.insert(1, (15360, 2, 2, 8, [4, -6, .4, -6, .25]))
    assert decode(records)[1].handles.out_speed == [-6]


def test_conflicting_interior_derivatives_refused():
    records = examples()
    records.insert(1, (15360, 2, 2, 8, [4, -6, .4, -5, .25]))
    with pytest.raises(BridgeError, match="velocidades internas iguais"):
        decode(records)


@pytest.mark.parametrize("flags", [16, 24, 32, 40, 1, 0x8008])
def test_auto_roving_unknown_flags_still_refused(flags):
    records = examples()
    records[0] = (0, 2, 2, flags, records[0][4])
    with pytest.raises(BridgeError):
        decode(records)


@pytest.mark.parametrize("code", [1, 3])
def test_continuous_nonbezier_refused(code):
    records = examples()
    records[0] = (0, code, 2, 8, records[0][4])
    with pytest.raises(BridgeError):
        decode(records)


def test_multidimensional_flags_and_handles_are_kept():
    values = [8, 9, 0, 0, .75, .7, -13, 3, .2, .3]
    keys = decode([(0, 2, 2, 8, values)], dims=2)
    assert keys[0].handles.out_speed == [-13, 3]
    assert keys[0].metadata["source_temporal_continuous"] == [True, True]


def test_export_preserves_curve_and_reports_editing_loss_strict(tmp_path):
    match = "ADBE Sharpen-0001"
    meta, _ = stream(match)
    header, data = raw_keys(examples())
    desc = bytearray(124)
    struct.pack_into(">HH", desc, 0, 0xDB99, 1)
    struct.pack_into(">I", desc, 12, 30720)
    desc[68] = 1
    node = chunk("tdmn", match.encode() + b"\0") + container("tdbs", chunk("tdb4", bytes(desc)), container("list", chunk("lhd3", bytes(header)), chunk("ldat", bytes(data))))
    source = tmp_path / "continuous.ffx"
    source.write_bytes(container("FaFX", container("besc", path(["ADBE Effect Parade", "ADBE Sharpen"]), path(["ADBE End of path sentinel"]), container("sspc", container("parT", meta), container("tdgp", node))), tag="RIFX"))
    out, report = preview(inspect_file(source))
    assert report.status == "PARTIAL" and report.effects[0].keyframes_preserved == 2
    assert out["effects"][0]["properties"][0]["keyframes"][0]["handles"]["out_speed"] == [-13]
    assert any(w.code == "KEYFRAME_CONTINUITY" and w.loss for w in report.effects[0].warnings)
    dest = tmp_path / "strict.json"
    assert convert_file(source, dest, strict=True).status == "FAILED"
    assert not dest.exists()
