from bincovering.experiments.runner import run_experiment
from bincovering.web.app import create_app


def test_web_reads_cli_runs_and_runs_background_job(tmp_path):
    cli_run = run_experiment({"output_root": str(tmp_path), "n": 10, "trials": 1})
    app = create_app(tmp_path)
    client = app.test_client()
    assert client.get("/").status_code == 200
    assert client.get("/api/runs").json[0]["id"] == cli_run.name
    response = client.post("/api/runs", json={"n": 10, "trials": 1, "seed": 42})
    assert response.status_code == 202
    run_id = response.json["id"]
    process = app.extensions["bincovering_jobs"][run_id]
    try:
        process.wait(timeout=20)
        assert process.returncode == 0
        result = client.get("/api/inspect/" + run_id).json
        assert result["manifest"]["status"] == "completed"
        comparison = client.get(
            "/api/compare", query_string=[("id", run_id), ("id", cli_run.name)]
        )
        assert comparison.json["same_trial_inputs"] is True
        response = client.post("/api/plot/" + run_id)
        assert response.status_code == 200
        assert client.get(response.json["url"]).mimetype == "image/png"
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()


def test_web_validation(tmp_path):
    client = create_app(tmp_path).test_client()
    assert client.post("/api/runs", json={"workers": 0}).status_code == 400
    assert client.get("/api/inspect/../../outside").status_code == 400
    assert (
        client.post(
            "/api/runs", json={"generator": {"id": "file", "path": "/etc/passwd"}}
        ).status_code
        == 400
    )


def test_web_cancellation(tmp_path):
    app = create_app(tmp_path)
    client = app.test_client()
    response = client.post("/api/runs", json={"n": 1000, "trials": 100})
    run_id = response.json["id"]
    process = app.extensions["bincovering_jobs"][run_id]
    try:
        assert client.post("/api/cancel/" + run_id).status_code == 200
        process.wait(timeout=20)
        assert (
            client.get("/api/inspect/" + run_id).json["manifest"]["status"]
            == "cancelled"
        )
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
