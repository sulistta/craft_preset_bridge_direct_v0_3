"""Validação opt-in; nunca baixa nem redistribui os arquivos do usuário."""

import os
from pathlib import Path

import pytest

from craft_bridge.core.pipeline import inspect_file, preview
from craft_bridge.core.safety import Budget, Limits
from craft_bridge.parsers.ffx.arbitrary import CURVES, HUE, LEVELS, decode_curves, decode_numeric
from craft_bridge.parsers.ffx.rifx import decode_string, parse_rifx

pytestmark = [
    pytest.mark.real,
    pytest.mark.skipif(
        os.environ.get("CRAFT_REAL_FIXTURES") != "1", reason="Fixtures reais opt-in: CRAFT_REAL_FIXTURES=1"
    ),
]
ROOT = Path(__file__).resolve().parents[2]


def test_real_godrays_twenty_five_controls_and_quality_separator():
    import hashlib

    from craft_bridge.extensions import extension_paths
    from craft_bridge.mappings.registry import Registry

    files = sorted((ROOT / "Presets-20261007T230529Z-1-001").rglob("*.ffx"))
    if not files:
        pytest.skip("Pacote privado do usuário ausente")
    registry = Registry(packages=[extension_paths("godrays")[0]])
    mapping = registry.find("ffx", "effectcraft", "PEGR")
    assert mapping is not None
    count = 0
    for file in files:
        before = hashlib.sha256(file.read_bytes()).hexdigest()
        doc = inspect_file(file)
        indices = [i for i, e in enumerate(doc.presets[0].effects) if e.identifier.match_name == "PEGR"]
        if not indices:
            continue
        original_ir = doc.model_dump()
        plan, report = preview(doc, registry=registry)
        assert doc.model_dump() == original_ir and report.status == "PARTIAL"
        converted = [e for e in plan["effects"] if e["source"] == "PEGR"]
        assert len(converted) == len(indices)
        for index, effect in zip(indices, converted, strict=True):
            source = {p.id: p for p in doc.presets[0].effects[index].parameters}
            values = {p["id"]: p["value"] for p in effect["properties"]}
            assert len(values) == 25 and report.effects[index].parameters_converted == 25
            for id, rule in mapping.params.items():
                original = source[id]
                assert original.metadata["animated"] is False and not original.keyframes
                expected = original.value.data
                if rule.operation == "minus_one":
                    expected -= 1
                elif rule.operation == "enum_map":
                    expected = rule.choices[expected]
                assert values[rule.target] == expected
            assert source["PEGR-0015"].metadata["menu"] == ["Draft", "Moderate", "High", "Extreme", "(-", "Custom"]
            assert source["PEGR-0002"].value.unit is None
            assert source["PEGR-0009"].value.unit == "degrees" and source["PEGR-0009"].metadata["hidden"]
            assert any(w.code == "MAPPING_APPROXIMATION" and w.loss for w in report.effects[index].warnings)
            count += 1
        assert hashlib.sha256(file.read_bytes()).hexdigest() == before
    assert count == 1


def test_real_olmdirectional_static_smooth_proves_noise_layer_inactive():
    import hashlib

    from craft_bridge.extensions import extension_paths
    from craft_bridge.mappings.registry import Registry

    files = sorted((ROOT / "Presets-20261007T230529Z-1-001").rglob("*.ffx"))
    if not files:
        pytest.skip("Pacote privado do usuário ausente")
    registry = Registry(packages=[extension_paths("olmdirectional")[0]])
    mapping = registry.find("ffx", "effectcraft", "OLM Directional Blur")
    assert mapping is not None
    count = 0
    for file in files:
        before = hashlib.sha256(file.read_bytes()).hexdigest()
        doc = inspect_file(file)
        indices = [i for i, e in enumerate(doc.presets[0].effects) if e.identifier.match_name == "OLM Directional Blur"]
        if not indices:
            continue
        original_ir = doc.model_dump()
        plan, report = preview(doc, registry=registry)
        assert doc.model_dump() == original_ir
        converted = [e for e in plan["effects"] if e["source"] == "OLM Directional Blur"]
        assert len(converted) == len(indices) and report.status == "PARTIAL"
        for index, effect in zip(indices, converted, strict=True):
            source = {p.id: p for p in doc.presets[0].effects[index].parameters}
            values = {p["id"]: p["value"] for p in effect["properties"]}
            assert len(values) == 15 and values["noise"] == {"layer_ref": None}
            for id, rule in mapping.params.items():
                original = source[id]
                assert not original.keyframes
                if rule.kind == "Layer":
                    assert original.value.kind == "unknown" and original.metadata["kind"] == 0
                    continue
                expected = original.value.data - 1 if rule.operation == "minus_one" else original.value.data
                assert values[rule.target] == expected
            assert values["front"] == 140 and values["angle"] == 106 and values["noise_type"] == 0
            assert source["OLM Directional Blur-0016"].metadata["menu"] == ["Smooth ", " Block ", " Layer"]
            assert any(w.code == "SOURCE_LAYER_INACTIVE" and w.loss for w in report.effects[index].warnings)
            assert any(w.code == "UNDECODED_VALUE" and w.loss for w in report.effects[index].warnings)
            count += 1
        assert hashlib.sha256(file.read_bytes()).hexdigest() == before
    assert count == 1


def test_real_hfhotspots_visible_controls_and_hidden_losses():
    import hashlib

    from craft_bridge.extensions import extension_paths
    from craft_bridge.mappings.registry import Registry

    files = sorted((ROOT / "Presets-20261007T230529Z-1-001").rglob("*.ffx"))
    if not files:
        pytest.skip("Pacote privado do usuário ausente")
    registry = Registry(packages=[extension_paths("hfhotspots")[0]])
    source_id = "com.FXHOME.HitFilm.Hotspots"
    mapping = registry.find("ffx", "effectcraft", source_id)
    assert mapping is not None
    thresholds = []
    for file in files:
        before = hashlib.sha256(file.read_bytes()).hexdigest()
        doc = inspect_file(file)
        indices = [i for i, e in enumerate(doc.presets[0].effects) if e.identifier.match_name == source_id]
        if not indices:
            continue
        plan, report = preview(doc, registry=registry)
        converted = [e for e in plan["effects"] if e["source"] == source_id]
        assert len(converted) == len(indices) and report.status == "PARTIAL"
        for index, effect in zip(indices, converted, strict=True):
            original = {p.id: p for p in doc.presets[0].effects[index].parameters}
            values = {p["id"]: p["value"] for p in effect["properties"]}
            assert len(values) == 5
            for id, rule in mapping.params.items():
                source = original[id]
                assert not source.keyframes
                assert source.metadata["kind"] == (5 if rule.kind == "Color" else 10)
                v = source.value.data
                expected = [v[1] / 255, v[2] / 255, v[3] / 255, v[0] / 255] if rule.kind == "Color" else v
                assert values[rule.target] == expected
            assert values["smooth_source"] == 0 and values["fill_color"] == [0., 0., 0., 1.]
            assert original[source_id + "-0005"].metadata["hidden"]
            assert original[source_id + "-1985"].metadata["menu"] == ["Preset"]
            for suffix in ["0005", "1985"]:
                assert any(w.path == source_id + "-" + suffix and w.loss for w in report.effects[index].warnings)
            thresholds.append(values["threshold"])
        assert hashlib.sha256(file.read_bytes()).hexdigest() == before
    assert sorted(thresholds) == [0.29999999999999993, 0.75]


