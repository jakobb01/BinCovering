"""Research pipeline and actual isolation checks, run by the primary verifier.

Set BINCOVERING_ISOLATION=1 after building tools/Containerfile.builder.
"""

import json
import os
import subprocess
import time
import uuid

import pytest

from bincovering.builders.execution import (
    container_command,
    execute_isolated,
    runtime_identity,
    settings,
)
from bincovering.builders.schema import RUNTIME_VERSION, generated_source, graph_hash
from bincovering.builders.templates import get_template
from bincovering.experiments.runner import run_experiment, seed_for

ISOLATION = pytest.mark.skipif(
    os.environ.get("BINCOVERING_ISOLATION") != "1", reason="opt-in actual rootless isolation"
)


def spec(graph, image, identity=None, revision="1", params=None):
    identity = identity or "custom:" + uuid.uuid4().hex
    frozen = {"id": identity, "name": graph.get("name", "Custom"), "revision": revision,
              "graph": graph, "content_hash": graph_hash(graph), "runtime_version": RUNTIME_VERSION,
              "runtime_image": image, "generated_source": generated_source(graph)}
    return {"id": identity, "revision": revision, "params": params or {}, "backend": "python", "frozen": frozen}


@ISOLATION
def test_actual_container_controls_and_no_host_mounts(tmp_path):
    identity = runtime_identity(tmp_path)
    command = container_command(identity["image"], "bincovering-builder-check-" + uuid.uuid4().hex, settings(tmp_path)["limits"])
    probe = (
        "import json,pathlib,socket; p=pathlib.Path; "
        "print(json.dumps({'cpu':p('/sys/fs/cgroup/cpu.max').read_text().strip(),"
        "'memory':p('/sys/fs/cgroup/memory.max').read_text().strip(),"
        "'pids':p('/sys/fs/cgroup/pids.max').read_text().strip(),"
        "'status':p('/proc/self/status').read_text(),"
        "'host_exists':p('/home/jakob/ws/BinCovering').exists(),"
        "'socket_exists':p('/run/user/1000/podman/podman.sock').exists(),"
        "'interfaces':list(p('/sys/class/net').iterdir()).__len__(),"
        "'root_readonly':next(line for line in p('/proc/mounts').read_text().splitlines() if line.split()[1]=='/').split()[3]}))"
    )
    command[-3:] = ["python", "-c", probe]
    result = subprocess.run(command, capture_output=True, text=True, timeout=30, check=True)
    evidence = json.loads(result.stdout)
    assert evidence["memory"] == str(256 * 1024 * 1024)
    assert evidence["pids"] == "64"
    assert evidence["cpu"].split()[0] != "max"
    assert "CapEff:\t0000000000000000" in evidence["status"]
    assert "NoNewPrivs:\t1" in evidence["status"]
    assert "Seccomp:\t2" in evidence["status"]
    assert evidence["root_readonly"].split(",")[0] == "ro"
    assert evidence["interfaces"] == 1
    assert not evidence["host_exists"] and not evidence["socket_exists"]


@ISOLATION
def test_custom_preview_runner_pairing_workers_revisions_and_frozen_rerun(tmp_path):
    from bincovering.experiments.artifacts import export_run, rerun
    from bincovering.reporting.reports import read_trials

    image = runtime_identity(tmp_path)["image"]
    algorithm = spec(get_template("online"), image)
    generator = spec(get_template("generator"), image)
    params = {"min_size": 0.1, "max_size": 0.9}
    generator["params"] = params
    base = {"output_root": str(tmp_path), "n": 12, "trials": 2, "seed": 73,
            "generator": generator, "algorithms": [algorithm, {"id": "dual_next_fit"}],
            "ordering": "original", "save_inputs": True, "trace_limit": 300,
            "trace_trials": [0], "trace_bytes": 200000}
    first = run_experiment(base)
    second = run_experiment({**base, "workers": 2})
    rows_a, rows_b = read_trials(first), read_trials(second)
    keys = ("trial", "algorithm", "parameters", "input_hash", "algorithm_seed", "covered_bins", "status")
    # Parallel trials deliberately write in completion order; compare trial identity.
    rows_a.sort(key=lambda row: (row["trial"], row["algorithm"]))
    rows_b.sort(key=lambda row: (row["trial"], row["algorithm"]))
    assert [{k: r[k] for k in keys} for r in rows_a] == [{k: r[k] for k in keys} for r in rows_b]
    assert {r["status"] for r in rows_a} == {"completed"}
    for trial in (0, 1):
        paired = [r for r in rows_a if int(r["trial"]) == trial]
        assert len({r["input_hash"] for r in paired}) == 1
        assert len({r["covered_bins"] for r in paired}) == 1
    generated = execute_isolated(get_template("generator"), n=12, seed=seed_for(73, 0, "data"), params=params,
                                 root=tmp_path, runtime_image=image)
    assert generated["result"]["items"] == json.loads((first / "inputs" / "0.json").read_text())
    algorithm_seed = seed_for(73, 0, json.dumps({"id": algorithm["id"], "params": {}}, sort_keys=True))
    preview = execute_isolated(algorithm["frozen"]["graph"], items=generated["result"]["items"], seed=algorithm_seed,
                              root=tmp_path, runtime_image=image, trace_limit=300, trace_bytes=200000)
    saved_trace = json.loads((first / "traces" / "0-0.json").read_text())
    assert saved_trace["events"] == preview["trace"]["events"]
    assert not (first / "traces" / "1-0.json").exists()
    assert (first / "builder-programs" / "algorithm-0.py").is_file()
    assert export_run(first).is_file()
    old_graph = json.loads(json.dumps(algorithm["frozen"]["graph"]))
    algorithm["frozen"]["graph"]["name"] = "A later editable library name"
    repeated = rerun(first, tmp_path)
    assert json.loads((repeated / "config.json").read_text())["algorithms"][0]["frozen"]["graph"] == old_graph
    assert json.loads((repeated / "manifest.json").read_text())["rerun_of"] == str(first)


