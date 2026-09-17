"""Compact, algorithm-independent evidence about each trial's input."""


def input_histogram(items, threshold, bins=20):
    counts = [0] * bins
    for item in items:
        counts[min(bins - 1, int(item / threshold * bins))] += 1
    return {
        "edges": [i / bins for i in range(bins + 1)],
        "counts": counts,
        "num_items": len(items),
        "size_unit": "fraction_of_covering_threshold",
    }
