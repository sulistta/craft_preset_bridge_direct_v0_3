"""OFP fixtures below are original synthetic data, not vendor/user presets."""

import struct

import pytest

from craft_bridge.core.safety import BridgeError
from craft_bridge.parsers.ffx.optical_flares import decode_ofp, encode_ofp


def atom(tag, value):
    return struct.pack("<HH", tag, len(value)) + value


def marker(tag):
    return atom(tag, b"\0")


def field(id, kind, raw):
    return (
        atom(50, struct.pack("<I", id))
        + atom(51, struct.pack("<I", kind))
        + atom(52, raw.ljust(32, b"\0"))
        + marker(2000)
    )


def scene():
    # Repeated separators/IDs are preserved in order. Trailing bytes are not assumed
    # to be zero or discarded; auxiliary color/vector flags are not renderer semantics.
    fields = field(8, 0, struct.pack("<f", 0.75)) + field(24, 6, b"") + field(24, 6, b"")
    fields += field(9, 1, struct.pack("<2f", 2.5, -4.5) + b"\xff")
    fields += field(10, 2, bytes([12, 24, 48, 128, 7]))
    fields += field(11, 3, struct.pack("<i", -25)) + field(12, 4, b"\xff")
    fields += field(13, 5, struct.pack("<i", 2) + b"Original\0")
    name = b"Original synthetic object".ljust(64, b"\0")
    obj = (
        atom(1, struct.pack("<I", 16))
        + atom(2, name)
        + atom(3, b"\0")
        + atom(4, b"\1")
        + fields
        + marker(1000)
    )
    return b"OFP\3" + marker(3000) + field(2, 0, struct.pack("<f", 4)) + marker(4000) + obj


def test_all_field_variants_and_unknown_object_type_have_exact_data_roundtrip():
    data = scene()
    decoded = decode_ofp(data)
    assert encode_ofp(decoded) == data
    assert decoded["field_count"] == 9 and decoded["objects"][0]["type"] == 16
    fields = decoded["objects"][0]["fields"]
    assert fields[0]["value"] == 0.75 and fields[3]["value"] == {"x": 2.5, "y": -4.5, "flag_byte": 255}
    assert fields[4]["value"] == {"rgba8": [12, 24, 48, 128], "flag_byte": 7}
    assert fields[5]["value"] == -25 and fields[6]["value"] is True
    assert decoded["render_semantics_verified"] is False


@pytest.mark.parametrize("cut", [0, 3, 6, 12, 24, -1])
def test_truncated_data_is_refused(cut):
    with pytest.raises(BridgeError):
        decode_ofp(scene()[:cut])


@pytest.mark.parametrize("tag,size", [(50, 3), (51, 5), (52, 31), (2000, 0)])
def test_field_lengths_and_tags_are_verified(tag, size):
    data = scene()
    start = data.index(struct.pack("<HH", tag, 4 if tag in (50, 51) else 32 if tag == 52 else 1))
    broken = bytearray(data)
    struct.pack_into("<H", broken, start + 2, size)
    with pytest.raises(BridgeError):
        decode_ofp(broken)


def test_unknown_versions_types_and_nonfinite_values_are_refused():
    data = scene()
    for broken in [
        b"OFP\4" + data[4:],
        b"OFP\3" + atom(3000, b"\1") + data[9:],
        data.replace(atom(3, b"\0"), atom(3, b"\7"), 1),
        data + b"junk",
        b"OFP\3" + marker(3000) + field(3, 42, b"") + marker(4000),
        b"OFP\3" + marker(3000) + field(3, 0, struct.pack("<f", float("nan"))) + marker(4000),
    ]:
        with pytest.raises(BridgeError):
            decode_ofp(broken)


def test_roundtrip_does_not_ignore_inconsistent_edits():
    decoded = decode_ofp(scene())
    decoded["globals"][0]["value"] = 99
    with pytest.raises(BridgeError):
        encode_ofp(decoded)


def test_decoder_observes_shared_parser_deadline():
    from craft_bridge.core.safety import Budget, Limits

    budget = Budget(Limits())
    budget.deadline = 0
    with pytest.raises(BridgeError, match="tempo"):
        decode_ofp(scene(), budget)
    with pytest.raises(BridgeError, match="parameters"):
        decode_ofp(scene(), Budget(Limits(max_parameters=1)))


def test_decoder_limits(monkeypatch):
    import craft_bridge.parsers.ffx.optical_flares as ofp

    monkeypatch.setattr(ofp, "MAX_FIELDS", 1)
    with pytest.raises(BridgeError, match="limite"):
        decode_ofp(scene())
    monkeypatch.setattr(ofp, "MAX_FIELDS", 100)
    monkeypatch.setattr(ofp, "MAX_OBJECTS", 0)
    with pytest.raises(BridgeError, match="limite"):
        decode_ofp(scene())


