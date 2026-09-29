"""Approved research views drawn solely from saved results and measurements."""

import hashlib
import json
import math
import statistics
import textwrap
import uuid
from bisect import bisect_left
from collections import Counter
from pathlib import Path

from bincovering.experiments.storage import write_json

from .reports import PLOT_LOCK, plot_data, read_trials, reference_label

COLORS = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#56B4E9"]


def pyplot():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def label(row):
    params = row.get("parameters", row.get("params", {}))
    return f"{row['algorithm'].replace('_', ' ')} · {row['backend']}\n{params}"


def save(fig, target, data):
    plt = pyplot()
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporaries = []
    try:
        for extension in ("png", "svg"):
            temporary = target.with_name(
                f"{target.stem}.{uuid.uuid4().hex}.{extension}"
            )
            temporaries.append(temporary)
            fig.savefig(temporary, dpi=150)
            temporary.replace(target.with_suffix("." + extension))
        write_json(target.with_suffix(".json"), data)
    finally:
        plt.close(fig)
        for temporary in temporaries:
            temporary.unlink(missing_ok=True)
    return target


def plot_overview(path, algorithm=0, panel="all"):
    import numpy as np

    if not isinstance(panel, str) or panel not in {
        "all",
        "input",
        "trials",
        "outcomes",
    }:
        raise ValueError("Unknown overview panel")
    path = Path(path)
    data = plot_data(path)
    if not 0 <= algorithm < len(data["groups"]):
        raise ValueError("Choose an algorithm recorded in this experiment")
    group = data["groups"][algorithm]
    values = group["percentages"]
    plt = pyplot()
    fig, axes = plt.subplots(
        3 if panel == "all" else 1,
        1,
        figsize=(11, 12 if panel == "all" else 5.5),
        layout="constrained",
        squeeze=False,
    )
    panels = ["input", "trials", "outcomes"] if panel == "all" else [panel]
    for ax, view in zip(axes[:, 0], panels, strict=True):
        if view == "input":
            records = data["inputs"]
            if data["dataset_mode"] == "fixed" and records:
                records = records[:1]
            if records:
                edges = records[0]["edges"]
                counts = np.sum([r["counts"] for r in records], axis=0)
                total = sum(counts)
                if total:
                    ax.bar(
                        edges[:-1],
                        100 * counts / total,
                        width=np.diff(edges),
                        align="edge",
                        color=COLORS[0],
                        edgecolor="white",
                    )
                else:
                    ax.text(
                        0.5,
                        0.5,
                        "The saved inputs are empty",
                        ha="center",
                        transform=ax.transAxes,
                    )
                ax.set_title(
                    "Fixed input multiset, counted once"
                    if data["dataset_mode"] == "fixed"
                    else f"Input sizes pooled from {len(records)}/{data['input_trials']} recorded trials"
                )
            else:
                ax.text(
                    0.5,
                    0.5,
                    "Input distribution unavailable for this old run.\nNo inputs have been regenerated.",
                    ha="center",
                    transform=ax.transAxes,
                )
                ax.set_title("Input size distribution")
            ax.set_xlim(0, 1)
            ax.set_xlabel("Item size / covering threshold")
            ax.set_ylabel("Items in class (%)")
        elif view == "trials":
            ax.scatter(group["trials"], values, color=COLORS[0], s=18, alpha=0.65)
            if values:
                q1, median, q3 = np.percentile(values, [25, 50, 75])
                ax.axhline(median, color=COLORS[1], label=f"Median {median:.2f}%")
                ax.axhspan(
                    q1,
                    q3,
                    color=COLORS[1],
                    alpha=0.12,
                    label=f"Middle 50%: {q1:.2f}–{q3:.2f}%",
                )
                ax.legend(fontsize=9)
            ax.set_title("Coverage in each trial · separate observations")
            ax.set_xlabel("Trial number")
            ax.set_ylabel("Covered / " + data["reference_label"] + " (%)")
        else:
            if values:
                references = group["references"]
                if len(set(references)) == 1:
                    counts = group["counts"]
                    # Cap the class count for large ranges without changing the scale.
                    step = max(1, math.ceil((max(counts) - min(counts) + 1) / 50))
                    edges = (
                        np.arange(min(counts) - 0.5, max(counts) + step + 0.5, step)
                        * 100
                        / references[0]
                    )
                else:
                    edges = np.histogram_bin_edges(values, bins="auto")
                    if len(edges) > 51:
                        edges = np.linspace(min(values), max(values), 51)
                ax.hist(
                    values,
                    bins=edges,
                    weights=np.full(len(values), 100 / len(values)),
                    color=COLORS[0],
                    alpha=0.75,
                    edgecolor="white",
                )
                q1, median, q3 = np.percentile(values, [25, 50, 75])
                ax.axvline(median, color=COLORS[1], label=f"Median {median:.2f}%")
                ax.axvline(
                    q1,
                    color=COLORS[1],
                    linestyle="--",
                    label=f"Q1 {q1:.2f}% · Q3 {q3:.2f}%",
                )
                ax.axvline(q3, color=COLORS[1], linestyle="--")
                ax.legend(fontsize=9)
            ax.set_title("Distribution of coverage outcomes")
            ax.set_xlabel("Covered / " + data["reference_label"] + " (%)")
            ax.set_ylabel("Trials in class (%)")
        if view != "input" and not values:
            ax.text(
                0.5,
                0.5,
                "No valid percentage observations",
                ha="center",
                transform=ax.transAxes,
            )
        ax.grid(axis="y", alpha=0.18)
        ax.set_axisbelow(True)
    fig.suptitle(
        f"{group['label']}\n{len(values)} valid trials · {data['omitted']} observations excluded · bands describe variability, not confidence",
        fontsize=11,
    )
    target = (
        path
        / "figures"
        / (
            "coverage.png"
            if algorithm == 0 and panel == "all"
            else f"overview-{algorithm}-{panel}.png"
        )
    )
    (path / "figures").mkdir(exist_ok=True)
    write_json(path / "figures" / "plot-data.json", data)
    return save(fig, target, data)


