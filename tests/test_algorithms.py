import random

import pytest

from bincovering.algorithms.registry import normalize, solve


@pytest.mark.parametrize(
    "items, expected",
    [([], 0), ([1], 0), ([400000, 600000], 1), ([700000, 700000, 600000], 1)],
)
def test_integer_dnf(items, expected):
    assert solve(items, normalize({"id": "dnf"}), 1000000, 1).covered_bins == expected


def test_harmonic_third_boundary():
    # 333333 is below the exact 1/3 boundary, so it must not mix with 333334.
    assert (
        solve(
            [333333, 333334, 333333], normalize({"id": "harmonic"}), 1000000, 1
        ).covered_bins
        == 0
    )


def test_retire_and_replace_are_distinct():
    items = [0.6] * 10
    a = solve(
        items, normalize({"id": "ThrowBin", "params": {"bin_ratio": 0.1}}), 1.0, 1
    )
    b = solve(
        items, normalize({"id": "ThrowBin_1", "params": {"bin_ratio": 0.1}}), 1.0, 1
    )
    assert (a.covered_bins, a.discarded_items) == (1, 8)
    assert b.covered_bins == 5


def test_private_random_stream():
    state = random.getstate()
    spec = normalize({"id": "AdaptiveBin"})
    a = solve([0.4, 0.7] * 50, spec, 1.0, 77)
    random.random()
    b = solve([0.4, 0.7] * 50, spec, 1.0, 77)
    assert a == b
    random.setstate(state)


def test_adaptive_rule_matches_code_not_old_comment():
    from bincovering.algorithms.AdaptiveBin import AdaptiveBinStrategy

    s = AdaptiveBinStrategy()
    s.items_received = 8
    assert s._calculate_target_bins() == 4


def test_big_items_optimum(tmp_path):
    from bincovering.generators.BigItemsGenerator import BigItemsGenerator

    g = BigItemsGenerator(min_size=0.9, max_size=0.9, path=str(tmp_path))
    g.start(10)
    assert g.get_optimal_bins() == 5
    g.stop()