def test_real_hotspots_requires_explicit_mask_replacement_and_preserves_controls():
    import hashlib

    from craft_bridge.core.resources import SourceLayerBindings
    from craft_bridge.extensions import extension_paths
    from craft_bridge.mappings.registry import Registry

    files = sorted((ROOT / "Presets-20261007T230529Z-1-001").rglob("*.ffx"))
    if not files:
        pytest.skip("Pacote privado do usuário ausente")
    registry = Registry(packages=[extension_paths("hotspots")[0]])
    mapping = registry.find("ffx", "effectcraft", "S_Hotspots")
    assert mapping is not None
    count = 0
    for file in files:
        before = hashlib.sha256(file.read_bytes()).hexdigest()
        doc = inspect_file(file)
        indices = [i for i, e in enumerate(doc.presets[0].effects) if e.identifier.match_name == "S_Hotspots"]
        if not indices:
            continue
        automatic, _ = preview(doc, registry=registry)
        assert not any(e["source"] == "S_Hotspots" for e in automatic["effects"])
        for i in indices:
            bindings = SourceLayerBindings(source_sha256=before, bindings=[{"effect_index": i, "parameter": "S_Hotspots-0001", "layer_ref": None}])
            plan, report = preview(doc, registry=registry, source_layers=bindings)
            effects = [e for e in plan["effects"] if e["source"] == "S_Hotspots"]
            assert len(effects) == 1 and report.status == "PARTIAL"
            original = {p.id: p for p in doc.presets[0].effects[i].parameters}
            values = {p["id"]: p["value"] for p in effects[0]["properties"]}
            assert len(values) == 10 and values["mask"] == {"layer_ref": None}
            for id, rule in mapping.params.items():
                if rule.kind == "Layer":
                    continue
                source = original[id]
                assert not source.keyframes
                v = source.value.data
                expected = v - 1 if rule.operation == "minus_one" else [v[1] / 255, v[2] / 255, v[3] / 255, v[0] / 255] if rule.operation == "argb255_to_rgba" else v
                assert values[rule.target] == expected
            assert values["blur_mask"] == 12 and values["opacity"] == 1
            assert original["S_Hotspots-0055"].metadata["menu"] == ["All Opaque", "Normal", "As Premult"]
            assert any(w.code == "SOURCE_LAYER_REPLACED" and w.loss for w in report.effects[i].warnings)
            for omitted in ["S_Hotspots-0235", "S_Hotspots-0520"]:
                assert any(w.path == omitted and w.loss for w in report.effects[i].warnings)
            count += 1
        assert hashlib.sha256(file.read_bytes()).hexdigest() == before
    assert count == 1


def test_real_pixelencoder_raw_controls_colors_and_menus():
    import hashlib

    from craft_bridge.extensions import extension_paths
    from craft_bridge.mappings.registry import Registry

    files = sorted((ROOT / "Presets-20261007T230529Z-1-001").rglob("*.ffx"))
    if not files:
        pytest.skip("Pacote privado do usuário ausente")
    registry = Registry(packages=[extension_paths("pixelencoder")[0]])
    mapping = registry.find("ffx", "effectcraft", "ADBE PixelEncoder - AEPlugins")
    assert mapping is not None
    count = 0
    for file in files:
        before = hashlib.sha256(file.read_bytes()).hexdigest()
        doc = inspect_file(file)
        indices = [i for i, e in enumerate(doc.presets[0].effects) if e.identifier.match_name == "ADBE PixelEncoder - AEPlugins"]
        if not indices:
            continue
        plan, report = preview(doc, registry=registry)
        effects = [e for e in plan["effects"] if e["source"] == "ADBE PixelEncoder - AEPlugins"]
        assert len(effects) == len(indices) and report.status == "PARTIAL"
        for i, effect in zip(indices, effects, strict=True):
            original = {p.id: p for p in doc.presets[0].effects[i].parameters}
            values = {p["id"]: p["value"] for p in effect["properties"]}
            assert len(values) == 16
            for id, rule in mapping.params.items():
                source = original[id]
                assert not source.keyframes
                v = source.value.data
                expected = v - 1 if rule.operation == "minus_one" else [v[1] / 255, v[2] / 255, v[3] / 255, v[0] / 255] if rule.operation == "argb255_to_rgba" else v
                assert values[rule.target] == expected
                if source.metadata.get("kind") == 10:
                    assert source.value.unit is None
            assert values["pattern"] == 1 and values["behavior"] == 0
            assert values["foreground"] == [1., 0., 0., 1.] and values["background"] == [0., 0., 0., 1.]
            assert values["brightness"] == -50 and values["contrast"] == 150
            assert len(original["ADBE PixelEncoder - AEPlugins-0003"].metadata["menu"]) == 10
            count += 1
        assert hashlib.sha256(file.read_bytes()).hexdigest() == before
    assert count == 1


def test_real_geometric_raw_controls_and_lossy_style_selector():
    import hashlib

    from craft_bridge.extensions import extension_paths
    from craft_bridge.mappings.registry import Registry

    files = sorted((ROOT / "Presets-20261007T230529Z-1-001").rglob("*.ffx"))
    if not files:
        pytest.skip("Pacote privado do usuário ausente")
    registry = Registry(packages=[extension_paths("geometric")[0]])
    mapping = registry.find("ffx", "effectcraft", "SatoriGeometricFilters")
    assert mapping is not None
    count = 0
    for file in files:
        before = hashlib.sha256(file.read_bytes()).hexdigest()
        doc = inspect_file(file)
        indices = [i for i, e in enumerate(doc.presets[0].effects) if e.identifier.match_name == "SatoriGeometricFilters"]
        if not indices:
            continue
        plan, report = preview(doc, registry=registry)
        effects = [e for e in plan["effects"] if e["source"] == "SatoriGeometricFilters"]
        assert len(effects) == len(indices) and report.status == "PARTIAL"
        for i, effect in zip(indices, effects, strict=True):
            original = {p.id: p for p in doc.presets[0].effects[i].parameters}
            values = {p["id"]: p["value"] for p in effect["properties"]}
            assert len(values) == 21
            for id, rule in mapping.params.items():
                source = original[id]
                assert not source.keyframes and source.value.unit is None
                expected = source.value.data - 1 if rule.operation == "minus_one" else source.value.data
                assert values[rule.target] == expected
            assert values["shape"] == 2 and values["strategy"] == 1
            assert values["angle"] == 228 and values["skip"] == 0
            assert original["SatoriGeometricFilters-0004"].metadata["menu"] == ["Line", "Curve", "Triangle", "Square", "Circle", "Rectangle"]
            for omitted in ["SatoriGeometricFilters-0001", "SatoriGeometricFilters-0026"]:
                assert any(w.path == omitted and w.loss for w in report.effects[i].warnings)
            count += 1
        assert hashlib.sha256(file.read_bytes()).hexdigest() == before
    assert count == 1


def test_real_signal_raw_controls_menus_and_untranslated_button():
    import hashlib

    from craft_bridge.extensions import extension_paths
    from craft_bridge.mappings.registry import Registry

    files = sorted((ROOT / "Presets-20261007T230529Z-1-001").rglob("*.ffx"))
    if not files:
        pytest.skip("Pacote privado do usuário ausente")
    registry = Registry(packages=[extension_paths("signal")[0]])
    mapping = registry.find("ffx", "effectcraft", "ADBE Signal")
    assert mapping is not None
    count = 0
    enabled = []
    for file in files:
        before = hashlib.sha256(file.read_bytes()).hexdigest()
        doc = inspect_file(file)
        indices = [
            i for i, e in enumerate(doc.presets[0].effects) if e.identifier.match_name == "ADBE Signal"
        ]
        if not indices:
            continue
        plan, report = preview(doc, registry=registry)
        converted = [e for e in plan["effects"] if e["source"] == "ADBE Signal"]
        assert len(converted) == len(indices) and report.status == "PARTIAL"
        for i, effect in zip(indices, converted, strict=True):
            original = {p.id: p for p in doc.presets[0].effects[i].parameters}
            values = {p["id"]: p["value"] for p in effect["properties"]}
            assert len(values) == 34
            for id, rule in mapping.params.items():
                source = original[id]
                assert not source.keyframes and source.value.unit is None
                expected = source.value.data - 1 if rule.operation == "minus_one" else source.value.data
                assert values[rule.target] == expected
            assert original["ADBE Signal-0011"].metadata["menu"] == ["VHS_SP", "VHS_LP", "VHS_EP"]
            assert original["ADBE Signal-0034"].metadata["menu"] == ["Off", "Lite", "Strong"]
            assert values["vhs"] == 0 and values["lowpass_out"] == 2
            assert values["seed"] == 1 and values["chroma_loss"] == 0.23999999463558197
            assert original["ADBE Signal-0012"].value.data is False
            assert any(w.path == "ADBE Signal-0012" and w.loss for w in report.effects[i].warnings)
            enabled.append(values["luma_enable"])
            count += 1
        assert hashlib.sha256(file.read_bytes()).hexdigest() == before
    assert count == 2 and sorted(enabled) == [False, True]