def mass_data(path):
    path = Path(path)
    rows = {
        (r["trial"], r["algorithm"], r["backend"], r["parameters"]): r
        for r in read_trials(path)
    }
    groups = {}
    omitted = 0
    seen = set()
    for file in sorted((path / "bin-statistics").glob("*.json")):
        try:
            record = json.loads(file.read_text())
            key = (
                record["trial"],
                record["algorithm"],
                record["backend"],
                record["parameters"],
            )
            row = rows.get(key)
            values = [
                record[k]
                for k in (
                    "input_mass",
                    "useful_mass",
                    "overshoot_mass",
                    "unfinished_mass",
                    "discarded_mass",
                )
            ]
            counts = record["overshoot_counts"]
            edges = record["overshoot_edges"]
            valid = (
                record["schema_version"] == 1
                and row is not None
                and row["status"] == "completed"
                and not row.get("numeric_warning")
                and row["input_hash"] == record["input_hash"]
                and row["covered_bins"] == record["covered_bins"]
                and record["conservation_ok"] is True
                and all(
                    type(v) in (int, float) and math.isfinite(v) and v >= 0
                    for v in values
                )
                and len(counts) == 20
                and all(type(c) is int and c >= 0 for c in counts)
                and sum(counts) == record["covered_bins"]
                and len(edges) == 21
                and all(
                    math.isclose(edge, i / 20, abs_tol=1e-12)
                    for i, edge in enumerate(edges)
                )
                and math.isclose(
                    record["useful_mass"],
                    row["covered_bins"] * float(row["threshold"]),
                    rel_tol=1e-9,
                    abs_tol=1e-9,
                )
                and abs(values[0] - sum(values[1:])) <= 1e-9 * max(1, values[0])
                and key not in seen
            )
        except (OSError, ValueError, KeyError, TypeError, OverflowError):
            valid = False
        if not valid:
            omitted += 1
            continue
        seen.add(key)
        identity = key[1:]
        group = groups.setdefault(identity, {"label": label(row), "records": []})
        group["records"].append(record)
    return {
        "groups": list(groups.values()),
        "omitted": omitted,
        "recorded_trials": len(rows),
    }


