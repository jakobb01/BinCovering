"""Research views must retain pairing, identities and measurement provenance."""

import json

import pytest

from bincovering.experiments.runner import run_experiment
from bincovering.reporting.visualizations import (
    mass_data,
    plot_mass,
    plot_ordering,
    plot_overview,
    plot_parameters,
)


def run(tmp_path, **settings):
    return run_experiment(
        {
            "output_root": str(tmp_path),
            "n": 20,
            "trials": 3,
            "algorithms": [{"id": "dnf"}],
            **settings,
        }
    )


def test_fixed_input_overview_retains_trial_outcomes_and_reference(tmp_path):
    path = run(tmp_path, dataset_mode="fixed", generator={"id": "complementary_pairs"})
    figure = plot_overview(path)
    data = json.loads(figure.with_suffix(".json").read_text())
    assert figure.is_file() and figure.with_suffix(".svg").is_file()
    assert data["dataset_mode"] == "fixed"
    assert data["reference_label"] == "known optimum"
    group = data["groups"][0]
    assert len(group["counts"]) == len(group["percentages"]) == 3
    assert group["percentages"] == [10 * count for count in group["counts"]]
    assert data["omitted"] == 0
    for panel in ("input", "trials", "outcomes"):
        assert plot_overview(path, panel=panel).is_file()


def test_missing_bin_measurements_never_reconstructed_from_inputs(tmp_path):
    path = run(tmp_path, save_inputs=True)
    for file in (path / "bin-statistics").glob("*.json"):
        file.unlink()
    assert (path / "inputs/0.json").exists()
    assert mass_data(path)["groups"] == []
    with pytest.raises(ValueError, match="no saved bin-load measurements"):
        plot_mass(path)
    assert list((path / "bin-statistics").iterdir()) == []


@pytest.mark.parametrize(
    "corruption",
    [
        {"input_hash": "wrong-sequence"},
        {"covered_bins": 999},
        {"conservation_ok": False},
        {"schema_version": 999},
        {"overshoot_counts": [0] * 20},
        {"input_mass": -1},
    ],
)
def test_invalid_bin_measurements_are_excluded(tmp_path, corruption):
    path = run(tmp_path, trials=1, generator={"id": "complementary_pairs"})
    file = next((path / "bin-statistics").glob("*.json"))
    record = json.loads(file.read_text())
    assert record["covered_bins"] > 0
    file.write_text(json.dumps(record | corruption))
    data = mass_data(path)
    assert data["groups"] == []
    assert data["omitted"] == 1


def test_malformed_measurement_does_not_hide_valid_trials(tmp_path):
    path = run(tmp_path)
    (path / "bin-statistics/broken.json").write_text("{truncated")
    data = mass_data(path)
    assert data["omitted"] == 1
    assert len(data["groups"][0]["records"]) == 3
    assert plot_mass(path).is_file()


def test_duplicate_measurements_do_not_inflate_sample_size(tmp_path):
    path = run(tmp_path, trials=1)
    file = next((path / "bin-statistics").glob("*.json"))
    (file.parent / "duplicate.json").write_bytes(file.read_bytes())
    data = mass_data(path)
    assert len(data["groups"][0]["records"]) == 1


def test_ordering_requires_matching_base_inputs(tmp_path):
    original = run(tmp_path, ordering="original")
    shuffled = run(tmp_path, ordering="shuffle")
    target = tmp_path / "order.png"
    assert plot_ordering([original, shuffled], target).is_file()
    data = json.loads(target.with_suffix(".json").read_text())
    assert data["controlled_inputs"] and data["conditions"] == 2
    unmatched = run(tmp_path, ordering="shuffle", seed=43)
    with pytest.raises(ValueError, match="matching base trial inputs"):
        plot_ordering([original, unmatched], target)


def test_throwbin_parameter_studies_separate_retirement_and_replacement(tmp_path):
    algorithms = [
        {"id": name, "params": {"bin_ratio": ratio}}
        for name in ("ThrowBin", "ThrowBin_1")
        for ratio in (0.2, 0.4)
    ]
    path = run(tmp_path, algorithms=algorithms)
    target = tmp_path / "parameters.png"
    assert plot_parameters([path], target).is_file()
    data = json.loads(target.with_suffix(".json").read_text())
    assert len(data["cells"]) == 4
    assert {cell["family"][0] for cell in data["cells"]} == {
        "throwbin_retire",
        "throwbin_replace",
    }
    assert all(
        len(cell["values"]) == len(cell["trial_inputs"]) == 3 for cell in data["cells"]
    )


def test_parameter_sweep_rejects_unmatched_trials_even_with_same_configuration(
    tmp_path,
):
    low = run(tmp_path, algorithms=[{"id": "ThrowBin_1", "params": {"bin_ratio": 0.2}}])
    high = run(
        tmp_path,
        algorithms=[{"id": "ThrowBin_1", "params": {"bin_ratio": 0.4}}],
        seed=43,
    )
    with pytest.raises(ValueError, match="identical recorded trial inputs"):
        plot_parameters([low, high], tmp_path / "unmatched.png")


def test_parameter_sweep_requires_a_throwbin_ratio_intervention(tmp_path):
    path = run(tmp_path)
    with pytest.raises(ValueError, match="at least two bin ratios"):
        plot_parameters([path], tmp_path / "invalid.png")


def test_parameter_sweep_requires_ratio_intervention_at_each_size(tmp_path):
    low = run(
        tmp_path,
        n=20,
        algorithms=[{"id": "ThrowBin_1", "params": {"bin_ratio": 0.2}}],
    )
    high = run(
        tmp_path,
        n=40,
        algorithms=[{"id": "ThrowBin_1", "params": {"bin_ratio": 0.4}}],
    )
    # Two ratios somewhere in the study cannot establish sensitivity if no N
    # has a controlled comparison across ratios.
    with pytest.raises(ValueError, match="(?i)(two|2|ratio)"):
        plot_parameters([low, high], tmp_path / "confounded.png")