def test_real_heatwave_raw_controls_menu_order_and_manual_mask():
    import hashlib

    from craft_bridge.core.resources import SourceLayerBindings
    from craft_bridge.extensions import extension_paths
    from craft_bridge.mappings.registry import Registry

    files = sorted((ROOT / "Presets-20261007T230529Z-1-001").rglob("*.ffx"))
    if not files:
        pytest.skip("Pacote privado do usuário ausente")
    registry = Registry(packages=[extension_paths("heatwave")[0]])
    mapping = registry.find("ffx", "effectcraft", "Universe_Distort_Heatwave")
    assert mapping is not None
    count = 0
    for file in files:
        before = hashlib.sha256(file.read_bytes()).hexdigest()
        doc = inspect_file(file)
        indices = [
            i
            for i, e in enumerate(doc.presets[0].effects)
            if e.identifier.match_name == "Universe_Distort_Heatwave"
        ]
        if not indices:
            continue
        unbound, _ = preview(doc, registry=registry, source_size=(1920, 1080))
        assert not any(e["source"] == "Universe_Distort_Heatwave" for e in unbound["effects"])
        bindings = SourceLayerBindings(
            source_sha256=before,
            bindings=[
                {"effect_index": i, "parameter": "Universe_Distort_Heatwave-0025", "layer_ref": None}
                for i in indices
            ],
        )
        plan, report = preview(doc, registry=registry, source_layers=bindings, source_size=(1920, 1080))
        converted = [e for e in plan["effects"] if e["source"] == "Universe_Distort_Heatwave"]
        assert len(converted) == len(indices) and report.status == "PARTIAL" and plan["version"] == 4
        for i, effect in zip(indices, converted, strict=True):
            source = doc.presets[0].effects[i]
            original = {p.id: p for p in source.parameters}
            values = {p["id"]: p["value"] for p in effect["properties"]}
            assert len(values) == 25 and values["mask"] == {"layer_ref": None} and values["shape"] == 0
            assert values["direction"] == 90 and values["intensity"] == 2 and values["blur_feather"] == 407
            for id, rule in mapping.params.items():
                assert not original[id].keyframes
                if rule.kind == "Layer":
                    continue
                expected = original[id].value.data
                if rule.operation == "minus_one":
                    expected -= 1
                elif rule.operation == "normalized_to_pixels":
                    expected = [expected[0] * 1920, expected[1] * 1080]
                assert values[rule.target] == expected
            warnings = report.effects[i].warnings
            assert any(w.code == "SOURCE_LAYER_REPLACED" and w.loss for w in warnings)
            assert any(
                w.code == "UNDECODED_VALUE" and w.path == "Universe_Distort_Heatwave-0025" for w in warnings
            )
            count += 1
        assert hashlib.sha256(file.read_bytes()).hexdigest() == before
    assert count == 1


def test_real_dissolveshake_complete_and_selected_groups():
    import hashlib

    from craft_bridge.core.resources import SourceLayerBindings
    from craft_bridge.extensions import extension_paths
    from craft_bridge.mappings.registry import Registry

    files = sorted((ROOT / "Presets-20261007T230529Z-1-001").rglob("*.ffx"))
    if not files:
        pytest.skip("Pacote privado do usuário ausente")
    registry = Registry(packages=[extension_paths("dissolveshake")[0]])
    complete = selected = selected_controls = selected_keys = complete_keys = 0
    for file in files:
        before = hashlib.sha256(file.read_bytes()).hexdigest()
        doc = inspect_file(file)
        indices = [
            i for i, e in enumerate(doc.presets[0].effects) if e.identifier.match_name == "S_DissolveShake"
        ]
        if not indices:
            continue
        unbound, _ = preview(doc, registry=registry)
        snapshots = [
            i
            for i in indices
            if any(p.id == "S_DissolveShake-0001" for p in doc.presets[0].effects[i].parameters)
        ]
        assert sum(e["source"] == "S_DissolveShake" for e in unbound["effects"]) == len(indices) - len(
            snapshots
        )
        bindings = (
            SourceLayerBindings(
                source_sha256=before,
                bindings=[
                    {"effect_index": i, "parameter": "S_DissolveShake-0001", "layer_ref": "background"}
                    for i in snapshots
                ],
            )
            if snapshots
            else None
        )
        plan, report = preview(doc, registry=registry, source_layers=bindings)
        converted = [e for e in plan["effects"] if e["source"] == "S_DissolveShake"]
        assert len(converted) == len(indices) and report.status == "PARTIAL" and plan["version"] == 4
        for i, effect in zip(indices, converted, strict=True):
            result = report.effects[i]
            values = {p["id"]: p["value"] for p in effect["properties"]}
            if i in snapshots:
                assert effect["application"] == "create" and len(values) == 41
                assert values["background"] == {"layer_ref": "background"} and values["auto_trans"] == 0
                assert any(w.code == "SOURCE_LAYER_REPLACED" and w.loss for w in result.warnings)
                assert any(
                    w.code == "UNDECODED_VALUE" and w.path == "S_DissolveShake-0001" for w in result.warnings
                )
                complete += 1
                complete_keys += result.keyframes_preserved
            else:
                assert effect["application"] == "existing" and "background" not in values
                selected += 1
                selected_controls += result.parameters_converted
                selected_keys += result.keyframes_preserved
        assert hashlib.sha256(file.read_bytes()).hexdigest() == before
    assert (complete, selected, selected_controls, selected_keys, complete_keys) == (4, 5, 48, 54, 13)


def test_real_mathops_manual_resources_and_nonneutral_controls():
    import hashlib

    from craft_bridge.core.resources import SourceLayerBindings
    from craft_bridge.extensions import extension_paths
    from craft_bridge.mappings.registry import Registry

    files = sorted((ROOT / "Presets-20261007T230529Z-1-001").rglob("*.ffx"))
    if not files:
        pytest.skip("Pacote privado do usuário ausente")
    registry = Registry(packages=[extension_paths("mathops")[0]])
    count = 0
    for file in files:
        before = hashlib.sha256(file.read_bytes()).hexdigest()
        doc = inspect_file(file)
        indices = [i for i, e in enumerate(doc.presets[0].effects) if e.identifier.match_name == "S_MathOps"]
        if not indices:
            continue
        no_binding, _ = preview(doc, registry=registry)
        assert not any(e["source"] == "S_MathOps" for e in no_binding["effects"])
        bindings = SourceLayerBindings(
            source_sha256=before,
            bindings=[
                {
                    "effect_index": i,
                    "parameter": "S_MathOps-" + id,
                    "layer_ref": "second" if id == "0001" else None,
                }
                for i in indices
                for id in ["0001", "0003"]
            ],
        )
        plan, report = preview(doc, registry=registry, source_layers=bindings)
        converted = [e for e in plan["effects"] if e["source"] == "S_MathOps"]
        assert len(converted) == len(indices) and plan["version"] == 4
        for effect in converted:
            values = {p["id"]: p["value"] for p in effect["properties"]}
            assert len(values) == 17 and values["a_darks"] == -0.04 and values["blur_mask"] == 12
            assert values["source_b"] == {"layer_ref": "second"} and values["mask"] == {"layer_ref": None}
            count += 1
        for i in indices:
            warnings = report.effects[i].warnings
            assert sum(w.code == "SOURCE_LAYER_REPLACED" and w.loss for w in warnings) == 2
            for id in ["0001", "0003", "0235", "0520"]:
                assert any(w.path == "S_MathOps-" + id and w.loss for w in warnings)
        assert hashlib.sha256(file.read_bytes()).hexdigest() == before
    assert count == 4


def test_real_bcc_colorize_twenty_three_controls_four_instances():
    from craft_bridge.extensions import extension_paths
    from craft_bridge.mappings.registry import Registry

    files = sorted((ROOT / "Presets-20261007T230529Z-1-001").rglob("*.ffx"))
    if not files:
        pytest.skip("Pacote privado do usuário ausente")
    registry = Registry(packages=[extension_paths("colorize")[0]])
    mapping = registry.find("ffx", "effectcraft", "BCC3Colorize")
    assert mapping is not None
    count = 0
    for file in files:
        doc = inspect_file(file)
        sources = [e for e in doc.presets[0].effects if e.identifier.match_name == "BCC3Colorize"]
        if not sources:
            continue
        plan, report = preview(doc, registry=registry)
        converted = [e for e in plan["effects"] if e["source"] == "BCC3Colorize"]
        assert len(converted) == len(sources) and report.status == "PARTIAL"
        for source, effect in zip(sources, converted, strict=True):
            assert effect["application"] == "create" and effect["plugin_fingerprint"]
            assert len(effect["properties"]) == 23
            values = {p["id"]: p["value"] for p in effect["properties"]}
            original = {p.id: p for p in source.parameters}
            assert values["input"] == values["color_space"] == values["loop_mode"] == 0
            assert values["color3_on"] is True and values["color4_on"] is True
            for id, rule in mapping.params.items():
                param = original[id]
                assert not param.keyframes
                expected = param.value.data
                if rule.operation == "enum_map":
                    expected = rule.choices[expected]
                elif rule.operation == "argb255_to_rgba":
                    expected = [expected[1] / 255, expected[2] / 255, expected[3] / 255, expected[0] / 255]
                assert values[rule.target] == expected
            result = next(e for e in report.effects if e.source == "BCC3Colorize")
            for id in ("11010125", "10158087", "4194305", "6488065"):
                assert any(w.path == "BCC3Colorize-" + id and w.loss for w in result.warnings)
            count += 1
    assert count == 4


