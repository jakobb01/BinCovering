import csv
import json
import threading
from pathlib import Path

from bincovering.experiments.runner import summarize

PLOT_LOCK = threading.RLock()


def reference_label(kinds):
    kinds = set(kinds)
    if kinds and kinds <= {"exact_optimum", "constructed_optimum"}:
        return "known optimum"
    if kinds == {"mass_upper_bound"}:
        return "mass upper bound (not OPT)"
    return "recorded reference (OPT / upper bound)"


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
        display = row.get("algorithm_name") or key[0]
        if row.get("algorithm_revision"):
            display += f" · revision {row['algorithm_revision']} · {row.get('input_access', '')}"
        group = groups.setdefault(
            key,
            {
                "label": f"{display} ({key[1]})\n{key[2]}",
                "trials": [],
                "percentages": [],
                "counts": [],
                "reference_kinds": [],
                "references": [],
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
            group["references"].append(reference)
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
    return {
        "groups": list(groups.values()),
        "inputs": inputs,
        "reference_label": reference_label(kinds),
        "omitted": omitted,
        "input_trials": len(seen_trials),
        "dataset_mode": cfg.get("dataset_mode", "fresh"),
    }


def _plot_run(path):
    from .visualizations import plot_overview

    return plot_overview(path)


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
