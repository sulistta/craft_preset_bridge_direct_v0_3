from craft_bridge.core.pipeline import inspect_file
from scripts.make_ffx_profiles import extract_profiles
from tests.helpers import ffx


def document(tmp_path, params, name="Raw Descriptor Probe"):
    source = tmp_path / "probe.ffx"
    source.write_bytes(ffx([(name, params)]))
    return inspect_file(source)


def test_profile_generation_includes_source_types_without_destination_maps(tmp_path):
    doc = document(tmp_path, [("Raw Descriptor Probe-0001", 12, 10), ("Raw Descriptor Probe-0002", 1, 4)])
    profile, conflicts = extract_profiles([doc])
    assert not conflicts
    assert profile["Raw Descriptor Probe-0001"]["kind"] == 10
    assert profile["Raw Descriptor Probe-0002"]["kind"] == 4
    # These descriptors are synthetic probes of the collector, never shipped as real profiles.
    assert all(set(p) == {"kind", "expected_dimensions", "evidence"} for p in profile.values())


def test_derived_properties_cannot_become_adobe_type_evidence(tmp_path):
    doc = document(tmp_path, [("Raw Descriptor Probe-0001", 12, 10)])
    derived = doc.presets[0].effects[0].parameters[0].model_copy(deep=True)
    derived.id += "/derived"
    derived.metadata["derived_from"] = "Raw Descriptor Probe-0001"
    doc.presets[0].effects[0].parameters.append(derived)
    profile, _ = extract_profiles([doc])
    assert derived.id not in profile


def test_conflicting_descriptors_are_removed_regardless_of_input_order(tmp_path):
    a = document(tmp_path, [("Raw Descriptor Probe-0001", 1, 4)])
    b = document(tmp_path, [("Raw Descriptor Probe-0001", 1, 7)])
    for docs in ([a, b], [b, a]):
        profile, conflicts = extract_profiles(docs)
        assert profile == {} and conflicts == {"Raw Descriptor Probe-0001"}


def test_inconsistent_shape_missing_header_and_selected_paths_cannot_supply_profiles(tmp_path):
    doc = document(tmp_path, [("Raw Descriptor Probe-0001", [1, 2], 10, 2)])
    assert extract_profiles([doc])[0] == {}
    doc = document(tmp_path, [("Raw Descriptor Probe-0001", 1, 10)])
    doc.presets[0].effects[0].feature = "effect-properties"
    assert extract_profiles([doc])[0] == {}
    doc.presets[0].effects[0].feature = "effect"
    doc.presets[0].effects[0].parameters[0].origin.clear()
    assert extract_profiles([doc])[0] == {}