def test_real_unmapped_effect_reports_retain_source_parameter_losses():
    from collections import Counter

    from craft_bridge.mappings.registry import Registry

    files = sorted((ROOT / "Presets-20261007T230529Z-1-001").rglob("*.ffx"))
    if not files:
        pytest.skip("Pacote privado do usuário ausente")
    registry = Registry(packages=[])
    checked = 0
    mathops = dissolve = background = 0
    for file in files:
        doc = inspect_file(file)
        plan, report = preview(doc, registry=registry)
        assert len(doc.presets[0].effects) == len(report.effects)
        for source, result in zip(doc.presets[0].effects, report.effects, strict=True):
            if registry.find("ffx", "effectcraft", source.identifier.match_name) is not None:
                continue
            expected = Counter(
                (w.code, w.path or p.id, w.loss)
                for p in source.parameters
                if not p.metadata.get("administrative")
                for w in p.warnings
            )
            actual = Counter((w.code, w.path, w.loss) for w in result.warnings)
            assert expected <= actual
            assert any(w.code == "NO_MAPPING" for w in result.warnings)
            assert not any(e["source"] == source.identifier.match_name for e in plan["effects"])
            checked += 1
            if source.identifier.match_name in ("S_MathOps", "S_DissolveShake"):
                id = source.identifier.match_name + "-0001"
                matches = [p for p in source.parameters if p.id == id]
                if matches:
                    assert len(matches) == 1
                    param = matches[0]
                    assert param.value.kind == "unknown" and param.value.data is None
                    assert any(
                        w.code == "COMPLEX_PARAMETER" and w.path == id and w.loss for w in result.warnings
                    )
                    background += source.identifier.match_name == "S_DissolveShake"
                else:
                    assert (
                        source.identifier.match_name == "S_DissolveShake"
                        and source.feature == "effect-properties"
                    )
                mathops += source.identifier.match_name == "S_MathOps"
                dissolve += source.identifier.match_name == "S_DissolveShake"
    assert checked > 0 and (mathops, dissolve, background) == (4, 9, 4)


def test_real_s_sharpen_processing_controls_preserved():
    from craft_bridge.extensions import extension_paths
    from craft_bridge.mappings.registry import Registry

    files = sorted((ROOT / "Presets-20261007T230529Z-1-001").rglob("*.ffx"))
    if not files:
        pytest.skip("Pacote privado do usuário ausente")
    registry = Registry(packages=[extension_paths("sharpen")[0]])
    count = 0
    for file in files:
        doc = inspect_file(file)
        sources = [e for e in doc.presets[0].effects if e.identifier.match_name == "S_Sharpen"]
        if not sources:
            continue
        out, report = preview(doc, registry=registry)
        converted = [e for e in out["effects"] if e["source"] == "S_Sharpen"]
        assert len(converted) == len(sources)
        mapping = registry.find("ffx", "effectcraft", "S_Sharpen")
        assert mapping is not None
        for source, effect in zip(sources, converted, strict=True):
            assert effect["application"] == "create" and effect["plugin_fingerprint"]
            assert report.status == "PARTIAL" and len(effect["properties"]) == 15
            original = {p.id: p for p in source.parameters}
            values = {p["id"]: p["value"] for p in effect["properties"]}
            assert values["quality"] == 0 and values["opacity"] == 1
            assert original["S_Sharpen-0200"].value.data is True
            for id, rule in mapping.params.items():
                param = original[id]
                assert not param.keyframes
                assert values[rule.target] == param.value.data - (1 if rule.operation == "minus_one" else 0)
            warnings = next(e for e in report.effects if e.source == "S_Sharpen").warnings
            assert all(
                any(w.path == "S_Sharpen-" + id and w.loss for w in warnings)
                for id in ("0002", "0235", "0520", "0200")
            )
            count += 1
    assert count == 1


def test_real_bcc_directional_twelve_controls_three_instances():
    from craft_bridge.extensions import extension_paths
    from craft_bridge.mappings.registry import Registry

    files = sorted((ROOT / "Presets-20261007T230529Z-1-001").rglob("*.ffx"))
    if not files:
        pytest.skip("Pacote privado do usuário ausente")
    registry = Registry(packages=[extension_paths("directional")[0]])
    variants, controls, keys = [], 0, 0
    for file in files:
        doc = inspect_file(file)
        if not any(e.identifier.match_name == "BCC3Directional Blur" for e in doc.presets[0].effects):
            continue
        out, report = preview(doc, registry=registry)
        for effect in out["effects"]:
            if effect["source"] != "BCC3Directional Blur":
                continue
            assert effect["application"] == "create" and effect["plugin_fingerprint"]
            assert report.status == "PARTIAL"
            values = {p["id"]: p["value"] for p in effect["properties"]}
            assert len(values) == 12 and values["apply_mode"] == values["channels"] == 0
            assert values["thin"] == values["spread"] == values["threshold"] == values["mix"] == 0
            assert values["deviation"] == 255 and values["apply_mix"] == 100
            assert values["displace"] is False
            variants.append((values["amount"], values["angle"], values["avoid_clipping"]))
            controls += len(effect["properties"])
            keys += sum(len(p["keyframes"]) for p in effect["properties"])
    assert sorted(variants) == [(31, 90, True), (67, 0, False), (72, 90, True)]
    assert (controls, keys) == (36, 0)


def test_real_median_three_oriented_windows():
    from craft_bridge.extensions import extension_paths
    from craft_bridge.mappings.registry import Registry

    files = sorted((ROOT / "Presets-20261007T230529Z-1-001").rglob("*.ffx"))
    if not files:
        pytest.skip("Pacote privado do usuário ausente")
    registry = Registry(packages=[extension_paths("median")[0]])
    angles, controls, keys = [], 0, 0
    for file in files:
        doc = inspect_file(file)
        if not any(e.identifier.match_name == "BCC3Median" for e in doc.presets[0].effects):
            continue
        out, report = preview(doc, registry=registry)
        for effect in out["effects"]:
            if effect["source"] != "BCC3Median":
                continue
            assert effect["application"] == "create" and effect["plugin_fingerprint"]
            assert report.status == "PARTIAL"
            values = {p["id"]: p["value"] for p in effect["properties"]}
            assert len(values) == 10 and values["mode"] == 2 and values["channel"] == 0
            assert values["length"] == 100 and values["width"] == 3
            assert values["preserve_alpha"] is True and values["fractional"] is False
            assert values["level"] == 100 and values["mix"] == values["softness"] == 0
            angles.append(values["angle"])
            controls += len(effect["properties"])
            keys += sum(len(p["keyframes"]) for p in effect["properties"])
        result = [e for e in report.effects if e.source == "BCC3Median"]
        assert all(any(w.path == "BCC3Median-0853" and w.loss for w in e.warnings) for e in result)
    assert sorted(angles) == [45, 108, 138]
    assert (controls, keys) == (30, 0)


def test_real_flicker_complete_and_selected_controls():
    from craft_bridge.extensions import extension_paths
    from craft_bridge.mappings.registry import Registry

    files = sorted((ROOT / "Presets-20261007T230529Z-1-001").rglob("*.ffx"))
    if not files:
        pytest.skip("Pacote privado do usuário ausente")
    registry = Registry(packages=[extension_paths("flicker")[0]])
    applications, controls, keys = [], 0, 0
    for file in files:
        doc = inspect_file(file)
        if not any(e.identifier.match_name == "S_Flicker" for e in doc.presets[0].effects):
            continue
        out, report = preview(doc, registry=registry)
        for effect in out["effects"]:
            if effect["source"] != "S_Flicker":
                continue
            assert effect["plugin_fingerprint"] and report.status == "PARTIAL"
            props = {p["id"]: p for p in effect["properties"]}
            if effect["application"] == "create":
                assert len(props) == 14 and props["seed"]["value"] == 0.12298583984375
                assert props["rand_freq"]["value"] == 30
            else:
                assert set(props) == {"amplitude", "rand_luma_amp", "rand_freq"}
                assert effect["source_effect_index"] == 1
                assert all(
                    len(p["keyframes"]) == 1
                    and p["keyframes"][0]["ticks"] == 0
                    and p["keyframes"][0]["time_base"] == 21504
                    for p in props.values()
                )
            applications.append(effect["application"])
            controls += len(props)
            keys += sum(len(p["keyframes"]) for p in props.values())
    assert sorted(applications) == ["create", "existing"]
    assert (controls, keys) == (17, 3)


