import json

from bincovering.web.review import create_review_app


def test_review_explicit_submission_preserves_other_decisions(tmp_path):
    original = {"01-research-overview": {"preference": "Keep", "notes": "Must have."}}
    (tmp_path / "user-review.json").write_text(json.dumps(original))
    (tmp_path / "browser-review-notes.json").write_text(json.dumps({
        "01-research-overview": {"preference": "Skip", "notes": "QA only"}
    }))
    client = create_review_app(tmp_path).test_client()
    assert client.get("/api/review").json == original
    updates = {"02-reliability-ecdf": {"preference": "Keep", "notes": "Clear now."}}
    response = client.post("/api/review", json=updates)
    assert response.status_code == 200
    assert response.json == original | updates
    assert json.loads((tmp_path / "user-review.json").read_text()) == original | updates
    assert list(tmp_path.glob(".review-*.tmp")) == []


def test_review_rejects_bad_notes_and_preserves_corrupt_evidence(tmp_path):
    client = create_review_app(tmp_path).test_client()
    for bad in (
        {}, [], {"unknown": {"preference": "Keep", "notes": ""}},
        {"02-reliability-ecdf": {"preference": "Maybe", "notes": ""}},
        {"02-reliability-ecdf": {"preference": "Keep", "notes": "a" * 4001}},
        {"02-reliability-ecdf": {"preference": "Keep", "notes": "", "extra": 1}},
    ):
        assert client.post("/api/review", json=bad).status_code == 400
    assert client.get("/browser-review-notes.json").status_code == 404
    assert client.get("/source/private.py").status_code == 404
    (tmp_path / "user-review.json").write_text("CORRUPT EVIDENCE")
    assert client.get("/api/review").status_code == 500
    assert client.post("/api/review", json={
        "02-reliability-ecdf": {"preference": "Keep", "notes": ""}
    }).status_code == 500
    assert (tmp_path / "user-review.json").read_text() == "CORRUPT EVIDENCE"
