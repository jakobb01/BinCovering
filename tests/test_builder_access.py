"""Real session/ownership tests; executor boundaries are covered separately."""

import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from werkzeug.security import check_password_hash

from bincovering.builders.storage import BuilderStore
from bincovering.experiments.runner import run_experiment
from bincovering.web.app import create_app


class AccessQueue:
    """Deterministic queue double: these tests verify HTTP authorization only."""

    def __init__(self):
        self.records = {}

    def submit_preview(self, owner_id, graph, settings):
        job_id = str(len(self.records) + 1)
        self.records[job_id] = {"id": job_id, "owner_id": owner_id, "status": "queued", "graph": graph, "settings": settings}
        return {"id": job_id, "status": "queued"}

    def get_job(self, owner_id, job_id, administrator=False):
        row = self.records.get(job_id)
        if not row or not administrator and row["owner_id"] != owner_id:
            raise ValueError("Unknown job")
        return row

    def cancel_job(self, owner_id, job_id, administrator=False):
        row = self.get_job(owner_id, job_id, administrator)
        row["status"] = "cancelled"
        return {"id": job_id, "status": "cancelled"}


@pytest.fixture
def workspace(tmp_path):
    store = BuilderStore(tmp_path)
    admin = store.create_user("administrator", "admin-password-2026", "admin")
    alice = store.create_user("alice", "alice-password-2026")
    bob = store.create_user("bob", "bob-password-2026")
    queue = AccessQueue()
    app = create_app(tmp_path, execution_queue=queue)
    app.config["TESTING"] = True
    return app, store, queue, admin, alice, bob


def sign_in(app, username, password):
    client = app.test_client()
    assert client.get("/login").status_code == 200
    with client.session_transaction() as session:
        token = session["csrf_token"]
    response = client.post("/login", json={"username": username, "password": password}, headers={"X-CSRF-Token": token})
    assert response.status_code == 200
    return client, {"X-CSRF-Token": response.json["csrf_token"]}


def registration_client(app):
    client = app.test_client()
    assert client.get("/register").status_code == 200
    with client.session_transaction() as session:
        token = session["csrf_token"]
    return client, {"X-CSRF-Token": token}


def test_default_auth_cannot_be_bypassed_before_setup(tmp_path):
    app = create_app(tmp_path, execution_queue=AccessQueue())
    client = app.test_client()
    assert client.get("/").status_code == 302
    assert client.get("/api/runs").status_code == 401
    assert client.post("/api/runs", json={}).status_code == 401
    assert b"setup-admin" in client.get("/login").data


def test_public_registration_waits_for_active_administrator(tmp_path):
    app = create_app(tmp_path, execution_queue=AccessQueue())
    store = app.extensions["bincovering_store"]
    client, headers = registration_client(app)
    assert b"administrator" in client.get("/register").data.lower()
    body = {"username": "researcher", "password": "researcher-password-2026", "password_confirm": "researcher-password-2026"}
    response = client.post("/register", json=body, headers=headers)
    assert response.status_code == 403
    assert response.json["setup_needed"] is True
    assert store.users() == []
    # A nonadministrator legacy account also does not complete initial setup.
    store.create_user("legacy", "legacy-password-2026")
    assert client.post("/register", json=body, headers=headers).status_code == 403
    assert [user["username"] for user in store.users()] == ["legacy"]


