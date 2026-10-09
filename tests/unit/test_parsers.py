import struct
import time

import pytest

from craft_bridge.core.pipeline import inspect_file
from craft_bridge.core.safety import BridgeError, Budget, Limits
from craft_bridge.parsers.ffx.keyframes import decode_keyframes
from craft_bridge.parsers.ffx.rifx import decode_string, parse_rifx
from tests.helpers import chunk, container, ffx, path, premiere, stream, string


def parse_bytes(tmp_path, data):
    p = tmp_path / "preset.unknown"
    p.write_bytes(data)
    return inspect_file(p)


def test_premiere_references_and_start_value(premiere_file):
    doc = inspect_file(premiere_file)
    assert doc.source.format == "prfpset"
    preset = doc.presets[0]
    assert preset.name == "Blur original"
    assert preset.effects[0].parameters[0].value.data == 25
    assert preset.keyframe_mode == "AnchorToIn"
    assert preset.source_duration_ticks == 254016000000


def test_premiere_multiple_effects_and_order(tmp_path):
    doc = parse_bytes(tmp_path, premiere(effects=3))
    assert [e.order for e in doc.presets[0].effects] == [0, 1, 2]
    assert [e.name for e in doc.presets[0].effects] == [
        "Blur original 0",
        "Blur original 1",
        "Blur original 2",
    ]


@pytest.mark.parametrize(
    "data",
    [
        b"<PremiereData>",
        b"<Other/>",
        b"\0garbage",
        b'<!DOCTYPE x [<!ENTITY xx "oops">]><PremiereData>&xx;</PremiereData>',
        premiere().replace(b'ObjectRef="12"', b'ObjectRef="999"'),
        premiere().replace(b'ObjectID="12"', b'ObjectID="11"'),
    ],
)
def test_premiere_malformed(tmp_path, data):
    with pytest.raises(BridgeError):
        parse_bytes(tmp_path, data)


def test_unknown_premiere_value_never_zero(tmp_path):
    doc = parse_bytes(tmp_path, premiere().replace(b",25.,", b",mystery,"))
    p = doc.presets[0].effects[0].parameters[0]
    assert p.value.data is None
    assert any(w.code == "UNDECODED_VALUE" for w in p.warnings)


def test_xml_animation_times_are_preserved_but_interp_unknown(tmp_path):
    doc = parse_bytes(tmp_path, premiere(animation=True))
    p = doc.presets[0].effects[0].parameters[0]
    assert [k.seconds for k in p.keyframes] == [0, 1]
    assert p.keyframes[0].out_interp[0].value == "Unknown"
    assert any(w.loss for w in p.warnings)


def test_ffx_effects_pairing_ignores_sentinel_position(tmp_path):
    data = ffx(
        [
            ("ADBE Sharpen", [("ADBE Sharpen-0001", 10.0, 1)]),
            ("ADBE Unsharp Mask2", [("ADBE Unsharp Mask2-0001", 35.0, 1)]),
        ],
        sentinel_first=True,
    )
    doc = parse_bytes(tmp_path, data)
    assert [e.identifier.match_name for e in doc.presets[0].effects] == ["ADBE Sharpen", "ADBE Unsharp Mask2"]
    assert [e.parameters[0].value.data for e in doc.presets[0].effects] == [10, 35]


def test_ffx_unknown_effect_still_inspected(tmp_path):
    doc = parse_bytes(tmp_path, ffx([("MysteryFX", [("MysteryFX-0001", 22.0, 1)])]))
    assert doc.presets[0].effects[0].parameters[0].value.data == 22


def test_ffx_no_sspc_property_class(tmp_path):
    _, node = stream("Unverified-0050", 0.5)
    # node includes sibling tdmn followed by a standalone tdbs block
    data = container(
        "FaFX",
        container(
            "besc",
            path(["ADBE Effect Parade", "Unverified", "Unverified-0050"]),
            path(["ADBE End of path sentinel"]),
            node,
        ),
        tag="RIFX",
    )
    doc = parse_bytes(tmp_path, data)
    assert doc.presets[0].effects[0].feature == "property"
    assert doc.presets[0].effects[0].parameters[0].id == "Unverified-0050"


def test_rifx_padding_nested_trailer():
    data = (
        container("FaFX", container("besc", chunk("odd ", b"abc"), chunk("zero", b"")), tag="RIFX") + b"XMP"
    )
    root, trailer = parse_rifx(data, Budget(Limits()))
    assert trailer == b"XMP"
    assert bytes(root.children[0].children[0].data) == b"abc"
    assert root.children[0].children[1].id == "zero"


