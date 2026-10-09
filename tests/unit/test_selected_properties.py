import copy
import struct

import pytest

from craft_bridge.core.pipeline import inspect_file, preview
from craft_bridge.core.safety import BridgeError
from craft_bridge.core.validation import validate_plan
from craft_bridge.exporters.effectcraft.exporter import preview_commands
from tests.helpers import chunk, container, path, stream


def selected_ffx(params, indices=None):
    paths, nodes = [], []
    for i, (effect, param, value, kind, *rest) in enumerate(params):
        index = indices[i] if indices else 0
        _, node = stream(param, value, kind, keys=rest[0] if rest else None)
        paths.append(path(["ADBE Effect Parade", effect, param], index))
        # Standalone tdbs has its match name only in the corresponding tdsp.
        nodes.append(node[len(chunk("tdmn", param.encode() + b"\0")) :])
    return container("FaFX", container("besc", *paths, *nodes), tag="RIFX")


def test_selected_motiontile_properties_bind_one_existing_instance(tmp_path):
    f = tmp_path / "selected.ffx"
    f.write_bytes(
        selected_ffx(
            [
                ("ADBE Tile", "ADBE Tile-0004", 240, 1),
                ("ADBE Tile", "ADBE Tile-0005", 350, 1),
                ("ADBE Tile", "ADBE Tile-0006", 1, 4),
            ]
        )
    )
    doc = inspect_file(f)
    assert len(doc.presets[0].effects) == 1
    effect = doc.presets[0].effects[0]
    assert effect.feature == "effect-properties"
    assert effect.metadata["source_effect_index"] == 0
    assert [p.value.data for p in effect.parameters] == [240, 350, True]
    payload, report = preview(doc)
    plan = validate_plan(payload)
    assert report.status == "SUCCESS"
    assert plan.effects[0].application == "existing"
    assert plan.commands[0]["command"] == "bridge.bindExistingEffect"
    assert not any(c["command"] == "effect.apply" for c in plan.commands)


def test_selected_distinct_instances_are_not_merged(tmp_path):
    f = tmp_path / "two.ffx"
    f.write_bytes(
        selected_ffx(
            [
                ("ADBE Tile", "ADBE Tile-0004", 240, 1),
                ("ADBE Tile", "ADBE Tile-0005", 350, 1),
            ],
            indices=[0, 2],
        )
    )
    payload, _ = preview(inspect_file(f))
    plan = validate_plan(payload)
    assert [e.source_effect_index for e in plan.effects] == [0, 2]


def test_unknown_type_is_not_guessed_from_one_dimension(tmp_path):
    f = tmp_path / "unknown.ffx"
    f.write_bytes(selected_ffx([("Unverified", "Unverified-0001", 1, 4)]))
    doc = inspect_file(f)
    assert doc.presets[0].effects[0].feature == "property"
    assert doc.presets[0].effects[0].parameters[0].value.data is None
    assert preview(doc)[1].status == "UNSUPPORTED"


def test_selected_index_requires_four_bytes(tmp_path):
    malformed = container(
        "tdsp",
        *[
            container(
                "tdsi", chunk("tdix", b"\xff" * 4 if i == 0 else b"\0"), chunk("tdmn", name.encode() + b"\0")
            )
            for i, name in enumerate(["ADBE Effect Parade", "ADBE Tile", "ADBE Tile-0004"])
        ],
    )
    f = tmp_path / "index.ffx"
    f.write_bytes(container("FaFX", container("besc", malformed), tag="RIFX"))
    with pytest.raises(BridgeError, match="quatro bytes"):
        inspect_file(f)


def test_profile_dimension_mismatch_is_reported(tmp_path):
    _, node = stream("ADBE Tile-0004", [1, 2], 1, dims=2)
    f = tmp_path / "dims.ffx"
    prefix = chunk("tdmn", b"ADBE Tile-0004\0")
    f.write_bytes(
        container(
            "FaFX",
            container(
                "besc", path(["ADBE Effect Parade", "ADBE Tile", "ADBE Tile-0004"]), node[len(prefix) :]
            ),
            tag="RIFX",
        )
    )
    doc = inspect_file(f)
    assert any(
        w.code == "PROFILE_DIMENSIONS" for p in doc.presets[0].effects[0].parameters for w in p.warnings
    )
    assert preview(doc)[1].status == "UNSUPPORTED"


def test_single_discrete_key_retains_value_time_and_normalizes_unused_interp(tmp_path):
    f = tmp_path / "bool.ffx"
    f.write_bytes(selected_ffx([("ADBE Tile", "ADBE Tile-0006", 1, 4, [(0, 1, 1)])]))
    payload, report = preview(inspect_file(f))
    plan = validate_plan(payload)
    prop = plan.effects[0].properties[0]
    assert prop.value is True and prop.keyframes[0].value is True
    assert prop.keyframes[0].seconds == 0
    assert prop.keyframes[0].in_interp[0].value == "Hold"
    assert report.effects[0].transformations