def test_public_registration_hashes_password_signs_in_and_has_researcher_access(workspace):
    app, store, _, _, _, bob = workspace
    client, headers = registration_client(app)
    password = "self-registration-password-2026"
    response = client.post("/register?next=/builder", json={"username": "New.Researcher", "password": password, "password_confirm": password}, headers=headers)
    assert response.status_code == 201
    account = response.json["user"]
    assert account["username"] == "new.researcher"
    assert account["role"] == "user"
    assert account["active"] == 1
    assert response.json["redirect"] == "/builder"
    assert response.json["csrf_token"] != headers["X-CSRF-Token"]
    assert "password" not in account and "password_hash" not in account
    with store.connect() as db:
        record = db.execute("SELECT password_hash FROM users WHERE id=?", (account["id"],)).fetchone()
    assert record["password_hash"] != password
    assert check_password_hash(record["password_hash"], password)
    assert store.authenticate("NEW.RESEARCHER", password)["id"] == account["id"]
    assert client.get("/api/session").json["user"]["id"] == account["id"]
    assert client.get("/register").status_code == 302
    assert client.get("/builder").status_code == 200
    assert client.get("/api/admin/users").status_code == 403
    assert client.get("/admin").status_code == 403
    new_headers = {"X-CSRF-Token": response.json["csrf_token"]}
    switch = client.post("/register", json={"username": "anotheruser", "password": password, "password_confirm": password}, headers=new_headers)
    assert switch.status_code == 409
    assert client.get("/api/session").json["user"]["id"] == account["id"]
    assert client.post("/api/admin/users", json={"username": "forged-admin", "password": password, "role": "admin"}, headers=new_headers).status_code == 403
    administrator, admin_headers = sign_in(app, "administrator", "admin-password-2026")
    assert administrator.patch("/api/admin/users/" + bob["id"], json={"active": False}, headers=admin_headers).status_code == 200
    users = administrator.get("/api/admin/users").json["users"]
    assert {user["username"] for user in users} == {"administrator", "alice", "bob", "new.researcher"}
    assert next(user for user in users if user["username"] == "bob")["active"] == 0
    assert all("password_hash" not in user and "password" not in user for user in users)


def test_registration_validates_confirmation_duplicates_and_rejects_privileges(workspace):
    app, store, _, _, _, _ = workspace
    client, headers = registration_client(app)
    good = {"username": "newuser", "password": "newuser-password-2026", "password_confirm": "newuser-password-2026"}
    cases = [
        ({**good, "username": "x"}, "3–64"),
        ({**good, "password": "short", "password_confirm": "short"}, "12–1024"),
        ({**good, "password_confirm": "different-password"}, "must match"),
        ({**good, "username": "ALICE"}, "already exists"),
        ({**good, "role": "admin"}, "only accepts"),
        ({**good, "active": True}, "only accepts"),
        ({**good, "admin": True}, "only accepts"),
    ]
    for body, error in cases:
        response = client.post("/register", json=body, headers=headers)
        assert response.status_code == 400
        assert error in response.json["error"]
    assert {user["username"] for user in store.users()} == {"administrator", "alice", "bob"}
    assert client.get("/api/session").status_code == 401
    response = client.post("/register", json=good)
    assert response.status_code == 403
    assert {user["username"] for user in store.users()} == {"administrator", "alice", "bob"}


@pytest.mark.parametrize("target", ["https://example.com/", "//example.com", "/\\example.com", "//[broken", "/path\x00"])
def test_registration_redirect_stays_local(workspace, target):
    app, _, _, _, _, _ = workspace
    client, headers = registration_client(app)
    response = client.post("/register", query_string={"next": target}, json={"username": "localnext", "password": "localnext-password-2026", "password_confirm": "localnext-password-2026"}, headers=headers)
    assert response.status_code == 201
    assert response.json["redirect"] == "/"


def test_registration_form_preserves_only_username_and_redirects_on_success(workspace):
    app, _, _, _, _, _ = workspace
    client, headers = registration_client(app)
    password = "form-registration-password-2026"
    response = client.post("/register", data={"username": "formuser", "password": password, "password_confirm": "wrong-confirmation", "csrf_token": headers["X-CSRF-Token"]})
    assert response.status_code == 400
    assert b"formuser" in response.data
    assert password.encode() not in response.data
    assert b"wrong-confirmation" not in response.data
    response = client.post("/register?next=/experiments", data={"username": "formuser", "password": password, "password_confirm": password, "csrf_token": headers["X-CSRF-Token"]})
    assert response.status_code == 302
    assert response.location == "/experiments"
    assert client.get("/api/session").json["user"]["role"] == "user"


@pytest.mark.parametrize("invalid_token", ["old-session-token", "é"])
def test_registration_invalid_csrf_is_rejected_with_usable_form_feedback(workspace, invalid_token):
    app, store, _, _, _, _ = workspace
    client, _ = registration_client(app)
    password = "csrf-researcher-password"
    body = {"username": "csrfuser", "password": password, "password_confirm": password}
    response = client.post("/register", json=body, headers={"X-CSRF-Token": invalid_token})
    assert response.status_code == 403
    assert "session token changed" in response.json["error"]
    response = client.post("/register", data={**body, "csrf_token": invalid_token})
    assert response.status_code == 403
    assert b'id="register-error"' in response.data
    assert b"session token changed" in response.data
    assert b'csrfuser' in response.data
    assert password.encode() not in response.data
    assert not any(user["username"] == "csrfuser" for user in store.users())


