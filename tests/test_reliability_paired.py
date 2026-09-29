"""Target achievement and DNF plots use actual valid, matched observations."""

import csv
import json

import pytest

from bincovering.experiments.config import DEFAULT
from bincovering.reporting.visualizations import (
    paired_data,
    plot_paired,
    plot_reliability,
    reliability_data,
    render_plot,
)


def saved_run(tmp_path, name, rows, **settings):
    path = tmp_path / name
    path.mkdir()
    cfg = DEFAULT | {"n": 100} | settings
    (path / "manifest.json").write_text(
        json.dumps({"status": "completed", "config": cfg})
    )
    defaults = {
        "algorithm": "dual_harmonic",
        "backend": "python",
        "parameters": '{"k": 5}',
        "covered_bins": 7,
        "discarded_items": 0,
        "num_items": 100,
        "reference_value": 10,
        "reference_kind": "exact_optimum",
        "status": "completed",
        "numeric_warning": "",
        "input_hash": "same-ordered-input",
        "base_input_hash": "same-multiset",
        "domain": cfg["domain"],
        "threshold": cfg["threshold"],
    }
    records = [defaults | {"trial": i} | row for i, row in enumerate(rows)]
    with (path / "trials.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    return path


def dnf(trial, covered_bins=7, **settings):
    return {
        "trial": trial,
        "algorithm": "dual_next_fit",
        "parameters": "{}",
        "covered_bins": covered_bins,
        **settings,
    }


def test_achievement_is_inclusive_and_curve_descends(tmp_path):
    path = saved_run(
        tmp_path, "observations", [{"covered_bins": value} for value in (0, 7, 10)]
    )
    for target, reached in ((0, 3), (70, 2), (100, 1), (70.01, 1)):
        data = reliability_data([path], target)
        group = data["groups"][0]
        assert data["target"] == target
        assert (group["reached"], group["total"]) == (reached, 3)
        assert group["percentage"] == pytest.approx(100 * reached / 3)
        assert group["reference_label"] == "known optimum"
        curve = group["curve"]
        assert [p["target"] for p in curve] == sorted(p["target"] for p in curve)
        assert [p["percentage"] for p in curve] == sorted(
            (p["percentage"] for p in curve), reverse=True
        )
        assert (
            next(p["percentage"] for p in curve if p["target"] == target)
            == group["percentage"]
        )


@pytest.mark.parametrize(
    "target", [-1, 101, 10**1000, float("nan"), float("inf"), True, "70", None]
)
def test_invalid_targets_are_rejected_before_reading_files(tmp_path, target):
    with pytest.raises(ValueError, match="finite number from 0 to 100"):
        reliability_data([tmp_path / "missing"], target)


def test_invalid_observations_excluded_instead_of_counted_as_misses(tmp_path):
    rows = [
        {"covered_bins": 7},
        {"covered_bins": 8, "status": "failed"},
        {"covered_bins": 0, "reference_value": 0},
        {"numeric_warning": "boundary"},
        {"covered_bins": 11},
        {"input_hash": ""},
        {"reference_value": float("inf")},
        {"covered_bins": -1},
    ]
    path = saved_run(tmp_path, "invalid", rows)
    data = reliability_data([path], 70)
    assert data["omitted"] == 7
    assert data["groups"][0]["reached"] == data["groups"][0]["total"] == 1


def test_reliability_preserves_parameters_backends_contexts_and_bound_labels(tmp_path):
    rows = [
        {"parameters": '{"k": 4}'},
        {"parameters": '{"k": 5}'},
        {"parameters": '{"k": 5}', "backend": "cpp"},
        {
            "algorithm": "dual_next_fit",
            "parameters": "{}",
            "reference_kind": "mass_upper_bound",
        },
    ]
    first = saved_run(tmp_path, "first", rows)
    second = saved_run(
        tmp_path,
        "other-generator",
        [{"parameters": '{"k": 4}'}],
        generator={"id": "big_items"},
    )
    data = reliability_data([first, first.resolve(), second])
    assert len(data["groups"]) == 5
    assert sum(g["total"] for g in data["groups"]) == 5
    assert {g["context"]["generator"]["id"] for g in data["groups"]} == {
        "uniform",
        "big_items",
    }
    assert data["groups"][3]["reference_label"] == "mass upper bound (not OPT)"
    assert all(g["context"]["n"] == 100 for g in data["groups"])


def test_paired_histogram_measures_extra_bins_and_loss_tie_gain(tmp_path):
    rows = []
    for trial, count in enumerate((6, 7, 9)):
        rows.extend([dnf(trial), {"trial": trial, "covered_bins": count}])
    path = saved_run(tmp_path, "paired", rows)
    data = paired_data([path])
    group = data["groups"][0]
    assert data["unmatched"] == 0
    assert (group["loss"], group["tie"], group["gain"], group["total"]) == (1, 1, 1, 3)
    assert [p["difference_bins"] for p in group["points"]] == [-1, 0, 2]
    assert [p["candidate_bins"] for p in group["points"]] == [6, 7, 9]
    assert all(p["dnf_bins"] == 7 for p in group["points"])
    assert [entry["difference_bins"] for entry in group["histogram"]] == [-1, 0, 2]
    assert sum(p["percentage"] for p in group["histogram"]) == pytest.approx(100)
    assert group["baseline_backend"] == "python"


def test_same_backend_baseline_preferred_and_candidate_identities_separate(tmp_path):
    path = saved_run(
        tmp_path,
        "backends",
        [
            dnf(0, 7),
            dnf(0, 8, backend="cpp"),
            {"trial": 0, "covered_bins": 9},
            {"trial": 0, "covered_bins": 9, "backend": "cpp"},
            {"trial": 0, "covered_bins": 8, "parameters": '{"k": 4}'},
        ],
    )
    groups = paired_data([path])["groups"]
    assert len(groups) == 3
    assert [
        (g["backend"], g["baseline_backend"], g["points"][0]["difference_bins"])
        for g in groups
    ] == [("python", "python", 2), ("cpp", "cpp", 1), ("python", "python", 1)]
    assert all(f"DNF · {g['baseline_backend']}" in g["label"] for g in groups)


def test_local_baseline_precedes_same_backend_elsewhere(tmp_path):
    local = saved_run(
        tmp_path, "local", [dnf(0, 7, backend="cpp"), {"trial": 0, "covered_bins": 9}]
    )
    external = saved_run(tmp_path, "external", [dnf(0, 8)])
    group = paired_data([local, external])["groups"][0]
    assert group["baseline_backend"] == "cpp"
    assert group["points"][0]["dnf_bins"] == 7
    assert group["points"][0]["baseline_run"] == str(local)


@pytest.mark.parametrize(
    "candidate",
    [
        {"input_hash": "different-ordered-input"},
        {"trial": 1},
        {"reference_value": 11},
        {"reference_kind": "mass_upper_bound"},
    ],
)
def test_pairing_requires_identical_ordered_trial_and_reference(tmp_path, candidate):
    path = saved_run(tmp_path, "unmatched", [dnf(0), {"trial": 0} | candidate])
    data = paired_data([path])
    assert data["groups"] == []
    assert data["unmatched"] == data["exclusions"]["missing_baseline"] == 1


@pytest.mark.parametrize(
    "settings",
    [
        {"domain": "integer", "threshold": 1},
        {"threshold": 2},
    ],
)
def test_cross_run_pairing_requires_same_domain_and_threshold(tmp_path, settings):
    baseline = saved_run(tmp_path, "baseline", [dnf(0)])
    candidate = saved_run(tmp_path, "candidate", [{"trial": 0}], **settings)
    assert paired_data([baseline, candidate])["groups"] == []


def test_ambiguous_and_invalid_baselines_do_not_generate_pairs(tmp_path):
    path = saved_run(tmp_path, "ambiguous", [dnf(0, 6), dnf(0, 8), {"trial": 0}])
    data = paired_data([path])
    assert data["groups"] == []
    assert data["exclusions"]["ambiguous_baseline"] == 1
    invalid = saved_run(
        tmp_path,
        "invalid-baseline",
        [dnf(0, 7, numeric_warning="bad rounding"), {"trial": 0}],
    )
    data = paired_data([invalid])
    assert data["invalid_baselines"] == 1
    assert data["exclusions"]["missing_baseline"] == 1


def test_plot_files_keep_adjusted_target_and_integer_pair_data(tmp_path):
    path = saved_run(tmp_path, "render", [dnf(0), {"trial": 0, "covered_bins": 8}])
    seventy = render_plot([path], "reliability", minimum_coverage=70)
    eighty = plot_reliability([path], target=80)
    assert seventy != eighty
    for figure in (seventy, eighty, render_plot([path], "paired")):
        assert figure.is_file() and figure.with_suffix(".svg").is_file()
    assert json.loads(seventy.with_suffix(".json").read_text())["target"] == 70
    assert json.loads(eighty.with_suffix(".json").read_text())["target"] == 80
    data = json.loads((path / "figures/paired.json").read_text())
    assert data["groups"][0]["histogram"] == [
        {"difference_bins": 1, "count": 1, "percentage": 100}
    ]
    assert plot_paired([path], tmp_path / "comparison.png").is_file()


def test_no_valid_percentages_or_pairs_report_unavailable(tmp_path):
    path = saved_run(tmp_path, "empty", [{"covered_bins": 0, "reference_value": 0}])
    with pytest.raises(ValueError, match="No valid recorded percentage"):
        plot_reliability([path])
    with pytest.raises(ValueError, match="No valid pairs"):
        plot_paired([path])


def test_all_ties_remain_a_real_zero_difference_class(tmp_path):
    path = saved_run(tmp_path, "ties", [dnf(0), {"trial": 0}])
    group = paired_data([path])["groups"][0]
    assert (group["loss"], group["tie"], group["gain"]) == (0, 1, 0)
    assert group["histogram"] == [{"difference_bins": 0, "count": 1, "percentage": 100}]
    assert plot_paired([path]).is_file()


def test_unrelated_order_and_seed_contexts_are_not_pooled(tmp_path):
    first = saved_run(tmp_path, "shuffle", [dnf(0), {"trial": 0}])
    second = saved_run(
        tmp_path, "descending", [dnf(0), {"trial": 0}], ordering="descending"
    )
    third = saved_run(tmp_path, "other-seed", [dnf(0), {"trial": 0}], seed=43)
    assert len(reliability_data([first, second, third])["groups"]) == 6
    assert len(paired_data([first, second, third])["groups"]) == 3
