"""Paired DNF differences and controlled ordering comparisons from saved trials."""

import json
import os
import statistics
from pathlib import Path

from bincovering.experiments.storage import write_json
from bincovering.reporting.reports import PLOT_LOCK, read_trials


def identity(row):
    return (row["algorithm"], row["backend"], row["parameters"])


def valid(row):
    reference = float(row.get("reference_value") or 0)
    return (
        row["status"] == "completed"
        and row["covered_bins"] is not None
        and reference > 0
        and not row.get("numeric_warning")
        and row["covered_bins"] <= reference
        and bool(row.get("input_hash"))
    )


def comparison_data(paths):
    runs = []
    for path in dict.fromkeys(str(Path(p).resolve()) for p in paths):
        directory = Path(path)
        manifest = json.loads((directory / "manifest.json").read_text())
        if manifest["status"] in ("queued", "running"):
            raise ValueError("Wait for selected experiments to finish")
        runs.append((path, manifest["config"], read_trials(directory)))
    if not runs:
        raise ValueError("Select at least one experiment")

    def pairing_key(cfg, row):
        return (
            row["trial"],
            row["input_hash"],
            cfg["domain"],
            cfg["threshold"],
            row.get("reference_kind"),
            float(row.get("reference_value") or 0),
        )

    baselines = {}
    for path, cfg, rows in runs:
        for row in rows:
            if row["algorithm"] == "dual_next_fit" and valid(row):
                baselines.setdefault(pairing_key(cfg, row), []).append((path, row))
    paired = {}
    unmatched = 0
    for path, cfg, rows in runs:
        for row in rows:
            if row["algorithm"] == "dual_next_fit":
                continue
            candidates = baselines.get(pairing_key(cfg, row), [])
            local = [r for p, r in candidates if p == path]
            candidates = local or [r for _, r in candidates]
            same_backend = [r for r in candidates if r["backend"] == row["backend"]]
            candidates = same_backend or candidates
            if (
                not valid(row)
                or not candidates
                or len({r["covered_bins"] for r in candidates}) != 1
            ):
                unmatched += 1
                continue
            baseline = candidates[0]
            key = identity(row) + (baseline["backend"],)
            group = paired.setdefault(
                key,
                {
                    "label": f"{row['algorithm']} ({row['backend']})\n{row['parameters']}; DNF: {baseline['backend']}",
                    "points": [],
                },
            )
            group["points"].append(
                {
                    "run": path,
                    "trial": row["trial"],
                    "input_hash": row["input_hash"],
                    "difference_pp": 100
                    * (row["covered_bins"] - baseline["covered_bins"])
                    / float(row["reference_value"]),
                }
            )

    # Hash each base multiset once per trial; never confuse independent base inputs
    # with an ordering-only intervention. Full input hashes differ intentionally.
    bases = [
        {
            (r["trial"], r.get("base_input_hash"), cfg["domain"], cfg["threshold"])
            for r in rows
            if r.get("base_input_hash")
        }
        for _, cfg, rows in runs
    ]
    controlled = bool(bases and bases[0]) and all(b == bases[0] for b in bases)
    orders = {}
    conditions = set()
    if controlled:
        for _path, cfg, rows in runs:
            condition = (
                cfg["ordering"],
                cfg.get("swap_mode") if cfg["ordering"] == "swaps" else None,
                cfg.get("swaps", 0) if cfg["ordering"] == "swaps" else None,
            )
            conditions.add(condition)
            for row in rows:
                if not valid(row):
                    continue
                group = orders.setdefault(
                    identity(row),
                    {
                        "label": f"{row['algorithm']} ({row['backend']})\n{row['parameters']}",
                        "conditions": {},
                    },
                )
                label = (
                    f"swaps={condition[2]} ({condition[1]})"
                    if condition[0] == "swaps"
                    else condition[0]
                )
                point = group["conditions"].setdefault(
                    label,
                    {
                        "order": condition[0],
                        "swaps": condition[2],
                        "swap_mode": condition[1],
                        "values": [],
                    },
                )
                point["values"].append(
                    100 * row["covered_bins"] / float(row["reference_value"])
                )
    return {
        "paired": list(paired.values()),
        "unmatched": unmatched,
        "ordering": list(orders.values()),
        "controlled_inputs": controlled,
        "conditions": len(conditions),
        "runs": [p for p, _, _ in runs],
    }


