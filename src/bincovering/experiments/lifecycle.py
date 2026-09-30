"""Cross-process ownership and recovery for persistent local experiments."""

import json
import os
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from .storage import list_runs, now, write_json


class RunLease:
    """An OS lock is released on worker death, unlike a saved PID."""

    def __init__(self, path):
        self.path = Path(path)
        self.stream = None

    def __enter__(self):
        self.stream = (self.path / ".run.lock").open("a+b")
        try:
            if os.name == "nt":
                import msvcrt

                self.stream.write(b"0")
                self.stream.flush()
                self.stream.seek(0)
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self.stream.close()
            self.stream = None
            raise ValueError("Run is owned by an active worker") from exc
        return self

    def __exit__(self, *args):
        self.stream.close()


def reconcile_runs(root, startup_grace=30):
    """Mark abandoned jobs interrupted; leave live workers alone after a UI restart."""
    for entry in list_runs(root):
        if entry.get("status") not in ("queued", "running"):
            continue
        path = Path(entry["path"])
        queue_database = Path(root).resolve() / ".dashboard" / "jobs.sqlite3"
        if queue_database.is_file():
            try:
                with closing(sqlite3.connect(queue_database)) as database:
                    queued = database.execute(
                        "SELECT status,pid,pid_start FROM jobs WHERE id=? AND kind='experiment'",
                        (str(path.relative_to(Path(root).resolve())),),
                    ).fetchone()
                if queued and queued[0] == "queued":
                    # A durable queued job has not acquired a run lease yet.
                    continue
                if queued and queued[0] == "running" and queued[1]:
                    from bincovering.builders.jobs import _process_identity

                    if _process_identity(queued[1]) == queued[2]:
                        continue
            except (sqlite3.Error, ValueError):
                pass
        try:
            with RunLease(path):
                current = json.loads((path / "manifest.json").read_text())
                if current["status"] not in ("queued", "running"):
                    continue
                age = (
                    datetime.now(UTC) - datetime.fromisoformat(current["created_at"])
                ).total_seconds()
                if current["status"] == "queued" and age < startup_grace:
                    continue
                current.update(
                    status="interrupted",
                    finished_at=now(),
                    error="Worker is no longer running. Completed trial files were retained; rerun to start a new execution.",
                )
                write_json(path / "manifest.json", current)
        except ValueError:
            # Another process owns the lease (or metadata needs manual inspection).
            continue
