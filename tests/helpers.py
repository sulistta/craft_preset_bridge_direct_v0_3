"""Fixtures inteiramente sintéticas, não salvas por Adobe."""

import struct


def chunk(tag: str, body: bytes) -> bytes:
    return tag.encode("ascii") + struct.pack(">I", len(body)) + body + b"\0" * (len(body) % 2)


def container(form: str, *children: bytes, tag="LIST") -> bytes:
    return chunk(tag, form.encode("ascii") + b"".join(children))


def string(text: str) -> bytes:
    raw = text.encode("utf-8")
    return b"Utf8" + struct.pack(">I", len(raw)) + raw


def path(names: list[str], index: int = 0) -> bytes:
    return container(
        "tdsp",
        *(
            container(
                "tdsi",
                chunk("tdix", struct.pack(">I", index if i else 0xFFFFFFFF)),
                chunk("tdmn", name.encode() + b"\0"),
            )
            for i, name in enumerate(names)
        ),
    )


def stream(match: str, value=15.0, kind=1, dims=1, keys=None, base=30720, flags=1, display_flags=0, ui_flags=0) -> tuple[bytes, bytes]:
    descriptor = bytearray(148)
    struct.pack_into(">I", descriptor, 12, kind)
    struct.pack_into(">I", descriptor, 4, ui_flags)
    if kind == 10:
        struct.pack_into(">H", descriptor, 0x7E, display_flags)
    descriptor[16 : 16 + len(match)] = match.encode()
    meta = chunk("tdmn", match.encode() + b"\0") + chunk("pard", bytes(descriptor))
    header = bytearray(124)
    struct.pack_into(">HHHH", header, 0, 0xDB99, dims, flags, 0)
    struct.pack_into(">I", header, 12, base)
    header[68] = int(keys is not None)
    if keys is None:
        values = value if isinstance(value, list) else [value]
        body = chunk("cdat", struct.pack(">" + "d" * len(values), *values) + b"\0" * (dims * 32))
    else:
        records = b""
        for ticks, vals, interp in keys:
            vals = vals if isinstance(vals, list) else [vals]
            records += struct.pack(">iBBH", ticks, interp, interp, 0)
            records += struct.pack(
                ">" + "d" * (5 * dims),
                *(vals + [0.0] * dims + [1 / 3] * dims + [0.0] * dims + [1 / 3] * dims),
            )
        lhd = struct.pack(
            ">13I",
            0xD00BEE,
            0,
            len(keys),
            max(1, (len(keys) + 3) // 4),
            8 + 40 * dims,
            4,
            1,
            max(4, len(keys)),
            0,
            0,
            0,
            0,
            0,
        )
        body = container("list", chunk("lhd3", lhd), chunk("ldat", records))
    node = chunk("tdmn", match.encode() + b"\0") + container(
        "tdbs",
        chunk("tdsb", struct.pack(">I", 1)),
        chunk("tdsn", string(match)),
        chunk("tdb4", bytes(header)),
        body,
    )
    return meta, node


def ffx(effects=None, sentinel_first=False, effect_indices=None, property_paths=None) -> bytes:
    effects = effects or [("ADBE Sharpen", [("ADBE Sharpen-0001", 15.0, 1)])]
    indices, snapshots = [], []
    for i, (name, parameters) in enumerate(effects):
        metas, nodes = [], []
        for param in parameters:
            meta, node = stream(*param)
            metas.append(meta)
            nodes.append(node)
        indices.append(
            path(["ADBE Effect Parade", name], effect_indices[i] if effect_indices is not None else i)
        )
        snapshots.append(
            container(
                "sspc",
                chunk("fnam", string(name)),
                container("parT", *metas),
                container("tdgp", chunk("tdsb", struct.pack(">I", 1)), *nodes),
            )
        )
    sentinel = path(["ADBE End of path sentinel"])
    indices = [*(property_paths or []), *indices]
    indices = [sentinel, *indices] if sentinel_first else [*indices, sentinel]
    return container(
        "FaFX",
        chunk("head", struct.pack(">4I", 3, 93, 43, 0)),
        container("besc", chunk("beso", b"\0" * 56), *indices, *snapshots),
        tag="RIFX",
    )


def premiere(effects=1, unknown=False, animation=False) -> bytes:
    objects = []
    refs = []
    for i in range(effects):
        f, c, p = 10 + i * 10, 11 + i * 10, 12 + i * 10
        refs.append(f'<FilterPreset Index="{i}" ObjectRef="{f}"/>')
        match = "UNKNOWN Plugin" if unknown else "AE.ADBE Gaussian Blur 2"
        objects.append(f'''<FilterPreset ObjectID="{f}"><FilterMatchName>{match}</FilterMatchName><Component ObjectRef="{c}"/><AnchorInPoint>0</AnchorInPoint><AnchorOutPoint>254016000000</AnchorOutPoint><Type>1</Type></FilterPreset>
<VideoFilterComponent ObjectID="{c}"><Component><DisplayName>Blur original {i}</DisplayName><Bypass>false</Bypass><Params><Param Index="0" ObjectRef="{p}"/></Params></Component></VideoFilterComponent>
<VideoComponentParam ObjectID="{p}"><ParameterID>1</ParameterID><Name>Blurriness</Name><ParameterControlType>8</ParameterControlType><StartKeyframe>-91445760000000000,25.,0,0,0,0,0,0</StartKeyframe><CurrentValue>0.</CurrentValue><IsTimeVarying>{str(animation).lower()}</IsTimeVarying><Keyframes>{"0,25,0,0,0,0,0,0;254016000000,0,0,0,0,0,0,0" if animation else ""}</Keyframes></VideoComponentParam>''')
    return (
        '<?xml version="1.0"?><PremiereData Version="3"><TreeItem><TreeItemBase><Name>Blur original</Name><Data ObjectRef="1"/></TreeItemBase></TreeItem><FilterPresetItem ObjectID="1"><FilterPresets>'
        + "".join(refs)
        + "</FilterPresets></FilterPresetItem>"
        + "".join(objects)
        + "</PremiereData>"
    ).encode()
