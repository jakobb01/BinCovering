"""Bounded regressions for GUARANTEES.md; these checks are not theorem proofs."""

import itertools
from fractions import Fraction

import pytest

from bincovering.algorithms.registry import PARAMETERS, normalize, solve

SEEDS = (0, 1, 17)


@pytest.fixture(scope="module")
def tiny_cases(exact_optimum):
    # All 3,906 ordered sequences of length 0..5. Integer units give exact OPT;
    # dyadic scaling preserves all loads exactly in the float64 implementations.
    return [
        (tuple(unit / 8 for unit in units), exact_optimum(units, 8))
        for length in range(6)
        for units in itertools.product((1, 2, 4, 7, 8), repeat=length)
    ]


@pytest.mark.parametrize(
    "items,threshold,expected",
    [
        ([], 4, 0),
        ([1, 1, 1], 4, 0),
        ([4], 4, 1),
        ([1, 2, 3], 4, 1),
        ([2] * 5, 4, 2),
        ([1] * 8, 4, 2),
        ([3] * 4, 4, 2),  # floor(total mass / threshold) is 3, not OPT.
        ([7, 6, 2, 1], 8, 2),
    ],
)
def test_exact_oracle_known_optima(exact_optimum, items, threshold, expected):
    for ordering in (items, list(reversed(items))):
        assert exact_optimum(ordering, threshold) == expected
        assert exact_optimum([item * 3 for item in ordering], threshold * 3) == expected


def _assert_feasible(result, optimum, context):
    assert 0 <= result.covered_bins <= optimum, context
    assert result.bin_statistics["covered_bins"] == result.covered_bins, context
    assert result.bin_statistics["conservation_ok"], context


@pytest.mark.parametrize("name", PARAMETERS)
def test_all_builtins_respect_tiny_exact_optimum(name, tiny_cases):
    spec = normalize({"id": name})
    for items, optimum in tiny_cases:
        if len(items) == 1 and name in ("throwbin_retire", "throwbin_replace"):
            # Defaults need N >= 2 to open a slot; use a valid parameter here.
            single_item_spec = normalize({"id": name, "params": {"bin_ratio": 1}})
            current = single_item_spec
        else:
            current = spec
        for seed in SEEDS:
            result = solve(items, current, 1.0, seed)
            _assert_feasible(result, optimum, (current, items, seed, optimum))


# Each row encodes a documented finite inequality: coefficient*A > OPT-additive.
# The default AdaptiveBinCovered bound instead uses >= with additive zero.
FINITE_BOUNDS = [
    pytest.param("dual_next_fit", {}, 2, 1, True, id="dnf"),
    *[
        pytest.param("dual_harmonic", {"k": k}, 2, k, True, id=f"harmonic-k{k}")
        for k in (2, 5)
    ],
    pytest.param("throwbin_fixed_active", {}, 2, 10, True, id="fixed-ten"),
    *[
        pytest.param(
            "adaptive_covered",
            {"multiplier": multiplier, "initial_bins": initial},
            coefficient,
            additive,
            strict,
            id=f"adaptive-mu{multiplier}-initial{initial}",
        )
        for multiplier, initial, coefficient, additive, strict in (
            (0.25, 1, 2, 2, True),
            (1, 1, 2, 2, True),
            (1.5, 1, Fraction(5, 2), 2, True),
            (2, 1, 3, 0, False),
            (3, 1, 4, 2, True),
            (2, 3, 3, 4, True),
        )
    ],
    *[
        pytest.param(
            name,
            {"m": m, "x_m": reservation},
            2,
            m + k,
            True,
            id=f"advice-k{k}-m{m}-x{reservation}",
        )
        for name, k in (("advice_reserved", 5), ("advice_reserved_k4", 4))
        for m, reservation in ((0, 0.75), (1, 0.5), (1, 0.75), (1, 1), (3, 0.75))
    ],
]


