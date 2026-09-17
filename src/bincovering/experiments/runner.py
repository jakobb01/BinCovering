"""Shared CLI/web runner. Workers own trial state; only the parent writes results."""

import csv
import hashlib
import json
import logging
import multiprocessing
import shutil
import statistics
import time
import zipfile
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from pathlib import Path

from bincovering.algorithms.registry import solve
from bincovering.experiments.config import validate
from bincovering.experiments.lifecycle import RunLease
from bincovering.experiments.storage import new_run, now, provenance, write_json
from bincovering.generators.instances import generate


def seed_for(seed, trial, purpose):
    return int.from_bytes(
        hashlib.sha256(f"{seed}:{trial}:{purpose}".encode()).digest()[:8], "big"
    )


def trial_job(cfg, trial, out):
    out = Path(out)

    def cancelled():
        return (out / "CANCEL").exists()

    if cancelled():
        raise InterruptedError("Cancelled")
    data_seed = seed_for(
        cfg["seed"], trial if cfg["dataset_mode"] == "fresh" else 0, "data"
    )
    order_seed = seed_for(cfg["seed"], trial, "order")
    input_error = None
    try:
        items, info = generate(cfg, data_seed, order_seed, cancelled)
    except InterruptedError:
        raise
    except Exception as exc:
        items = []
        info = dict(
            base_input_hash=None,
            input_hash=None,
            upper_bound=None,
            exact_optimum=None,
            construction_target=None,
            reference_kind="unavailable",
        )
        input_error = f"Input generation: {type(exc).__name__}: {exc}"
    if cfg["save_inputs"]:
        (out / "inputs").mkdir(exist_ok=True)
        write_json(out / "inputs" / f"{trial}.json", items)
    rows = []
    for i, spec in enumerate(cfg["algorithms"]):
        if cancelled():
            raise InterruptedError("Cancelled")
        algorithm_seed = seed_for(
            cfg["seed"],
            trial,
            json.dumps({"id": spec["id"], "params": spec["params"]}, sort_keys=True),
        )
        row = {
            "trial": trial,
            "algorithm": spec["id"],
            "backend": spec["backend"],
            "parameters": json.dumps(spec["params"], sort_keys=True),
            "data_seed": data_seed,
            "order_seed": order_seed,
            "algorithm_seed": algorithm_seed,
            "num_items": len(items),
            "domain": cfg["domain"],
            "threshold": cfg["threshold"],
            **info,
            "status": "completed",
            "error": "",
            "covered_bins": None,
            "discarded_items": None,
            "ratio_to_reference": None,
            "numeric_warning": "",
            "reference_value": info["exact_optimum"]
            if info["exact_optimum"] is not None
            else info["upper_bound"],
        }
        trace = []

        def capture(index, item, covered, trace=trace):
            if len(trace) < cfg["trace_limit"]:
                trace.append({"index": index, "item": item, "covered_bins": covered})

        start = time.perf_counter()
        try:
            if input_error:
                raise ValueError(input_error)
            if spec["backend"] == "cpp":
                from bincovering.backends.native import solve_native

                result = solve_native(
                    items,
                    spec,
                    cfg["domain"],
                    cfg["threshold"],
                    cfg["native_executable"],
                    cancelled,
                )
            else:
                result = solve(
                    items,
                    spec,
                    cfg["threshold"],
                    algorithm_seed,
                    capture if cfg["trace_limit"] else None,
                    cancelled,
                )
            row["covered_bins"] = result.covered_bins
            row["discarded_items"] = result.discarded_items
            if (
                row["reference_value"] is not None
                and result.covered_bins > row["reference_value"]
            ):
                row["numeric_warning"] = (
                    "Computed coverage exceeds the real-arithmetic reference; inspect floating-point boundary effects."
                )
            elif row["reference_value"]:
                row["ratio_to_reference"] = result.covered_bins / row["reference_value"]
        except InterruptedError:
            raise
        except Exception as exc:
            row.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        row["elapsed_seconds"] = time.perf_counter() - start
        if trace:
            (out / "traces").mkdir(exist_ok=True)
            write_json(out / "traces" / f"{trial}-{i}.json", trace)
        rows.append(row)
    return rows


def summarize(rows):
    groups = {}
    for row in rows:
        key = (row["algorithm"], row["backend"], row["parameters"])
        groups.setdefault(key, []).append(row)
    result = []
    for (name, backend, params), group in groups.items():
        scores = [r["covered_bins"] for r in group if r["status"] == "completed"]
        result.append(
            {
                "algorithm": name,
                "backend": backend,
                "parameters": json.loads(params),
                "successful_trials": len(scores),
                "failed_trials": len(group) - len(scores),
                "mean_covered": statistics.mean(scores) if scores else None,
                "stdev_covered": statistics.stdev(scores)
                if len(scores) > 1
                else 0
                if scores
                else None,
                "min_covered": min(scores) if scores else None,
                "max_covered": max(scores) if scores else None,
            }
        )
    return result