def test_real_modulation_twelve_controls_and_six_keys():
    from craft_bridge.extensions import extension_paths
    from craft_bridge.mappings.registry import Registry

    files = sorted((ROOT / "Presets-20261007T230529Z-1-001").rglob("*.ffx"))
    if not files:
        pytest.skip("Pacote privado do usuário ausente")
    registry = Registry(packages=[extension_paths("modulation")[0]])
    controls = keys = instances = 0
    for file in files:
        doc = inspect_file(file)
        if not any(e.identifier.match_name == "ADBE Checkout" for e in doc.presets[0].effects):
            continue
        payload, report = preview(doc, registry=registry, source_size=(1920, 1080))
        for effect in payload["effects"]:
            if effect["source"] != "ADBE Checkout":
                continue
            source = next(e for e in doc.presets[0].effects if e.identifier.match_name == "ADBE Checkout")
            assert source.name == "Modulation" and effect["plugin_fingerprint"]
            values = {p["id"]: p["value"] for p in effect["properties"]}
            assert values["direction"] == values["orientation"] == 0
            assert values["opacity"] == 255
            menus = {p.id: p.metadata.get("menu") for p in source.parameters}
            assert menus["ADBE Checkout-0007"] == ["Forward", "Backward"]
            assert menus["ADBE Checkout-0011"] == ["Vertical", "Horizontal"]
            assert report.status == "PARTIAL"
            controls += len(effect["properties"])
            keys += sum(len(p["keyframes"]) for p in effect["properties"])
            instances += 1
    assert (instances, controls, keys) == (2, 24, 6)


def test_real_continuous_endpoint_speeds_are_preserved():
    import struct

    from craft_bridge.extensions import extension_paths
    from craft_bridge.mappings.registry import Registry

    file = ROOT / "Presets-20261007T230529Z-1-001/Presets/Flow Shakes/kl4ps flow shake 4.ffx"
    if not file.is_file():
        pytest.skip("Preset privado opt-in ausente")
    doc = inspect_file(file)
    effect = next(e for e in doc.presets[0].effects if e.identifier.match_name == "S_Shake")
    param = next(p for p in effect.parameters if p.id == "S_Shake-0050")
    assert len(param.keyframes) == 2 and not param.warnings
    tree, _ = parse_rifx(file.read_bytes(), Budget(Limits()))
    raw = next(n.data for n in tree.walk() if n.offset == param.origin["ldat"]["offset"])
    for i, key in enumerate(param.keyframes):
        values = struct.unpack_from(">5d", raw, i * 48 + 8)
        assert key.value == values[0]
        assert key.handles.in_speed == [values[1]] and key.handles.in_influence == [values[2]]
        assert key.handles.out_speed == [values[3]] and key.handles.out_influence == [values[4]]
        assert key.metadata["source_temporal_continuous"] == [True]
    assert param.keyframes[0].handles.in_speed != param.keyframes[0].handles.out_speed
    registry = Registry(packages=[extension_paths("shake")[0]])
    _, report = preview(doc, registry=registry, source_size=(1920, 1080))
    result = next(e for e in report.effects if e.source == "S_Shake")
    assert result.parameters_converted == 11 and result.keyframes_preserved == 12
    assert any(w.code == "KEYFRAME_CONTINUITY" and w.path == param.id and w.loss for w in result.warnings)


def test_public_cs6_pack_legacy_maps():
    """Download manual opt-in; nunca copia o pack para fixtures públicas."""
    import hashlib

    raw_path = os.environ.get("CRAFT_CS6_PRESETS")
    if not raw_path:
        pytest.skip("Referência CS6 ausente: CRAFT_CS6_PRESETS")
    path = Path(raw_path)
    assert (
        hashlib.sha256(path.read_bytes()).hexdigest()
        == "f87d7c0f7422d2f876990a772ccd557a680c837c97b5d31619240f9cb3432367"
    )
    doc = inspect_file(path)
    assert len(doc.presets) == 10 and sum(len(p.effects) for p in doc.presets) == 21
    out, report = preview(doc, source_size=(1920, 1080))
    assert report.status == "PARTIAL"
    assert sum(len(p["effects"]) for p in out["presets"]) == 5
    assert sum(e.parameters_converted for e in report.effects) == 26
    assert sum(e.keyframes_preserved for e in report.effects) == 0
    mosaic = next(e for p in doc.presets for e in p.effects if e.identifier.match_name == "AE.ADBE Mosaic")
    assert [p.value.data for p in mosaic.parameters] == [1, 1, False]
    channel = next(
        e for p in doc.presets for e in p.effects if e.identifier.match_name == "AE.ADBE Channel Blur"
    )
    assert channel.parameters[4].value.data is True  # CurrentValue=false é prévia antiga
    assert all(
        e.mapping_validation == "real-source-partial; native-import" for e in report.effects if e.target
    )


def test_reference_prfpset_values():
    files = sorted((ROOT / ".research/prfpset-analysis/analysis/sample-files").glob("*.prfpset"))
    if not files:
        pytest.skip("Clone de referência ausente")
    assert len(files) == 3
    docs = [inspect_file(p) for p in files]
    assert all(d.source.detected_version == "3" for d in docs)
    geometry = next(d for d in docs if d.presets[0].effects[0].identifier.match_name == "AE.ADBE Geometry2")
    assert geometry.presets[0].effects[0].parameters[0].value.data == [0.5, 0.5]
    out, report = preview(geometry, source_size=(1920, 1080))
    assert out["presets"][0]["effects"][0]["params"]["position"]["value"] == {
        "Vec2": {"x": 960.0, "y": 540.0}
    }
    assert report.status == "PARTIAL"  # shutter dependency and sampling not silently ignored


def test_reference_ffx_values_and_keyframes():
    p = ROOT / ".research/ffx-compat/FfxTool.Core.Tests/fixtures/sample_1.ffx"
    if not p.exists():
        pytest.skip("Fixture de referência ausente")
    doc = inspect_file(p)
    assert [e.identifier.match_name for e in doc.presets[0].effects] == [
        "S_BlurMoCurves",
        "BCC3Directional Blur",
        "ADBE Brightness & Contrast 2",
    ]
    p = doc.presets[0].effects[2].parameters[1]
    assert p.id == "ADBE Brightness & Contrast 2-0001"
    assert [(k.ticks, k.time_base) for k in p.keyframes] == [(0, 30720), (21504, 30720)]
    assert p.keyframes[0].value == 100.0
    output, report = preview(doc)
    assert report.status == "PARTIAL" and output["effects"][0]["effect"] == "ec.color.brightnesscontrast"
    assert report.effects[2].keyframes_preserved == 2


def test_user_corpus_structural_reading():
    files = sorted((ROOT / "Presets-20261007T230529Z-1-001").rglob("*.ffx"))
    if not files:
        pytest.skip("Pacote privado do usuário ausente")
    assert len(files) == 144
    docs = [inspect_file(p) for p in files]
    assert all(d.presets[0].effects for d in docs)
    assert any(
        p.metadata.get("time_base") == 23976 for d in docs for e in d.presets[0].effects for p in e.parameters
    )
    reports = [preview(d)[1] for d in docs]
    assert any(r.status == "PARTIAL" for r in reports)
    assert all(r.status in ("PARTIAL", "UNSUPPORTED", "SUCCESS") for r in reports)