def test_registration_rate_limit_persists_and_counts_invalid_csrf_without_forwarded_ip(workspace):
    app, store, _, _, _, _ = workspace
    client, _ = registration_client(app)
    body = {"username": "rateuser", "password": "rateuser-password-2026", "password_confirm": "rateuser-password-2026"}
    for attempt in range(10):
        response = client.post("/register", json=body, headers={"X-Forwarded-For": f"203.0.113.{attempt}"})
        assert response.status_code == 403
    response = client.post("/register", json=body)
    assert response.status_code == 429
    assert 1 <= int(response.headers["Retry-After"]) <= 300
    restarted_app = create_app(store.root, execution_queue=AccessQueue())
    next_client, headers = registration_client(restarted_app)
    assert next_client.post("/register", json=body, headers=headers).status_code == 429
    assert len(store.users()) == 3
    different_peer = next_client.post("/register", json=body, headers=headers, environ_overrides={"REMOTE_ADDR": "198.51.100.42"})
    assert different_peer.status_code == 201


def test_registration_rate_limit_claims_are_atomic_and_expired_cleanup_is_bounded(tmp_path):
    store = BuilderStore(tmp_path)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: store.registration_attempt("192.0.2.10", timestamp=1000), range(20)))
    assert results.count(0) == 10
    assert results.count(300) == 10
    assert store.registration_attempt("192.0.2.10", timestamp=1300) == 0
    with store.connect() as db:
        db.executemany("INSERT INTO registration_attempts(remote_key,attempted_at) VALUES (?,?)", [("expired", 1000)] * 250)
    assert store.registration_attempt("192.0.2.11", timestamp=1400) == 0
    with store.connect() as db:
        assert db.execute("SELECT count(*) FROM registration_attempts WHERE remote_key='expired'").fetchone()[0] == 150


def test_sessions_csrf_admin_and_password_invalidation(workspace):
    app, store, _, admin, alice, _ = workspace
    client, headers = sign_in(app, "alice", "alice-password-2026")
    assert client.get("/api/session").json["user"]["id"] == alice["id"]
    assert client.post("/api/logout").status_code == 403
    assert client.get("/api/admin/users").status_code == 403
    assert client.post("/api/admin/users", json={}, headers=headers).status_code == 403
    store.change_user(alice["id"], password="new-alice-password-2026")
    assert client.get("/api/session").status_code == 401
    administrator, admin_headers = sign_in(app, "administrator", "admin-password-2026")
    response = administrator.patch("/api/admin/users/" + admin["id"], json={"active": False}, headers=admin_headers)
    assert response.status_code == 400
    assert "one active administrator" in response.json["error"]
    response = administrator.post("/api/admin/users", json={"username": "charlie", "password": "charlie-password-2026"}, headers=admin_headers)
    assert response.status_code == 201
    assert "password_hash" not in response.json["user"]


def test_all_existing_run_routes_enforce_owner_and_trash_tokens(workspace, tmp_path):
    app, store, _, _, alice, bob = workspace
    run = run_experiment({"output_root": str(tmp_path), "n": 6, "trials": 1})
    store.assign_run(run.name, alice["id"])
    a, ah = sign_in(app, "alice", "alice-password-2026")
    b, bh = sign_in(app, "bob", "bob-password-2026")
    assert a.get("/api/runs").json[0]["id"] == run.name
    assert b.get("/api/runs").json == []
    for path in ("inspect", "export", "figure"):
        assert b.get(f"/api/{path}/{run.name}").status_code == 400
    assert b.get(f"/api/traces/{run.name}").status_code == 400
    assert b.get(f"/api/trace/{run.name}?trial=0&algorithm=0").status_code == 400
    for path in ("pin", "remove", "cancel", "plot"):
        assert b.post(f"/api/{path}/{run.name}", json={}, headers=bh).status_code == 400
    assert b.get("/api/compare", query_string=[("id", run.name), ("id", run.name)]).status_code == 400
    assert b.post("/api/study-plot", json={"ids": [run.name], "kind": "paired"}, headers=bh).status_code == 400
    assert b.post("/api/comparison-plot", json={"ids": [run.name]}, headers=bh).status_code == 400
    token = "a" * 32
    store.comparison(token, alice["id"], [run.name])
    figures = tmp_path / ".comparisons"
    figures.mkdir()
    (figures / (token + ".png")).write_bytes(b"PNG")
    assert a.get("/api/comparison-figure/" + token).status_code == 200
    assert b.get("/api/comparison-figure/" + token).status_code == 400
    removed = a.post("/api/remove/" + run.name, headers=ah).json["token"]
    assert b.post("/api/restore/" + removed, headers=bh).status_code == 400
    assert a.post("/api/restore/" + removed, headers=ah).status_code == 200
    administrator, admin_headers = sign_in(app, "administrator", "admin-password-2026")
    original = (run / "manifest.json").read_bytes()
    response = administrator.post("/api/admin/reassign", json={"run_id": run.name, "owner_id": bob["id"]}, headers=admin_headers)
    assert response.status_code == 200
    assert (run / "manifest.json").read_bytes() == original
    assert a.get("/api/inspect/" + run.name).status_code == 400
    assert b.get("/api/inspect/" + run.name).status_code == 200
    assert a.get("/api/comparison-figure/" + token).status_code == 400