def test_encoder_checks_limits_before_hex_decoding_or_output_allocation(monkeypatch):
    import craft_bridge.parsers.ffx.optical_flares as ofp

    decoded = decode_ofp(scene())
    monkeypatch.setattr(ofp, "MAX_BYTES", len(scene()) - 1)
    with pytest.raises(BridgeError):
        encode_ofp(decoded)
    monkeypatch.setattr(ofp, "MAX_BYTES", 2 * 1024 * 1024)
    monkeypatch.setattr(ofp, "MAX_FIELDS", 1)
    with pytest.raises(BridgeError):
        encode_ofp(decoded)
    monkeypatch.setattr(ofp, "MAX_FIELDS", 100)
    decoded["globals"][0]["raw_hex"] = "invalid" * 1_000_000
    with pytest.raises(BridgeError):
        encode_ofp(decoded)


@pytest.mark.parametrize("valid", [True, False])
def test_ffx_scene_is_associated_to_its_owner_without_fake_export(tmp_path, valid):
    from craft_bridge.core.pipeline import inspect_file, preview
    from craft_bridge.parsers.ffx.optical_flares import OPTIONS
    from tests.helpers import chunk, container, path, stream

    meta, node = stream(OPTIONS, 0, 11, flags=7)
    blob = scene() if valid else b"OFP\4" + scene()[4:]
    snapshot = container(
        "sspc", container("parT", meta), container("tdgp", node, container("aRbs", chunk("aRbp", blob)))
    )
    file = tmp_path / "original.ffx"
    file.write_bytes(
        container(
            "FaFX",
            container("besc", path(["ADBE Effect Parade", "VIDEOCOPILOT OpticalFlares"]), snapshot),
            tag="RIFX",
        )
    )
    document = inspect_file(file)
    parameter = document.presets[0].effects[0].parameters[0]
    assert parameter.id == OPTIONS and parameter.value.data is None
    if valid:
        assert parameter.metadata["decoded_arbitrary"]["field_count"] == 9
        assert parameter.metadata["decoded_arbitrary"]["render_semantics_verified"] is False
        assert any(w.code == "OFP_RENDER_UNSUPPORTED" and w.loss for w in parameter.warnings)
    else:
        assert "decoded_arbitrary" not in parameter.metadata
        assert any(w.code == "ARBITRARY_LAYOUT" and w.loss for w in parameter.warnings)
    payload, report = preview(document)
    assert report.status == "UNSUPPORTED" and not payload["effects"]


@pytest.mark.parametrize("snapshot", [True, False])
@pytest.mark.parametrize("diagnostic_limit", [1, 4])
def test_multiple_scenes_remain_unassociated_and_diagnostics_are_bounded(
    tmp_path, snapshot, diagnostic_limit
):
    from craft_bridge.core.pipeline import inspect_file, preview
    from craft_bridge.core.safety import Limits
    from craft_bridge.parsers.ffx.optical_flares import OPTIONS
    from tests.helpers import chunk, container, path, stream

    meta, node = stream(OPTIONS, 0, 11, flags=7)
    arbitrary = container("aRbs", chunk("aRbp", scene()), chunk("aRbp", scene()))
    if snapshot:
        blocks = [container("sspc", container("parT", meta), container("tdgp", node, arbitrary))]
    else:
        blocks = [arbitrary]
    file = tmp_path / "multiple.ffx"
    file.write_bytes(container(
        "FaFX", container("besc", path(["ADBE Effect Parade", "VIDEOCOPILOT OpticalFlares"]), *blocks),
        tag="RIFX",
    ))
    document = inspect_file(file, Limits(max_diagnostics=diagnostic_limit))
    entries = document.diagnostics["unassociated_ofp_scenes"]
    assert len(entries) == min(diagnostic_limit, 2)
    assert document.diagnostics["unassociated_ofp_count"] == 2
    assert len({entry["origin"]["offset"] for entry in entries}) == len(entries)
    assert all(entry["associated"] is False and entry["scene"] == decode_ofp(scene()) for entry in entries)
    assert any(w.code == "OFP_ASSOCIATION_UNSUPPORTED" and w.loss for w in document.warnings)
    assert not any(
        p.metadata.get("decoded_arbitrary") for e in document.presets[0].effects for p in e.parameters
    )
    output, report = preview(document)
    assert report.status == "UNSUPPORTED" and not output["effects"]