def plot_mass(path):
    import numpy as np

    data = mass_data(path)
    groups = data["groups"]
    if not groups:
        raise ValueError(
            "This run has no saved bin-load measurements. Run a new experiment or rerun it to collect mass accounting; old results are not reconstructed."
        )
    plt = pyplot()
    fig, (ax, hist) = plt.subplots(
        1, 2, figsize=(13, max(5.5, len(groups) * 0.8)), layout="constrained"
    )
    positions = np.arange(len(groups))
    bottom = np.zeros(len(groups))
    for key, title, color in [
        ("useful_mass", "Threshold mass in covered bins", COLORS[0]),
        ("overshoot_mass", "Excess load in covered bins", "#E69F00"),
        ("unfinished_mass", "Unfinished-bin mass", "#999999"),
        ("discarded_mass", "Discarded item mass", "#CC79A7"),
    ]:
        heights = [
            100
            * sum(r[key] for r in g["records"])
            / sum(r["input_mass"] for r in g["records"])
            if sum(r["input_mass"] for r in g["records"])
            else 0
            for g in groups
        ]
        ax.barh(positions, heights, left=bottom, label=title, color=color)
        for i, height in enumerate(heights):
            if height >= 5:
                ax.text(
                    bottom[i] + height / 2,
                    i,
                    f"{height:.1f}%",
                    va="center",
                    ha="center",
                    color="white" if key == "useful_mass" else "black",
                    fontsize=9,
                )
        bottom += heights
    ax.set_yticks(
        positions,
        [f"{g['label']}\n{len(g['records'])} measured trials" for g in groups],
        fontsize=9,
    )
    ax.set_xlim(0, 100)
    ax.set_xlabel("Share of measured total input mass (%)")
    ax.set_title("Where the item mass ended up")
    ax.legend(fontsize=8, loc="upper left", bbox_to_anchor=(0, -0.12))
    for i, group in enumerate(groups):
        counts = np.sum([r["overshoot_counts"] for r in group["records"]], axis=0)
        if sum(counts):
            hist.stairs(
                100 * counts / sum(counts),
                group["records"][0]["overshoot_edges"],
                color=COLORS[i % len(COLORS)],
                label=group["label"],
                linewidth=2,
                linestyle=["-", "--", "-.", ":"][i % 4],
            )
    if hist.get_legend_handles_labels()[0]:
        hist.legend(fontsize=8)
    hist.set_title("Overshoot at actual bin closure")
    hist.set_xlabel("Excess load / covering threshold")
    hist.set_ylabel("Covered bins in class (%)")
    fig.suptitle(
        f"Mass accounting · pooled by measured mass · {data['omitted']} invalid measurements excluded\nMeasurements may be missing for older trials/backends; no values are inferred",
        fontsize=11,
    )
    return save(fig, Path(path) / "figures/mass.png", data)


