"""Compact measurements of real loads; placement and RNG behavior are unchanged."""

import math


class MassAccounting:
    def __init__(self, threshold):
        self.threshold = threshold
        self.closed = 0
        self.excess = 0.0
        self.histogram = [0] * 20

    def close(self, load):
        self.closed += 1
        excess = (load - self.threshold) / self.threshold
        self.excess += load - self.threshold
        self.histogram[min(19, max(0, int(excess * 20)))] += 1

    def finish(self, items, loads, discarded_mass=0):
        total = math.fsum(items)
        unfinished = math.fsum(load for load in loads if load < self.threshold)
        useful = self.closed * self.threshold
        error = total - useful - self.excess - unfinished - discarded_mass
        return {
            "schema_version": 1,
            "input_mass": total,
            "useful_mass": useful,
            "overshoot_mass": self.excess,
            "unfinished_mass": unfinished,
            "discarded_mass": discarded_mass,
            "covered_bins": self.closed,
            "conservation_error": error,
            "conservation_ok": abs(error) <= 1e-9 * max(1, abs(total)),
            "overshoot_edges": [i / 20 for i in range(21)],
            "overshoot_counts": self.histogram,
            "load_unit": "fraction_of_covering_threshold",
        }


class ObservedLoads(list):
    def __init__(self, values, accounting):
        super().__init__(values)
        self.accounting = accounting

    def __setitem__(self, index, value):
        if self[index] < self.accounting.threshold <= value:
            self.accounting.close(value)
        super().__setitem__(index, value)
