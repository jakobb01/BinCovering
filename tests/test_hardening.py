import importlib
import json
import random
from datetime import UTC, datetime, timedelta

import pytest

from bincovering.algorithms.registry import normalize, solve
from bincovering.experiments.artifacts import export_run, rerun
from bincovering.experiments.config import validate
from bincovering.experiments.lifecycle import RunLease, reconcile_runs
from bincovering.experiments.runner import run_experiment
from bincovering.experiments.storage import write_json
from bincovering.generators.instances import generate
from bincovering.web.app import create_app


@pytest.mark.parametrize(
    "cfg",
    [
        None,
        [],
        {"name": 1},
        {"generator": None},
        {"generator": []},
        {"algorithms": [None]},
        {"algorithms": [{}]},
        {"algorithms": [{"id": []}]},
        {"algorithms": [{"id": "dnf", "params": None}]},
        {"algorithms": [{"id": "ThrowBin", "params": {"bin_ratio": "bad"}}]},
        {"algorithms": [{"id": "AdaptiveBinCovered", "params": {"multiplier": True}}]},
        {"output_root": None},
        {"threshold": True},
        {"generator": {"id": "file"}},
    ],
)
def test_malformed_settings(cfg):
    with pytest.raises(ValueError):
        validate(cfg)


@pytest.mark.parametrize(
    "cfg",
    [{"generator": None}, {"algorithms": [{}]}, {"name": []}, {"output_root": None}],
)
def test_web_invalid_settings_return_400(tmp_path, cfg):
    # output root is intentionally server-controlled, so a caller's null is ignored.
    if "output_root" in cfg:
        cfg = {"workers": False}
    response = create_app(tmp_path).test_client().post("/api/runs", json=cfg)
    assert response.status_code == 400


@pytest.mark.parametrize(
    "items,expected",
    [
        ([0.125, 0.125], 0),
        ([0.125, 0.125, 0.75], 1),
        ([0.75, 0.125, 0.125], 1),
        ([0.75] + [0.125] * 10, 2),
        ([1.0, 1.0], 2),
    ],
)
def test_advice_physical_accounting(items, expected):
    spec = normalize({"id": "advice", "params": {"m": 1, "x_m": 0.75}})
    assert solve(items, spec, 1.0, 0).covered_bins == expected


def test_advice_variants_are_distinct_and_zero_reservations_work():
    items = [0.2] * 5
    spec = normalize({"id": "advice", "params": {"m": 0}})
    assert solve(items, spec, 1.0, 0).covered_bins == 1
    assert normalize({"id": "advice_k"})["id"] == "advice_reserved_k4"


@pytest.mark.parametrize(
    "generator,module,method,args",
    [
        ("one_over_n", "OneOverN", "_generate_complementary_pairs", (40,)),
        (
            "optimal_uniform_legacy",
            "OptimalUniformGenerator",
            "_generate_items_for_bins",
            (4,),
        ),
    ],
)
def test_historical_generator_matches_source(
    monkeypatch, generator, module, method, args
):
    imported = importlib.import_module("bincovering.generators." + module)
    monkeypatch.setattr(imported, "random", random.Random(5))
    cls = getattr(imported, "OneOverNGenerator" if module == "OneOverN" else module)
    original = getattr(cls(), method)(*args)
    original.sort(reverse=True)
    cfg = validate(
        {"n": 40, "ordering": "original", "generator": {"id": generator, "bins": 4}}
    )
    items, info = generate(cfg, 5, 3)
    assert items == original
    assert info["exact_optimum"] is None


def test_requested_optimum_is_not_a_certificate():
    cfg = validate(
        {
            "generator": {
                "id": "optimal_uniform_legacy",
                "min": 0.51,
                "max": 0.51,
                "bins": 2,
            },
            "ordering": "original",
        }
    )
    items, info = generate(cfg, 1, 2)
    assert items == [0.51, 0.51]
    assert info["construction_target"] == 2
    assert info["upper_bound"] == 1
    assert info["exact_optimum"] is None