@pytest.mark.parametrize("name,params,coefficient,additive,strict", FINITE_BOUNDS)
def test_documented_finite_bounds(
    tiny_cases, name, params, coefficient, additive, strict
):
    spec = normalize({"id": name, "params": params})
    # These optima are certified independently: groups of eight tiny items,
    # complementary pairs, two required big items per bin, and unit items.
    # Every larger case has OPT > additive, so zero coverage fails the bound.
    certified_cases = [
        ((0.125,) * 256, 32),
        ((0.125,) * 32 + (0.875,) * 32, 32),
        ((0.875,) * 32 + (0.125,) * 32, 32),
        ((0.875,) * 64, 32),
        ((1.0,) * 32, 32),
    ]
    assert all(optimum > additive for _, optimum in certified_cases)
    for items, optimum in [*tiny_cases, *certified_cases]:
        for seed in SEEDS:
            result = solve(items, spec, 1.0, seed)
            context = (spec, items, seed, result.covered_bins, optimum)
            _assert_feasible(result, optimum, context)
            left, right = coefficient * result.covered_bins, optimum - additive
            assert left > right if strict else left >= right, context


@pytest.mark.parametrize("multiplier", (0.25, 0.5, 1))
def test_single_active_adaptive_matches_dnf(multiplier, tiny_cases):
    adaptive = normalize(
        {"id": "adaptive_covered", "params": {"multiplier": multiplier}}
    )
    dnf = normalize({"id": "dual_next_fit"})
    for items, _ in tiny_cases:
        dnf_trace = []
        expected = solve(
            items,
            dnf,
            1.0,
            0,
            trace=lambda *event, output=dnf_trace: output.append(event),
        )
        for seed in SEEDS:
            adaptive_trace = []
            actual = solve(
                items,
                adaptive,
                1.0,
                seed,
                trace=lambda *event, output=adaptive_trace: output.append(event),
            )
            assert actual == expected, (items, multiplier, seed)
            assert adaptive_trace == dnf_trace, (items, multiplier, seed)


@pytest.mark.parametrize("seed", SEEDS)
def test_adaptive_items_is_optimal_on_strict_big_items(seed):
    spec = normalize({"id": "adaptive_items"})
    # Both odd/even lengths, every ordering, and values near the two boundaries.
    # Since one item cannot cover but any pair can, OPT = floor(N/2).
    for length in range(7):
        for items in itertools.product((33 / 64, 0.75, 63 / 64), repeat=length):
            result = solve(items, spec, 1.0, seed)
            assert result.covered_bins == length // 2, (items, seed)
            _assert_feasible(result, length // 2, (items, seed))


@pytest.mark.parametrize("seed", range(5))
def test_adaptive_items_complementary_counterexample(exact_optimum, seed):
    units = [7, 6, 2, 1]
    optimum = exact_optimum(units, 8)
    assert optimum == 2  # (7+1) and (6+2), total mass is exactly two thresholds.
    result = solve(
        [unit / 8 for unit in units], normalize({"id": "AdaptiveBin"}), 1.0, seed
    )
    assert result.covered_bins == 1
    _assert_feasible(result, optimum, (units, seed))


@pytest.mark.parametrize(
    "name", ("adaptive_items", "throwbin_retire", "throwbin_replace")
)
@pytest.mark.parametrize("seed", range(5))
def test_length_growth_tiny_item_counterexample(name, seed):
    items = [1 / 64] * 4096
    # Exactly 64 items cover each bin; partitioning into groups attains OPT=64.
    optimum = 64
    baseline = solve(items, normalize({"id": "dual_next_fit"}), 1.0, seed)
    assert baseline.covered_bins == optimum
    result = solve(items, normalize({"id": name}), 1.0, seed)
    assert result.covered_bins == 0
    _assert_feasible(result, optimum, (name, seed))


@pytest.mark.parametrize("name", ("advice_reserved", "advice_reserved_k4"))
def test_supplied_advice_defaults_do_not_inherit_paper_bound(name):
    # Complementary pairs attain the mass upper bound, certifying OPT=1000.
    items = [0.125] * 1000 + [0.875] * 1000
    optimum = 1000
    result = solve(items, normalize({"id": name}), 1.0, 0)
    assert result.covered_bins == 650
    paper_bound = Fraction(2, 3) * optimum - Fraction(173, 60)
    assert result.covered_bins < paper_bound
    _assert_feasible(result, optimum, name)
    # This is supplied, uncertified advice, not a counterexample to its theorem.
    k = 4 if name.endswith("k4") else 5
    assert 2 * result.covered_bins > optimum - 103 - k
