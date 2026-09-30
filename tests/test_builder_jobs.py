"""Durable claims, quotas, cancellation, and recovery independent of Flask."""

import json
import os

import pytest

from bincovering.builders.jobs import Supervisor, _process_identity, finish_job
from bincovering.builders.templates import get_template
from bincovering.experiments.config import validate
from bincovering.experiments.lifecycle import reconcile_runs
from bincovering.experiments.storage import new_run, write_json


def queue(tmp_path, monkeypatch):
    supervisor = Supervisor(tmp_path, dispatch=False)
    monkeypatch.setattr(supervisor, "start", lambda: None)
    return supervisor


def test_claims_are_durable_and_bound_worker_slots_by_account(tmp_path, monkeypatch):
    supervisor = queue(tmp_path, monkeypatch)
    ids = [supervisor.submit_preview("alice", get_template("generator"), {})["id"] for _ in range(3)]
    bob = supervisor.submit_preview("bob", get_template("generator"), {})["id"]
    assert supervisor._claim()["id"] == ids[0]
    assert supervisor._claim()["id"] == ids[1]
    assert supervisor._claim()["id"] == bob
    assert supervisor._claim() is None  # Alice cannot consume the fourth global slot.
    restored = Supervisor(tmp_path, dispatch=False)
    assert restored.get_job("alice", ids[2])["status"] == "queued"
    with pytest.raises(ValueError, match="Unknown job"):
        restored.get_job("bob", ids[0])
    finish_job(supervisor, ids[0], "completed", result={"ok": True})
    assert restored._claim()["id"] == ids[2]


def test_queued_cancellation_never_launches_and_manifest_stays_finished(tmp_path, monkeypatch):
    supervisor = queue(tmp_path, monkeypatch)
    path = new_run(tmp_path)
    cfg = validate({"n": 10, "trials": 1, "output_root": str(tmp_path)})
    write_json(path / "manifest.json", {"name": "queued", "status": "queued", "created_at": "2020-01-01T00:00:00+00:00"})
    supervisor.submit_experiment("alice", cfg, path)
    reconcile_runs(tmp_path, startup_grace=0)
    assert json.loads((path / "manifest.json").read_text())["status"] == "queued"
    supervisor.cancel_job("alice", path.name)
    assert supervisor._claim() is None
    assert supervisor.get_job("alice", path.name)["status"] == "cancelled"
    assert json.loads((path / "manifest.json").read_text())["status"] == "cancelled"


def test_recovery_distinguishes_live_process_from_abandoned_claim(tmp_path, monkeypatch):
    supervisor = queue(tmp_path, monkeypatch)
    first = supervisor.submit_preview("alice", get_template("generator"), {})["id"]
    second = supervisor.submit_preview("bob", get_template("generator"), {})["id"]
    supervisor._claim()
    supervisor._claim()
    with supervisor.connect() as db:
        db.execute("UPDATE jobs SET started_at='2020-01-01T00:00:00+00:00' WHERE id=?", (second,))
        db.execute("UPDATE jobs SET pid=?,pid_start=? WHERE id=?", (os.getpid(), _process_identity(os.getpid()), first))
    supervisor.reconcile()
    assert supervisor.get_job("alice", first)["status"] == "running"
    assert supervisor.get_job("bob", second)["status"] == "interrupted"


def test_workload_trace_and_pending_limits_are_checked_before_submission(tmp_path, monkeypatch):
    supervisor = queue(tmp_path, monkeypatch)
    cfg = validate({"n": 1000, "trials": 1, "workers": 3, "output_root": str(tmp_path)})
    with pytest.raises(ValueError, match="workers"):
        supervisor.submit_experiment("alice", cfg, new_run(tmp_path))
    cfg = validate({"n": 300000, "trials": 1, "output_root": str(tmp_path)})
    with pytest.raises(ValueError, match="budget"):
        supervisor.submit_experiment("alice", cfg, new_run(tmp_path))
    cfg = validate({"n": 10, "trials": 100, "trace_limit": 100, "output_root": str(tmp_path)})
    with pytest.raises(ValueError, match="Trace capture"):
        supervisor.submit_experiment("alice", cfg, new_run(tmp_path))
    supervisor.account_pending = 1
    supervisor.submit_preview("alice", get_template("generator"), {})
    with pytest.raises(ValueError, match="queue is full"):
        supervisor.submit_preview("alice", get_template("generator"), {})


@pytest.mark.parametrize("legacy", [
    {},
    {"trace_limit": 0, "trace_bytes": 0},
    {"trace_limit": 1, "trace_bytes": 1},
    {"trace_limit": 100000, "trace_bytes": 100000000},
    {"trace_limit": "obsolete", "trace_bytes": None},
])
def test_preview_trace_policy_cannot_be_disabled_or_capped(tmp_path, monkeypatch, legacy):
    supervisor = queue(tmp_path, monkeypatch)
    settings = {"n": 3, **legacy}
    job = supervisor.submit_preview("alice", get_template("generator"), settings)
    submitted = json.loads((supervisor.payloads / job["id"] / "request.json").read_text())["settings"]
    assert submitted["trace_limit"] == 10000
    assert submitted["trace_bytes"] == 4 * 1024 * 1024
    assert settings == {"n": 3, **legacy}


def test_preview_admission_counts_mandatory_capture_not_legacy_zero_budget(tmp_path, monkeypatch):
    supervisor = queue(tmp_path, monkeypatch)
    supervisor.max_trace_bytes = 4 * 1024 * 1024 - 1
    with pytest.raises(ValueError, match="Mandatory preview trace capture"):
        supervisor.submit_preview("alice", get_template("generator"), {"trace_limit": 0, "trace_bytes": 0})
    with supervisor.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0
    supervisor.max_trace_bytes += 1
    assert supervisor.submit_preview("alice", get_template("generator"), {})["status"] == "queued"


def test_preview_worker_receives_mandatory_policy_and_keeps_truncation(tmp_path, monkeypatch):
    from bincovering.builders import execution, job_worker

    supervisor = queue(tmp_path, monkeypatch)
    job = supervisor.submit_preview("alice", get_template("generator"), {"n": 3, "trace_limit": 0, "trace_bytes": 0})
    calls = []
    def isolated(graph, **settings):
        calls.append(settings)
        return {"ok": True, "result": {"items": [0.5] * 3},
                "trace": {"schema_version": 1, "events": [], "total_events": 4, "truncated": True}}
    monkeypatch.setattr(execution, "execute_isolated", isolated)
    job_worker.work(tmp_path, job["id"])
    assert calls[0]["trace_limit"] == 10000
    assert calls[0]["trace_bytes"] == 4 * 1024 * 1024
    result = supervisor.get_job("alice", job["id"])["result"]
    assert result["trace"]["truncated"]
    assert result["trace"]["total_events"] == 4
