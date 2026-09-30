"""Read recorded trace evidence with the graph frozen in that experiment."""

import json

from flask import jsonify, request


def register_trace_routes(app, locate):
    def record(path):
        return json.loads((path / "manifest.json").read_text())

    @app.get("/api/traces/<path:run_id>")
    def trace_index(run_id):
        path = locate(run_id)
        manifest = record(path)
        algorithms = manifest.get("config", {}).get("algorithms", [])
        traces = []
        folder = path / "traces"
        if folder.is_dir():
            for filename in sorted(folder.glob("*.json")):
                if filename.is_symlink():
                    continue
                try:
                    parts = filename.stem.split("-")
                    if parts[0] == "generator":
                        trial, index = int(parts[1]), -1
                        spec = manifest["config"]["generator"]
                    else:
                        trial, index = int(parts[0]), int(parts[1])
                        spec = algorithms[index]
                    if index < -1 or trial < 0:
                        continue
                    data = json.loads(filename.read_text())
                except (ValueError, IndexError, TypeError):
                    continue
                frozen = spec.get("frozen", {})
                traces.append({
                    "trial": trial, "algorithm": index, "index": index,
                    "label": frozen.get("name", spec["id"]),
                    "revision": spec.get("revision"), "available": True,
                    "kind": "generator" if index == -1 else "algorithm",
                    "schema_version": data.get("schema_version", 1) if isinstance(data, dict) else 0,
                    "truncated": data.get("truncated", False) if isinstance(data, dict) else False,
                })
        return jsonify(traces=traces, trace_enabled=manifest.get("trace_enabled", False),
                       message="Select a recorded trial" if traces else "No trace was captured for this experiment")

    @app.get("/api/trace/<path:run_id>")
    def trace_detail(run_id):
        path = locate(run_id)
        try:
            trial = int(request.args.get("trial", "0"))
            index = int(request.args.get("algorithm", "0"))
        except ValueError as exc:
            raise ValueError("Choose a recorded trial and algorithm") from exc
        manifest = record(path)
        algorithms = manifest.get("config", {}).get("algorithms", [])
        if trial < 0 or index < -1 or index >= len(algorithms):
            raise ValueError("Unknown trace")
        filename = path / "traces" / (f"generator-{trial}.json" if index == -1 else f"{trial}-{index}.json")
        if not filename.is_file() or filename.is_symlink():
            raise ValueError("No trace was captured for that trial and algorithm")
        trace = json.loads(filename.read_text())
        spec = manifest["config"]["generator"] if index == -1 else algorithms[index]
        frozen = spec.get("frozen", {})
        return jsonify(graph=frozen.get("graph"), trace=trace, metadata={
            "trial": trial, "algorithm": spec["id"], "revision": spec.get("revision"),
            "parameters": spec.get("params", {}), "access": frozen.get("graph", {}).get("access"),
            "runtime_image": frozen.get("runtime_image"), "legacy": isinstance(trace, list),
            "kind": "generator" if index == -1 else "algorithm",
            "threshold": manifest["config"].get("threshold", 1), "domain": manifest["config"].get("domain", "float64"),
        })
