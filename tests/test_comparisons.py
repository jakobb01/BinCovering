import json

from bincovering.experiments.runner import run_experiment
from bincovering.experiments.storage import list_runs
from bincovering.reporting.comparisons import comparison_data, plot_comparison
from bincovering.web.app import create_app


def test_pairs_and_ordering_require_correct_inputs(tmp_path):
    cfg = {"output_root": str(tmp_path), "n": 30, "trials": 3}
    a = run_experiment(cfg | {"ordering": "descending"})
    b = run_experiment(cfg | {"ordering": "swaps", "swaps": 20})
    data = comparison_data([a, b])
    assert data["controlled_inputs"]
    assert data["conditions"] == 2
    assert len(data["paired"][0]["points"]) == 6
    c = run_experiment(cfg | {"seed": 53})
    assert not comparison_data([a, c])["controlled_inputs"]
    # Non-DNF runs cannot be paired just because trial indices match.
    d = run_experiment(cfg | {"seed": 54, "algorithms": [{"id": "harmonic"}]})
    assert not comparison_data([d])["paired"]
    assert comparison_data([a, d])["unmatched"] == 3
    target = plot_comparison([a, b], tmp_path / "figure.png")
    assert target.is_file()
    assert target.with_suffix(".svg").is_file()


def test_pair_difference_is_percentage_points(tmp_path):
    path = run_experiment(
        {
            "output_root": str(tmp_path),
            "n": 20,
            "trials": 2,
            "generator": {"id": "complementary_pairs"},
        }
    )
    from bincovering.reporting.reports import read_trials

    rows = read_trials(path)
    data = comparison_data([path])
    for point in data["paired"][0]["points"]:
        trial = [r for r in rows if r["trial"] == point["trial"]]
        baseline = next(r for r in trial if r["algorithm"] == "dual_next_fit")
        other = next(r for r in trial if r["algorithm"] == "dual_harmonic")
        assert point["difference_pp"] == 10 * (
            other["covered_bins"] - baseline["covered_bins"]
        )


def test_removal_restore_and_protection(tmp_path):
    path = run_experiment({"output_root": str(tmp_path), "n": 10, "trials": 1})
    client = create_app(tmp_path).test_client()
    evidence = (path / "trials.csv").read_bytes()
    (path / "PINNED").touch()
    assert client.post("/api/remove/" + path.name).status_code == 400
    (path / "PINNED").unlink()
    from bincovering.experiments.lifecycle import RunLease

    with RunLease(path):
        assert client.post("/api/remove/" + path.name).status_code == 400
    response = client.post("/api/remove/" + path.name)
    assert response.status_code == 200
    token = response.json["token"]
    assert list_runs(tmp_path) == []
    assert client.get("/api/inspect/.trash/" + token).status_code == 400
    assert client.post("/api/restore/" + token).status_code == 200
    assert (path / "trials.csv").read_bytes() == evidence
    assert client.post("/api/restore/" + token).status_code == 400
    metadata = json.loads((path / "manifest.json").read_text())
    metadata["status"] = "running"
    (path / "manifest.json").write_text(json.dumps(metadata))
    assert client.post("/api/remove/" + path.name).status_code == 400


def test_comparison_plot_api(tmp_path):
    path = run_experiment({"output_root": str(tmp_path), "n": 10, "trials": 1})
    client = create_app(tmp_path).test_client()
    assert client.post("/api/comparison-plot", json={"ids": []}).status_code == 400
    response = client.post("/api/comparison-plot", json={"ids": [path.name]})
    assert response.status_code == 200
    assert client.get(response.json["url"]).mimetype == "image/png"
