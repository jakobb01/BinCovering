import json
import subprocess
import sys
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file

from bincovering.algorithms.registry import PARAMETERS
from bincovering.experiments.config import validate
from bincovering.experiments.storage import list_runs, new_run, now, write_json
from bincovering.reporting.reports import compare, plot_run


def create_app(output_root="outputs"):
    app = Flask(__name__)
    root = Path(output_root).resolve()
    jobs = {}
    app.extensions["bincovering_jobs"] = jobs

    def locate(run_id):
        path = (root / run_id).resolve()
        if not path.is_relative_to(root) or not (path / "manifest.json").is_file():
            raise ValueError("Unknown run")
        return path

    @app.errorhandler(ValueError)
    def bad_request(exc):
        return jsonify(error=str(exc)), 400

    @app.get("/")
    def index():
        return render_template("index.html", algorithms=PARAMETERS)

    @app.get("/api/runs")
    def runs():
        for key, process in list(jobs.items()):
            if process.poll() is not None:
                path = locate(key)
                record = json.loads((path / "manifest.json").read_text())
                if record["status"] in ("queued", "running"):
                    record.update(
                        status="failed",
                        error=f"Worker exited ({process.returncode}); see worker.log",
                        finished_at=now(),
                    )
                    write_json(path / "manifest.json", record)
                del jobs[key]
        return jsonify(
            [
                {**r, "id": str(Path(r["path"]).relative_to(root))}
                for r in list_runs(root)
            ]
        )

    @app.post("/api/runs")
    def submit():
        raw = request.get_json()
        if not isinstance(raw, dict):
            raise ValueError("Expected experiment settings")
        if raw.get("generator", {}).get("id") == "file":
            raise ValueError("Use the CLI to import a file")
        # Browser jobs use fixed server-owned output and executable paths.
        raw["output_root"] = str(root)
        raw["native_executable"] = str(Path("build/bincovering-native").resolve())
        cfg = validate(raw)
        path = new_run(root)
        write_json(path / "request.json", cfg)
        write_json(
            path / "manifest.json",
            {
                "name": cfg["name"],
                "status": "queued",
                "created_at": now(),
                "completed_trials": 0,
                "total_trials": cfg["trials"],
                "config": cfg,
            },
        )
        with (path / "worker.log").open("w") as log:
            process = subprocess.Popen(
                [sys.executable, "-m", "bincovering.web.worker", str(path)],
                stdout=log,
                stderr=log,
            )
        jobs[path.name] = process
        return jsonify(id=path.name), 202

    @app.post("/api/cancel/<path:run_id>")
    def cancel(run_id):
        path = locate(run_id)
        (path / "CANCEL").touch()
        return jsonify(message="Cancellation requested")

    @app.get("/api/inspect/<path:run_id>")
    def inspect(run_id):
        path = locate(run_id)
        result = {"manifest": json.loads((path / "manifest.json").read_text())}
        if (path / "summary.json").exists():
            result["summary"] = json.loads((path / "summary.json").read_text())
        return jsonify(result)

    @app.get("/api/compare")
    def comparison():
        ids = request.args.getlist("id")
        if len(ids) < 2:
            raise ValueError("Select at least two runs")
        return jsonify(compare([locate(i) for i in ids]))

    @app.post("/api/plot/<path:run_id>")
    def plot(run_id):
        path = locate(run_id)
        record = json.loads((path / "manifest.json").read_text())
        if record["status"] in ("queued", "running"):
            raise ValueError("Wait for the run to finish")
        plot_run(path)
        return jsonify(url="/api/figure/" + run_id)

    @app.get("/api/figure/<path:run_id>")
    def figure(run_id):
        return send_file(locate(run_id) / "figures" / "coverage.png")

    return app
