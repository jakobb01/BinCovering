"""Independent exact reference for tiny bin-covering test instances."""

from functools import cache

import pytest


@cache
def _subset_optimum(items, threshold):
    """Maximize disjoint covering subsets using exact integer sums.

    This exponential test oracle is intended only for tiny inputs. It does not
    call any solver or use the total-mass bound as the optimum.
    """
    subset_sums = [0] * (1 << len(items))
    for mask in range(1, len(subset_sums)):
        bit = mask & -mask
        subset_sums[mask] = subset_sums[mask ^ bit] + items[bit.bit_length() - 1]

    @cache
    def visit(mask):
        if not mask:
            return 0
        pivot = mask & -mask
        # An optimal covering either leaves this item unused or puts it in
        # one covered subset. Enumerate every such subset, then its complement.
        best = visit(mask ^ pivot)
        subset = mask
        while subset:
            if subset & pivot and subset_sums[subset] >= threshold:
                best = max(best, 1 + visit(mask ^ subset))
            subset = (subset - 1) & mask
        return best

    return visit(len(subset_sums) - 1)


@pytest.fixture(scope="session")
def exact_optimum():
    def optimum(items, threshold):
        return _subset_optimum(tuple(sorted(items)), threshold)

    return optimum