@ISOLATION
def test_actual_timeout_cancellation_invalid_runtime_and_trace_bounds(tmp_path, monkeypatch):
    from bincovering.builders.execution import IsolationError

    image = runtime_identity(tmp_path)["image"]
    graph = get_template("online")
    truncated = execute_isolated(graph, items=[0.6, 0.6], root=tmp_path, runtime_image=image, trace_limit=1)
    assert truncated["ok"] and truncated["trace"]["truncated"]
    assert len(truncated["trace"]["events"]) <= 1
    with pytest.raises(InterruptedError):
        execute_isolated(graph, root=tmp_path, cancelled=lambda: True)
    with pytest.raises(IsolationError):
        execute_isolated(graph, root=tmp_path, runtime_image="sha256:" + "0" * 64)
    tiny = tmp_path / ".dashboard"
    tiny.mkdir(exist_ok=True)
    (tiny / "execution.json").write_text(json.dumps({"limits": {"seconds": 0.001}}))
    with pytest.raises(IsolationError, match="time limit"):
        execute_isolated(graph, items=[0.6, 0.6], root=tmp_path, runtime_image=image)


@ISOLATION
def test_durable_queue_resumes_pending_work_and_cancels_running_preview(tmp_path, monkeypatch):
    from bincovering.builders.jobs import TERMINAL, Supervisor

    def until(queue, owner, job_id, predicate):
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            row = queue.get_job(owner, job_id)
            if predicate(row):
                return row
            time.sleep(0.05)
        pytest.fail(f"Queue did not reach the expected state: {row}")

    paused = Supervisor(tmp_path, dispatch=False)
    monkeypatch.setattr(paused, "start", lambda: None)
    queued = paused.submit_preview("alice", get_template("generator"), {"n": 3, "trace_limit": 0})["id"]
    assert paused.get_job("alice", queued)["status"] == "queued"
    resumed = Supervisor(tmp_path)
    complete = until(resumed, "alice", queued, lambda r: r["status"] in TERMINAL)
    assert complete["status"] == "completed", complete
    assert len(complete["result"]["result"]["items"]) == 3
    assert complete["result"]["execution"]["isolation"] == "rootless-podman"

    running = resumed.submit_preview("alice", get_template("generator"), {"n": 10000, "trace_limit": 0})["id"]
    until(resumed, "alice", running, lambda r: r["status"] == "running")
    observer = Supervisor(tmp_path, dispatch=False)
    observer.reconcile()
    assert observer.get_job("alice", running)["status"] == "running"
    with pytest.raises(ValueError, match="Unknown job"):
        observer.cancel_job("bob", running)
    observer.cancel_job("alice", running)
    cancelled = until(observer, "alice", running, lambda r: r["status"] in TERMINAL)
    assert cancelled["status"] == "cancelled", cancelled


@ISOLATION
def test_actual_output_and_supervisor_time_budgets(tmp_path):
    from bincovering.builders.execution import IsolationError
    from bincovering.builders.jobs import TERMINAL, Supervisor

    state = tmp_path / ".dashboard"
    state.mkdir()
    (state / "execution.json").write_text(json.dumps({"limits": {"output_bytes": 64}}))
    with pytest.raises(IsolationError, match="output limit"):
        execute_isolated(get_template("generator"), n=1, root=tmp_path)
    (state / "execution.json").unlink()
    (state / "queue.json").write_text(json.dumps({"job_seconds": 1}))
    queue = Supervisor(tmp_path)
    job_id = queue.submit_preview("alice", get_template("generator"), {"n": 10000, "trace_limit": 0})["id"]
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        row = queue.get_job("alice", job_id)
        if row["status"] in TERMINAL:
            break
        time.sleep(0.05)
    assert row["status"] == "failed", row
    assert row["error"]["code"] == "timeout"


def test_frozen_content_and_parameter_domain_rejection():
    from bincovering.experiments.config import validate

    algorithm = spec(get_template("online"), "sha256:" + "a" * 64)
    algorithm["frozen"]["graph"]["nodes"][3]["config"]["item"] = "item / 2"
    with pytest.raises(ValueError, match="hash"):
        validate({"algorithms": [algorithm]})
    algorithm = spec(get_template("online"), "sha256:" + "a" * 64)
    with pytest.raises(ValueError, match="domain"):
        validate({"domain": "integer", "threshold": 100,
                  "generator": {"id": "uniform", "min": 1, "max": 100},
                  "algorithms": [algorithm]})