def test_private_library_shared_revision_clone_and_frozen_exports(workspace):
    from bincovering.builders.schema import graph_hash
    from bincovering.builders.templates import starter_templates

    app, store, queue, _, alice, bob = workspace
    graph = starter_templates()[0]["graph"]
    a, ah = sign_in(app, "alice", "alice-password-2026")
    b, bh = sign_in(app, "bob", "bob-password-2026")
    response = a.post("/api/builder/library", json={"name": "Alice online", "kind": graph["kind"], "graph": graph}, headers=ah)
    assert response.status_code == 201
    item_id = response.json["id"]
    assert b.get("/api/builder/library").json["items"] == []
    assert b.get("/api/builder/library/" + item_id).status_code == 400
    assert b.put("/api/builder/library/" + item_id, json={"name": "stolen"}, headers=bh).status_code == 400
    preview = a.post(f"/api/builder/library/{item_id}/preview", json={"settings": {"items": [0.6, 0.6]}}, headers=ah)
    assert preview.status_code == 202
    job_id = preview.json["id"]
    assert b.get("/api/builder/jobs/" + job_id).status_code == 400
    assert b.post("/api/builder/jobs/" + job_id + "/cancel", headers=bh).status_code == 400
    graph = queue.records[job_id]["graph"]
    queue.records[job_id].update(status="completed", result={"ok": True, "runtime_version": "1", "graph_hash": graph_hash(graph), "execution": {"image": "sha256:" + "a" * 64}})
    made = a.post(f"/api/builder/library/{item_id}/available", json={"job_id": job_id}, headers=ah)
    assert made.status_code == 201
    frozen = made.json["frozen"]
    assert frozen["runtime_image"].startswith("sha256:")
    assert b.post(f"/api/builder/library/{item_id}/clone", json={"revision": "1"}, headers=bh).status_code == 400
    shared = a.post(f"/api/builder/library/{item_id}/share", json={"revision": "1", "shared": True}, headers=ah)
    assert shared.status_code == 200
    assert b.get("/api/builder/library/" + item_id).json["owned"] is False
    assert b.post(f"/api/builder/library/{item_id}/share", json={"revision": "1", "shared": False}, headers=bh).status_code == 400
    cloned = b.post(f"/api/builder/library/{item_id}/clone", json={"revision": "1"}, headers=bh)
    assert cloned.status_code == 201
    assert cloned.json["owner_id"] == bob["id"]
    assert cloned.json["id"] != item_id
    altered = json.loads(json.dumps(graph))
    altered["label"] = "Changed draft"
    assert a.put("/api/builder/library/" + item_id, json={"graph": altered}, headers=ah).status_code == 200
    assert store.freeze(alice["id"], item_id, "1") == frozen
    changed_execution = json.loads(json.dumps(graph))
    next(node for node in changed_execution["nodes"] if node["id"] == "check")["config"]["expression"] = "False"
    assert a.put("/api/builder/library/" + item_id, json={"graph": changed_execution}, headers=ah).status_code == 200
    stale = a.post(f"/api/builder/library/{item_id}/available", json={"job_id": job_id}, headers=ah)
    assert stale.status_code == 400
    assert "changed after" in stale.json["error"]
    assert a.put("/api/builder/library/" + item_id, json={"graph": altered}, headers=ah).status_code == 200
    exported = b.get(f"/api/builder/library/{item_id}/export?revision=1")
    assert exported.status_code == 200
    assert exported.json["content_hash"] == frozen["content_hash"]
    assert a.post(f"/api/builder/library/{item_id}/share", json={"revision": "1", "shared": False}, headers=ah).status_code == 200
    assert b.get(f"/api/builder/library/{item_id}/export?revision=1").status_code == 400
    assert b.get("/api/builder/library/" + cloned.json["id"]).status_code == 200
    assert a.post(f"/api/builder/library/{item_id}/archive", headers=ah).status_code == 200
    assert a.get("/api/builder/library").json["items"] == []
    assert a.post(f"/api/builder/library/{item_id}/restore", headers=ah).status_code == 200
    assert store.freeze(alice["id"], item_id, "1") == frozen


