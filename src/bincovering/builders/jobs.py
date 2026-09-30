"""Durable, account-scoped queue for previews and experiment workers."""

import json
import os
import signal
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from bincovering.experiments.storage import now, write_json

TERMINAL = {"completed", "failed", "cancelled", "interrupted"}


def _process_identity(pid):
    try:
        # The start tick distinguishes a surviving worker from a reused PID.
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19]
    except (OSError, IndexError):
        return None


class JobHandle:
    """Small subprocess-compatible handle retained for local callers and tests."""

    def __init__(self, queue, job_id):
        self.queue, self.id = queue, job_id

    def poll(self):
        row = self.queue._get(self.id)
        if row["status"] not in TERMINAL:
            return None
        return 0 if row["status"] in {"completed", "cancelled"} else 1

    @property
    def returncode(self):
        return self.poll()

    @property
    def pid(self):
        return self.queue._get(self.id).get("pid")

    def wait(self, timeout=None):
        deadline = time.monotonic() + timeout if timeout is not None else None
        while self.poll() is None:
            if deadline is not None and time.monotonic() >= deadline:
                raise subprocess.TimeoutExpired(self.id, timeout)
            time.sleep(0.05)
        return self.returncode

    def kill(self):
        row = self.queue._get(self.id)
        self.queue.cancel_job(row["owner_id"], self.id)


