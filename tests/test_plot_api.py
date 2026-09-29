"""Approved plot routes expose saved evidence and clear study validation errors."""

import pytest

from bincovering.experiments.runner import run_experiment
from bincovering.web.app import create_app


def make_run(root, **settings):
    return run_experiment({"output_root": str(root), "n": 20, "trials": 2, **settings})


def assert_downloads(client, response):
    assert response.status_code == 200, response.json
    png = client.get(response.json["url"])
    svg = client.get(response.json["svg_url"])
    assert png.mimetype == "image/png" and png.data.startswith(b"\x89PNG")
    assert svg.mimetype == "image/svg+xml" and b"<svg" in svg.data


def test_overview_panel_and_mass_downloads_from_same_saved_run(tmp_path):
    run = make_run(tmp_path)
    client = create_app(tmp_path).test_client()
    assert_downloads(
        client,
        client.post(
            f"/api/plot/{run.name}",
            json={"kind": "overview", "algorithm": 1, "panel": "outcomes"},
        ),
    )
    assert_downloads(
        client, client.post(f"/api/plot/{run.name}", json={"kind": "mass"})
    )
    for file in (run / "bin-statistics").glob("*.json"):
        file.unlink()
    response = client.post(f"/api/plot/{run.name}", json={"kind": "mass"})
    assert response.status_code == 400
    assert "no saved bin-load measurements" in response.json["error"]
    assert_downloads(client, client.post(f"/api/plot/{run.name}"))


@pytest.mark.parametrize(
    "body",
    [
        {"kind": []},
        {"kind": "unapproved"},
        {"algorithm": -1},
        {"algorithm": True},
        {"algorithm": 999},
        {"panel": []},
    ],
)
def test_plot_api_rejects_invalid_selections(tmp_path, body):
    run = make_run(tmp_path)
    client = create_app(tmp_path).test_client()
    assert client.post(f"/api/plot/{run.name}", json=body).status_code == 400
    assert (
        client.get(
            f"/api/figure/{run.name}?name=../../manifest&format=json"
        ).status_code
        == 400
    )


def test_controlled_study_downloads_and_confounded_inputs_rejected(tmp_path):
    original = make_run(tmp_path, ordering="original")
    shuffled = make_run(tmp_path, ordering="shuffle")
    unmatched = make_run(tmp_path, ordering="shuffle", seed=43)
    client = create_app(tmp_path).test_client()
    assert_downloads(
        client,
        client.post(
            "/api/study-plot",
            json={"kind": "ordering", "ids": [original.name, shuffled.name]},
        ),
    )
    response = client.post(
        "/api/study-plot",
        json={"kind": "ordering", "ids": [original.name, unmatched.name]},
    )
    assert response.status_code == 400
    assert "matching base trial inputs" in response.json["error"]
    parameters = make_run(
        tmp_path,
        algorithms=[
            {"id": "ThrowBin_1", "params": {"bin_ratio": ratio}} for ratio in (0.2, 0.4)
        ],
    )
    assert_downloads(
        client,
        client.post(
            "/api/study-plot",
            json={"kind": "parameters", "ids": [parameters.name]},
        ),
    )


def test_reliability_target_updates_table_and_preserves_downloads(tmp_path):
    run = make_run(tmp_path, trials=3)
    client = create_app(tmp_path).test_client()
    urls = []
    for target in (0, 100):
        response = client.post(
            f"/api/plot/{run.name}", json={"kind": "reliability", "target": target}
        )
        assert_downloads(client, response)
        table = response.json["target_data"]
        assert table["target"] == target
        assert len(table["groups"]) == 2
        assert all(group["total"] == 3 for group in table["groups"])
        if target == 0:
            assert all(group["reached"] == 3 for group in table["groups"])
        urls.append(response.json["url"])
    assert urls[0] != urls[1]
    assert client.get(urls[0]).mimetype == "image/png"
    study = client.post(
        "/api/study-plot",
        json={"kind": "reliability", "target": 75, "ids": [run.name]},
    )
    assert_downloads(client, study)
    assert study.json["target_data"]["target"] == 75


@pytest.mark.parametrize("target", [-1, 101, True, "70", None, [], 10**100])
def test_reliability_rejects_invalid_numeric_target(tmp_path, target):
    run = make_run(tmp_path)
    client = create_app(tmp_path).test_client()
    for route, settings in (
        (f"/api/plot/{run.name}", {}),
        ("/api/study-plot", {"ids": [run.name]}),
    ):
        response = client.post(
            route, json={"kind": "reliability", "target": target, **settings}
        )
        assert response.status_code == 400
        assert "0 to 100" in response.json["error"]


def test_paired_dnf_available_for_single_and_selected_experiments(tmp_path):
    run = make_run(tmp_path)
    client = create_app(tmp_path).test_client()
    assert_downloads(
        client, client.post(f"/api/plot/{run.name}", json={"kind": "paired"})
    )
    assert_downloads(
        client,
        client.post("/api/study-plot", json={"kind": "paired", "ids": [run.name]}),
    )
    no_dnf = make_run(tmp_path, algorithms=[{"id": "harmonic"}])
    response = client.post(f"/api/plot/{no_dnf.name}", json={"kind": "paired"})
    assert response.status_code == 400
    assert "DNF" in response.json["error"]