@pytest.mark.parametrize(
    "data",
    [
        b"RIFX",
        b"RIFF" + b"\0" * 20,
        b"RIFX" + struct.pack(">I", 100) + b"FaFX",
        container("FaFX", chunk("LIST", b"x"), tag="RIFX"),
        container("FaFX", b"abc", tag="RIFX"),
        container("FaFX", chunk("test", b"abc")[:-1], tag="RIFX"),
    ],
)
def test_rifx_invalid(data):
    with pytest.raises(BridgeError):
        parse_rifx(data, Budget(Limits()))


def test_rifx_depth_count_and_deadline():
    data = container("FaFX", container("aaaa", container("bbbb", chunk("test", b""))), tag="RIFX")
    for limits in [Limits(max_depth=1), Limits(max_chunks=2)]:
        with pytest.raises(BridgeError):
            parse_rifx(data, Budget(limits))
    budget = Budget(Limits())
    budget.deadline = time.monotonic() - 1
    with pytest.raises(BridgeError):
        parse_rifx(data, budget)


def test_size_limit(ffx_file):
    with pytest.raises(BridgeError):
        inspect_file(ffx_file, Limits(max_file_bytes=5))


@pytest.mark.parametrize("base", [20480, 23976, 24576, 30720])
def test_ffx_timebase_and_bezier(tmp_path, base):
    meta, node = stream("ADBE Sharpen-0001", 15.0, 1, 1, [(0, 10.0, 2), (base, 30.0, 2)], base, 0)
    data = container(
        "FaFX",
        container(
            "besc",
            path(["ADBE Effect Parade", "ADBE Sharpen"]),
            path(["ADBE End of path sentinel"]),
            container("sspc", container("parT", meta), container("tdgp", node)),
        ),
        tag="RIFX",
    )
    param = parse_bytes(tmp_path, data).presets[0].effects[0].parameters[0]
    assert [k.seconds for k in param.keyframes] == [0, 1]
    assert param.keyframes[0].handles.in_influence == [1 / 3]
    assert param.keyframes[0].in_interp[0].value == "Bezier"


@pytest.mark.parametrize("dims", [2, 3])
def test_multidimensional_normal_layout(tmp_path, dims):
    meta, node = stream(
        "Point-0001", [1.0] * dims, 6, dims, [(0, [1.0] * dims, 1), (30720, [2.0] * dims, 2)], 30720, 0
    )
    data = container(
        "FaFX",
        container(
            "besc",
            path(["ADBE Effect Parade", "Point"]),
            container("sspc", container("parT", meta), container("tdgp", node)),
        ),
        tag="RIFX",
    )
    p = parse_bytes(tmp_path, data).presets[0].effects[0].parameters[0]
    assert p.keyframes[1].value == [2.0] * dims
    assert len(p.keyframes[1].handles.out_speed) == dims


def test_interleaved_layout_requires_matching_dimension_times():
    header = memoryview(struct.pack(">13I", 0xD00BEE, 0, 2, 2, 48, 4, *([0] * 7)))

    def record(t, v):
        return struct.pack(">iBBH5d", t, 1, 1, 0, v, 0, 1 / 3, 0, 1 / 3)

    data = memoryview(record(0, 1) + record(0, 2) + record(30720, 3) + record(30720, 4))
    keys = decode_keyframes(
        header, data, dimensions=2, stream_flags=0, time_base=30720, budget=Budget(Limits())
    )
    assert keys[1].value == [3, 4]
    bad = memoryview(record(0, 1) + record(1, 2) + record(30720, 3) + record(30720, 4))
    with pytest.raises(BridgeError):
        decode_keyframes(header, bad, dimensions=2, stream_flags=0, time_base=30720, budget=Budget(Limits()))


def test_nonfinite_value_and_spatial_layout_are_reported(tmp_path):
    data = ffx([("ADBE Sharpen", [("ADBE Sharpen-0001", float("nan"), 1)])])
    assert parse_bytes(tmp_path, data).presets[0].effects[0].parameters[0].value.data is None
    _, node = stream("Point-0001", [0, 0], 6, 2, [(0, [1, 2], 1)], 30720, 2)
    data = container(
        "FaFX",
        container("besc", path(["ADBE Effect Parade", "Point"]), container("sspc", container("tdgp", node))),
        tag="RIFX",
    )
    p = parse_bytes(tmp_path, data).presets[0].effects[0].parameters[0]
    assert any(w.code == "KEYFRAME_LAYOUT" for w in p.warnings)


def test_utf8_and_legacy_strings():
    assert decode_string(string("Olá")) == "Olá"
    assert decode_string(b"Legacy\0\0") == "Legacy"
    with pytest.raises(BridgeError):
        decode_string(b"Utf8" + struct.pack(">I", 99) + b"x")
