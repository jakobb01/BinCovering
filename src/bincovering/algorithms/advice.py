"""Experimental reservation-advice variants, with physical bin accounting.

The parameters are supplied advice, not an inferred oracle. This is a corrected
interpretation of the historical code, not a claim of matching a published theorem.
"""


def reserved_advice(items, threshold, m, fraction, k, trace, cancelled):
    reservation = threshold * fraction
    loads = [0] * m
    present = [False] * m
    harmonic = [0] * k
    critical_cursor = 0
    small_cursor = 0
    covered = 0

    for index, item in enumerate(items):
        if index % 1024 == 0 and cancelled():
            raise InterruptedError("Cancelled")
        if item >= reservation and critical_cursor < m:
            slot = critical_cursor
            critical_cursor += 1
            loads[slot] += item
            present[slot] = True
            if loads[slot] >= threshold:
                covered += 1
        elif item < threshold / k:
            # A placeholder guides placement but is never counted as an actual item.
            while (
                small_cursor < m
                and loads[small_cursor] + (0 if present[small_cursor] else reservation)
                >= threshold
            ):
                small_cursor += 1
            if small_cursor < m:
                loads[small_cursor] += item
                if present[small_cursor] and loads[small_cursor] >= threshold:
                    covered += 1
            else:
                # The item which discovers that reservations are full is not dropped.
                harmonic[-1] += item
                if harmonic[-1] >= threshold:
                    covered += 1
                    harmonic[-1] = 0
        else:
            bucket = next(d - 2 for d in range(2, k + 1) if item >= threshold / d)
            harmonic[bucket] += item
            if harmonic[bucket] >= threshold:
                covered += 1
                harmonic[bucket] = 0
        if trace:
            trace(index, item, covered)
    return covered
