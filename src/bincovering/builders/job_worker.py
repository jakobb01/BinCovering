"""Trusted queue child: custom statements execute only through isolation."""

import json
import sys
from pathlib import Path

from bincovering.builders.jobs import Supervisor, finish_job


def work(root, job_id):
    queue = Supervisor(root, dispatch=False)
    # Workers update durable state themselves, but do not become dispatchers.
    request = json.loads((queue.payloads / job_id / "request.json").read_text())
    job = queue._get(job_id)

    def cancelled():
        return bool(queue._get(job_id)["cancel"])

    try:
        if job["kind"] == "preview":
            from bincovering.builders.execution import execute_isolated
            from bincovering.experiments.runner import seed_for

            settings = dict(request["settings"])
            base_seed = settings.pop("seed", 42)
            trial = settings.pop("trial", 0)
            algorithm_id = settings.pop("algorithm_id", "builder-preview")
            purpose = "data" if request["graph"]["kind"] == "generator" else json.dumps(
                {"id": algorithm_id, "params": settings.get("params", {})}, sort_keys=True,
            )
            from bincovering.builders.schema import resolve_parameters

            settings["params"] = resolve_parameters(request["graph"], settings.get("params", {}))
            if purpose != "data":
                purpose = json.dumps({"id": algorithm_id, "params": settings["params"]}, sort_keys=True)
            result = execute_isolated(request["graph"], root=root, seed=seed_for(base_seed, trial, purpose), cancelled=cancelled, **settings)
            finish_job(queue, job_id, "completed" if result["ok"] else "failed", result=result,
                       error=result.get("error"))
        else:
            from bincovering.experiments.runner import run_experiment

            path = Path(job["run_path"])
            if cancelled():
                (path / "CANCEL").touch()
            run_experiment(request["cfg"], path)
            manifest = json.loads((path / "manifest.json").read_text())
            finish_job(queue, job_id, manifest["status"], result={"run_id": path.name},
                       error={"message": manifest["error"]} if manifest.get("error") else None)
    except InterruptedError:
        finish_job(queue, job_id, "cancelled", error={"message": "Cancelled"})
    except Exception as exc:
        finish_job(queue, job_id, "failed", error={"message": str(exc), "code": type(exc).__name__})
        if job["kind"] == "experiment":
            from bincovering.experiments.storage import now, write_json

            manifest_path = Path(job["run_path"]) / "manifest.json"
            if manifest_path.is_file():
                manifest = json.loads(manifest_path.read_text())
                if manifest.get("status") in {"queued", "running"}:
                    manifest.update(status="failed", error=str(exc), finished_at=now())
                    write_json(manifest_path, manifest)


if __name__ == "__main__":
    work(sys.argv[1], sys.argv[2])