def plot_ordering(paths, target):
    import numpy as np

    from .comparisons import comparison_data, valid

    data = comparison_data(paths)
    data["reference_label"] = reference_label(
        row["reference_kind"]
        for path in paths
        for row in read_trials(path)
        if valid(row)
    )
    if not data["controlled_inputs"] or data["conditions"] < 2:
        raise ValueError(
            "Select at least two ordering/swap settings with matching base trial inputs (same size, generator and input seeds)."
        )
    plt = pyplot()
    fig, ax = plt.subplots(figsize=(12, 6), layout="constrained")
    groups = data["ordering"]
    if not groups:
        raise ValueError("Selected runs have no valid recorded coverage observations.")
    all_conditions = [p for g in groups for p in g["conditions"].values()]
    numeric = (
        bool(all_conditions)
        and all(p["order"] == "swaps" for p in all_conditions)
        and len({p["swap_mode"] for p in all_conditions}) == 1
    )
    categories = sorted({name for g in groups for name in g["conditions"]})
    for i, group in enumerate(groups):
        points = sorted(
            group["conditions"].items(),
            key=lambda p: p[1]["swaps"] if numeric else categories.index(p[0]),
        )
        x = np.array(
            [p["swaps"] if numeric else categories.index(name) for name, p in points],
            dtype=float,
        )
        q1, median, q3 = np.array(
            [np.percentile(p["values"], [25, 50, 75]) for _, p in points]
        ).T
        color = COLORS[i % len(COLORS)]
        if numeric:
            ax.plot(x, median, marker="o", color=color, label=group["label"])
            ax.fill_between(x, q1, q3, color=color, alpha=0.12)
        else:
            x += (i - (len(groups) - 1) / 2) * min(0.12, 0.6 / max(1, len(groups)))
            ax.errorbar(
                x,
                median,
                yerr=[median - q1, q3 - median],
                fmt="o",
                capsize=4,
                color=color,
                label=group["label"],
            )
    if numeric:
        ax.set_xscale("symlog", linthresh=1)
        ax.set_xlabel("Random pair swaps (log spacing; not percentage of items moved)")
    else:
        ax.set_xticks(range(len(categories)), categories, rotation=20)
        ax.set_xlabel("Ordering condition")
    ax.set_ylabel("Covered / " + data["reference_label"] + " (%)")
    ax.set_title("Ordering sensitivity · matching base inputs")
    ax.grid(axis="y", alpha=0.18)
    if groups:
        ax.legend(fontsize=8)
    fig.suptitle(
        "Median and observed middle 50% · not confidence intervals\nFixed-input conclusions are conditional on that multiset",
        fontsize=11,
    )
    return save(fig, target, data)


