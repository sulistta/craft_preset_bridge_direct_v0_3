"""Regenera dados declarativos auditados; IDs e limites dos commits de references.json."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REF = json.loads((ROOT / "docs/references.json").read_text())


def f(lo=-1e9, hi=1e9):
    return {"kind": "Float", "min": lo, "max": hi}


def b():
    return {"kind": "Bool"}


def c(n):
    return {"kind": "Choice", "min": 0, "max": n - 1}


def p():
    return {"kind": "Vec2"}


film = {
    "gaussian_blur": {"blurriness": f(0, 3000), "dimensions": c(3), "repeat_edge": b()},
    "transform": {
        "anchor": p(),
        "position": p(),
        "uniform_scale": b(),
        "scale_height": f(0, 10000),
        "scale_width": f(0, 10000),
        "skew": f(-70, 70),
        "skew_axis": f(),
        "rotation": f(),
        "opacity": f(0, 100),
        "shutter_angle": f(0, 360),
    },
}
film_catalog = {}
for native_effect in json.loads((ROOT / "docs/catalogs/filmcraft.json").read_text()):
    params = {}
    for param in native_effect["params"]:
        native_kind = param["kind"]
        kind = native_kind if isinstance(native_kind, str) else next(iter(native_kind))
        spec = {"native_ui": kind, "default": param["default"], "animatable": param["animatable"]}
        if kind == "Float":
            spec.update(kind="Float", min=native_kind[kind]["min"], max=native_kind[kind]["max"])
        elif kind == "Choice":
            options = native_kind[kind]
            spec.update(kind="Choice", min=0, max=len(options) - 1, options=options)
        else:
            spec["kind"] = {"Point": "Vec2", "Angle": "Float"}.get(kind, kind)
        params[param["id"]] = spec
    film_catalog[native_effect["id"]] = params
# Keep reviewed limits without discarding native animation capabilities/defaults.
for effect_id, params in film.items():
    for param_id, spec in params.items():
        film_catalog[effect_id][param_id].update(spec)
film = film_catalog
effect = {
    "ec.blur.gaussian": {"blurriness": f(0, 3000), "dimensions": c(3), "repeatEdge": b()},
    "ec.blur.directional": {"direction": f(), "length": f(0, 1000)},
    "ec.blur.sharpen": {"amount": f(0, 500)},
    "ec.blur.unsharp": {"amount": f(0, 500), "radius": f(0.1, 500), "threshold": f(0, 255)},
    "ec.color.brightnesscontrast": {"brightness": f(-150, 150), "contrast": f(-100, 100), "useLegacy": b()},
    "ec.distort.transform": {
        "anchor": p(),
        "position": p(),
        "uniform": b(),
        "scaleHeight": f(-10000, 10000),
        "scaleWidth": f(-10000, 10000),
        "skew": f(-70, 70),
        "skewAxis": f(),
        "rotation": f(),
        "opacity": f(0, 100),
        "useCompositionShutterAngle": b(),
        "shutterAngle": f(0, 720),
        "sampling": c(2),
    },
}
native_specs = json.loads((ROOT / "docs/catalogs/effectcraft.json").read_text())
native_catalog = {}
for native_effect in native_specs:
    params = {}
    for param in native_effect["params"]:
        ui = param["ui"]
        kind = ui["kind"]
        spec = {"native_ui": kind, "default": param["default"]}
        if kind == "Slider":
            spec.update(kind="Float", min=ui["min"], max=ui["max"])
        elif kind == "Popup":
            spec.update(kind="Choice", min=0, max=len(ui["options"]) - 1, options=ui["options"])
        elif kind == "Angle":
            spec["kind"] = "Float"
        elif kind == "Hidden" and isinstance(param["default"], str):
            # Evidence comes from the real default Value::Str, not the Hidden UI.
            spec["kind"] = "Text"
            spec["animatable"] = False  # Static-only adapter profile.
        else:
            spec["kind"] = {
                "Checkbox": "Bool",
                "Point": "Vec2",
                "Point3": "Vec3",
                "Color": "Color",
                "Text": "Text",
                "Layer": "Layer",
                "Mask": "Mask",
            }.get(kind, "Opaque")
        params[param["id"]] = spec
    native_catalog[native_effect["id"]] = params
# Preserve stricter, manually reviewed profiles for the original mappings.
native_catalog.update(effect)
effect = native_catalog
for channel in ("rgb", "red", "green", "blue", "alpha"):
    effect["ec.color.curves"][channel]["text_format"] = "curve-points"
cat = {
    k: {"commit": REF[k]["commit"], "effects": v} for k, v in [("filmcraft", film), ("effectcraft", effect)]
}
M = []


def mapping(src, fmt, target, fx, params, validation, evidence):
    M.append(
        {
            "source": src,
            "source_format": fmt,
            "target": target,
            "effect": fx,
            "params": params,
            "validation": validation,
            "evidence": evidence,
            "target_commit": REF[target]["commit"],
        }
    )


def rules(d, types=None, ops=None):
    return {
        src: {
            "target": dst,
            "kind": (types or {}).get(src, "Float"),
            "operation": (ops or {}).get(src, "identity"),
        }
        for src, dst in d.items()
    }


mapping(
    "AE.ADBE Gaussian Blur 2",
    "prfpset",
    "filmcraft",
    "gaussian_blur",
    rules({"1": "blurriness", "2": "dimensions", "3": "repeat_edge"}, {"2": "Choice", "3": "Bool"}),
    "real-source; target-schema",
    "notoow: Gaussian Blur samples; filmcraft project/effect.rs",
)
mapping(
    "AE.ADBE Geometry2",
    "prfpset",
    "filmcraft",
    "transform",
    rules(
        {
            "1": "anchor",
            "2": "position",
            "11": "uniform_scale",
            "3": "scale_height",
            "4": "scale_width",
            "5": "skew",
            "6": "skew_axis",
            "7": "rotation",
            "8": "opacity",
            "10": "shutter_angle",
        },
        {"1": "Vec2", "2": "Vec2", "11": "Bool"},
        {"1": "normalized_to_pixels", "2": "normalized_to_pixels"},
    ),
    "real-source-partial; target-schema",
    "notoow: 변형.prfpset; filmcraft project/effect.rs; source 9 and 12 intentionally unsupported",
)
for src, fx, ps, types in [
    (
        "ADBE Gaussian Blur 2",
        "ec.blur.gaussian",
        {"1": "blurriness", "2": "dimensions", "3": "repeatEdge"},
        {"2": "Choice", "3": "Bool"},
    ),
    ("ADBE Directional Blur", "ec.blur.directional", {"1": "direction", "2": "length"}, {}),
    ("ADBE Sharpen", "ec.blur.sharpen", {"1": "amount"}, {}),
    ("ADBE Unsharp Mask2", "ec.blur.unsharp", {"1": "amount", "2": "radius", "3": "threshold"}, {}),
    (
        "ADBE Brightness & Contrast 2",
        "ec.color.brightnesscontrast",
        {"1": "brightness", "2": "contrast", "3": "useLegacy"},
        {"3": "Bool"},
    ),
]:
    full = {src + "-" + k.zfill(4): v for k, v in ps.items()}
    t = {src + "-" + k.zfill(4): v for k, v in types.items()}
    ops = {src + "-0002": "minus_one"} if "Gaussian" in src else {}
    mapping(
        src,
        "ffx",
        "effectcraft",
        fx,
        rules(full, t, ops),
        "real-source; protocol-mock"
        if src in ("ADBE Sharpen", "ADBE Unsharp Mask2", "ADBE Brightness & Contrast 2")
        else "synthetic-only; source-parameter-ids-require-real-fixture",
        "FFX parT naming; sample_1/user corpus for real-source; EffectCraft effects misc.rs/color_fx.rs",
    )
# FFX points are normalized; EffectCraft stores effect points in layer pixels.
src = "ADBE Geometry2"
ps = {
    "1": "anchor",
    "2": "position",
    "11": "uniform",
    "3": "scaleHeight",
    "4": "scaleWidth",
    "5": "skew",
    "6": "skewAxis",
    "7": "rotation",
    "8": "opacity",
    "9": "useCompositionShutterAngle",
    "10": "shutterAngle",
    "12": "sampling",
}
full = {src + "-" + k.zfill(4): v for k, v in ps.items()}
types = {
    src + "-" + k.zfill(4): v
    for k, v in {"1": "Vec2", "2": "Vec2", "11": "Bool", "9": "Bool", "12": "Choice"}.items()
}
mapping(
    src,
    "ffx",
    "effectcraft",
    "ec.distort.transform",
    rules(
        full,
        types,
        {
            src + "-0012": "minus_one",
            src + "-0001": "normalized_to_pixels",
            src + "-0002": "normalized_to_pixels",
        },
    ),
    "real-source-static; protocol-mock",
    "User corpus Geometry2; EffectCraft effects/lib.rs default_value and distort.rs: pixel points; 0-based sampling",
)


def native_mapping(
    source,
    target,
    parameters,
    types=None,
    operations=None,
    validation="real-source; native-engine-param-roundtrip; per-parameter-limitations",
):
    full = {source + "-" + str(k).zfill(4): v for k, v in parameters.items()}
    typed = {source + "-" + str(k).zfill(4): v for k, v in (types or {}).items()}
    ops = {source + "-" + str(k).zfill(4): v for k, v in (operations or {}).items()}
    mapping(
        source,
        "ffx",
        "effectcraft",
        target,
        rules(full, typed, ops),
        validation,
        "Private corpus: parT match IDs/types/menu and tdbs values; official EffectCraft ParamSpec snapshot at pinned commit; docs/effect-expansion.md",
    )


native_mapping(
    "ADBE Tile",
    "ec.stylize.motiontile",
    {
        1: "tileCenter",
        2: "tileWidth",
        3: "tileHeight",
        4: "outputWidth",
        5: "outputHeight",
        6: "mirrorEdges",
        7: "phase",
        8: "horizontalPhaseShift",
    },
    {1: "Vec2", 6: "Bool", 8: "Bool"},
    {1: "normalized_to_pixels"},
)
native_mapping("ADBE Noise2", "ec.noise.noise", {1: "amount", 2: "color", 3: "clip"}, {2: "Bool", 3: "Bool"})
for source, target, last in [
    ("ADBE Noise HLS2", "ec.noise.noisehls", "noisePhase"),
    ("ADBE Noise HLS Auto2", "ec.noise.noisehlsauto", "noiseAnimationSpeed"),
]:
    native_mapping(
        source,
        target,
        {1: "noise", 2: "hue", 3: "lightness", 4: "saturation", 5: "grainSize", 6: last},
        {1: "Choice"},
        {1: "minus_one"},
    )
native_mapping(
    "ADBE Wave Warp",
    "ec.distort.wavewarp",
    {1: "waveType", 2: "height", 3: "width", 4: "direction", 5: "speed", 6: "pinning", 7: "phase"},
    {1: "Choice", 6: "Choice"},
    {1: "minus_one", 6: "minus_one"},
)
native_mapping(
    "ADBE Optics Compensation",
    "ec.distort.opticscompensation",
    {
        1: "fieldOfView",
        2: "reverseLensDistortion",
        3: "fovOrientation",
        4: "viewCenter",
        5: "optimalPixels",
        6: "resize",
    },
    {2: "Bool", 3: "Choice", 4: "Vec2", 5: "Bool", 6: "Choice"},
    {3: "minus_one", 4: "normalized_to_pixels", 6: "minus_one"},
)
native_mapping(
    "ADBE Upscale",
    "ec.distort.upscale",
    {1: "scale", 2: "reduceNoise", 7: "detail", 5: "alpha"},
    {5: "Choice"},
    {5: "minus_one"},
)
native_mapping(
    "ADBE CameraShakeDeblur",
    "ec.blur.camerashakedeblur",
    {1: "blurDuration", 2: "deblurMethod", 3: "strength", 4: "shakeSensitivity"},
    {2: "Choice"},
    {2: "minus_one"},
)
native_mapping(
    "ADBE Tritone",
    "ec.color.tritone",
    {1: "highlights", 2: "midtones", 3: "shadows", 4: "blend"},
    {1: "Color", 2: "Color", 3: "Color"},
    {1: "argb255_to_rgba", 2: "argb255_to_rgba", 3: "argb255_to_rgba"},
)
native_mapping(
    "ADBE Tint",
    "ec.color.tint",
    {1: "black", 2: "white", 3: "amount"},
    {1: "Color", 2: "Color"},
    {1: "argb255_to_rgba", 2: "argb255_to_rgba"},
)
native_mapping(
    "ADBE 4ColorGradient",
    "ec.generate.fourcolor",
    {
        1: "positionsColors/point1",
        2: "positionsColors/color1",
        3: "positionsColors/point2",
        4: "positionsColors/color2",
        5: "positionsColors/point3",
        6: "positionsColors/color3",
        7: "positionsColors/point4",
        8: "positionsColors/color4",
        9: "blend",
        10: "jitter",
        13: "opacity",
        14: "blendingMode",
    },
    {**{n: "Vec2" for n in [1, 3, 5, 7]}, **{n: "Color" for n in [2, 4, 6, 8]}, 14: "Choice"},
    {
        **{n: "normalized_to_pixels" for n in [1, 3, 5, 7]},
        **{n: "argb255_to_rgba" for n in [2, 4, 6, 8]},
        14: "minus_one",
    },
)
native_mapping(
    "ADBE Exposure2",
    "ec.color.exposure",
    {
        1: "channels",
        3: "master/exposure",
        4: "master/offset",
        5: "master/gamma",
        8: "red/redExposure",
        9: "red/redOffset",
        10: "red/redGamma",
        13: "green/greenExposure",
        14: "green/greenOffset",
        15: "green/greenGamma",
        18: "blue/blueExposure",
        19: "blue/blueOffset",
        20: "blue/blueGamma",
        22: "bypassLinearLight",
    },
    {1: "Choice", 22: "Bool"},
    {1: "minus_one"},
    validation="real-source; native-engine-param-roundtrip",
)
native_mapping(
    "ADBE Black&White",
    "ec.color.blackwhite",
    {1: "reds", 2: "yellows", 3: "greens", 4: "cyans", 5: "blues", 6: "magentas", 7: "tint", 8: "tintColor"},
    {7: "Bool", 8: "Color"},
    {8: "argb255_to_rgba"},
    validation="real-source; native-engine-param-roundtrip",
)
native_mapping(
    "ADBE Invert",
    "ec.channel.invert",
    {1: "channel", 2: "blend"},
    {1: "Choice"},
    validation="real-source; native-engine-param-roundtrip",
)
M[-1]["params"]["ADBE Invert-0001"].update(
    operation="enum_map",
    choices={1: 0, 2: 1, 3: 2, 4: 3, 6: 4, 7: 5, 8: 6, 9: 7, 11: 8, 12: 9, 13: 10, 14: 11, 16: 12},
)
native_mapping(
    "ADBE Box Blur2",
    "ec.blur.fastbox",
    {1: "radius", 2: "iterations", 3: "dimensions", 4: "repeatEdge"},
    {3: "Choice", 4: "Bool"},
    {3: "minus_one"},
    validation="real-source; native-engine-param-roundtrip",
)

# aRbp contains all channels; p4..6 (Hue/Saturation) and p3..7 (Levels)
# are UI shadows and intentionally have no rendering rule. See arbitrary.py.
src = "ADBE HUE SATURATION"
params = rules(
    {
        src + "-" + str(i).zfill(4): target
        for i, target in {
            2: "channelControl",
            7: "colorize",
            8: "colorizeHue",
            9: "colorizeSaturation",
            10: "colorizeLightness",
        }.items()
    },
    {src + "-0002": "Choice", src + "-0007": "Bool"},
    {src + "-0002": "minus_one"},
)
for target in ["hue", "saturation", "lightness"] + [
    prefix + suffix
    for prefix in ("reds", "yellows", "greens", "cyans", "blues", "magentas")
    for suffix in ("RangeStart", "RangeEnd", "StartFalloff", "EndFalloff", "Hue", "Saturation", "Lightness")
]:
    params[src + "-0003/" + target] = {"target": target, "kind": "Float"}
mapping(
    src,
    "ffx",
    "effectcraft",
    "ec.color.huesaturation",
    params,
    "real-source-static; native-engine-param-roundtrip",
    "py-aep aRbp 180-byte BE45i; private real blobs; EffectCraft color_fx.rs HueRange and specs",
)

src = "ADBE Easy Levels2"
params = rules({src + "-0001": "channel"}, {src + "-0001": "Choice"}, {src + "-0001": "minus_one"})
for prefix in ("", "red", "green", "blue", "alpha"):
    for suffix in ("inBlack", "inWhite", "gamma", "outBlack", "outWhite"):
        target = prefix + suffix[0].upper() + suffix[1:] if prefix else suffix
        params[src + "-0002/" + target] = {"target": target, "kind": "Float"}
    for i, suffix in ((8, "clipToOutputBlack"), (9, "clipToOutputWhite")):
        target = prefix + suffix[0].upper() + suffix[1:] if prefix else suffix
        source = src + "-" + str(i).zfill(4) + ("/" + prefix if prefix else "")
        # "Off for 32bpc" needs source depth context and differs in the native
        # renderer; it is refused rather than changed silently to On.
        params[source] = {
            "target": target,
            "kind": "Choice",
            "operation": "enum_map",
            "choices": {1: 1, 2: 0},
        }
mapping(
    src,
    "ffx",
    "effectcraft",
    "ec.color.levels",
    params,
    "real-source-static; native-engine-param-roundtrip; 32bpc-clip-option-unsupported",
    "py-aep aRbp 108-byte magic/version/BE25f; private real blobs; EffectCraft color_fx.rs levels_channel_ids/LEVELS_CLIP",
)

# Lumetri's native renderer does not expose the source's group-enable switches.
# A rule only applies when the relevant source group is proven active/static.
native_mapping(
    "ADBE Lumetri",
    "ec.color.lumetri",
    {
        62: "highDynamicRange",
        63: "basicCorrection/tone/hdrWhite",
        64: "basicCorrection/tone/hdrSpecular",
        5: "basicCorrection/inputLut",
        7: "basicCorrection/whiteBalance/temperature",
        8: "basicCorrection/whiteBalance/tint",
        11: "basicCorrection/tone/exposure",
        12: "basicCorrection/tone/contrast",
        13: "basicCorrection/tone/highlights",
        14: "basicCorrection/tone/shadows",
        15: "basicCorrection/tone/whites",
        16: "basicCorrection/tone/blacks",
        20: "basicCorrection/saturation",
        25: "creative/look",
        26: "creative/lookIntensity",
        28: "creative/adjustments/fadedFilm",
        29: "creative/adjustments/sharpen",
        30: "creative/adjustments/vibrance",
        31: "creative/adjustments/creativeSaturation",
        33: "creative/adjustments/tintBalance",
        51: "vignette/vignetteAmount",
        52: "vignette/vignetteMidpoint",
        53: "vignette/vignetteRoundness",
        54: "vignette/vignetteFeather",
    },
    {62: "Bool", 5: "Choice", 25: "Choice"},
    validation="real-source-static; native-engine-param-roundtrip; group-conditions; opaque-curves-LUTs-wheels-unsupported",
)
for source_id, rule in M[-1]["params"].items():
    target = rule["target"]
    if target.startswith("basicCorrection/"):
        rule["requires"] = {"ADBE Lumetri-0003": True}
    elif target.startswith("creative/"):
        rule["requires"] = {"ADBE Lumetri-0023": True, "ADBE Lumetri-0026": 100.0}
    elif target.startswith("vignette/"):
        rule["requires"] = {"ADBE Lumetri-0050": True}
    if source_id in ("ADBE Lumetri-0005", "ADBE Lumetri-0025"):
        # Built-in Look/LUT names in the engines are different. Only None is
        # verified here; source Custom requires its actual LUT data and version.
        rule.update(operation="enum_map", choices={1: 0})

native_mapping(
    "ADBE Radial Blur",
    "ec.blur.radial",
    {1: "amount", 2: "center", 3: "type", 4: "antialiasing"},
    {2: "Vec2", 3: "Choice", 4: "Choice"},
    {2: "normalized_to_pixels", 3: "minus_one"},
    validation="real-source; native-engine-param-roundtrip; low-antialias-and-seed-unsupported",
)
# The destination renderer always anti-aliases, regardless of its UI choice.
# Only source High is representable. Amount > 100 is refused by native bounds.
M[-1]["params"]["ADBE Radial Blur-0004"].update(operation="enum_map", choices={2: 1})
native_mapping(
    "CC Radial Blur",
    "ec.blur.ccradial",
    {1: "type", 2: "amount", 3: "quality", 4: "center"},
    {1: "Choice", 4: "Vec2"},
    {4: "normalized_to_pixels"},
    validation="real-source; native-engine-param-roundtrip; scratch-unsupported",
)
# Source index 4 is a separator; 6 is Scratch, absent from the native renderer.
M[-1]["params"]["CC Radial Blur-0001"].update(
    operation="enum_map", choices={1: 0, 2: 1, 3: 2, 5: 3, 7: 4}
)
native_mapping(
    "ADBE Camera Lens Blur",
    "ec.blur.cameralens",
    {
        1: "blurRadius",
        3: "irisProperties/irisShape",
        4: "irisProperties/irisRoundness",
        5: "irisProperties/irisAspectRatio",
        6: "irisProperties/irisRotation",
        7: "irisProperties/diffractionFringe",
        11: "blurMap/channel",
        12: "blurMap/placement",
        13: "blurMap/blurFocalDistance",
        14: "blurMap/invertBlurMap",
        17: "highlight/specularBrightness",
        18: "highlight/specularThreshold",
        19: "highlight/highlightSaturation",
        21: "repeatEdge",
        22: "useLinear",
    },
    {3: "Choice", 11: "Choice", 12: "Choice", 14: "Bool", 21: "Bool", 22: "Bool"},
    {12: "minus_one", 18: "times_255"},
    validation="real-source; native-engine-param-roundtrip; layer-reference-and-nonzero-focal-distance-unsupported",
)
lens = M[-1]["params"]
lens["ADBE Camera Lens Blur-0003"].update(operation="enum_map", choices={i: i - 1 for i in range(1, 9)})
# Native Color is a combined channel; it does not represent the separate RGB options.
lens["ADBE Camera Lens Blur-0011"].update(operation="enum_map", choices={1: 0, 5: 1})
# Nonzero focal-distance units are not established by the available corpus.
lens["ADBE Camera Lens Blur-0013"]["requires"] = {"ADBE Camera Lens Blur-0013": 0.0}
M[-1]["evidence"] += "; Adobe Blur & Sharpen documentation: highlight Threshold 0..1; native blur2.rs divides by 255"
native_mapping(
    "CC Scale Wipe",
    "ec.transition.ccscalewipe",
    {1: "stretch", 2: "center", 3: "direction"},
    {2: "Vec2"},
    {2: "normalized_to_pixels"},
    validation="real-source; native-engine-param-roundtrip; no-visual-comparison",
)

mapping(
    "ADBE CurvesCustom",
    "ffx",
    "effectcraft",
    "ec.color.curves",
    {"ADBE CurvesCustom-0001/" + channel: {"target": channel, "kind": "Text"}
     for channel in ("rgb", "red", "green", "blue", "alpha")},
    "real-source-static; native-engine-param-roundtrip; LUT-resampling-loss-explicit",
    "py-aep aRbp 1644-byte BE Curves v1; 256-sample/channel LUT; EffectCraft color2.rs Curve::parse/eval; docs/decisions/005-curves-lut-transfer.md",
)

mapping(
    "CS Color Neutralizer", "ffx", "effectcraft", "ec.color.cccolorneutralizer",
    {
        **{f"CS Color Neutralizer/rgb/{tone}": {"target": tone + "Balance", "kind": "Color"}
           for tone in ("shadows", "midtones", "highlights")},
        "CS Color Neutralizer-0019": {"target": "pinning", "kind": "Float"},
        "CS Color Neutralizer-0020": {"target": "blendWOriginal", "kind": "Float"},
    },
    "real-source-pinning-blend; native-engine-param-roundtrip; RGB-percent-profile-synthetic; approximate-tonal-algorithm; default-black-white-final-view-only",
    "Cycore FX HD 1.8.9 Manual pp12-13; pard percent/UI-only flags; native color3.rs Balance-Unbalance; docs/decisions/006-neutralizer-rgb-transfer.md",
)
for rule in M[-1]["params"].values():
    rule["requires"] = {
        "CS Color Neutralizer-0022": 1.0,
        "CS Color Neutralizer-0023": 0.0,
        "CS Color Neutralizer-0024": 100.0,
    }

for entry in M:
    source = entry["source"]
    if source == "ADBE Wave Warp":
        entry["params"][source + "-0006"].update(
            operation="enum_map", choices={1: 0, 2: 1, 3: 2, 5: 3, 6: 4, 7: 5, 8: 6, 10: 7, 11: 8}
        )
    elif source == "ADBE 4ColorGradient":
        entry["params"][source + "-0014"].update(
            operation="enum_map",
            choices={
                1: 0,
                2: 1,
                4: 2,
                5: 3,
                6: 4,
                7: 5,
                8: 6,
                9: 7,
                11: 8,
                12: 9,
                14: 10,
                15: 11,
                16: 12,
                17: 13,
                19: 14,
                20: 15,
                21: 16,
                22: 17,
            },
        )
    elif source == "ADBE Upscale":
        # Source "Detail-preserving" has no equivalent in the destination alpha menu.
        entry["params"][source + "-0005"].update(operation="enum_map", choices={2: 1})
for name, value in [
    ("catalog.json", cat),
    ("builtin.json", {"format": "craftbridge.mappings", "version": 1, "name": "builtin-1", "mappings": M}),
]:
    (ROOT / "src/craft_bridge/mappings" / name).write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    )
