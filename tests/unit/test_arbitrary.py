"""Fixtures sintéticas independentes, baseadas no layout documentado de aRbp."""

import struct

import pytest

from craft_bridge.core.pipeline import convert_file, inspect_file, preview
from craft_bridge.core.safety import BridgeError
from craft_bridge.core.validation import validate_plan
from craft_bridge.parsers.ffx.arbitrary import CURVES, HUE, LEVELS, decode_curves, decode_numeric
from tests.helpers import chunk, container, path, stream


def hue_blob():
    values = [35, -21, -2]
    for i in range(6):
        values.extend(
            [
                (315 + 60 * i) % 360,
                (345 + 60 * i) % 360,
                (15 + 60 * i) % 360,
                (45 + 60 * i) % 360,
                i * 5,
                -i * 3,
                i,
            ]
        )
    return struct.pack(">45i", *values)


def levels_blob():
    return struct.pack(
        ">2I25f", 0x000F10A7, 1, *[v for i in range(5) for v in [0.02 * i, 1 - i * 0.03, 1 + i * 0.2, 0, 0.9]]
    )


def arbitrary_ffx(blob_id, blob, *, animated=False, copies=1, shadow_animated=False, clip=1):
    source = blob_id.rsplit("-", 1)[0]
    meta, node = stream(blob_id, 0, 11, flags=7, keys=[(0, 0, 1)] if animated else None)
    metas, nodes = [meta], [node, container("aRbs", *[chunk("aRbp", blob)] * copies)]
    if blob_id == HUE:
        params = [(2, 2, 7), (4, 0, 3), (5, 0, 2), (6, 0, 2), (7, 0, 4)]
    elif blob_id == LEVELS:
        params = [
            (1, 3, 7),
            (3, 0, 10),
            (4, 1, 10),
            (5, 1, 10),
            (6, 0, 10),
            (7, 1, 10),
            (8, clip, 7),
            (9, clip, 7),
        ]
    else:
        params = []
    for i, value, kind in params:
        m, n = stream(
            source + "-" + str(i).zfill(4),
            value,
            kind,
            keys=[(0, value, 1), (30720, value + 1, 1)] if shadow_animated and i == 4 else None,
        )
        metas.append(m)
        nodes.append(n)
    return container(
        "FaFX",
        container(
            "besc",
            path(["ADBE Effect Parade", source]),
            container("sspc", container("parT", *metas), container("tdgp", *nodes)),
        ),
        tag="RIFX",
    )


def test_hue_blob_preserves_every_range_and_wrap():
    result = decode_numeric(HUE, hue_blob())
    assert len(result) == 45
    assert result["hue"] == 35 and result["saturation"] == -21
    assert result["redsRangeStart"] == 345 and result["redsRangeEnd"] == 15
    assert result["redsStartFalloff"] == result["redsEndFalloff"] == 30
    assert result["magentasHue"] == 25 and result["magentasSaturation"] == -15


def test_levels_blob_uses_all_channels_float32_and_gamma():
    result = decode_numeric(LEVELS, levels_blob())
    assert len(result) == 25
    assert result["redInBlack"] == pytest.approx(0.02)
    assert result["blueGamma"] == pytest.approx(1.6)
    assert result["alphaInWhite"] == pytest.approx(0.88)


@pytest.mark.parametrize("match,blob", [(HUE, hue_blob()), (LEVELS, levels_blob())])
def test_blobs_replace_stale_ui_shadows_and_convert(tmp_path, match, blob):
    p = tmp_path / "channels.ffx"
    p.write_bytes(arbitrary_ffx(match, blob))
    doc = inspect_file(p)
    payload, report = preview(doc)
    plan = validate_plan(payload)
    props = {p.id: p.value for p in plan.effects[0].properties}
    assert report.status == "SUCCESS"
    assert doc.diagnostics["opaque_count"] == 0
    if match == HUE:
        assert props["hue"] == 35 and props["saturation"] == -21
        assert props["channelControl"] == 1
    else:
        assert props["redInBlack"] == pytest.approx(0.02)
        assert props["blueGamma"] == pytest.approx(1.6)
        for prefix in ("", "red", "green", "blue", "alpha"):
            assert props[prefix + "ClipToOutputBlack" if prefix else "clipToOutputBlack"] == 1
    parent = next(p for p in doc.presets[0].effects[0].parameters if p.id == match)
    assert parent.metadata["administrative"] is True
    assert parent.origin["aRbp"]["size"] == len(blob)