def plot_parameters(paths, target):
    import numpy as np

    from .comparisons import valid

    families = {}
    for path in dict.fromkeys(map(Path, paths)):
        cfg = json.loads((path / "manifest.json").read_text())["config"]
        context = {
            k: cfg.get(k)
            for k in ("generator", "domain", "threshold", "ordering", "dataset_mode")
        }
        if cfg["ordering"] == "swaps":
            context.update(swaps=cfg["swaps"], swap_mode=cfg["swap_mode"])
        for row in read_trials(path):
            if row["algorithm"] not in {
                "throwbin_retire",
                "throwbin_replace",
            } or not valid(row):
                continue
            params = json.loads(row["parameters"])
            ratio = params.pop("bin_ratio")
            family = (
                row["algorithm"],
                row["backend"],
                json.dumps(params, sort_keys=True),
                json.dumps(context, sort_keys=True),
            )
            cells = families.setdefault(family, {})
            cell = cells.setdefault(
                (row["num_items"], ratio), {"values": [], "inputs": set()}
            )
            cell["values"].append(
                100 * row["covered_bins"] / float(row["reference_value"])
            )
            cell["inputs"].add(
                (
                    row["trial"],
                    row["input_hash"],
                    row.get("base_input_hash"),
                    row["reference_kind"],
                    row["reference_value"],
                )
            )
    families = {k: v for k, v in families.items() if len({r for _, r in v}) >= 2}
    if not families:
        raise ValueError(
            "Select ThrowBin retirement/replacement runs with at least two bin ratios. Keep size, generator, ordering and input seeds matched across ratios."
        )
    for cells in families.values():
        for n in {n for n, _ in cells}:
            inputs = [cell["inputs"] for (size, _), cell in cells.items() if size == n]
            if len(inputs) < 2:
                raise ValueError(
                    "Select at least two bin ratios at every N in the parameter study; a different size alone is not a matched ratio comparison."
                )
            if not inputs[0] or any(s != inputs[0] for s in inputs[1:]):
                raise ValueError(
                    "Parameter comparisons require identical recorded trial inputs and references across bin ratios at each N."
                )
    plt = pyplot()
    fig, axes = plt.subplots(
        len(families),
        2,
        figsize=(13, 6 * len(families)),
        squeeze=False,
        layout="constrained",
    )
    serial = []
    for row_index, (family, cells) in enumerate(families.items()):
        heat, line = axes[row_index]
        context = json.loads(family[3])
        context_label = (
            f"{context['generator']['id']} · {context['ordering']} · "
            f"{context['dataset_mode']} · {context['domain']} · threshold {context['threshold']}"
        )
        if context["ordering"] == "swaps":
            context_label += f" · {context['swaps']} swaps ({context['swap_mode']})"
        other_params = json.loads(family[2])
        if other_params:
            context_label += f"\nOther algorithm parameters: {other_params}"
        denominator = reference_label(
            item[3] for cell in cells.values() for item in cell["inputs"]
        )
        sizes = sorted({n for n, _ in cells})
        ratios = sorted({r for _, r in cells})
        matrix = np.full((len(sizes), len(ratios)), np.nan)
        for i, n in enumerate(sizes):
            points = []
            for j, r in enumerate(ratios):
                if (n, r) in cells:
                    values = cells[n, r]["values"]
                    q1, median, q3 = np.percentile(values, [25, 50, 75])
                    matrix[i, j] = median
                    points.append((r * 100, q1, median, q3))
                    serial.append(
                        {
                            "family": family,
                            "n": n,
                            "bin_ratio": r,
                            "values": values,
                            "trial_inputs": sorted(cells[n, r]["inputs"]),
                        }
                    )
                    heat.text(
                        j,
                        i,
                        f"{median:.1f}%\nn={len(values)}",
                        ha="center",
                        va="center",
                        fontsize=9,
                        color="white" if median < 50 else "black",
                    )
            x, q1, median, q3 = np.array(points).T
            line.plot(x, median, marker="o", label=f"N={n:,}")
            line.fill_between(x, q1, q3, alpha=0.12)
        image = heat.imshow(
            np.ma.masked_invalid(matrix),
            aspect="auto",
            cmap="cividis",
            vmin=0,
            vmax=100,
        )
        heat.set_xticks(range(len(ratios)), [f"{r:.0%}" for r in ratios])
        heat.set_yticks(range(len(sizes)), sizes)
        heat.set_xlabel("Initial active bins / N")
        heat.set_ylabel("Number of items N")
        heat.set_title(
            f"{family[0]} · {family[1]}\n{context_label}\nMedian coverage; blank cells have no observations",
            fontsize=10,
        )
        fig.colorbar(
            image, ax=heat, label="Covered / " + denominator + " (%)", shrink=0.8
        )
        line.set_xlabel("Initial active bins / N (%)")
        line.set_ylabel("Covered / " + denominator + " (%)")
        line.set_title("Parameter sensitivity · median and observed middle 50%")
        line.legend()
        line.grid(axis="y", alpha=0.18)
    fig.suptitle(
        "ThrowBin parameter studies · variant and input families stay separate\nInputs are matched across ratios at each size · ranges are not confidence intervals",
        fontsize=11,
    )
    return save(fig, target, {"cells": serial})


def _saved_runs(paths):
    runs = []
    for path in dict.fromkeys(Path(p).resolve() for p in paths):
        manifest = json.loads((path / "manifest.json").read_text())
        if manifest["status"] in {"queued", "running"}:
            raise ValueError("Wait for selected experiments to finish")
        runs.append((path, manifest["config"], read_trials(path)))
    if not runs:
        raise ValueError("Select at least one experiment")
    return runs


def _research_context(cfg, row):
    context = {
        key: cfg.get(key)
        for key in (
            "generator",
            "domain",
            "threshold",
            "ordering",
            "dataset_mode",
            "seed",
        )
    }
    context["n"] = row["num_items"]
    if cfg["ordering"] == "swaps":
        context.update(swaps=cfg.get("swaps", 0), swap_mode=cfg.get("swap_mode"))
    return context


def _context_label(context):
    generator = context.get("generator") or {}
    order = context["ordering"]
    if order == "swaps":
        order = f"{context['swaps']} swaps ({context['swap_mode']})"
    return f"{generator.get('id', 'saved input')} · N={context['n']:,} · {order} · {context['dataset_mode']} input · seed={context['seed']}"


def _wrapped_label(value, width):
    return "\n".join(
        textwrap.fill(line, width=width, break_long_words=False)
        for line in value.splitlines()
    )