@pytest.mark.parametrize(
    "field,value", [("source_effect_index", None), ("enabled", False), ("application", "create")]
)
def test_patch_contract_is_validated(tmp_path, field, value):
    f = tmp_path / "selected.ffx"
    f.write_bytes(selected_ffx([("ADBE Tile", "ADBE Tile-0004", 240, 1)]))
    plan = validate_plan(preview(inspect_file(f))[0])
    setattr(plan.effects[0], field, value)
    plan.commands = preview_commands(plan)
    with pytest.raises(BridgeError):
        validate_plan(plan.model_dump(mode="json"))


def test_duplicate_existing_binding_is_rejected(tmp_path):
    f = tmp_path / "selected.ffx"
    f.write_bytes(selected_ffx([("ADBE Tile", "ADBE Tile-0004", 240, 1)]))
    plan = validate_plan(preview(inspect_file(f))[0])
    second = copy.deepcopy(plan.effects[0])
    second.ref = "fx1"
    plan.effects.append(second)
    plan.commands = preview_commands(plan)
    with pytest.raises(BridgeError, match="duplicado"):
        validate_plan(plan.model_dump(mode="json"))


def test_v2_creation_plan_before_binding_extension_stays_valid(ffx_file):
    payload, _ = preview(inspect_file(ffx_file))
    payload["version"] = 2
    for effect in payload["effects"]:
        effect.pop("application")
        effect.pop("source_effect_index")
        effect.pop("plugin_fingerprint")
    plan = validate_plan(payload)
    assert plan.version == 2 and plan.effects[0].application == "create"
    assert plan.effects[0].source_effect_index is None


def test_block_count_mismatch_never_promotes_selected_properties(tmp_path):
    data = selected_ffx([("ADBE Tile", "ADBE Tile-0004", 240, 1)])
    # Add an unmatched path; lengths are rebuilt instead of corrupting the container.
    from craft_bridge.core.safety import Budget, Limits
    from craft_bridge.parsers.ffx.rifx import parse_rifx

    tree, _ = parse_rifx(data, Budget(Limits()))
    besc = tree.children[0]
    raw = bytes(besc.data[4:]) + path(["ADBE Effect Parade", "ADBE Tile", "ADBE Tile-0005"])
    f = tmp_path / "mismatch.ffx"
    f.write_bytes(container("FaFX", chunk("LIST", b"besc" + raw), tag="RIFX"))
    doc = inspect_file(f)
    assert all(e.feature == "property" for e in doc.presets[0].effects)
    assert any(w.code == "BLOCK_COUNT" for w in doc.warnings)


def color_key(ticks=0, code=1, flags=1, spatial=2, values=(255, 120, 60, 30)):
    return struct.pack(
        ">iBBHII5d12d", ticks, code, code, flags, spatial, 0, 0, 0, 0, 0, 0, *values, *([0] * 8)
    )


def test_color_single_ease_layout_keeps_argb_linear_values():
    from craft_bridge.core.safety import Budget, Limits
    from craft_bridge.parsers.ffx.keyframes import decode_keyframes

    records = color_key() + color_key(30720, 3, values=(127.5, 255, 0, 63.75))
    header = struct.pack(">13I", 0xD00BEE, 0, 2, 1, 152, 4, 1, 4, 0, 0, 0, 0, 0)
    keys = decode_keyframes(
        memoryview(header),
        memoryview(records),
        dimensions=4,
        stream_flags=6,
        time_base=30720,
        budget=Budget(Limits()),
        value_kind="color",
    )
    assert keys[0].value == [255, 120, 60, 30]
    assert keys[1].seconds == 1 and keys[1].out_interp[0].value == "Hold"
    one_header = bytearray(header)
    struct.pack_into(">I", one_header, 8, 1)
    for invalid in [color_key(code=2), color_key(flags=17), color_key(spatial=3)]:
        with pytest.raises(BridgeError):
            decode_keyframes(
                memoryview(one_header),
                memoryview(invalid),
                dimensions=4,
                stream_flags=6,
                time_base=30720,
                budget=Budget(Limits()),
                value_kind="color",
            )
    with pytest.raises(BridgeError, match="152"):
        decode_keyframes(
            memoryview(header),
            memoryview(records[:-1]),
            dimensions=4,
            stream_flags=6,
            time_base=30720,
            budget=Budget(Limits()),
            value_kind="color",
        )
