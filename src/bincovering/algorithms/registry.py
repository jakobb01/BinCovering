"""Public identities and adapters; aliases preserve historical names."""

import math
import random
from dataclasses import dataclass

from .AdaptiveBin import AdaptiveBinStrategy
from .AdaptiveBinCovered import AdaptiveBinCoveredStrategy
from .ThrowBin import ThrowBinStrategy
from .ThrowBin_1 import ThrowBin_1_Strategy
from .ThrowBin_DNF import ThrowBinDNFStrategy

ALIASES = {
    "dnf": "dual_next_fit",
    "DNF_1": "dual_next_fit",
    "harmonic": "dual_harmonic",
    "ThrowBin": "throwbin_retire",
    "ThrowBin_1": "throwbin_replace",
    "ThrowBin_DNF": "throwbin_fixed_active",
    "AdaptiveBin": "adaptive_items",
    "AdaptiveBinCovered": "adaptive_covered",
}
PARAMETERS = {
    "dual_next_fit": {},
    "dual_harmonic": {"k": 5},
    "throwbin_retire": {"bin_ratio": 0.5},
    "throwbin_replace": {"bin_ratio": 0.5},
    "throwbin_fixed_active": {},
    "adaptive_items": {},
    "adaptive_covered": {"multiplier": 2.0, "initial_bins": 1},
}


def normalize(spec):
    spec = dict(spec)
    name = ALIASES.get(spec["id"], spec["id"])
    if name not in PARAMETERS:
        raise ValueError(f"Unknown algorithm: {name}")
    params = dict(spec.get("params", {}))
    if params.keys() - PARAMETERS[name].keys():
        raise ValueError(
            f"Unknown parameters for {name}: {params.keys() - PARAMETERS[name].keys()}"
        )
    params = PARAMETERS[name] | params
    if "k" in params and (type(params["k"]) is not int or not 2 <= params["k"] <= 1000):
        raise ValueError("k must be an integer in [2, 1000]")
    if "bin_ratio" in params and not 0 < params["bin_ratio"] <= 1:
        raise ValueError("bin_ratio must be in (0, 1]")
    if "initial_bins" in params and (
        type(params["initial_bins"]) is not int or params["initial_bins"] < 1
    ):
        raise ValueError("initial_bins must be a positive integer")
    if "multiplier" in params and (
        not math.isfinite(params["multiplier"]) or params["multiplier"] <= 0
    ):
        raise ValueError("multiplier must be finite and positive")
    backend = spec.get("backend", "python")
    if backend not in ("python", "cpp") or (
        backend == "cpp" and name not in ("dual_next_fit", "dual_harmonic")
    ):
        raise ValueError(f"Unsupported backend {backend} for {name}")
    return {"id": name, "params": params, "backend": backend}


@dataclass
class Result:
    covered_bins: int
    discarded_items: int = 0


class Stream:
    def __init__(self, items):
        self.items = iter(items)

    def next(self):
        return next(self.items)


def solve(items, spec, threshold, seed, trace=None, cancelled=lambda: False):
    """Process in order. No epsilon or conversion between integer and float domains."""
    name, params = spec["id"], spec["params"]
    if name in ("dual_next_fit", "dual_harmonic"):
        k = params.get("k", 2)
        loads = [0] * (k if name == "dual_harmonic" else 1)
        covered = 0
        for index, item in enumerate(items):
            if index % 1024 == 0 and cancelled():
                raise InterruptedError("Cancelled")
            bucket = 0
            if name == "dual_harmonic":
                bucket = k - 1
                for divisor in range(2, k + 1):
                    if item >= threshold / divisor:
                        bucket = divisor - 2
                        break
            loads[bucket] += item
            if loads[bucket] >= threshold:
                covered += 1
                loads[bucket] = 0
            if trace:
                trace(index, item, covered)
        return Result(covered)
    if threshold != 1.0:
        raise ValueError("Migrated server algorithms require float64 threshold 1.0")
    constructors = {
        "throwbin_retire": ThrowBinStrategy,
        "throwbin_replace": ThrowBin_1_Strategy,
        "throwbin_fixed_active": ThrowBinDNFStrategy,
        "adaptive_items": AdaptiveBinStrategy,
        "adaptive_covered": AdaptiveBinCoveredStrategy,
    }
    strategy = constructors[name](**params)
    strategy.rng = random.Random(seed)
    if name in ("throwbin_retire", "throwbin_replace"):
        if items and int(len(items) * params["bin_ratio"]) < 1:
            raise ValueError("bin_ratio produces zero active bins")
        strategy.start(Stream(items), num_items=len(items))
    else:
        strategy.start(Stream(items))
    discarded = 0
    for index, item in enumerate(items):
        if index % 1024 == 0 and cancelled():
            raise InterruptedError("Cancelled")
        if name == "throwbin_retire" and not strategy.active_bins:
            discarded += 1
        strategy.next()
        if trace:
            trace(index, item, strategy.covered_bins)
    strategy.stop()
    return Result(strategy.covered_bins, discarded)
