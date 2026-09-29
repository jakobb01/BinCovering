"""Mass measurements must describe actual placements without changing outcomes."""

import json
import math
import random
import shutil
import subprocess

import pytest

from bincovering.algorithms.advice import reserved_advice
from bincovering.algorithms.registry import Stream, normalize, solve
from bincovering.backends.native import solve_native
from bincovering.experiments.runner import run_experiment


def assert_accounting(result, items, threshold):
    stats = result.bin_statistics
    assert stats["covered_bins"] == result.covered_bins
    assert sum(stats["overshoot_counts"]) == result.covered_bins
    assert all(type(count) is int and count >= 0 for count in stats["overshoot_counts"])
    assert len(stats["overshoot_edges"]) == len(stats["overshoot_counts"]) + 1
    assert stats["input_mass"] == pytest.approx(math.fsum(items))
    assert stats["useful_mass"] == result.covered_bins * threshold
    components = ("useful_mass", "overshoot_mass", "unfinished_mass", "discarded_mass")
    assert all(stats[key] >= 0 for key in components)
    assert sum(stats[key] for key in components) == pytest.approx(math.fsum(items))
    assert stats["conservation_ok"]
    assert abs(stats["conservation_error"]) <= 1e-9 * max(1, math.fsum(items))


@pytest.mark.parametrize("name", ["dnf", "harmonic"])
@pytest.mark.parametrize("threshold", [1.0, 1000000])
def test_boundary_closures_and_partial_bins(name, threshold):
    # All values are exact in both domains. Equality closes a bin; a lone quarter
    # remains unfinished, and three-quarter items produce half-threshold excess.
    items = [threshold, threshold * 3 / 4, threshold * 3 / 4, threshold / 4]
    if isinstance(threshold, int):
        items = list(map(int, items))
    result = solve(items, normalize({"id": name}), threshold, 19)
    assert result.covered_bins == 2
    assert result.bin_statistics["overshoot_mass"] == threshold / 2
    assert result.bin_statistics["unfinished_mass"] == threshold / 4
    assert_accounting(result, items, threshold)


@pytest.mark.parametrize(
    "name", ["dnf", "harmonic", "advice_reserved", "advice_reserved_k4"]
)
def test_empty_input_accounting(name):
    assert_accounting(solve([], normalize({"id": name}), 1.0, 3), [], 1.0)


@pytest.mark.parametrize(
    "name,class_name,module_name",
    [
        ("throwbin_retire", "ThrowBinStrategy", "ThrowBin"),
        ("throwbin_replace", "ThrowBin_1_Strategy", "ThrowBin_1"),
        ("throwbin_fixed_active", "ThrowBinDNFStrategy", "ThrowBin_DNF"),
        ("adaptive_items", "AdaptiveBinStrategy", "AdaptiveBin"),
        ("adaptive_covered", "AdaptiveBinCoveredStrategy", "AdaptiveBinCovered"),
    ],
)
def test_instrumentation_preserves_legacy_placements_and_rng(
    name, class_name, module_name
):
    import importlib

    spec = normalize({"id": name})
    items = [random.Random(31 + i).random() for i in range(100)]
    for seed in (0, 17):
        # Execute the migrated strategy with its ordinary list, independently of
        # the registry's observed-list wrapper; compare every coverage event.
        cls = getattr(
            importlib.import_module(f"bincovering.algorithms.{module_name}"), class_name
        )
        strategy = cls(**spec["params"])
        strategy.rng = random.Random(seed)
        kwargs = (
            {"num_items": len(items)}
            if name in {"throwbin_retire", "throwbin_replace"}
            else {}
        )
        strategy.start(Stream(items), **kwargs)
        expected_trace = []
        for _ in items:
            strategy.next()
            expected_trace.append(strategy.covered_bins)
        trace = []
        result = solve(
            items,
            spec,
            1.0,
            seed,
            trace=lambda i, item, covered, trace=trace: trace.append(covered),
        )
        assert trace == expected_trace
        assert result.covered_bins == strategy.covered_bins
        assert_accounting(result, items, 1.0)


def test_retirement_discard_is_not_replacement_overshoot():
    items = [0.75] * 8
    retire = solve(
        items, normalize({"id": "ThrowBin", "params": {"bin_ratio": 0.125}}), 1.0, 7
    )
    replace = solve(
        items, normalize({"id": "ThrowBin_1", "params": {"bin_ratio": 0.125}}), 1.0, 7
    )
    assert (retire.covered_bins, retire.discarded_items) == (1, 6)
    assert (replace.covered_bins, replace.discarded_items) == (4, 0)
    assert retire.bin_statistics["discarded_mass"] == 4.5
    assert replace.bin_statistics["discarded_mass"] == 0
    assert retire.bin_statistics["overshoot_counts"][10] == 1
    assert replace.bin_statistics["overshoot_counts"][10] == 4
    assert_accounting(retire, items, 1.0)
    assert_accounting(replace, items, 1.0)


