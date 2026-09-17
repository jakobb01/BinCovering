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


def plot_data(path):
    """Use recorded results only; never reconstruct old inputs with newer code."""
    from bincovering.reporting.distributions import input_histogram

    path = Path(path)
    rows = read_trials(path)
    cfg = json.loads((path / "manifest.json").read_text())["config"]
    groups = {}
    inputs = []
    seen_trials = set()
    omitted = 0
    for row in rows:
        key = (row["algorithm"], row["backend"], row["parameters"])
        group = groups.setdefault(
            key,
            {
                "label": f"{key[0]} ({key[1]})\n{key[2]}",
                "trials": [],
                "percentages": [],
                "counts": [],
                "reference_kinds": [],
            },
        )
        reference = float(row.get("reference_value") or 0)
        count = row["covered_bins"]
        if (
            row["status"] == "completed"
            and count is not None
            and reference > 0
            and not row.get("numeric_warning")
            and count <= reference
        ):
            group["trials"].append(row["trial"] + 1)
            group["percentages"].append(100 * count / reference)
            group["counts"].append(count)
            group["reference_kinds"].append(row["reference_kind"])
        else:
            omitted += 1
        trial = row["trial"]
        if trial in seen_trials or not row.get("input_hash"):
            continue
        seen_trials.add(trial)
        stats = path / "input-statistics" / f"{trial}.json"
        saved = path / "inputs" / f"{trial}.json"
        if stats.exists():
            record = json.loads(stats.read_text())
            if record.get("input_hash") != row["input_hash"]:
                continue
            inputs.append(record)
        elif saved.exists():
            from bincovering.generators.instances import digest

            items = json.loads(saved.read_text())
            if digest(items) == row["input_hash"]:
                inputs.append(
                    input_histogram(items, cfg["threshold"]) | {"trial": trial}
                )
    kinds = {kind for group in groups.values() for kind in group["reference_kinds"]}
    reference_label = (
        "known optimum"
        if kinds and kinds <= {"exact_optimum", "constructed_optimum"}
        else "mass upper bound (not OPT)"
        if kinds == {"mass_upper_bound"}
        else "recorded reference (OPT / upper bound)"
    )
    return {
        "groups": list(groups.values()),
        "inputs": inputs,
        "reference_label": reference_label,
        "omitted": omitted,
        "input_trials": len(seen_trials),
        "dataset_mode": cfg.get("dataset_mode", "fresh"),
    }


def _plot_run(path):
    path = Path(path)
    os.environ.setdefault("MPLCONFIGDIR", str(path.resolve() / "cache" / "matplotlib"))
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import MaxNLocator, PercentFormatter

    data = plot_data(path)
    write_json(path / "summary.json", summarize(read_trials(path)))
    groups = [group for group in data["groups"] if group["percentages"]]
    fig, axes = plt.subplots(
        3, 1, figsize=(max(10, len(groups) * 1.5), 13), layout="constrained"
    )
    percentage_axis, distribution_axis, input_axis = axes
    colors = plt.get_cmap("tab10")
    for index, group in enumerate(groups):
        points = sorted(zip(group["trials"], group["percentages"], strict=True))
        percentage_axis.scatter(
            *zip(*points, strict=True),
            s=24,
            alpha=0.75,
            color=colors(index % 10),
            label=group["label"],
        )
    if groups:
        percentage_axis.legend(fontsize=8, loc="best")
        distribution_axis.boxplot(
            [g["percentages"] for g in groups],
            tick_labels=[g["label"] for g in groups],
            showmeans=True,
        )
    else:
        percentage_axis.text(
            0.5,
            0.5,
            "No valid percentage observations",
            ha="center",
            transform=percentage_axis.transAxes,
        )
    for ax in (percentage_axis, distribution_axis):
        ax.set_ylim(0, 105)
        ax.yaxis.set_major_formatter(PercentFormatter(100))
        ax.set_ylabel("Covered bins / " + data["reference_label"])
        ax.grid(axis="y", alpha=0.2)
    percentage_axis.xaxis.set_major_locator(MaxNLocator(integer=True))
    percentage_axis.axhline(100, color="gray", linestyle="--", linewidth=1)
    percentage_axis.set_xlabel("Round (trial number; rounds are separate experiments)")
    percentage_axis.set_title("Coverage in each round")
    distribution_axis.set_title(
        "Distribution across rounds: median, quartiles, 1.5×IQR whiskers; triangle = mean"
    )
    distribution_axis.tick_params(axis="x", labelrotation=15, labelsize=8)
    inputs = data["inputs"]
    if inputs:
        edges = inputs[0]["edges"]
        counts = [
            sum(record["counts"][i] for record in inputs) for i in range(len(edges) - 1)
        ]
        total = sum(counts)
        if total:
            input_axis.bar(
                edges[:-1],
                [100 * count / total for count in counts],
                width=edges[1] - edges[0],
                align="edge",
                color="#267d72",
                edgecolor="white",
            )
        else:
            input_axis.text(
                0.5,
                0.5,
                "Recorded sequences are empty",
                ha="center",
                transform=input_axis.transAxes,
            )
        input_axis.set_title(
            f"Generated input sizes — {len(inputs)}/{data['input_trials']} rounds recorded; pooled by item count ({data['dataset_mode']} inputs)"
        )
    else:
        input_axis.text(
            0.5,
            0.5,
            "Input distribution unavailable for this old run.\nNo saved inputs or histogram; no data has been regenerated.",
            ha="center",
            transform=input_axis.transAxes,
        )
        input_axis.set_title("Generated input sizes")
    input_axis.set_xlim(0, 1)
    input_axis.set_xlabel("Item size / covering threshold")
    input_axis.set_ylabel("Share of generated items")
    input_axis.yaxis.set_major_formatter(PercentFormatter(100))
    input_axis.grid(axis="y", alpha=0.2)
    fig.suptitle(
        f"Experiment distributions • {data['omitted']} observations excluded from percentages\nFailed trials, zero references, and numerical inconsistencies are excluded",
        fontsize=12,
    )
    (path / "figures").mkdir(exist_ok=True)
    target = path / "figures" / "coverage.png"
    try:
        fig.savefig(target, dpi=150)
        fig.savefig(target.with_suffix(".svg"))
        write_json(path / "figures" / "plot-data.json", data)
    finally:
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