def _record_valid(cfg, row):
    from .comparisons import valid

    try:
        return (
            valid(row)
            and math.isfinite(float(row["reference_value"]))
            and row["covered_bins"] >= 0
            and row["num_items"] is not None
            and row["num_items"] >= 0
            and row.get("domain", cfg["domain"]) == cfg["domain"]
            and float(row.get("threshold", cfg["threshold"])) == float(cfg["threshold"])
        )
    except (TypeError, ValueError, KeyError, OverflowError):
        return False


def reliability_data(paths, target=70):
    """Observed target attainment; failed/invalid trials are excluded, not failures."""
    if (
        type(target) not in (int, float)
        or not 0 <= target <= 100
        or not math.isfinite(target)
    ):
        raise ValueError(
            "Minimum coverage target must be a finite number from 0 to 100"
        )
    target = float(target)
    groups = {}
    omitted = 0
    runs = _saved_runs(paths)
    for path, cfg, rows in runs:
        for row in rows:
            if not _record_valid(cfg, row):
                omitted += 1
                continue
            context = _research_context(cfg, row)
            key = (
                row["algorithm"],
                row["backend"],
                row["parameters"],
                json.dumps(context, sort_keys=True),
                row["reference_kind"],
            )
            group = groups.setdefault(
                key,
                {
                    "label": label(row) + "\n" + _context_label(context),
                    "algorithm": row["algorithm"],
                    "backend": row["backend"],
                    "parameters": row["parameters"],
                    "context": context,
                    "reference_label": reference_label([row["reference_kind"]]),
                    "coverage_percentages": [],
                    "observations": [],
                },
            )
            value = 100 * row["covered_bins"] / float(row["reference_value"])
            group["coverage_percentages"].append(value)
            group["observations"].append(
                {
                    "run": str(path),
                    "trial": row["trial"],
                    "input_hash": row["input_hash"],
                    "covered_bins": row["covered_bins"],
                    "reference_kind": row["reference_kind"],
                    "reference_value": float(row["reference_value"]),
                }
            )
    for group in groups.values():
        values = sorted(group["coverage_percentages"])
        group["total"] = len(values)
        group["reached"] = len(values) - bisect_left(values, target)
        group["percentage"] = 100 * group["reached"] / len(values)
        thresholds = sorted({0.0, 100.0, target, *values})
        group["curve"] = [
            {
                "target": value,
                "percentage": 100
                * (len(values) - bisect_left(values, value))
                / len(values),
            }
            for value in thresholds
        ]
    return {
        "target": target,
        "groups": list(groups.values()),
        "omitted": omitted,
        "runs": [str(path) for path, _, _ in runs],
    }


def plot_reliability(paths, destination=None, target=70):
    data = reliability_data(paths, target)
    groups = data["groups"]
    if not groups:
        raise ValueError(
            "No valid recorded percentage observations for target achievement"
        )
    plt = pyplot()
    columns = min(3, len(groups))
    rows = math.ceil(len(groups) / columns)
    fig, axes = plt.subplots(
        rows,
        columns,
        figsize=(5 * columns, 4.8 * rows),
        squeeze=False,
        layout="constrained",
    )
    values = [value for group in groups for value in group["coverage_percentages"]]
    lower = max(0, min(min(values), data["target"]) - 5)
    upper = min(100, max(max(values), data["target"]) + 5)
    for index, (ax, group) in enumerate(zip(axes.flat, groups, strict=False)):
        curve = group["curve"]
        color = COLORS[index % len(COLORS)]
        ax.step(
            [p["target"] for p in curve],
            [p["percentage"] for p in curve],
            where="pre",
            color=color,
            linewidth=2.3,
        )
        ax.axvline(data["target"], color="#65645c", linestyle=":", linewidth=1.4)
        ax.scatter([data["target"]], [group["percentage"]], color=color, s=50, zorder=5)
        ax.set_title(
            f"{_wrapped_label(group['label'], 46)}\nAt {data['target']:g}%: {group['reached']}/{group['total']} trials ({group['percentage']:.1f}%)",
            fontsize=10,
        )
        ax.set_xlabel(f"Minimum covered / {group['reference_label']} (%)", fontsize=9)
        ax.set_ylabel("Observed trials reaching at least target (%)", fontsize=9)
        ax.set_xlim(lower, upper)
        ax.set_ylim(-3, 103)
        ax.set_yticks([0, 25, 50, 75, 100])
        ax.grid(axis="y", alpha=0.2)
    for ax in list(axes.flat)[len(groups) :]:
        ax.set_visible(False)
    fig.suptitle(
        f"How often does each algorithm reach your minimum target?\nHigher targets are harder to reach · target equality counts as reached\n{data['omitted']} invalid/failed observations excluded · observed frequencies, not guarantees",
        fontsize=12,
    )
    if destination is None:
        token = hashlib.sha256(repr(data["target"]).encode()).hexdigest()[:12]
        destination = Path(data["runs"][0]) / "figures" / f"reliability-{token}.png"
    return save(fig, destination, data)


