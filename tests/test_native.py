import itertools
import random
import shutil
import subprocess

import pytest

from bincovering.algorithms.registry import normalize, solve
from bincovering.backends.native import solve_native


@pytest.fixture(scope="module")
def executable(tmp_path_factory):
    if not shutil.which("g++"):
        pytest.skip("g++ not installed")
    target = tmp_path_factory.mktemp("native") / "solver"
    subprocess.run(
        ["g++", "-std=c++17", "-O2", "cpp/src/main.cpp", "-o", str(target)], check=True
    )
    return target


@pytest.mark.parametrize("domain,threshold", [("integer", 1000000), ("float64", 1.0)])
@pytest.mark.parametrize("name", ["dnf", "harmonic"])
def test_native_matches_python(executable, domain, threshold, name):
    spec = normalize({"id": name})
    rng = random.Random(42)
    fixtures = [
        [],
        [1] if domain == "integer" else [0.000001],
        [threshold],
        [threshold / 2] * 4,
    ]
    if domain == "integer":
        fixtures[-1] = [threshold // 2] * 4
        fixtures.append([333333, 333334, 333333, 250000, 200000, 1])
    fixtures.append(
        [
            rng.randint(1, threshold) if domain == "integer" else rng.random()
            for _ in range(1000)
        ]
    )
    for items in fixtures:
        assert solve_native(items, spec, domain, threshold, executable) == solve(
            items, spec, threshold, 42
        )


def oracle(items, threshold):
    """Independent exhaustive set-partition search for very small instances."""

    def visit(index, loads):
        if index == len(items):
            return sum(x >= threshold for x in loads)
        best = visit(index + 1, loads + [items[index]])
        for slot in range(len(loads)):
            if loads[slot] >= threshold:
                continue
            next_loads = loads.copy()
            next_loads[slot] += items[index]
            best = max(best, visit(index + 1, next_loads))
        return best

    return visit(0, [])


def test_scores_do_not_exceed_small_exact_optimum():
    for items in itertools.product([1, 2, 3], repeat=4):
        optimum = oracle(items, 4)
        for name in ("dnf", "harmonic"):
            assert solve(items, normalize({"id": name}), 4, 1).covered_bins <= optimum


def test_native_rejects_bad_input(executable):
    result = subprocess.run(
        [str(executable), "dual_next_fit", "integer", "1000000", "5"],
        input="1.5\n",
        text=True,
        capture_output=True,
    )
    assert result.returncode == 2


def test_legacy_dnf_regression(tmp_path):
    if not shutil.which("g++"):
        pytest.skip("g++ not installed")
    binary = tmp_path / "dnf"
    subprocess.run(["g++", "-std=c++17", "main.cpp", "-o", str(binary)], check=True)
    items = tmp_path / "items.txt"
    items.write_text("1\n")
    assert subprocess.check_output([str(binary), str(items)], text=True).strip() == "0"
    assert subprocess.run([str(binary)], capture_output=True).returncode == 2
