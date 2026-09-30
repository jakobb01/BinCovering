import hashlib
import json
import uuid
from pathlib import Path

from flask import Flask, g, jsonify, render_template, request, send_file

from bincovering.algorithms.registry import PARAMETERS
from bincovering.experiments.config import validate
from bincovering.experiments.lifecycle import reconcile_runs
from bincovering.experiments.storage import list_runs, new_run, now, write_json
from bincovering.reporting.reports import compare


def create_app(output_root="outputs", *, auth_required=True, execution_queue=None):
    from bincovering.builders.jobs import Supervisor
    from bincovering.builders.storage import BuilderStore
    from bincovering.web.auth import install_auth
    from bincovering.web.builder import install_builder

    app = Flask(__name__)
    root = Path(output_root).resolve()
    store = BuilderStore(root)
    queue = execution_queue if execution_queue is not None else Supervisor(root)
    app.extensions["bincovering_store"] = store
    app.extensions["bincovering_queue"] = queue
    install_auth(app, store, required=auth_required)
    install_builder(app, store, queue)
    jobs = {}
    app.extensions["bincovering_jobs"] = jobs

    def locate(run_id):
        path = (root / run_id).resolve()
        if (
            path == root
            or not path.is_relative_to(root)
            or ".trash" in path.relative_to(root).parts
            or not (path / "manifest.json").is_file()
        ):
            raise ValueError("Unknown run")
        if not store.can_access_run(g.user, run_id):
            raise ValueError("Unknown run")
        return path

    @app.errorhandler(ValueError)
    def bad_request(exc):
        return jsonify(error=str(exc)), 400

    from bincovering.builders.language import BuilderError

    @app.errorhandler(BuilderError)
    def builder_error(exc):
        return jsonify(error=str(exc), detail=exc.as_dict()), 400

    @app.errorhandler(403)
    def forbidden(exc):
        return jsonify(error=exc.description), 403

    @app.get("/")
    def index():
        return render_template("index.html", algorithms=PARAMETERS, page="home")

    @app.get("/experiments")
    def experiments():
        return render_template("index.html", algorithms=PARAMETERS, page="experiments")

    def coverage_target(body):
        value = body.get("target", 70)
        if type(value) not in (int, float) or not 0 <= value <= 100:
            raise ValueError("Minimum coverage target must be a number from 0 to 100%")
        return float(value)

    def target_results(paths, minimum):
        from bincovering.reporting.visualizations import reliability_data

        data = reliability_data(paths, minimum)
        # Full per-trial evidence stays in figure JSON. The interactive table
        # needs only counts and labels, even for studies with many trials.
        return {
            "target": data["target"],
            "omitted": data["omitted"],
            "groups": [
                {
                    key: group[key]
                    for key in (
                        "label",
                        "reached",
                        "total",
                        "percentage",
                        "reference_label",
                    )
                }
                for group in data["groups"]
            ],
        }

    @app.get("/api/runs")
    def runs():
        for key, process in list(jobs.items()):
            if process.poll() is not None:
                path = (root / key).resolve()
                if not (path / "manifest.json").is_file():
                    del jobs[key]
                    continue
                record = json.loads((path / "manifest.json").read_text())
                if record["status"] in ("queued", "running"):
                    record.update(
                        status="failed",
                        error=f"Worker exited ({process.returncode}); see worker.log",
                        finished_at=now(),
                    )
                    write_json(path / "manifest.json", record)
                del jobs[key]
        reconcile_runs(root)
        return jsonify(
            [
                {
                    **r,
                    "id": str(Path(r["path"]).relative_to(root)),
                    "pinned": (Path(r["path"]) / "PINNED").exists(),
                }
                for r in list_runs(root)
                if store.can_access_run(g.user, str(Path(r["path"]).relative_to(root)))
            ]
        )

    @app.post("/api/runs")
    def submit():
        raw = request.get_json()
        if not isinstance(raw, dict):
            raise ValueError("Expected experiment settings")
        if (
            isinstance(raw.get("generator"), dict)
            and raw["generator"].get("id") == "file"
        ):
            raise ValueError("Use the CLI to import a file")
        # Browser jobs use fixed server-owned output and executable paths.
        raw = store.authorize_specs(g.user["id"], raw)
        raw["output_root"] = str(root)
        raw["native_executable"] = str(Path("build/bincovering-native").resolve())
        cfg = validate(raw)
        path = new_run(root)
        store.assign_run(path.name, g.user["id"])
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
        try:
            process = queue.submit_experiment(g.user["id"], cfg, path)
        except (OSError, ValueError) as exc:
            manifest = json.loads((path / "manifest.json").read_text())
            manifest.update(status="failed", error=str(exc), finished_at=now())
            write_json(path / "manifest.json", manifest)
            raise ValueError(str(exc) or "Could not launch experiment worker") from exc
        jobs[path.name] = process
        return jsonify(id=path.name), 202

    @app.post("/api/remove/<path:run_id>")
    def remove(run_id):
        from bincovering.experiments.lifecycle import RunLease

        path = locate(run_id)
        with RunLease(path):
            record = json.loads((path / "manifest.json").read_text())
            if record["status"] in ("queued", "running") or (path / "PINNED").exists():
                raise ValueError("Finish the run and unpin it before removing")
            token = uuid.uuid4().hex
            trash = root / ".trash"
            trash.mkdir(exist_ok=True)
            write_json(
                trash / (token + ".json"), {
                    "original_id": str(path.relative_to(root)),
                    "owner_id": store.run_owner(run_id),
                }
            )
            path.rename(trash / token)
        jobs.pop(run_id, None)
        return jsonify(token=token, message="Moved to trash")

    @app.post("/api/restore/<token>")
    def restore(token):
        if len(token) != 32 or any(c not in "0123456789abcdef" for c in token):
            raise ValueError("Unknown removed experiment")
        trash = root / ".trash"
        metadata = trash / (token + ".json")
        source = trash / token
        if not metadata.is_file() or not source.is_dir():
            raise ValueError("Unknown removed experiment")
        original = json.loads(metadata.read_text())["original_id"]
        if not store.can_access_run(g.user, original):
            raise ValueError("Unknown removed experiment")
        destination = (root / original).resolve()
        if (
            destination == root
            or not destination.is_relative_to(root)
            or destination.exists()
        ):
            raise ValueError("Cannot restore over an existing location")
        destination.parent.mkdir(parents=True, exist_ok=True)
        source.rename(destination)
        metadata.unlink()
        return jsonify(id=original)

    @app.post("/api/comparison-plot")
    def comparison_plot():
        from bincovering.reporting.comparisons import plot_comparison

        body = request.get_json(silent=True) or {}
        ids = body.get("ids")
        if (
            not isinstance(ids, list)
            or not ids
            or not all(isinstance(i, str) for i in ids)
        ):
            raise ValueError("Select experiments to plot")
        token = hashlib.sha256(json.dumps([g.user["id"], sorted(set(ids))]).encode()).hexdigest()[:32]
        plot_comparison(
            [locate(i) for i in ids], root / ".comparisons" / (token + ".png")
        )
        store.comparison(token, g.user["id"], sorted(set(ids)))
        return jsonify(url="/api/comparison-figure/" + token)

    @app.get("/api/comparison-figure/<token>")
    def comparison_figure(token):
        if len(token) != 32 or any(c not in "0123456789abcdef" for c in token):
            raise ValueError("Unknown comparison")
        for run_id in store.comparison(token, g.user["id"]):
            locate(run_id)
        extension = request.args.get("format", "png")
        if extension not in {"png", "svg"}:
            raise ValueError("Unknown figure format")
        path = root / ".comparisons" / (token + "." + extension)
        if not path.is_file():
            raise ValueError("Unknown comparison")
        return send_file(path)

    @app.post("/api/cancel/<path:run_id>")
    def cancel(run_id):
        path = locate(run_id)
        if json.loads((path / "manifest.json").read_text())["status"] not in (
            "queued",
            "running",
        ):
            raise ValueError("Run is already finished")
        (path / "CANCEL").touch()
        try:
            queue.get_job(g.user["id"], run_id, administrator=True)
        except ValueError:
            # CLI studies have a run lease and cancellation marker, but no queue row.
            pass
        else:
            # locate() already authorized the current experiment owner. The queue
            # keeps its submitting account for fair resource accounting even if an
            # administrator has since reassigned experiment access.
            queue.cancel_job(g.user["id"], run_id, administrator=True)
        return jsonify(message="Cancellation requested")

    @app.get("/api/inspect/<path:run_id>")
    def inspect(run_id):
        path = locate(run_id)
        result = {"manifest": json.loads((path / "manifest.json").read_text())}
        if (path / "summary.json").exists():
            result["summary"] = json.loads((path / "summary.json").read_text())
        return jsonify(result)

    @app.get("/api/export/<path:run_id>")
    def export(run_id):
        from bincovering.experiments.artifacts import export_run

        path = locate(run_id)
        destination = export_run(path)
        return send_file(destination, as_attachment=True)

    @app.post("/api/pin/<path:run_id>")
    def pin(run_id):
        path = locate(run_id)
        body = request.get_json(silent=True) or {}
        if body.get("pinned", True):
            (path / "PINNED").touch()
        else:
            (path / "PINNED").unlink(missing_ok=True)
        return jsonify(pinned=(path / "PINNED").exists())

    @app.get("/api/compare")
    def comparison():
        ids = request.args.getlist("id")
        if len(ids) < 2:
            raise ValueError("Select at least two runs")
        return jsonify(compare([locate(i) for i in ids]))

    @app.post("/api/plot/<path:run_id>")
    def plot(run_id):
        from bincovering.reporting.visualizations import render_plot

        path = locate(run_id)
        record = json.loads((path / "manifest.json").read_text())
        if record["status"] in ("queued", "running"):
            raise ValueError("Wait for the run to finish")
        body = request.get_json(silent=True) or {}
        if not isinstance(body, dict):
            raise ValueError("Expected plot settings")
        kind = body.get("kind", "overview")
        algorithm = body.get("algorithm", 0)
        if (
            not isinstance(kind, str)
            or kind not in {"overview", "mass", "reliability", "paired"}
            or type(algorithm) is not int
            or algorithm < 0
        ):
            raise ValueError("Choose an available plot and algorithm")
        minimum = coverage_target(body) if kind == "reliability" else 70
        target = render_plot(
            [path],
            kind,
            algorithm=algorithm,
            panel=body.get("panel", "all"),
            minimum_coverage=minimum,
        )
        name = target.stem
        payload = dict(
            url=f"/api/figure/{run_id}?name={name}",
            svg_url=f"/api/figure/{run_id}?name={name}&format=svg",
            kind=kind,
        )
        if kind == "reliability":
            payload["target_data"] = target_results([path], minimum)
        return jsonify(payload)

    @app.get("/api/figure/<path:run_id>")
    def figure(run_id):
        name = request.args.get("name", "coverage")
        extension = request.args.get("format", "png")
        if (
            not name
            or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in name)
            or extension not in {"png", "svg"}
        ):
            raise ValueError("Unknown figure")
        target = locate(run_id) / "figures" / f"{name}.{extension}"
        if not target.is_file():
            raise ValueError("This figure has not been generated")
        return send_file(target)

    @app.post("/api/study-plot")
    def study_plot():
        from bincovering.reporting.visualizations import render_plot

        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            raise ValueError("Expected selected studies")
        ids = body.get("ids")
        kind = body.get("kind")
        if (
            not isinstance(kind, str)
            or kind not in {"ordering", "parameters", "paired", "reliability"}
            or not isinstance(ids, list)
            or not ids
            or not all(isinstance(i, str) for i in ids)
        ):
            raise ValueError("Select saved experiments and an available study plot")
        paths = [locate(i) for i in sorted(set(ids))]
        if any(
            json.loads((p / "manifest.json").read_text())["status"]
            in {"queued", "running"}
            for p in paths
        ):
            raise ValueError("Wait for selected experiments to finish")
        minimum = coverage_target(body) if kind == "reliability" else 70
        token = hashlib.sha256(
            json.dumps([g.user["id"], kind, sorted(set(ids)), minimum]).encode()
        ).hexdigest()[:32]
        render_plot(
            paths,
            kind,
            root / ".comparisons" / f"{token}.png",
            minimum_coverage=minimum,
        )
        store.comparison(token, g.user["id"], sorted(set(ids)))
        payload = dict(
            url="/api/comparison-figure/" + token,
            svg_url="/api/comparison-figure/" + token + "?format=svg",
            kind=kind,
        )
        if kind == "reliability":
            payload["target_data"] = target_results(paths, minimum)
        return jsonify(payload)

    from bincovering.builders.traces import register_trace_routes

    register_trace_routes(app, locate)
    return app