def paired_data(paths):
    """Candidate minus DNF counts, with the established local/backend precedence."""
    runs = _saved_runs(paths)

    def pairing_key(cfg, row):
        return (
            row["trial"],
            row["input_hash"],
            cfg["domain"],
            cfg["threshold"],
            row["reference_kind"],
            float(row["reference_value"]),
        )

    baselines = {}
    invalid_baselines = 0
    for path, cfg, rows in runs:
        for row in rows:
            if row["algorithm"] != "dual_next_fit":
                continue
            if _record_valid(cfg, row):
                baselines.setdefault(pairing_key(cfg, row), []).append((path, row))
            else:
                invalid_baselines += 1
    groups = {}
    exclusions = {
        "invalid_candidate": 0,
        "missing_baseline": 0,
        "ambiguous_baseline": 0,
    }
    for path, cfg, rows in runs:
        for row in rows:
            if row["algorithm"] == "dual_next_fit":
                continue
            if not _record_valid(cfg, row):
                exclusions["invalid_candidate"] += 1
                continue
            choices = baselines.get(pairing_key(cfg, row), [])
            local = [candidate for candidate in choices if candidate[0] == path]
            choices = local or choices
            same_backend = [
                candidate
                for candidate in choices
                if candidate[1]["backend"] == row["backend"]
            ]
            choices = same_backend or choices
            if not choices:
                exclusions["missing_baseline"] += 1
                continue
            if (
                len(
                    {
                        (
                            candidate["covered_bins"],
                            candidate["backend"],
                            candidate["parameters"],
                        )
                        for _, candidate in choices
                    }
                )
                != 1
            ):
                exclusions["ambiguous_baseline"] += 1
                continue
            baseline_path, baseline = choices[0]
            context = _research_context(cfg, row)
            key = (
                row["algorithm"],
                row["backend"],
                row["parameters"],
                baseline["backend"],
                baseline["parameters"],
                json.dumps(context, sort_keys=True),
                row["reference_kind"],
            )
            group = groups.setdefault(
                key,
                {
                    "label": label(row)
                    + f"\nCompared with DNF · {baseline['backend']} · {baseline['parameters']}\n"
                    + _context_label(context),
                    "algorithm": row["algorithm"],
                    "backend": row["backend"],
                    "parameters": row["parameters"],
                    "baseline_backend": baseline["backend"],
                    "baseline_parameters": baseline["parameters"],
                    "context": context,
                    "reference_label": reference_label([row["reference_kind"]]),
                    "points": [],
                },
            )
            group["points"].append(
                {
                    "run": str(path),
                    "baseline_run": str(baseline_path),
                    "trial": row["trial"],
                    "input_hash": row["input_hash"],
                    "candidate_bins": row["covered_bins"],
                    "dnf_bins": baseline["covered_bins"],
                    "difference_bins": row["covered_bins"] - baseline["covered_bins"],
                    "reference_kind": row["reference_kind"],
                    "reference_value": float(row["reference_value"]),
                    "domain": cfg["domain"],
                    "threshold": cfg["threshold"],
                }
            )
    for group in groups.values():
        differences = [point["difference_bins"] for point in group["points"]]
        group.update(
            total=len(differences),
            loss=sum(d < 0 for d in differences),
            tie=sum(d == 0 for d in differences),
            gain=sum(d > 0 for d in differences),
            median_extra_bins=statistics.median(differences),
        )
        group["histogram"] = [
            {
                "difference_bins": difference,
                "count": count,
                "percentage": 100 * count / len(differences),
            }
            for difference, count in sorted(Counter(differences).items())
        ]
    return {
        "groups": list(groups.values()),
        "unmatched": sum(exclusions.values()),
        "exclusions": exclusions,
        "invalid_baselines": invalid_baselines,
        "runs": [str(path) for path, _, _ in runs],
    }