def test_client_cannot_inject_frozen_program(workspace):
    app, _, _, _, _, _ = workspace
    client, headers = sign_in(app, "alice", "alice-password-2026")
    response = client.post("/api/runs", json={"algorithms": [{"id": "custom:" + "a" * 32, "revision": "1", "frozen": {"graph": {}, "runtime_image": "fake"}}]}, headers=headers)
    assert response.status_code == 400
    assert "Unknown" in response.json["error"]


def test_obsolete_preview_capture_settings_are_ignored_without_breaking_old_clients(workspace):
    from bincovering.builders.templates import get_template

    app, _, queue, _, _, _ = workspace
    client, headers = sign_in(app, "alice", "alice-password-2026")
    created = client.post("/api/builder/library", json={"name": "Trace verification", "graph": get_template("online")}, headers=headers)
    assert created.status_code == 201
    response = client.post(f"/api/builder/library/{created.json['id']}/preview",
        json={"settings": {"items": [0.6, 0.6], "trace_limit": 0, "trace_bytes": 0}}, headers=headers)
    assert response.status_code == 202
    settings = queue.records[response.json["id"]]["settings"]
    assert "trace_limit" not in settings and "trace_bytes" not in settings
    assert settings["items"] == [0.6, 0.6]


def test_shared_bundle_clone_survives_private_dependency_and_revocation(workspace):
    from bincovering.builders.schema import graph_hash
    from bincovering.builders.templates import get_template

    _, store, _, _, alice, bob = workspace

    def publish(item):
        graph = store.freeze_graph(alice["id"], item["draft"])
        job_id = "preview-" + item["id"]
        store.record_preview(alice["id"], item["id"], job_id, graph)
        job = {"status": "completed", "result": {"ok": True, "runtime_version": "1", "graph_hash": graph_hash(graph), "execution": {"image": "sha256:" + "b" * 64}}}
        return store.make_available(alice["id"], item["id"], job_id, job)

    dependency = store.create(alice["id"], "Private scale", "component", get_template("component"))
    frozen_dependency = publish(dependency)
    parent_graph = get_template("component")
    parent_graph["components"] = {dependency["id"]: {"revision": 1}}
    parent_graph["nodes"][1].update(type="component", config={"component_id": dependency["id"], "inputs": {"incoming": "incoming"}, "outputs": {"value": "value"}, "params": {"factor": "factor"}})
    parent = store.create(alice["id"], "Shared compound", "component", parent_graph)
    frozen_parent = publish(parent)
    store.share(alice["id"], parent["id"], 1, True)
    with pytest.raises(ValueError, match="Unknown available"):
        store.freeze(bob["id"], dependency["id"], 1)
    cloned = store.clone(bob["id"], parent["id"], 1)
    store.share(alice["id"], parent["id"], 1, False)
    store.archive(alice["id"], dependency["id"])
    clone_graph = store.freeze_graph(bob["id"], cloned["draft"])
    embedded = next(iter(clone_graph["components"].values()))
    assert embedded["origin"]["id"] == dependency["id"]
    assert embedded["origin"]["content_hash"] == frozen_dependency["content_hash"]
    assert embedded["graph"] == frozen_dependency["graph"]
    assert store.freeze(alice["id"], parent["id"], 1) == frozen_parent