def plot_comparison(paths, destination):
    with PLOT_LOCK:
        return _plot_comparison(paths, destination)


def _plot_comparison(paths, destination):
    os.environ.setdefault(
        "MPLCONFIGDIR", str(Path(destination).resolve().parent / "cache" / "matplotlib")
    )
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.ticker import PercentFormatter

    data = comparison_data(paths)
    fig, (paired_ax, order_ax) = plt.subplots(
        2, 1, figsize=(12, 11), layout="constrained"
    )
    groups = data["paired"]
    paired_ax.axhline(0, color="gray", linestyle="--")
    if groups:
        paired_ax.boxplot(
            [[p["difference_pp"] for p in g["points"]] for g in groups],
            tick_labels=[g["label"] + f"\nn={len(g['points'])}" for g in groups],
            showmeans=True,
        )
    else:
        paired_ax.text(
            0.5,
            0.5,
            "No valid pairs. Include DNF on the same trial inputs.",
            ha="center",
            transform=paired_ax.transAxes,
        )
    paired_ax.set_title(
        f"Paired improvement over DNF • {data['unmatched']} unmatched/invalid observations"
    )
    paired_ax.set_ylabel(
        "Difference in percentage points of recorded reference\nPositive = better than DNF"
    )
    paired_ax.tick_params(axis="x", labelrotation=15, labelsize=8)
    if not data["controlled_inputs"]:
        order_ax.text(
            0.5,
            0.5,
            "Ordering comparison unavailable: base trial inputs differ.\nUse the same input seeds, trial count, generator and size.",
            ha="center",
            transform=order_ax.transAxes,
        )
    elif data["conditions"] < 2:
        order_ax.text(
            0.5,
            0.5,
            "Select experiments with at least two ordering/swap settings.\nKeep the base trial inputs fixed across settings.",
            ha="center",
            transform=order_ax.transAxes,
        )
    else:
        entries = [p for g in data["ordering"] for p in g["conditions"].values()]
        numeric = (
            all(p["order"] == "swaps" for p in entries)
            and len({p["swap_mode"] for p in entries}) == 1
        )
        labels = sorted({label for g in data["ordering"] for label in g["conditions"]})
        for group in data["ordering"]:
            points = sorted(
                group["conditions"].items(),
                key=lambda pair: pair[1]["swaps"] if numeric else labels.index(pair[0]),
            )
            xs = [p["swaps"] if numeric else labels.index(label) for label, p in points]
            medians = [statistics.median(p["values"]) for _, p in points]
            low = [float(np.percentile(p["values"], 25)) for _, p in points]
            high = [float(np.percentile(p["values"], 75)) for _, p in points]
            order_ax.errorbar(
                xs,
                medians,
                yerr=[
                    [
                        median - lower
                        for median, lower in zip(medians, low, strict=True)
                    ],
                    [
                        upper - median
                        for median, upper in zip(medians, high, strict=True)
                    ],
                ],
                marker="o",
                linestyle="-" if numeric else "none",
                capsize=4,
                label=group["label"],
            )
        if not numeric:
            order_ax.set_xticks(range(len(labels)), labels, rotation=15)
        order_ax.set_xlabel(
            "Swap operations (not % of items moved)" if numeric else "Input ordering"
        )
        order_ax.legend(fontsize=8)
    order_ax.set_ylim(0, 105)
    order_ax.yaxis.set_major_formatter(PercentFormatter(100))
    order_ax.set_ylabel(
        "Covered bins / recorded reference (%)\nCertified OPT where known; otherwise mass upper bound"
    )
    order_ax.set_title(
        "Ordering sensitivity • median and interquartile range (not confidence intervals)"
    )
    for ax in (paired_ax, order_ax):
        ax.grid(axis="y", alpha=0.2)
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        fig.savefig(target, dpi=150)
        fig.savefig(target.with_suffix(".svg"))
        write_json(target.with_suffix(".json"), data)
    finally:
        plt.close(fig)
    return target