def plot_paired(paths, destination=None):
    from matplotlib.patches import Patch

    data = paired_data(paths)
    groups = data["groups"]
    if not groups:
        raise ValueError(
            "No valid pairs. Select recorded DNF and at least one other algorithm on identical ordered trial inputs, with matching references, domain and threshold."
        )
    plt = pyplot()
    fig, axes = plt.subplots(
        len(groups),
        1,
        figsize=(12, 4.4 * len(groups)),
        squeeze=False,
        layout="constrained",
    )
    limit = (
        max(
            1,
            max(abs(p["difference_bins"]) for group in groups for p in group["points"]),
        )
        + 1
    )
    shades = {"loss": "#A6313E", "tie": "#65645C", "gain": "#0072B2"}
    for ax, group in zip(axes[:, 0], groups, strict=True):
        histogram = group["histogram"]
        ax.bar(
            [p["difference_bins"] for p in histogram],
            [p["percentage"] for p in histogram],
            color=[
                shades[
                    "loss"
                    if p["difference_bins"] < 0
                    else "gain"
                    if p["difference_bins"] > 0
                    else "tie"
                ]
                for p in histogram
            ],
            width=0.9,
        )
        ax.axvline(0, color="#26251d", linewidth=1.3)
        ax.set_xlim(-limit, limit)
        from matplotlib.ticker import MaxNLocator

        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        ax.set_title(
            f"{group['label']}\nFewer bins: {group['loss']}/{group['total']} · Equal: {group['tie']}/{group['total']} · More bins: {group['gain']}/{group['total']}",
            loc="left",
            fontsize=10,
        )
        ax.set_xlabel(
            "Extra covered bins (candidate − DNF) · negative = fewer · zero = equal · positive = more"
        )
        ax.set_ylabel("Matched trial pairs (%)")
        ax.grid(axis="y", alpha=0.2)
        ax.set_axisbelow(True)
        ax.legend(
            handles=[
                Patch(facecolor=shades["loss"], label="Red: fewer bins than DNF"),
                Patch(facecolor=shades["tie"], label="Gray: equal number of bins"),
                Patch(facecolor=shades["gain"], label="Blue: more bins than DNF"),
            ],
            fontsize=8,
        )
    fig.suptitle(
        f"Does the candidate cover more bins than DNF?\nSame ordered input in every pair · colours describe loss/tie/gain\n{data['unmatched']} invalid/unmatched candidates and {data['invalid_baselines']} invalid baselines excluded · frequencies are descriptive",
        fontsize=12,
    )
    if destination is None:
        destination = Path(data["runs"][0]) / "figures" / "paired.png"
    return save(fig, destination, data)


def render_plot(
    paths, kind, target=None, algorithm=0, panel="all", minimum_coverage=70
):
    with PLOT_LOCK:
        if kind == "overview":
            return plot_overview(paths[0], algorithm, panel)
        if kind == "mass":
            return plot_mass(paths[0])
        if kind == "ordering":
            return plot_ordering(paths, target)
        if kind == "parameters":
            return plot_parameters(paths, target)
        if kind == "reliability":
            return plot_reliability(paths, target, minimum_coverage)
        if kind == "paired":
            return plot_paired(paths, target)
        raise ValueError("Unknown plot type")