def test_real_arbitrary_values_match_instance_blobs_not_ui_shadows():
    files = sorted((ROOT / "Presets-20261007T230529Z-1-001").rglob("*.ffx"))
    if not files:
        pytest.skip("Pacote privado do usuário ausente")
    counts = {HUE: 0, LEVELS: 0, CURVES: 0}
    stale_ui = False
    for file in files:
        doc = inspect_file(file)
        tree, _ = parse_rifx(file.read_bytes(), Budget(Limits()))
        for effect in doc.presets[0].effects:
            for param in effect.parameters:
                if param.id not in counts or not param.metadata.get("decoded_arbitrary"):
                    continue
                offset = param.origin["aRbp"]["offset"]
                leaf = next(n for n in tree.walk() if n.offset == offset and n.id == "aRbp")
                # Compare directly to the instance bytes, never parT defaults.
                if param.id == CURVES:
                    assert param.metadata["decoded_arbitrary"] == decode_curves(leaf.data)
                else:
                    decoded = decode_numeric(param.id, leaf.data)
                    actual = {
                        p.id.removeprefix(param.id + "/"): p.value.data
                        for p in effect.parameters
                        if p.metadata.get("derived_from") == param.id
                    }
                    assert actual == decoded
                    if param.id == HUE:
                        ui = next((p for p in effect.parameters if p.id == "ADBE HUE SATURATION-0005"), None)
                        stale_ui |= ui is not None and ui.value.data != decoded["saturation"]
                counts[param.id] += 1
        # Association must use the adjacent instance tdbs/aRbs pair, not a
        # different property or the effect's descriptor default.
        for group in (n for n in tree.walk() if n.form == "tdgp"):
            pending = ""
            for child in group.children:
                if child.id == "tdmn":
                    pending = decode_string(child.data)
                elif child.form == "aRbs" and pending in counts:
                    assert all(n.id == "aRbp" for n in child.children)
    assert counts[HUE] == 7 and counts[LEVELS] == 3
    assert counts[CURVES] >= 20
    assert stale_ui, "O corpus deve cobrir a divergência real entre UI e blob"


def test_real_selected_property_groups_have_exact_types_and_bindings():
    from craft_bridge.mappings.registry import Registry

    files = sorted((ROOT / "Presets-20261007T230529Z-1-001").rglob("*.ffx"))
    if not files:
        pytest.skip("Pacote privado do usuário ausente")
    found = []
    for file in files:
        doc = inspect_file(file)
        selected = [
            e
            for e in doc.presets[0].effects
            if e.feature == "effect-properties"
            and Registry().find("ffx", "effectcraft", e.identifier.match_name) is not None
        ]
        if not selected:
            continue
        payload, report = preview(doc)
        assert report.status == "PARTIAL"  # Other source plug-ins still remain unsupported.
        assert len(payload["effects"]) == len(selected) == 1
        plan_effect = payload["effects"][0]
        assert plan_effect["application"] == "existing"
        assert plan_effect["source_effect_index"] in (0, 1)
        assert not any(c["command"] == "effect.apply" for c in payload["commands"])
        for effect in selected:
            for param in effect.parameters:
                assert param.metadata["evidence"] == "real-parT-and-tdb4"
                assert param.value.data is not None and not param.warnings
                if param.value.kind == "boolean":
                    assert isinstance(param.value.data, bool)
                    assert all(isinstance(k.value, bool) for k in param.keyframes)
        found.append((plan_effect["effect"], len(plan_effect["properties"])))
    assert found.count(("ec.stylize.motiontile", 3)) == 4
    assert found.count(("ec.color.tritone", 1)) == 1


def test_real_blur_expansion_keeps_rejected_options_and_values_in_reports():
    from collections import Counter

    files = sorted((ROOT / "Presets-20261007T230529Z-1-001").rglob("*.ffx"))
    if not files:
        pytest.skip("Pacote privado do usuário ausente")
    sources = {"CC Radial Blur", "ADBE Radial Blur", "ADBE Camera Lens Blur", "CC Scale Wipe"}
    counts = Counter()
    parameters = keys = 0
    for file in files:
        document = inspect_file(file)
        payload, report = preview(document, source_size=(1920, 1080))
        for effect in payload.get("effects", []):
            if effect["source"] not in sources:
                continue
            source = effect["source"]
            counts[source] += 1
            parameters += len(effect["properties"])
            keys += sum(len(p["keyframes"]) for p in effect["properties"])
            values = {p["id"]: p["value"] for p in effect["properties"]}
            result = next(e for e in report.effects if e.source == source)
            if source == "CC Radial Blur":
                assert "type" not in values  # All three use unsupported Scratch.
                assert any(
                    w.path == source + "-0001" and w.code == "PARAMETER_REJECTED" for w in result.warnings
                )
            elif source == "ADBE Camera Lens Blur":
                assert values["highlight/specularThreshold"] == pytest.approx(204.00000303983688)
                assert values["irisProperties/irisShape"] == 3
                assert "blurMap/blurMapLayer" not in values
                assert any(w.code == "COMPLEX_PARAMETER" for w in result.warnings)
            elif source == "ADBE Radial Blur":
                assert "antialiasing" not in values
                original = next(e for e in document.presets[0].effects if e.identifier.match_name == source)
                amount = next(p.value.data for p in original.parameters if p.id == source + "-0001")
                assert ("amount" in values) == (amount <= 100)
    assert counts == {
        "CC Radial Blur": 3,
        "ADBE Radial Blur": 2,
        "ADBE Camera Lens Blur": 2,
        "CC Scale Wipe": 1,
    }
    assert parameters == 47 and keys == 2


def test_real_curves_transfer_all_lut_samples_and_never_flatten_animation():
    files = sorted((ROOT / "Presets-20261007T230529Z-1-001").rglob("*.ffx"))
    if not files:
        pytest.skip("Pacote privado do usuário ausente")
    decoded = refused = 0
    for file in files:
        document = inspect_file(file)
        for effect in document.presets[0].effects:
            if effect.identifier.match_name != "ADBE CurvesCustom":
                continue
            parent = next(p for p in effect.parameters if p.id == CURVES)
            info = parent.metadata.get("decoded_arbitrary")
            derived = [p for p in effect.parameters if p.metadata.get("derived_from") == CURVES]
            if info is None:
                refused += 1
                assert not derived
                assert any(w.code == "ARBITRARY_LAYOUT" for w in parent.warnings)
                continue
            decoded += 1
            assert len(derived) == 5 and parent.metadata["administrative"] is True
            assert any(w.code == "CURVES_INTERPOLATION" and w.loss for w in effect.warnings)
            for channel, param in zip(info["channels"], derived, strict=True):
                assert param.id == CURVES + "/" + channel["channel"]
                pairs = [tuple(map(float, t.split(","))) for t in param.value.data.split()]
                assert len(pairs) == 256
                assert [y for _, y in pairs] == [v / 255 for v in channel["lut"]]
        payload, report = preview(document, source_size=(1920, 1080))
        for effect in payload.get("effects", []):
            if effect["source"] == "ADBE CurvesCustom":
                assert report.status == "PARTIAL"
                assert len(effect["properties"]) == 5
                assert all(p["kind"] == "Text" and not p["keyframes"] for p in effect["properties"])
    assert decoded == 22 and refused == 2


def test_real_neutralizer_without_rgb_units_retains_only_documented_controls():
    files = sorted((ROOT / "Presets-20261007T230529Z-1-001").rglob("*.ffx"))
    if not files:
        pytest.skip("Pacote privado do usuário ausente")
    count = 0
    for file in files:
        document = inspect_file(file)
        for original in document.presets[0].effects:
            if original.identifier.match_name != "CS Color Neutralizer":
                continue
            count += 1
            assert not any(
                p.metadata.get("layout") == "Cycore-static-percent-RGB-v1" for p in original.parameters
            )
            sliders = [
                p
                for p in original.parameters
                if p.id in {f"CS Color Neutralizer-{i:04}" for i in (3, 4, 5, 9, 10, 11, 15, 16, 17)}
            ]
            assert len(sliders) == 9 and all(p.metadata["display_flags"] == 0 for p in sliders)
            payload, report = preview(document, source_size=(1920, 1080))
            converted = next(e for e in payload["effects"] if e["source"] == "CS Color Neutralizer")
            props = {p["id"]: p["value"] for p in converted["properties"]}
            assert props == {
                "pinning": next(p.value.data for p in original.parameters if p.id.endswith("-0019")),
                "blendWOriginal": next(p.value.data for p in original.parameters if p.id.endswith("-0020")),
            }
            assert report.status == "PARTIAL"
            result = next(e for e in report.effects if e.source == "CS Color Neutralizer")
            assert sum(w.code == "NEUTRALIZER_RGB_PROFILE" for w in result.warnings) == 3
    assert count == 2


