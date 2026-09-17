import csv
import json
import os
import threading
from pathlib import Path

from bincovering.experiments.runner import summarize
from bincovering.experiments.storage import write_json

PLOT_LOCK = threading.RLock()


def read_trials(path):
    with (Path(path) / "trials.csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    for row in rows:
        for key in ("covered_bins", "discarded_items", "trial", "num_items"):
            row[key] = int(row[key]) if row[key] else None
    return rows


def plot_run(path):
    with PLOT_LOCK:
        return _plot_run(path)


def _plot_run(path):
    path = Path(path)
    os.environ.setdefault("MPLCONFIGDIR", str(path.resolve() / "cache" / "matplotlib"))
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    summary = summarize(read_trials(path))
    write_json(path / "summary.json", summary)
    good = [s for s in summary if s["mean_covered"] is not None]
    if not good:
        raise ValueError("No successful trials to plot")
    fig, ax = plt.subplots(figsize=(max(6, len(good) * 2), 4), layout="constrained")
    ax.bar(
        range(len(good)),
        [s["mean_covered"] for s in good],
        yerr=[s["stdev_covered"] for s in good],
        capsize=4,
    )
    ax.set_xticks(
        range(len(good)),
        [
            s["algorithm"] + "\n" + s["backend"] + " " + json.dumps(s["parameters"])
            for s in good
        ],
        rotation=20,
        ha="right",
    )
    ax.set_ylabel("Covered bins (mean ± sample standard deviation)")
    ax.set_title("Trials within this experiment")
    (path / "figures").mkdir(exist_ok=True)
    target = path / "figures" / "coverage.png"
    fig.savefig(target, dpi=150)
    plt.close(fig)
    return target


def compare(paths):
    records = []
    identities = []
    for path in paths:
        path = Path(path)
        rows = read_trials(path)
        manifest = json.loads((path / "manifest.json").read_text())
        cfg = manifest["config"]
        identities.append(
            {
                (r["trial"], r["input_hash"], cfg["domain"], cfg["threshold"])
                for r in rows
                if r["input_hash"]
            }
        )
        records.append({"path": str(path), "summary": summarize(rows)})
    paired = bool(identities and identities[0]) and all(
        s == identities[0] for s in identities[1:]
    )
    return {"same_trial_inputs": paired, "runs": records}