def test_lease_and_restart_recovery(tmp_path):
    path = tmp_path / "run"
    path.mkdir()
    write_json(
        path / "manifest.json",
        {
            "name": "test",
            "status": "running",
            "created_at": datetime.now(UTC).isoformat(),
        },
    )
    with RunLease(path):
        with pytest.raises(ValueError, match="active worker"):
            with RunLease(path):
                pass
        reconcile_runs(tmp_path, 0)
        assert json.loads((path / "manifest.json").read_text())["status"] == "running"
    reconcile_runs(tmp_path, 0)
    assert json.loads((path / "manifest.json").read_text())["status"] == "interrupted"


def test_queued_job_has_startup_grace(tmp_path):
    path = tmp_path / "run"
    path.mkdir()
    record = {
        "name": "test",
        "status": "queued",
        "created_at": datetime.now(UTC).isoformat(),
    }
    write_json(path / "manifest.json", record)
    reconcile_runs(tmp_path)
    assert json.loads((path / "manifest.json").read_text())["status"] == "queued"
    record["created_at"] = (datetime.now(UTC) - timedelta(seconds=60)).isoformat()
    write_json(path / "manifest.json", record)
    reconcile_runs(tmp_path)
    assert json.loads((path / "manifest.json").read_text())["status"] == "interrupted"


def test_file_is_frozen_and_rerunnable(tmp_path):
    source = tmp_path / "data.txt"
    source.write_text("0.25\n0.75\n")
    path = run_experiment(
        {
            "output_root": str(tmp_path),
            "trials": 1,
            "generator": {"id": "file", "path": str(source)},
        }
    )
    source.unlink()
    repeated = rerun(path)
    assert (repeated / "input-source.txt").read_text() == "0.25\n0.75\n"
    assert json.loads((repeated / "manifest.json").read_text())["rerun_of"] == str(path)
    assert export_run(path).is_file()


def test_generation_failures_leave_rows_and_summary(tmp_path):
    source = tmp_path / "bad.txt"
    source.write_text("not-a-number")
    path = run_experiment(
        {
            "output_root": str(tmp_path),
            "trials": 2,
            "generator": {"id": "file", "path": str(source)},
        }
    )
    assert json.loads((path / "manifest.json").read_text())["status"] == "failed"
    assert json.loads((path / "summary.json").read_text())[0]["failed_trials"] == 2
    assert "Input generation" in (path / "trials.csv").read_text()


def test_float_reference_mismatch_is_visible(tmp_path):
    source = tmp_path / "boundary.txt"
    source.write_text("0.3\n0.7\n")
    path = run_experiment(
        {
            "output_root": str(tmp_path),
            "trials": 1,
            "algorithms": [{"id": "dnf"}],
            "generator": {"id": "file", "path": str(source)},
        }
    )
    assert "floating-point boundary" in (path / "trials.csv").read_text()


def test_cleanup_preserves_evidence_and_pinned_runs(tmp_path, monkeypatch, capsys):
    import sys

    from bincovering.cli import main

    paths = []
    for pinned in (False, True):
        path = run_experiment({"output_root": str(tmp_path), "n": 10, "trials": 1})
        (path / "figures").mkdir()
        (path / "figures" / "plot.png").write_bytes(b"derived")
        (path / "traces").mkdir()
        (path / "traces" / "trace.json").write_text("[]")
        if pinned:
            (path / "PINNED").touch()
        paths.append(path)
    monkeypatch.setattr(
        sys, "argv", ["bincovering", "cleanup", "--root", str(tmp_path)]
    )
    main()
    assert "Would remove" in capsys.readouterr().out
    assert all((path / "figures").is_dir() for path in paths)
    monkeypatch.setattr(sys, "argv", sys.argv + ["--apply"])
    main()
    assert not (paths[0] / "figures").exists()
    assert not (paths[0] / "traces").exists()
    assert (paths[1] / "figures" / "plot.png").is_file()
    for path in paths:
        for name in (
            "trials.csv",
            "manifest.json",
            "config.json",
            "source.zip",
            "run.log",
        ):
            assert (path / name).is_file()