def test_real_deep_glow_snapshots_transfer_control_contract_without_equivalence(tmp_path, monkeypatch):
    from craft_bridge.extensions import extension_paths
    from craft_bridge.mappings.registry import Registry

    files = sorted((ROOT / "Presets-20261007T230529Z-1-001").rglob("*.ffx"))
    if not files:
        pytest.skip("Pacote privado do usuário ausente")
    monkeypatch.setenv("CRAFT_BRIDGE_CONFIG", str(tmp_path / "config"))
    Registry().install(extension_paths("glow")[0])
    count = 0
    for file in files:
        doc = inspect_file(file)
        payload, report = preview(doc, source_size=(1920, 1080))
        for effect in payload["effects"]:
            if effect["source"] != "PEDG":
                continue
            if effect["application"] == "existing":
                continue  # Separately checked below; this test covers full parT snapshots.
            assert effect["application"] == "create"
            assert effect["plugin_fingerprint"]
            assert 11 <= len(effect["properties"]) <= 13
            assert report.status == "PARTIAL"
            source = [
                e
                for e in doc.presets[0].effects
                if e.identifier.match_name == "PEDG" and e.feature == "effect"
            ]
            assert source
            assert any(
                w.code == "MAPPING_APPROXIMATION"
                for e in report.effects
                if e.source == "PEDG"
                for w in e.warnings
            )
            count += 1
    assert count == 23


def test_real_selected_glow_keys_have_source_types_and_existing_bindings(tmp_path, monkeypatch):
    from collections import Counter

    from craft_bridge.extensions import extension_paths
    from craft_bridge.mappings.registry import Registry

    files = sorted((ROOT / "Presets-20261007T230529Z-1-001").rglob("*.ffx"))
    if not files:
        pytest.skip("Pacote privado do usuário ausente")
    monkeypatch.setenv("CRAFT_BRIDGE_CONFIG", str(tmp_path / "config"))
    Registry().install(extension_paths("glow")[0])
    groups = params = 0
    keys = Counter()
    for file in files:
        doc = inspect_file(file)
        payload, report = preview(doc, source_size=(1920, 1080))
        for effect in payload["effects"]:
            if effect["source"] != "PEDG" or effect["application"] != "existing":
                continue
            assert report.status == "PARTIAL" and effect["source_effect_index"] in (1, 2, 3, 4)
            assert effect["plugin_fingerprint"]
            source = next(
                e
                for e in doc.presets[0].effects
                if e.identifier.match_name == "PEDG"
                and e.feature == "effect-properties"
                and e.metadata["source_effect_index"] == effect["source_effect_index"]
            )
            assert all(p.metadata["evidence"] == "real-parT-and-tdb4" for p in source.parameters)
            assert not any(p.warnings for p in source.parameters)
            groups += 1
            params += len(effect["properties"])
            for prop in effect["properties"]:
                keys[prop["id"]] += len(prop["keyframes"])
    assert groups == 18 and params == 49
    assert keys["radius"] == 18 and keys["exposure"] == 67 and keys["unmult"] == 8


def test_real_shake_contract_preserves_scalar_controls_and_selected_keys(tmp_path, monkeypatch):
    from collections import Counter

    from craft_bridge.extensions import extension_paths
    from craft_bridge.mappings.registry import Registry

    files = sorted((ROOT / "Presets-20261007T230529Z-1-001").rglob("*.ffx"))
    if not files:
        pytest.skip("Pacote privado do usuário ausente")
    monkeypatch.setenv("CRAFT_BRIDGE_CONFIG", str(tmp_path / "config"))
    Registry().install(extension_paths("shake")[0])
    counts = Counter()
    for file in files:
        doc = inspect_file(file)
        payload, report = preview(doc, source_size=(1920, 1080))
        for effect in payload["effects"]:
            if effect["source"] != "S_Shake":
                continue
            assert report.status == "PARTIAL" and effect["plugin_fingerprint"]
            counts[effect["application"]] += 1
            counts["controls"] += len(effect["properties"])
            counts["keys"] += sum(len(p["keyframes"]) for p in effect["properties"])
            assert all(p["kind"] in ("Float", "Bool", "Choice") for p in effect["properties"])
            if effect["application"] == "create":
                assert len(effect["properties"]) == 43
            else:
                source = next(
                    e
                    for e in doc.presets[0].effects
                    if e.identifier.match_name == "S_Shake"
                    and e.feature == "effect-properties"
                    and e.metadata["source_effect_index"] == effect["source_effect_index"]
                )
                assert all(p.metadata["evidence"] == "real-parT-and-tdb4" for p in source.parameters)
    assert counts == {"create": 19, "existing": 13, "controls": 955, "keys": 235}


def test_real_ofp_scene_data_roundtrip_and_snapshot_association():
    from craft_bridge.parsers.ffx.optical_flares import OPTIONS, decode_ofp, encode_ofp

    files = sorted((ROOT / "Presets-20261007T230529Z-1-001").rglob("*.ffx"))
    if not files:
        pytest.skip("Pacote privado ausente")
    scenes = objects = fields = associated = unassociated = 0
    for file in files:
        tree, _ = parse_rifx(file.read_bytes(), Budget(Limits()))
        for leaf in tree.walk():
            if leaf.id == "aRbp" and bytes(leaf.data[:4]) == b"OFP\3":
                decoded = decode_ofp(leaf.data)
                assert encode_ofp(decoded) == bytes(leaf.data)
                scenes += 1
                objects += len(decoded["objects"])
                fields += decoded["field_count"]
        doc = inspect_file(file)
        entries = doc.diagnostics.get("unassociated_ofp_scenes", [])
        unassociated += len(entries)
        for entry in entries:
            assert entry["associated"] is False and entry["scene"]["render_semantics_verified"] is False
            leaf = next(leaf for leaf in tree.walk() if leaf.offset == entry["origin"]["offset"])
            assert encode_ofp(entry["scene"]) == bytes(leaf.data)
        for preset in doc.presets:
            for effect in preset.effects:
                for parameter in effect.parameters:
                    if parameter.id == OPTIONS and parameter.metadata.get("decoded_arbitrary"):
                        associated += 1
                        assert effect.feature == "effect" and parameter.value.data is None
                        assert any(w.code == "OFP_RENDER_UNSUPPORTED" for w in parameter.warnings)
    assert (scenes, objects, fields, associated, unassociated) == (38, 602, 39665, 9, 29)


def test_real_flare_library_requires_exact_scene_and_preserves_selected_controls(tmp_path):
    import hashlib
    from collections import Counter

    from craft_bridge.extensions.flare.library import build_library
    from craft_bridge.mappings.registry import Registry
    from craft_bridge.parsers.ffx.optical_flares import OPTIONS, encode_ofp

    folder = ROOT / "Presets-20261007T230529Z-1-001"
    if not list(folder.rglob("*.ffx")):
        pytest.skip("Pacote privado ausente")
    output = tmp_path / "library"
    library = build_library(folder, output)
    assert library["associated_snapshots"] == 9 and len(library["scene_ids"]) == 6
    registry = Registry(packages=[output / "mapping.json"])
    counts = Counter()
    for file in sorted(folder.rglob("*.ffx")):
        doc = inspect_file(file)
        payload, report = preview(doc, registry=registry, source_size=(1920, 1080))
        for effect in payload["effects"]:
            if effect["source"] != "VIDEOCOPILOT OpticalFlares":
                continue
            assert report.status == "PARTIAL"
            assert effect["plugin_fingerprint"] == library["manifest_fingerprint"]
            counts[effect["application"]] += 1
            counts["properties"] += len(effect["properties"])
            counts["keys"] += sum(len(p["keyframes"]) for p in effect["properties"])
            scene_properties = [p for p in effect["properties"] if p["id"] == "scene"]
            if effect["application"] == "existing":
                assert not scene_properties
            else:
                assert len(scene_properties) == 1 and not scene_properties[0]["keyframes"]
                source = next(
                    e
                    for e in doc.presets[0].effects
                    if e.identifier.match_name == effect["source"] and e.feature == "effect"
                )
                options = next(p for p in source.parameters if p.id == OPTIONS)
                digest = hashlib.sha256(encode_ofp(options.metadata["decoded_arbitrary"])).hexdigest()
                assert digest == options.origin["aRbp"]["sha256"]
                assert scene_properties[0]["value"] == library["scene_ids"][digest]
    assert counts == {"create": 9, "existing": 21, "properties": 219, "keys": 141}


