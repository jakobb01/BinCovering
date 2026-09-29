"""Local plot review gallery with explicit, durable submission of researcher notes."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from threading import Lock

from flask import Flask, jsonify, request, send_from_directory

PLOT_IDS = frozenset(
    {
        "01-research-overview",
        "02-reliability-ecdf",
        "03-paired-dnf",
        "04-order-sensitivity",
        "05-size-and-runtime",
        "06-parameter-sweep",
        "07-mass-accounting",
        "08-distribution-robustness",
    }
)


def validate_review(data: object) -> dict:
    if not isinstance(data, dict) or not data:
        raise ValueError("Expected a nonempty object of plot decisions.")
    for plot_id, decision in data.items():
        if plot_id not in PLOT_IDS:
            raise ValueError(f"Unknown plot ID: {plot_id}")
        if not isinstance(decision, dict) or set(decision) != {"preference", "notes"}:
            raise ValueError("Each decision must contain preference and notes.")
        if decision["preference"] not in ("Keep", "Adjust", "Skip"):
            raise ValueError("Preference must be Keep, Adjust, or Skip.")
        if not isinstance(decision["notes"], str) or len(decision["notes"]) > 4000:
            raise ValueError("Notes must be text of at most 4,000 characters.")
    return data


def create_review_app(root: str | Path) -> Flask:
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = 64 * 1024
    review_path = root / "user-review.json"
    write_lock = Lock()

    def read_review():
        # Only explicit submissions are authoritative. Browser QA captures and
        # localStorage exports are never automatically imported here.
        if not review_path.exists():
            return {}
        return validate_review(json.loads(review_path.read_text(encoding="utf-8")))

    @app.get("/")
    def gallery():
        return send_from_directory(root, "index.html")

    @app.get("/api/review")
    def read():
        try:
            return jsonify(read_review())
        except (ValueError, OSError):
            return jsonify(
                error="Saved review could not be read; it was preserved."
            ), 500

    @app.post("/api/review")
    def submit():
        try:
            changes = validate_review(request.get_json())
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        with write_lock:
            try:
                saved = read_review()
                saved.update(changes)
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    encoding="utf-8",
                    dir=root,
                    delete=False,
                    prefix=".review-",
                    suffix=".tmp",
                ) as handle:
                    temporary = Path(handle.name)
                    json.dump(saved, handle, ensure_ascii=False, indent=2)
                    handle.write("\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                try:
                    temporary.replace(review_path)
                finally:
                    temporary.unlink(missing_ok=True)
                return jsonify(saved)
            except (ValueError, OSError):
                return jsonify(
                    error="Review could not be saved; previous file was preserved."
                ), 500

    @app.get("/<path:filename>")
    def artifact(filename):
        # Only the gallery's public figures, methods, and records are served.
        allowed = {
            "README.md",
            "review-data.json",
            "approved-review.json",
            "trials.csv",
            "provenance.json",
            "refine.py",
        }
        allowed.update(
            f"{plot_id}.{extension}"
            for plot_id in PLOT_IDS
            for extension in ("png", "svg")
        )
        if filename not in allowed:
            return jsonify(error="Unknown gallery artifact."), 404
        return send_from_directory(root, filename)

    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--port", default=5001, type=int)
    args = parser.parse_args()
    create_review_app(args.root).run(host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
