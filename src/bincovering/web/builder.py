"""HTTP library operations; user code never executes in the Flask process."""

import io
import json

from flask import Blueprint, g, jsonify, render_template, request, send_file


def install_builder(app, store, queue):
    builder = Blueprint("builder", __name__)

    def body():
        value = request.get_json(silent=True)
        if not isinstance(value, dict):
            raise ValueError("Expected builder settings")
        return value

    @builder.get("/builder")
    def page():
        return render_template("builder.html")

    @builder.get("/api/builder/templates")
    def templates():
        from bincovering.builders.templates import examples, starter_templates

        return jsonify(templates=starter_templates(), examples=examples())

    @builder.get("/api/builder/library")
    def library():
        return jsonify(items=store.items(g.user["id"], archived=request.args.get("archived") == "true"))

    @builder.post("/api/builder/library")
    def create():
        value = body()
        graph = value.get("graph")
        kind = value.get("kind") or (graph.get("kind") if isinstance(graph, dict) else None)
        return jsonify(store.create(g.user["id"], value.get("name"), kind, graph)), 201

    @builder.get("/api/builder/library/<library_id>")
    def inspect(library_id):
        return jsonify(store.item(g.user["id"], library_id, revision=request.args.get("revision")))

    @builder.put("/api/builder/library/<library_id>")
    def update(library_id):
        value = body()
        return jsonify(store.update(g.user["id"], library_id, graph=value.get("graph"), name=value.get("name")))

    @builder.post("/api/builder/library/<library_id>/preview")
    def preview(library_id):
        value = body()
        item = store.item(g.user["id"], library_id)
        if not item["owned"] or item["archived"]:
            raise ValueError("Clone a shared revision before editing or testing it")
        graph = store.freeze_graph(g.user["id"], value.get("graph", item["draft"]))
        settings = value.get("settings", {})
        if not isinstance(settings, dict):
            raise ValueError("Expected preview settings")
        settings = dict(settings)
        # Kept as ignored compatibility fields for dashboards loaded before
        # mandatory verification capture; clients no longer control this policy.
        settings.pop("trace_limit", None)
        settings.pop("trace_bytes", None)
        allowed = {"items", "n", "seed", "params", "inputs", "component_context", "domain", "threshold", "trial"}
        if set(settings) - allowed:
            raise ValueError("Unknown preview setting")
        if "component_context" in settings and graph["kind"] != "component":
            raise ValueError("A component fixture is only available for reusable-component previews")
        settings["algorithm_id"] = library_id
        job = queue.submit_preview(g.user["id"], graph, settings)
        store.record_preview(g.user["id"], library_id, job["id"], graph)
        return jsonify(job), 202

    @builder.get("/api/builder/jobs/<job_id>")
    def job(job_id):
        return jsonify(queue.get_job(g.user["id"], job_id, administrator=g.user["role"] == "admin"))

    @builder.post("/api/builder/jobs/<job_id>/cancel")
    def cancel(job_id):
        return jsonify(queue.cancel_job(g.user["id"], job_id, administrator=g.user["role"] == "admin"))

    @builder.post("/api/builder/library/<library_id>/available")
    def available(library_id):
        value = body()
        job_id = value.get("job_id")
        if not isinstance(job_id, str):
            raise ValueError("Choose a completed preview")
        job = queue.get_job(g.user["id"], job_id)
        frozen = store.make_available(g.user["id"], library_id, job_id, job)
        return jsonify(frozen=frozen, item=store.item(g.user["id"], library_id)), 201

    @builder.get("/api/builder/available")
    def available_choices():
        return jsonify(store.available(g.user["id"]))

    @builder.post("/api/builder/library/<library_id>/share")
    def share(library_id):
        value = body()
        return jsonify(store.share(g.user["id"], library_id, value.get("revision"), value.get("shared")))

    @builder.post("/api/builder/library/<library_id>/clone")
    def clone(library_id):
        value = body()
        return jsonify(store.clone(g.user["id"], library_id, value.get("revision"), value.get("name"))), 201

    @builder.post("/api/builder/library/<library_id>/archive")
    def archive(library_id):
        return jsonify(store.archive(g.user["id"], library_id))

    @builder.post("/api/builder/library/<library_id>/restore")
    def restore(library_id):
        return jsonify(store.archive(g.user["id"], library_id, False))

    @builder.get("/api/builder/library/<library_id>/export")
    def export(library_id):
        from bincovering.builders.schema import generated_source

        item = store.item(g.user["id"], library_id, revision=request.args.get("revision"))
        format_name = request.args.get("format", "graph")
        if format_name == "python":
            # Editable drafts must pass the same schema checks before exporting an adapter.
            graph = item.get("frozen", {}).get("graph") or store.freeze_graph(g.user["id"], item["draft"])
            payload = item.get("frozen", {}).get("generated_source") or generated_source(graph)
            extension, mimetype = "py", "text/x-python"
        elif format_name == "graph":
            payload = json.dumps(item.get("frozen", item["draft"]), indent=2, allow_nan=False)
            extension, mimetype = "json", "application/json"
        else:
            raise ValueError("Choose graph or Python export")
        filename = library_id.replace(":", "-") + "." + extension
        return send_file(io.BytesIO(payload.encode()), download_name=filename, mimetype=mimetype, as_attachment=True)

    @builder.post("/api/builder/translate")
    def translate_code():
        from bincovering.builders.language import translate

        value = body()
        return jsonify(source=translate(value.get("source", ""), value.get("from_language", value.get("from_notation")), value.get("to_language", value.get("to_notation"))))

    app.register_blueprint(builder)