def test_real_stretch_contract_preserves_both_version_profiles(tmp_path, monkeypatch):
    from collections import Counter

    from craft_bridge.extensions import extension_paths
    from craft_bridge.mappings.registry import Registry

    files = sorted((ROOT / "Presets-20261007T230529Z-1-001").rglob("*.ffx"))
    if not files:
        pytest.skip("Pacote privado ausente")
    monkeypatch.setenv("CRAFT_BRIDGE_CONFIG", str(tmp_path / "config"))
    Registry().install(extension_paths("stretch")[0])
    counts = Counter()
    for file in files:
        doc = inspect_file(file)
        plan, report = preview(doc, source_size=(1920, 1080))
        for effect in plan["effects"]:
            if effect["source"] != "pixel_stretch":
                continue
            assert report.status == "PARTIAL" and effect["effect"] == "org.craftbridge.stretch"
            assert effect["application"] == "create" and effect["plugin_fingerprint"]
            source = next(e for e in doc.presets[0].effects if e.identifier.match_name == "pixel_stretch")
            source_values = {p.id: p.value.data for p in source.parameters}
            values = {p["id"]: p["value"] for p in effect["properties"]}
            assert values["stretch"] == source_values["pixel_stretch-0002"]
            assert values["pixel_size"] == source_values["pixel_stretch-0003"]
            assert values["direction"] == source_values["pixel_stretch-0001"] - 1
            assert values["sync"] is True
            assert "Intensity Source" in " ".join(w.message for e in report.effects for w in e.warnings)
            counts[len(effect["properties"])] += 1
            counts["keys"] += sum(len(p["keyframes"]) for p in effect["properties"])
    assert counts == {20: 3, 17: 5, "keys": 0}


def test_real_diffusion_seventeen_static_controls(tmp_path, monkeypatch):
    from craft_bridge.extensions import extension_paths
    from craft_bridge.mappings.registry import Registry

    files = sorted((ROOT / "Presets-20261007T230529Z-1-001").rglob("*.ffx"))
    if not files:
        pytest.skip("Pacote privado ausente")
    monkeypatch.setenv("CRAFT_BRIDGE_CONFIG", str(tmp_path / "config"))
    mapping, _ = extension_paths("diffusion")
    Registry().install(mapping)
    rules = Registry().find("ffx", "effectcraft", "omino_diffusion").params
    count = 0
    for file in files:
        doc = inspect_file(file)
        plan, report = preview(doc, source_size=(1920, 1080))
        for effect in plan["effects"]:
            if effect["source"] != "omino_diffusion":
                continue
            count += 1
            assert report.status == "PARTIAL" and effect["application"] == "create"
            assert len(effect["properties"]) == 17 and effect["plugin_fingerprint"]
            assert all(not p["keyframes"] for p in effect["properties"])
            source = next(e for e in doc.presets[0].effects if e.identifier.match_name == "omino_diffusion")
            raw = {p.id: p.value.data for p in source.parameters}
            values = {p["id"]: p["value"] for p in effect["properties"]}
            for name, rule in rules.items():
                expected = raw[name]
                if rule.operation == "enum_map":
                    expected = rule.choices[int(expected)]
                elif rule.operation == "argb255_to_rgba":
                    expected = [expected[1] / 255, expected[2] / 255, expected[3] / 255, expected[0] / 255]
                assert values[rule.target] == expected
    assert count == 4


def test_real_mesh_structure_roundtrip_and_instance_ownership():
    from craft_bridge.parsers.ffx.mesh import MESH, decode_mesh, encode_mesh

    files = sorted((ROOT / "Presets-20261007T230529Z-1-001").rglob("*.ffx"))
    if not files:
        pytest.skip("Pacote privado ausente")
    components = 0
    for file in files:
        doc = inspect_file(file)
        effects = [e for p in doc.presets for e in p.effects if e.identifier.match_name == "ADBE MESH WARP"]
        if not effects:
            continue
        assert len(effects) == 1
        components += 1
        parameter = next(p for p in effects[0].parameters if p.id == MESH)
        tree, _ = parse_rifx(file.read_bytes(), Budget(Limits()))

        def blobs(n):
            result = [bytes(n.data)] if n.id == "aRbp" else []
            return result + [b for child in n.children for b in blobs(child)]

        payloads = blobs(tree)
        assert len(payloads) == 2
        assert all(encode_mesh(decode_mesh(b)) == b for b in payloads)
        assert encode_mesh(parameter.metadata["decoded_arbitrary"]) == payloads[1]
        default = decode_mesh(payloads[0])["records"]
        instance = parameter.metadata["decoded_arbitrary"]["records"]
        assert sum(a != b for a, b in zip(default, instance, strict=True)) == 4
        assert parameter.value.kind == "unknown" and parameter.value.data is None
        assert {w.code for w in parameter.warnings} == {"MESH_RENDER_UNSUPPORTED"}
        plan, report = preview(doc, source_size=(1920, 1080))
        assert report.status == "UNSUPPORTED" and not plan["effects"]
    assert components == 1


def test_real_glint_twenty_five_controls_and_twelve_keys():
    from craft_bridge.core.pipeline import preview
    from craft_bridge.extensions import extension_paths
    from craft_bridge.mappings.registry import Registry

    mapping, _ = extension_paths("glint")
    registry = Registry(packages=[mapping])
    corpus = ROOT / "Presets-20261007T230529Z-1-001"
    if not corpus.is_dir():
        pytest.skip("Authorized private corpus absent")
    components = properties = keys = 0
    for file in sorted(corpus.rglob("*.ffx")):
        doc = inspect_file(file)
        source = [e for p in doc.presets for e in p.effects if e.identifier.match_name == "S_Glint"]
        if not source:
            continue
        plan, report = preview(doc, registry=registry, source_size=(1920, 1080))
        converted = [e for e in plan["effects"] if e["source"] == "S_Glint"]
        assert report.status == "PARTIAL" and len(converted) == len(source)
        for effect, original in zip(converted, source, strict=True):
            assert effect["effect"] == "org.craftbridge.glint"
            assert len(effect["properties"]) == 25
            values = {p["id"]: p["value"] for p in effect["properties"]}
            assert values["opacity_mode"] == 1 and values["scale_colors"] == [1, 1, 1, 1]
            assert values["threshold_add_color"] == [0, 0, 0, 1]
            assert next(p for p in original.parameters if p.id == "S_Glint-0074").metadata["menu"] == [
                "All Opaque",
                "Normal",
                "As Premult",
            ]
            assert any(w.path == "S_Glint-0001" and w.loss for e in report.effects for w in e.warnings)
            components += 1
            properties += len(effect["properties"])
            keys += sum(len(p["keyframes"]) for p in effect["properties"])
    assert (components, properties, keys) == (2, 50, 12)


def test_real_pixelsort_twenty_four_controls_and_exact_menus():
    from craft_bridge.extensions import extension_paths
    from craft_bridge.mappings.registry import Registry

    mapping, _ = extension_paths("pixelsort")
    registry = Registry(packages=[mapping])
    files = sorted((ROOT / "Presets-20261007T230529Z-1-001").rglob("*.ffx"))
    if not files:
        pytest.skip("Authorized private corpus absent")
    components = 0
    for file in files:
        doc = inspect_file(file)
        source = [e for p in doc.presets for e in p.effects if e.identifier.match_name == "S_PixelSort"]
        if not source:
            continue
        plan, report = preview(doc, registry=registry, source_size=(1920, 1080))
        effect = next(e for e in plan["effects"] if e["source"] == "S_PixelSort")
        assert report.status == "PARTIAL" and len(effect["properties"]) == 24
        assert sum(len(p["keyframes"]) for p in effect["properties"]) == 0
        values = {p["id"]: p["value"] for p in effect["properties"]}
        assert values["radial_center"] == values["circular_center"] == [960, 540]
        assert values["mode"] == values["sort_type"] == values["show"] == 0
        assert values["sort_angle"] == 37 and values["sort_direction"] == values["opacity_mode"] == 1
        assert values["seed"] == 0.2729949951171875 and values["reverse"] is False
        menus = {p.id: p.metadata.get("menu") for p in source[0].parameters}
        assert menus["S_PixelSort-0045"] == ["Linear", "Radial", "Circular"]
        assert menus["S_PixelSort-0066"] == [
            "monochrome",
            "average",
            "minimum",
            "maximum",
            "red",
            "green",
            "blue",
            "hue",
            "saturation",
            "brightness",
        ]
        assert menus["S_PixelSort-0071"] == [
            "Result",
            "Raw Sort Values",
            "Threshold Mask",
            "Random Restart Noise",
            "Combined Mask",
        ]
        assert menus["S_PixelSort-0075"] == ["All Opaque", "Normal", "As Premult"]
        assert any(w.path == "S_PixelSort-0001" and w.loss for e in report.effects for w in e.warnings)
        components += 1
    assert components == 1