@pytest.mark.parametrize("name,k", [("advice_reserved", 5), ("advice_reserved_k4", 4)])
def test_advice_placeholders_are_not_physical_mass(name, k):
    items = [0.125] * 4 + [0.875, 0.875] + [0.375] * 5 + [0.0625] * 50
    spec = normalize({"id": name, "params": {"m": 2, "x_m": 0.75}})
    result = solve(items, spec, 1.0, 42)
    expected = reserved_advice(items, 1.0, 2, 0.75, k, None, lambda: False)
    assert result.covered_bins == expected
    assert_accounting(result, items, 1.0)


@pytest.fixture(scope="module")
def accounting_native(tmp_path_factory):
    if not shutil.which("g++"):
        pytest.skip("g++ not installed")
    executable = tmp_path_factory.mktemp("accounting-native") / "solver"
    subprocess.run(
        [
            "g++",
            "-std=c++17",
            "-O2",
            "-Icpp/include",
            "cpp/src/main.cpp",
            "-o",
            str(executable),
        ],
        check=True,
    )
    return executable


@pytest.mark.parametrize("name", ["dnf", "harmonic"])
@pytest.mark.parametrize("domain,threshold", [("float64", 1.0), ("integer", 1000000)])
def test_native_statistics_match_python_with_numeric_tolerance(
    accounting_native, name, domain, threshold
):
    rng = random.Random(84)
    items = [
        rng.random() if domain == "float64" else rng.randint(1, threshold)
        for _ in range(300)
    ]
    spec = normalize({"id": name})
    python = solve(items, spec, threshold, 1)
    native = solve_native(items, spec, domain, threshold, accounting_native)
    assert native.covered_bins == python.covered_bins
    for result in (native, python):
        assert_accounting(result, items, threshold)
    for key in ("overshoot_counts", "overshoot_edges", "covered_bins"):
        assert native.bin_statistics[key] == python.bin_statistics[key]
    for key in (
        "input_mass",
        "useful_mass",
        "overshoot_mass",
        "unfinished_mass",
        "discarded_mass",
    ):
        assert native.bin_statistics[key] == pytest.approx(python.bin_statistics[key])


def test_integer_overshoot_histogram_boundaries(accounting_native):
    threshold = 1000000
    # Every exact 5% edge, plus one integer unit either side. This catches
    # backend normalization/rounding differences without rescaling the inputs.
    excesses = sorted(
        {
            max(0, min(threshold - 1, edge + delta))
            for edge in range(0, threshold, 50000)
            for delta in (-1, 0, 1)
        }
    )
    items = [item for excess in excesses for item in (threshold - 1, excess + 1)]
    spec = normalize({"id": "dnf"})
    python = solve(items, spec, threshold, 1)
    native = solve_native(items, spec, "integer", threshold, accounting_native)
    assert (
        native.bin_statistics["overshoot_counts"]
        == python.bin_statistics["overshoot_counts"]
    )
    assert python.covered_bins == native.covered_bins == len(excesses)
    for result in (native, python):
        assert_accounting(result, items, threshold)


def test_float_overshoot_histogram_boundaries(accounting_native):
    # Values deliberately expose different long-double versus float64 rounding
    # when the normalized overshoot is multiplied by 20 for classification.
    spec = normalize({"id": "dnf"})
    for value in (0.725, 0.85, 0.95, 0.975):
        items = [value, value]
        python = solve(items, spec, 1.0, 1)
        native = solve_native(items, spec, "float64", 1.0, accounting_native)
        assert (
            native.bin_statistics["overshoot_counts"]
            == python.bin_statistics["overshoot_counts"]
        )
        for result in (native, python):
            assert_accounting(result, items, 1.0)


def test_statistics_reproducible_across_process_count(tmp_path):
    cfg = {
        "n": 40,
        "trials": 3,
        "output_root": str(tmp_path),
        "algorithms": [
            {"id": "dnf"},
            {"id": "ThrowBin"},
            {"id": "ThrowBin_1"},
            {"id": "advice_reserved", "params": {"m": 2}},
        ],
    }
    serial = run_experiment(cfg)
    parallel = run_experiment(cfg | {"workers": 2})

    def statistics(path):
        return {
            file.name: json.loads(file.read_text())
            for file in (path / "bin-statistics").glob("*.json")
        }

    assert len(statistics(serial)) == 12
    assert statistics(serial) == statistics(parallel)
