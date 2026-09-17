"""Measure native adapter overhead before deciding what to optimize."""

import csv
import statistics

from bincovering.experiments.runner import run_experiment
from bincovering.experiments.storage import write_json


def benchmark(sizes, trials, root):
    paths = []
    for size in sizes:
        path = run_experiment(
            {
                "name": "native-benchmark",
                "n": size,
                "trials": trials,
                "workers": 1,
                "domain": "integer",
                "threshold": 1000000,
                "generator": {"id": "uniform", "min": 1, "max": 1000000},
                "algorithms": [
                    {"id": name, "backend": backend}
                    for name in ("dual_next_fit", "dual_harmonic")
                    for backend in ("python", "cpp")
                ],
                "output_root": str(root),
            }
        )
        groups = {}
        with (path / "trials.csv").open() as stream:
            for row in csv.DictReader(stream):
                if row["status"] != "completed":
                    raise RuntimeError(f"Benchmark failed: {row['error']}; see {path}")
                groups.setdefault((row["algorithm"], row["backend"]), []).append(
                    float(row["elapsed_seconds"])
                )
        write_json(
            path / "benchmark.json",
            {
                "scope": "adapter including native serialization and subprocess startup; generation excluded",
                "n": size,
                "trials": trials,
                "median_seconds": {
                    f"{name}/{backend}": statistics.median(values)
                    for (name, backend), values in groups.items()
                },
            },
        )
        paths.append(path)
    return paths
