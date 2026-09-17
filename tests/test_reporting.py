from bincovering.experiments.runner import run_experiment
from bincovering.reporting.distributions import input_histogram
from bincovering.reporting.reports import plot_data, plot_run


def test_histogram_threshold_boundary_and_integer_equivalence():
    floats = input_histogram([0.01, 0.5, 1.0], 1)
    assert floats == input_histogram([1, 50, 100], 100)
    assert sum(floats["counts"]) == 3
    assert floats["counts"][-1] == 1


def test_percentage_uses_optimum_not_item_count_and_inputs_not_duplicated(tmp_path):
    path = run_experiment(
        {
            "output_root": str(tmp_path),
            "n": 20,
            "trials": 3,
            "generator": {"id": "complementary_pairs"},
        }
    )
    data = plot_data(path)
    assert data["reference_label"] == "known optimum"
    assert len(data["inputs"]) == 3
    assert sum(sum(r["counts"]) for r in data["inputs"]) == 60
    for group in data["groups"]:
        assert group["percentages"] == [count * 10 for count in group["counts"]]
    assert not (path / "inputs").exists()
    assert plot_run(path).is_file()
    assert (path / "figures/coverage.svg").is_file()


def test_old_run_distribution_is_explicitly_unavailable(tmp_path):
    path = run_experiment({"output_root": str(tmp_path), "n": 10, "trials": 1})
    (path / "input-statistics/0.json").unlink()
    assert plot_data(path)["inputs"] == []
    assert plot_run(path).is_file()


def test_saved_inputs_fallback_and_zero_reference(tmp_path):
    path = run_experiment(
        {"output_root": str(tmp_path), "n": 0, "trials": 1, "save_inputs": True}
    )
    (path / "input-statistics/0.json").unlink()
    data = plot_data(path)
    assert data["omitted"] == 2
    assert data["inputs"][0]["num_items"] == 0
    assert plot_run(path).is_file()


def test_numerical_warning_excluded(tmp_path):
    source = tmp_path / "boundary.txt"
    source.write_text("0.3\n0.7\n")
    path = run_experiment(
        {
            "output_root": str(tmp_path),
            "trials": 1,
            "generator": {"id": "file", "path": str(source)},
            "algorithms": [{"id": "dnf"}],
        }
    )
    data = plot_data(path)
    assert data["omitted"] == 1
    assert data["groups"][0]["percentages"] == []