def run_experiment(raw, output_dir=None):
    cfg = validate(raw)
    out = Path(output_dir).resolve() if output_dir else new_run(cfg["output_root"])
    out.mkdir(parents=True, exist_ok=True)
    with RunLease(out):
        return _run_owned(cfg, out)


def _run_owned(cfg, out):
    if (out / "manifest.json").exists():
        existing = json.loads((out / "manifest.json").read_text())
        if existing["status"] != "queued":
            raise ValueError("Refusing to overwrite an existing run")
    logger = logging.getLogger("bincovering.run." + out.name)
    handler = logging.FileHandler(out / "run.log")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    manifest = {
        "schema_version": 2,
        "name": cfg["name"],
        "status": "running",
        "created_at": now(),
        "completed_trials": 0,
        "total_trials": cfg["trials"],
        "config": cfg,
        "timing_scope": "algorithm adapter; native includes subprocess and serialization; excludes generation and plots",
        "trace_enabled": bool(cfg["trace_limit"]),
    }
    rows = []
    try:
        write_json(out / "manifest.json", manifest)
        if cfg["generator"]["id"] == "file":
            source = Path(cfg["generator"]["path"])
            frozen = out / "input-source.txt"
            shutil.copyfile(source, frozen)
            manifest["input_source"] = {
                "original_path": str(source),
                "sha256": hashlib.sha256(frozen.read_bytes()).hexdigest(),
            }
            cfg["generator"]["path"] = str(frozen)
        manifest["provenance"] = provenance(out)
        if any(a["backend"] == "cpp" for a in cfg["algorithms"]):
            executable = Path(cfg["native_executable"])
            manifest["native_sha256"] = hashlib.sha256(
                executable.read_bytes()
            ).hexdigest()
            shutil.copy2(executable, out / "native-executable")
            native_source = executable.parent.parent / "cpp"
            if native_source.is_dir():
                with zipfile.ZipFile(
                    out / "native-source.zip", "w", zipfile.ZIP_DEFLATED
                ) as archive:
                    for source in sorted(native_source.rglob("*")):
                        if source.is_file() and source.suffix in (".cpp", ".hpp", ".h"):
                            archive.write(
                                source, str(source.relative_to(native_source))
                            )
            build_cache = executable.parent / "CMakeCache.txt"
            if build_cache.is_file():
                manifest["native_build_settings"] = [
                    line
                    for line in build_cache.read_text().splitlines()
                    if line.startswith(
                        ("CMAKE_BUILD_TYPE:", "CMAKE_CXX_COMPILER:", "CMAKE_CXX_FLAGS")
                    )
                ]
            # Execute the recorded binary even if a concurrent build replaces the original.
            cfg["native_executable"] = str(out / "native-executable")
        write_json(out / "config.json", cfg)
        write_json(out / "manifest.json", manifest)
        with (out / "trials.csv").open("w", newline="") as stream:
            writer = None

            def collect(batch):
                nonlocal writer
                if writer is None:
                    writer = csv.DictWriter(stream, fieldnames=list(batch[0]))
                    writer.writeheader()
                writer.writerows(batch)
                stream.flush()
                rows.extend(batch)
                manifest["completed_trials"] += 1
                write_json(out / "manifest.json", manifest)
                logger.info(
                    "Completed trial %s/%s", manifest["completed_trials"], cfg["trials"]
                )

            if cfg["workers"] == 1:
                for trial in range(cfg["trials"]):
                    collect(trial_job(cfg, trial, str(out)))
            else:
                with ProcessPoolExecutor(
                    max_workers=cfg["workers"],
                    mp_context=multiprocessing.get_context("spawn"),
                ) as pool:
                    trials = iter(range(cfg["trials"]))
                    pending = set()

                    def refill():
                        while len(pending) < 2 * cfg["workers"]:
                            trial = next(trials, None)
                            if trial is None:
                                break
                            pending.add(pool.submit(trial_job, cfg, trial, str(out)))

                    refill()
                    try:
                        while pending:
                            done, pending = wait(pending, return_when=FIRST_COMPLETED)
                            for future in done:
                                collect(future.result())
                            refill()
                    except BaseException:
                        (out / "CANCEL").touch()
                        for future in pending:
                            future.cancel()
                        raise
        manifest["status"] = (
            "failed" if any(r["status"] == "failed" for r in rows) else "completed"
        )
        write_json(out / "summary.json", summarize(rows))
        if cfg["plot"]:
            from bincovering.reporting.reports import plot_run

            plot_run(out)
    except (InterruptedError, KeyboardInterrupt):
        manifest["status"] = "cancelled"
        (out / "CANCEL").touch()
        write_json(out / "summary.json", summarize(rows))
    except Exception as exc:
        manifest.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        logger.exception("Run failed")
        raise
    finally:
        write_json(out / "summary.json", summarize(rows))
        manifest["finished_at"] = now()
        write_json(out / "manifest.json", manifest)
        logger.removeHandler(handler)
        handler.close()
    return out