class Supervisor:
    """SQLite claims enforce global limits even across multiple Flask processes.

    Children update their own durable job state. Surviving workers remain owned on
    web restart; queued work resumes and dead workers become interrupted.
    """

    def __init__(self, root, *, dispatch=True):
        self.root = Path(root).resolve()
        self.state = self.root / ".dashboard"
        self.state.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.db = self.state / "jobs.sqlite3"
        self.payloads = self.state / "jobs"
        self.payloads.mkdir(exist_ok=True, mode=0o700)
        self.global_slots, self.account_slots = 4, 2
        self.global_pending, self.account_pending = 64, 16
        self.max_items, self.max_trials, self.max_total_items = 200000, 1000, 2000000
        self.max_trace_bytes, self.job_seconds = 128 * 1024 * 1024, 600
        limits_file = self.state / "queue.json"
        if limits_file.is_file():
            limits = json.loads(limits_file.read_text())
            allowed = {"global_slots", "account_slots", "global_pending", "account_pending",
                       "max_items", "max_trials", "max_total_items", "max_trace_bytes", "job_seconds"}
            if not isinstance(limits, dict) or limits.keys() - allowed:
                raise ValueError("Invalid server queue settings")
            for key, value in limits.items():
                ceiling = 256 if key in {"global_slots", "account_slots", "global_pending", "account_pending"} else 10**9
                if type(value) is not int or not 1 <= value <= ceiling:
                    raise ValueError(f"Queue limit {key} must be an integer in [1, {ceiling}]")
                setattr(self, key, value)
        self._lock = threading.Lock()
        self._thread = None
        with self.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, kind TEXT NOT NULL,
                status TEXT NOT NULL, weight INTEGER NOT NULL, created_at TEXT NOT NULL,
                started_at TEXT, finished_at TEXT, pid INTEGER, pid_start TEXT,
                run_path TEXT, result TEXT, error TEXT, cancel INTEGER NOT NULL DEFAULT 0
            )""")
            db.execute("CREATE INDEX IF NOT EXISTS jobs_status ON jobs(status,created_at)")
        if dispatch:
            self.reconcile()
        if dispatch and self._has_work():
            self.start()

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.db, timeout=20)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA busy_timeout=20000")
            connection.execute("PRAGMA journal_mode=WAL")
            with connection:
                yield connection
        finally:
            connection.close()

    def _get(self, job_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            raise ValueError("Unknown job")
        return dict(row)

    def get_job(self, owner_id, job_id, administrator=False):
        row = self._get(job_id)
        if not administrator and row["owner_id"] != str(owner_id):
            raise ValueError("Unknown job")
        for key in ("result", "error"):
            row[key] = json.loads(row[key]) if row[key] else None
        for key in ("run_path", "pid", "pid_start"):
            row.pop(key, None)
        return row

    def _submit(self, owner_id, kind, payload, *, weight=1, job_id=None, run_path=None):
        if weight > min(self.global_slots, self.account_slots):
            raise ValueError(f"This account may use at most {min(self.global_slots, self.account_slots)} workers per job")
        job_id = job_id or uuid.uuid4().hex
        location = self.payloads / job_id
        if location.exists():
            raise ValueError("Duplicate job")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute("SELECT owner_id FROM jobs WHERE status IN ('queued','running')").fetchall()
            if len(rows) >= self.global_pending or sum(r[0] == str(owner_id) for r in rows) >= self.account_pending:
                raise ValueError("The execution queue is full; wait for an existing job to finish")
            location.mkdir(mode=0o700)
            write_json(location / "request.json", payload)
            db.execute(
                "INSERT INTO jobs(id,owner_id,kind,status,weight,created_at,run_path) VALUES(?,?,?,'queued',?,?,?)",
                (job_id, str(owner_id), kind, weight, now(), str(run_path) if run_path else None),
            )
        self.start()
        return {"id": job_id, "status": "queued"}

    def submit_preview(self, owner_id, graph, settings):
        from .runtime import MAX_TRACE_BYTES, MAX_TRACE_EVENTS
        from .schema import validate_graph

        if not isinstance(settings, dict):
            raise ValueError("Expected preview settings")
        settings = dict(settings)
        allowed = {"items", "n", "seed", "params", "domain", "threshold", "trace_limit", "trace_bytes", "algorithm_id", "trial", "inputs", "component_context"}
        if settings.keys() - allowed:
            raise ValueError("Unknown preview setting")
        graph = validate_graph(graph)
        context = settings.get("component_context")
        if context is not None and (graph["kind"] != "component" or not isinstance(context, dict)):
            raise ValueError("Fixture context is available only for reusable component previews")
        if type(settings.get("seed", 42)) is not int or settings.get("seed", 42) < 0:
            raise ValueError("Preview seed must be a nonnegative integer")
        if type(settings.get("trial", 0)) is not int or not 0 <= settings.get("trial", 0) <= 100000:
            raise ValueError("Preview trial must be in [0, 100000]")
        if type(settings.get("n", 10)) is not int or not 0 <= settings.get("n", 10) <= 10000:
            raise ValueError("Preview item count must be in [0, 10000]")
        items = settings.get("items", [])
        if not isinstance(items, list) or len(items) > 10000:
            raise ValueError("Preview accepts at most 10000 items")
        if not isinstance(settings.get("inputs", {}), dict) or len(settings.get("inputs", {})) > 100:
            raise ValueError("Component preview inputs must be an object with at most 100 ports")
        # Verification always records execution evidence. Older clients can still
        # submit these obsolete fields during a reload, but their values never
        # disable or reduce the server-owned capture policy.
        settings["trace_limit"] = MAX_TRACE_EVENTS
        settings["trace_bytes"] = MAX_TRACE_BYTES
        if settings["trace_bytes"] > self.max_trace_bytes:
            raise ValueError("Mandatory preview trace capture exceeds the server trace budget")
        return self._submit(owner_id, "preview", {"graph": graph, "settings": settings})

    def submit_experiment(self, owner_id, cfg, path):
        path = Path(path).resolve()
        if path.parent != self.root:
            raise ValueError("Experiment destination must be server-owned")
        if cfg["n"] > self.max_items or cfg["trials"] > self.max_trials or cfg["n"] * cfg["trials"] > self.max_total_items:
            raise ValueError("Experiment exceeds the server item/trial budget")
        if cfg["trace_limit"]:
            trials = cfg["trials"] if cfg["trace_trials"] is None else len(cfg["trace_trials"])
            programs = len(cfg["algorithms"]) + int(cfg["generator"]["id"].startswith("custom:"))
            if cfg["trace_bytes"] * trials * programs > self.max_trace_bytes:
                raise ValueError("Trace capture exceeds the server budget; select fewer trials or lower the byte limit")
        if any(spec.get("params", {}).get(key, 0) > self.max_items for spec in cfg["algorithms"] if not spec["id"].startswith("custom:") for key in ("initial_bins", "m")):
            raise ValueError("Algorithm bin parameters exceed the server budget")
        if cfg["generator"].get("bins", 0) > self.max_items:
            raise ValueError("Generator bin target exceeds the server budget")
        self._submit(owner_id, "experiment", {"cfg": cfg}, weight=cfg["workers"], job_id=path.name, run_path=path)
        return JobHandle(self, path.name)

    def cancel_job(self, owner_id, job_id, administrator=False):
        row = self._get(job_id)
        if not administrator and row["owner_id"] != str(owner_id):
            raise ValueError("Unknown job")
        if row["status"] in TERMINAL:
            raise ValueError("Job is already finished")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            current = db.execute("SELECT status FROM jobs WHERE id=?", (job_id,)).fetchone()[0]
            db.execute("UPDATE jobs SET cancel=1 WHERE id=?", (job_id,))
            if current == "queued":
                db.execute("UPDATE jobs SET status='cancelled',finished_at=?,error=? WHERE id=?",
                           (now(), json.dumps({"message": "Cancelled before execution"}), job_id))
        if row.get("run_path"):
            path = Path(row["run_path"])
            (path / "CANCEL").touch()
            if current == "queued":
                manifest_path = path / "manifest.json"
                manifest = json.loads(manifest_path.read_text())
                manifest.update(status="cancelled", finished_at=now())
                write_json(manifest_path, manifest)
        return {"id": job_id, "message": "Cancellation requested"}

    def _has_work(self):
        with self.connect() as db:
            return bool(db.execute("SELECT 1 FROM jobs WHERE status IN ('queued','running') LIMIT 1").fetchone())

    def reconcile(self):
        with self.connect() as db:
            for row in db.execute("SELECT * FROM jobs WHERE status='running'").fetchall():
                # Submission owns the claim for ten seconds before a child PID is stored.
                if not row["pid"]:
                    from datetime import datetime
                    age = time.time() - datetime.fromisoformat(row["started_at"]).timestamp()
                    if age < 10:
                        continue
                elif _process_identity(row["pid"]) == row["pid_start"]:
                    # A zombie is no longer executing; its parent still needs to reap it.
                    try:
                        if Path(f"/proc/{row['pid']}/stat").read_text().rsplit(")", 1)[1].split()[0] != "Z":
                            continue
                    except OSError:
                        pass
                db.execute(
                    "UPDATE jobs SET status='interrupted',finished_at=?,error=? WHERE id=? AND status='running'",
                    (now(), json.dumps({"message": "Execution worker disappeared; restart interrupted the job"}), row["id"]),
                )
                if row["run_path"]:
                    manifest_path = Path(row["run_path"]) / "manifest.json"
                    if manifest_path.is_file():
                        manifest = json.loads(manifest_path.read_text())
                        if manifest.get("status") in {"queued", "running"}:
                            manifest.update(status="interrupted", finished_at=now(), error="Execution worker disappeared")
                            write_json(manifest_path, manifest)

    def _claim(self):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            running = db.execute("SELECT owner_id,weight FROM jobs WHERE status='running'").fetchall()
            occupied = sum(row["weight"] for row in running)
            for row in db.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY created_at").fetchall():
                account = sum(r["weight"] for r in running if r["owner_id"] == row["owner_id"])
                if occupied + row["weight"] > self.global_slots or account + row["weight"] > self.account_slots:
                    continue
                db.execute("UPDATE jobs SET status='running',started_at=? WHERE id=? AND status='queued'", (now(), row["id"]))
                return dict(row)
        return None

    def _enforce_timeouts(self):
        from datetime import datetime

        with self.connect() as db:
            running = [dict(row) for row in db.execute("SELECT * FROM jobs WHERE status='running'")]
        for row in running:
            elapsed = time.time() - datetime.fromisoformat(row["started_at"]).timestamp()
            if elapsed <= self.job_seconds:
                continue
            with self.connect() as db:
                updated = db.execute("UPDATE jobs SET cancel=1,error=? WHERE id=? AND status='running'",
                           (json.dumps({"message": "Execution exceeded the server job time limit", "code": "timeout"}), row["id"]))
                if not updated.rowcount:
                    continue
            if row["run_path"]:
                (Path(row["run_path"]) / "CANCEL").touch()
            if elapsed > self.job_seconds + 5 and row["pid"] and _process_identity(row["pid"]) == row["pid_start"]:
                try:
                    os.killpg(row["pid"], signal.SIGKILL)
                except ProcessLookupError:
                    pass
                finish_job(self, row["id"], "failed", error={"message": "Execution exceeded the server job time limit", "code": "timeout"})
                if row["run_path"]:
                    manifest_path = Path(row["run_path"]) / "manifest.json"
                    manifest = json.loads(manifest_path.read_text())
                    manifest.update(status="failed", finished_at=now(), error="Execution exceeded the server job time limit")
                    write_json(manifest_path, manifest)

    def start(self):
        with self._lock:
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._dispatch, daemon=True)
                self._thread.start()

    def _dispatch(self):
        children = {}
        idle = time.monotonic()
        while True:
            try:
                self.reconcile()
                self._enforce_timeouts()
                for key, child in list(children.items()):
                    if child.poll() is not None:
                        child.wait()
                        del children[key]
                claimed = self._claim()
                if claimed:
                    job_id = claimed["id"]
                    try:
                        with (self.payloads / job_id / "worker.log").open("w") as output:
                            child = subprocess.Popen(
                                [sys.executable, "-m", "bincovering.builders.job_worker", str(self.root), job_id],
                                stdout=output, stderr=output, start_new_session=True,
                            )
                        children[job_id] = child
                        with self.connect() as db:
                            db.execute("UPDATE jobs SET pid=?,pid_start=? WHERE id=?", (child.pid, _process_identity(child.pid), job_id))
                    except OSError as exc:
                        finish_job(self, job_id, "failed", error={"message": str(exc)})
                    idle = time.monotonic()
                    continue
                if self._has_work():
                    idle = time.monotonic()
                elif not children and time.monotonic() - idle > 5:
                    return
            except (OSError, sqlite3.Error):
                # Keep durable queued work for the next pass or service restart.
                pass
            time.sleep(0.1)


def finish_job(queue, job_id, status, *, result=None, error=None):
    with queue.connect() as db:
        row = db.execute("SELECT error,run_path FROM jobs WHERE id=?", (job_id,)).fetchone()
        previous_error = json.loads(row[0]) if row and row[0] else {}
        if previous_error.get("code") == "timeout":
            status, error = "failed", previous_error
        db.execute(
            "UPDATE jobs SET status=?,finished_at=?,result=?,error=? WHERE id=?",
            (status, now(), json.dumps(result, allow_nan=False) if result is not None else None,
             json.dumps(error, allow_nan=False) if error is not None else None, job_id),
        )
    if previous_error.get("code") == "timeout" and row[1]:
        manifest_path = Path(row[1]) / "manifest.json"
        if manifest_path.is_file():
            manifest = json.loads(manifest_path.read_text())
            manifest.update(status="failed", error=previous_error["message"], finished_at=now())
            write_json(manifest_path, manifest)