@pytest.mark.parametrize("animated,copies", [(True, 1), (False, 2), (False, 0)])
def test_animated_or_multiple_blobs_are_not_flattened(tmp_path, animated, copies):
    p = tmp_path / "unsupported.ffx"
    p.write_bytes(arbitrary_ffx(HUE, hue_blob(), animated=animated, copies=copies))
    doc = inspect_file(p)
    params = doc.presets[0].effects[0].parameters
    assert not any(p.metadata.get("derived_from") == HUE for p in params)
    assert any(w.code == "ARBITRARY_LAYOUT" for p in params for w in p.warnings)
    assert convert_file(p, tmp_path / "out.json", strict=True, dry_run=True).status == "FAILED"


def test_animated_ui_shadow_blocks_static_hue_effect(tmp_path):
    p = tmp_path / "animated-shadow.ffx"
    p.write_bytes(arbitrary_ffx(HUE, hue_blob(), shadow_animated=True))
    payload, report = preview(inspect_file(p))
    assert report.status == "UNSUPPORTED"
    assert not payload["effects"]
    assert any(w.code == "ARBITRARY_SHADOW_ANIMATION" for e in report.effects for w in e.warnings)


@pytest.mark.parametrize("clip,expected", [(1, 1), (2, 0), (3, None)])
def test_levels_clip_menu_order_and_32bpc_limit(tmp_path, clip, expected):
    p = tmp_path / "levels.ffx"
    p.write_bytes(arbitrary_ffx(LEVELS, levels_blob(), clip=clip))
    payload, report = preview(inspect_file(p))
    props = {p["id"]: p["value"] for p in payload["effects"][0]["properties"]}
    if expected is None:
        assert report.status == "PARTIAL"
        assert "clipToOutputBlack" not in props and "redClipToOutputBlack" not in props
        assert convert_file(p, tmp_path / "out.json", strict=True, dry_run=True).status == "FAILED"
    else:
        assert props["clipToOutputBlack"] == props["alphaClipToOutputWhite"] == expected


@pytest.mark.parametrize(
    "match,blob",
    [
        (HUE, hue_blob()[:-1]),
        (LEVELS, levels_blob() + b"\0"),
        (LEVELS, b"\0" * 8 + levels_blob()[8:]),
        (LEVELS, levels_blob()[:8] + struct.pack(">f", float("nan")) + levels_blob()[12:]),
        (HUE, hue_blob()[:12] + struct.pack(">i", 1000) + hue_blob()[16:]),
    ],
)
def test_unrecognized_arbitrary_payload_is_rejected(match, blob):
    with pytest.raises(BridgeError):
        decode_numeric(match, blob)


def test_curve_lut_transfer_retains_points_and_reports_interpolation_loss(tmp_path):
    record = struct.pack(">32H2I", *([0, 0, 255, 255] + [0] * 28), 2, 1)
    blob = struct.pack(">2H", 1, 1) + bytes(range(256)) * 5 + record * 5
    data = decode_curves(blob)
    assert data["channels"][0]["lut"] == list(range(256))
    assert data["channels"][4]["points"] == [[0, 0], [255, 255]]
    p = tmp_path / "curves.ffx"
    p.write_bytes(arbitrary_ffx(CURVES, blob))
    doc = inspect_file(p)
    param = doc.presets[0].effects[0].parameters[0]
    assert param.metadata["decoded_arbitrary"] == data
    assert param.metadata["administrative"] is True and not param.warnings
    assert any(w.code == "CURVES_INTERPOLATION" for w in doc.presets[0].effects[0].warnings)
    payload, report = preview(doc)
    assert report.status == "PARTIAL"
    assert len(payload["effects"][0]["properties"]) == 5
    assert convert_file(p, tmp_path / "strict.json", strict=True, dry_run=True).status == "FAILED"
    invalid = bytearray(blob)
    struct.pack_into(">I", invalid, 1284 + 64, 17)
    with pytest.raises(BridgeError, match="Registro"):
        decode_curves(invalid)
