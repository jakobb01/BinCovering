import copy
import math
from pathlib import Path

from bincovering.algorithms.registry import normalize

DEFAULT = {
    "name": "baseline",
    "seed": 42,
    "trials": 3,
    "workers": 1,
    "n": 1000,
    "domain": "float64",
    "threshold": 1.0,
    "generator": {"id": "uniform", "min": 0.0001, "max": 1.0, "path": None},
    "ordering": "shuffle",
    "swaps": 0,
    "dataset_mode": "fresh",
    "algorithms": [
        {"id": "dual_next_fit"},
        {"id": "dual_harmonic", "params": {"k": 5}},
    ],
    "save_inputs": False,
    "trace_limit": 0,
    "plot": False,
    "output_root": "outputs",
    "native_executable": "build/bincovering-native",
}


def validate(raw):
    if raw.keys() - DEFAULT.keys():
        raise ValueError(f"Unknown settings: {raw.keys() - DEFAULT.keys()}")
    cfg = copy.deepcopy(DEFAULT)
    cfg.update(raw)
    if (
        not isinstance(cfg["generator"], dict)
        or cfg["generator"].keys() - DEFAULT["generator"].keys()
    ):
        raise ValueError("Invalid generator settings")
    cfg["generator"] = DEFAULT["generator"] | cfg["generator"]
    for key in ("seed", "trials", "workers", "n", "swaps", "trace_limit"):
        if type(cfg[key]) is not int or cfg[key] < (
            1 if key in ("trials", "workers") else 0
        ):
            raise ValueError(
                f"{key} must be an integer >= {1 if key in ('trials', 'workers') else 0}"
            )
    for key in ("save_inputs", "plot"):
        if type(cfg[key]) is not bool:
            raise ValueError(f"{key} must be boolean")
    if cfg["ordering"] not in (
        "original",
        "ascending",
        "descending",
        "shuffle",
        "swaps",
    ):
        raise ValueError("Unknown ordering")
    if cfg["dataset_mode"] not in ("fresh", "fixed"):
        raise ValueError("dataset_mode must be fresh or fixed")
    if cfg["domain"] not in ("float64", "integer"):
        raise ValueError("domain must be float64 or integer")
    t = cfg["threshold"]
    if not isinstance(t, (int, float)) or not math.isfinite(t) or t <= 0:
        raise ValueError("threshold must be finite and positive")
    if cfg["domain"] == "integer" and (type(t) is not int or not 2 <= t <= 10**9):
        raise ValueError("integer threshold must be in [2, 1000000000]")
    if cfg["domain"] == "float64" and t != 1:
        raise ValueError("float64 experiments currently use threshold 1.0")
    g = cfg["generator"]
    if g["id"] not in ("uniform", "big_items", "complementary_pairs", "file"):
        raise ValueError("Unknown generator")
    if g["id"] in ("uniform", "big_items"):
        if not all(
            isinstance(g[k], (int, float)) and math.isfinite(g[k])
            for k in ("min", "max")
        ):
            raise ValueError("Generator limits must be finite numbers")
        if not 0 < g["min"] <= g["max"] <= t:
            raise ValueError("Generator range must be in (0, threshold]")
        if cfg["domain"] == "integer" and any(
            type(g[k]) is not int for k in ("min", "max")
        ):
            raise ValueError("Integer generators require integer limits")
    if g["id"] == "big_items" and not t / 2 < g["min"] <= g["max"] < t:
        raise ValueError("Big items require threshold/2 < min <= max < threshold")
    if g["id"] == "complementary_pairs" and cfg["n"] % 2:
        raise ValueError("Complementary pairs require even n")
    if g["id"] == "file":
        g["path"] = str(Path(g["path"]).resolve())
        if not Path(g["path"]).is_file():
            raise ValueError("Input file does not exist")
        cfg["save_inputs"] = True
    if not isinstance(cfg["algorithms"], list) or not cfg["algorithms"]:
        raise ValueError("Specify at least one algorithm")
    cfg["algorithms"] = [normalize(s) for s in cfg["algorithms"]]
    if cfg["domain"] == "integer" and any(
        s["id"] not in ("dual_next_fit", "dual_harmonic") for s in cfg["algorithms"]
    ):
        raise ValueError("Server strategies require float64 inputs")
    cfg["output_root"] = str(Path(cfg["output_root"]).resolve())
    cfg["native_executable"] = str(Path(cfg["native_executable"]).resolve())
    return cfg
