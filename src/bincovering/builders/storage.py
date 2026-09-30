"""Account-scoped drafts and immutable builder revisions.

The index belongs to the dashboard root. Scientific artifacts remain ordinary
files; ownership changes never rewrite their configuration or provenance.
"""

import hashlib
import json
import math
import re
import secrets
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from werkzeug.security import check_password_hash, generate_password_hash

from bincovering.experiments.storage import now

_DUMMY_PASSWORD_HASH = generate_password_hash(secrets.token_urlsafe(32))


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


class BuilderStore:
    def __init__(self, output_root):
        self.root = Path(output_root).resolve()
        self.state = self.root / ".dashboard"
        self.state.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.database = self.state / "index.sqlite3"
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL, role TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL,
                    session_version INTEGER NOT NULL DEFAULT 1);
                CREATE TABLE IF NOT EXISTS libraries (
                    id TEXT PRIMARY KEY, owner_id TEXT NOT NULL,
                    name TEXT NOT NULL, kind TEXT NOT NULL, draft TEXT NOT NULL,
                    archived INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS revisions (
                    library_id TEXT NOT NULL, revision INTEGER NOT NULL,
                    content_hash TEXT NOT NULL, frozen TEXT NOT NULL,
                    shared INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL,
                    PRIMARY KEY (library_id, revision));
                CREATE TABLE IF NOT EXISTS previews (
                    job_id TEXT PRIMARY KEY, library_id TEXT NOT NULL,
                    owner_id TEXT NOT NULL, content_hash TEXT NOT NULL,
                    graph TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS experiments (
                    run_id TEXT PRIMARY KEY, owner_id TEXT NOT NULL,
                    assigned_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS comparison_access (
                    token TEXT PRIMARY KEY, owner_id TEXT NOT NULL,
                    run_ids TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS login_attempts (
                    key TEXT PRIMARY KEY, failures INTEGER NOT NULL,
                    last_attempt REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS registration_attempts (
                    id INTEGER PRIMARY KEY, remote_key TEXT NOT NULL,
                    attempted_at REAL NOT NULL);
                CREATE INDEX IF NOT EXISTS registration_attempts_remote
                    ON registration_attempts(remote_key, attempted_at);
                CREATE INDEX IF NOT EXISTS registration_attempts_time
                    ON registration_attempts(attempted_at);
            """)
            columns = {r[1] for r in db.execute("PRAGMA table_info(users)")}
            if "session_version" not in columns:
                db.execute("ALTER TABLE users ADD COLUMN session_version INTEGER NOT NULL DEFAULT 1")
        self.database.chmod(0o600)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.database, timeout=30)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA busy_timeout=30000")
            with db:
                yield db
        finally:
            db.close()

    def secret(self):
        path = self.state / "session.key"
        if not path.exists():
            try:
                with path.open("x") as stream:
                    stream.write(secrets.token_hex(32))
                path.chmod(0o600)
            except FileExistsError:
                pass
        return path.read_text().strip()

    @staticmethod
    def public_user(row):
        if row is None:
            return None
        return {key: row[key] for key in ("id", "username", "role", "active", "created_at", "session_version")}

    def user(self, user_id):
        with self.connect() as db:
            return self.public_user(db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone())

    def users(self):
        with self.connect() as db:
            return [self.public_user(r) for r in db.execute("SELECT * FROM users ORDER BY username")]

    def has_active_administrator(self):
        with self.connect() as db:
            return db.execute("SELECT 1 FROM users WHERE role='admin' AND active=1 LIMIT 1").fetchone() is not None

    def registration_attempt(self, remote_addr, *, timestamp=None):
        """Atomically consume one of ten attempts in a sliding five-minute window.

        Use the direct peer address, never a forwarded header. Store only its hash;
        obsolete records are cleaned in bounded batches while traffic continues.
        Returns zero when allowed or the number of seconds until a retry is allowed.
        """
        stamp = time.time() if timestamp is None else timestamp
        cutoff = stamp - 300
        key = hashlib.sha256(str(remote_addr).encode()).hexdigest()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM registration_attempts WHERE id IN (SELECT id FROM registration_attempts WHERE attempted_at<=? ORDER BY attempted_at LIMIT 100)", (cutoff,))
            attempts = db.execute("SELECT count(*), min(attempted_at) FROM registration_attempts WHERE remote_key=? AND attempted_at>?", (key, cutoff)).fetchone()
            if attempts[0] >= 10:
                return max(1, math.ceil(attempts[1] + 300 - stamp))
            db.execute("INSERT INTO registration_attempts(remote_key,attempted_at) VALUES (?,?)", (key, stamp))
        return 0

    def create_user(self, username, password, role="user"):
        if not isinstance(username, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{3,64}", username):
            raise ValueError("Use 3–64 letters, digits, dots, underscores or hyphens for the account name")
        if not isinstance(password, str) or not 12 <= len(password) <= 1024:
            raise ValueError("Passwords must contain 12–1024 characters")
        if role not in {"user", "admin"}:
            raise ValueError("Choose user or administrator")
        user_id = uuid.uuid4().hex
        try:
            with self.connect() as db:
                db.execute("INSERT INTO users(id,username,password_hash,role,active,created_at) VALUES (?,?,?,?,1,?)", (
                    user_id, username.lower(), generate_password_hash(password), role, now()))
        except sqlite3.IntegrityError as exc:
            raise ValueError("That account name already exists") from exc
        return self.user(user_id)

    def change_user(self, user_id, *, active=None, password=None, role=None):
        user = self.user(user_id)
        if user is None:
            raise ValueError("Unknown account")
        changes = {}
        if active is not None:
            if type(active) is not bool:
                raise ValueError("Active must be true or false")
            changes["active"] = int(active)
        if role is not None:
            if role not in {"admin", "user"}:
                raise ValueError("Choose user or administrator")
            changes["role"] = role
        if password is not None:
            if not isinstance(password, str) or not 12 <= len(password) <= 1024:
                raise ValueError("Passwords must contain 12–1024 characters")
            changes["password_hash"] = generate_password_hash(password)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            user = self.public_user(db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone())
            if user["role"] == "admin" and user["active"] and (
                changes.get("active", 1) == 0 or changes.get("role", "admin") != "admin"
            ):
                count = db.execute("SELECT count(*) FROM users WHERE role='admin' AND active=1").fetchone()[0]
                if count <= 1:
                    raise ValueError("Keep at least one active administrator")
            for key, value in changes.items():
                db.execute(f"UPDATE users SET {key}=? WHERE id=?", (value, user_id))
            if changes:
                db.execute("UPDATE users SET session_version=session_version+1 WHERE id=?", (user_id,))
        return self.user(user_id)

    def authenticate(self, username, password):
        if not isinstance(username, str) or len(username) > 64 or not isinstance(password, str) or len(password) > 1024:
            return None
        with self.connect() as db:
            row = db.execute("SELECT * FROM users WHERE username=?", (username.lower(),)).fetchone()
        # A dummy hash keeps the account-not-found path from skipping password work.
        password_hash = row["password_hash"] if row else _DUMMY_PASSWORD_HASH
        valid = check_password_hash(password_hash, password)
        return self.public_user(row) if row and row["active"] and valid else None

    def assign_run(self, run_id, owner_id):
        owner = self.user(owner_id)
        if owner is None or not owner["active"]:
            raise ValueError("Choose an active account")
        with self.connect() as db:
            db.execute("INSERT INTO experiments VALUES (?,?,?) ON CONFLICT(run_id) DO UPDATE SET owner_id=excluded.owner_id,assigned_at=excluded.assigned_at", (run_id, owner_id, now()))

    def run_owner(self, run_id):
        with self.connect() as db:
            row = db.execute("SELECT owner_id FROM experiments WHERE run_id=?", (run_id,)).fetchone()
        return row[0] if row else None

    def can_access_run(self, user, run_id):
        return user["role"] == "admin" or self.run_owner(run_id) == user["id"]

    def comparison(self, token, owner_id, run_ids=None):
        with self.connect() as db:
            if run_ids is not None:
                db.execute("INSERT OR REPLACE INTO comparison_access VALUES (?,?,?)", (token, owner_id, canonical(run_ids)))
                return run_ids
            row = db.execute("SELECT * FROM comparison_access WHERE token=? AND owner_id=?", (token, owner_id)).fetchone()
            if not row:
                raise ValueError("Unknown comparison")
            return json.loads(row["run_ids"])

    def create(self, owner_id, name, kind, graph):
        self._metadata(name, kind, graph)
        library_id = "custom:" + uuid.uuid4().hex
        stamp = now()
        with self.connect() as db:
            db.execute("INSERT INTO libraries VALUES (?,?,?,?,?,0,?,?)", (library_id, owner_id, name.strip(), kind, canonical(graph), stamp, stamp))
        return self.item(owner_id, library_id)

    @staticmethod
    def _metadata(name, kind, graph):
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 120:
            raise ValueError("Give the component a name of 1–120 characters")
        if kind not in {"algorithm", "generator", "component"}:
            raise ValueError("Choose algorithm, generator or reusable component")
        if not isinstance(graph, dict):
            raise ValueError("Expected a graph object")
        if len(canonical(graph).encode()) > 1_000_000:
            raise ValueError("Graph exceeds the 1 MB limit")
        if graph.get("kind", kind) != kind:
            raise ValueError("The graph kind must match the library item")

    def _row(self, library_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM libraries WHERE id=?", (library_id,)).fetchone()
        if row is None:
            raise ValueError("Unknown library item")
        return row

    def item(self, owner_id, library_id, *, revision=None, shared=False):
        row = self._row(library_id)
        owned = row["owner_id"] == owner_id
        with self.connect() as db:
            revisions = list(db.execute("SELECT revision,content_hash,shared,created_at FROM revisions WHERE library_id=? ORDER BY revision", (library_id,)))
        visible = revisions if owned else [r for r in revisions if r["shared"] and not row["archived"]]
        if not owned and not visible:
            raise ValueError("Unknown library item")
        result = {key: row[key] for key in ("id", "owner_id", "name", "kind", "created_at", "updated_at")}
        result.update(owned=owned, archived=bool(row["archived"]), revisions=[dict(r) for r in visible], revision=str(visible[-1]["revision"]) if visible else None, shared=any(r["shared"] for r in visible))
        if owned and revision is None:
            result["draft"] = json.loads(row["draft"])
        else:
            frozen = self.freeze(owner_id, library_id, revision or visible[-1]["revision"])
            result["draft"] = frozen["graph"]
            result["frozen"] = frozen
            result["name"] = frozen["name"]
            selected_revision = next(r for r in visible if str(r["revision"]) == str(frozen["revision"]))
            result["updated_at"] = selected_revision["created_at"]
        return result

    def items(self, owner_id, *, archived=False):
        with self.connect() as db:
            ids = [r[0] for r in db.execute("SELECT DISTINCT l.id FROM libraries l LEFT JOIN revisions r ON l.id=r.library_id WHERE (l.owner_id=? OR (r.shared=1 AND l.archived=0)) ORDER BY l.updated_at DESC", (owner_id,))]
        result = [self.item(owner_id, library_id) for library_id in ids]
        return [item for item in result if archived or not item["archived"]]

    def update(self, owner_id, library_id, *, graph=None, name=None):
        row = self._row(library_id)
        if row["owner_id"] != owner_id or row["archived"]:
            raise ValueError("Only the owner can edit an active draft")
        graph = json.loads(row["draft"]) if graph is None else graph
        name = row["name"] if name is None else name
        self._metadata(name, row["kind"], graph)
        with self.connect() as db:
            db.execute("UPDATE libraries SET name=?,draft=?,updated_at=? WHERE id=?", (name.strip(), canonical(graph), now(), library_id))
        return self.item(owner_id, library_id)

    def archive(self, owner_id, library_id, archived=True):
        row = self._row(library_id)
        if row["owner_id"] != owner_id:
            raise ValueError("Only the owner can archive a definition")
        with self.connect() as db:
            db.execute("UPDATE libraries SET archived=?,updated_at=? WHERE id=?", (int(archived), now(), library_id))
        return self.item(owner_id, library_id)

    def freeze_graph(self, owner_id, graph, stack=()):
        from bincovering.builders.schema import validate_graph

        if len(stack) > 8:
            raise ValueError("Reusable component nesting is limited to eight levels")
        graph = json.loads(canonical(graph))
        components = graph.get("components", {})
        if not isinstance(components, dict):
            raise ValueError("Components must be a map of immutable revisions")
        frozen = {}
        for library_id, reference in components.items():
            if library_id in stack:
                raise ValueError("Recursive components are not supported")
            if not isinstance(reference, dict) or "revision" not in reference:
                raise ValueError("Choose an immutable revision for every reusable component")
            if not library_id.startswith("custom:"):
                if not isinstance(reference.get("graph"), dict):
                    raise ValueError("Inline components need their complete graph")
                reference["graph"] = self.freeze_graph(owner_id, reference["graph"], (*stack, library_id))
                frozen[library_id] = reference
                continue
            dependency = self.freeze(owner_id, library_id, reference["revision"])
            if dependency["graph"].get("kind") != "component":
                raise ValueError("Reusable graph nodes require a component revision")
            frozen[library_id] = {"revision": int(dependency["revision"]), "graph": dependency["graph"], "content_hash": dependency["content_hash"]}
        graph["components"] = frozen
        return validate_graph(graph)

    def freeze(self, owner_id, library_id, revision):
        if type(revision) not in {str, int} or not re.fullmatch(r"[1-9][0-9]{0,8}", str(revision)):
            raise ValueError("Choose an available revision")
        try:
            revision = int(revision)
        except (TypeError, ValueError) as exc:
            raise ValueError("Choose an available revision") from exc
        row = self._row(library_id)
        with self.connect() as db:
            record = db.execute("SELECT * FROM revisions WHERE library_id=? AND revision=?", (library_id, revision)).fetchone()
        if record is None or (row["owner_id"] != owner_id and (not record["shared"] or row["archived"])):
            raise ValueError("Unknown available revision")
        return json.loads(record["frozen"])

    def record_preview(self, owner_id, library_id, job_id, graph):
        from bincovering.builders.schema import graph_hash

        row = self._row(library_id)
        if row["owner_id"] != owner_id or row["archived"]:
            raise ValueError("Only the owner can test an active draft")
        with self.connect() as db:
            db.execute("INSERT INTO previews VALUES (?,?,?,?,?,?)", (job_id, library_id, owner_id, graph_hash(graph), canonical(graph), now()))

    def make_available(self, owner_id, library_id, job_id, job):
        from bincovering.builders.schema import (
            RUNTIME_VERSION,
            generated_source,
            graph_hash,
        )

        row = self._row(library_id)
        if row["owner_id"] != owner_id or row["archived"]:
            raise ValueError("Only the owner can make a draft available")
        with self.connect() as db:
            preview = db.execute("SELECT * FROM previews WHERE job_id=? AND library_id=? AND owner_id=?", (job_id, library_id, owner_id)).fetchone()
        result = job.get("result") or {}
        if not preview or job.get("status") != "completed" or not result.get("ok"):
            raise ValueError("Run a successful preview before making this revision available")
        if str(result.get("runtime_version")) != str(RUNTIME_VERSION):
            raise ValueError("Test the draft with the current builder runtime before making it available")
        graph = self.freeze_graph(owner_id, json.loads(row["draft"]))
        content_hash = graph_hash(graph)
        if content_hash != preview["content_hash"] or result.get("graph_hash") != content_hash:
            raise ValueError("The draft changed after its preview; test it again")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            previous = db.execute("SELECT frozen FROM revisions WHERE library_id=? AND content_hash=? ORDER BY revision DESC LIMIT 1", (library_id, content_hash)).fetchone()
            if previous:
                return json.loads(previous[0])
            revision = db.execute("SELECT coalesce(max(revision),0)+1 FROM revisions WHERE library_id=?", (library_id,)).fetchone()[0]
            image = result.get("execution", {}).get("image")
            if not isinstance(image, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", image):
                raise ValueError("The preview has no verified runtime image identity")
            frozen = dict(id=library_id, name=row["name"], revision=str(revision), content_hash=content_hash, graph=graph, dependencies=graph.get("components", {}), runtime_version=RUNTIME_VERSION, runtime_image=image, generated_source=generated_source(graph))
            db.execute("INSERT INTO revisions VALUES (?,?,?,?,0,?)", (library_id, revision, content_hash, canonical(frozen), now()))
        return frozen

    def share(self, owner_id, library_id, revision, shared):
        if type(shared) is not bool:
            raise ValueError("Shared must be true or false")
        if self._row(library_id)["owner_id"] != owner_id:
            raise ValueError("Only the owner can share a revision")
        self.freeze(owner_id, library_id, revision)
        with self.connect() as db:
            db.execute("UPDATE revisions SET shared=? WHERE library_id=? AND revision=?", (int(shared), library_id, int(revision)))
        return self.item(owner_id, library_id)

    def clone(self, owner_id, library_id, revision, name=None):
        frozen = self.freeze(owner_id, library_id, revision)
        graph = self._inline_bundle(frozen["graph"])
        return self.create(owner_id, name or (frozen["name"] + " copy"), graph["kind"], graph)

    @classmethod
    def _inline_bundle(cls, original):
        """Clones own their bundle, independently of live source-library access."""
        graph = json.loads(canonical(original))
        renamed, components = {}, {}
        for component_id, reference in graph.get("components", {}).items():
            copied = json.loads(canonical(reference))
            if component_id.startswith("custom:"):
                new_id = "embedded-" + hashlib.sha256(canonical(reference).encode()).hexdigest()[:32]
                renamed[component_id] = new_id
                copied["origin"] = {"id": component_id, "revision": reference["revision"], "content_hash": reference.get("content_hash")}
            else:
                new_id = component_id
            copied["graph"] = cls._inline_bundle(copied["graph"])
            components[new_id] = copied
        graph["components"] = components
        for node in graph.get("nodes", []):
            if node.get("type") == "component":
                config = node.setdefault("config", {})
                config["component_id"] = renamed.get(config.get("component_id"), config.get("component_id"))
        return graph

    def available(self, owner_id):
        choices = {"algorithms": [], "generators": [], "components": []}
        for item in self.items(owner_id):
            for revision in item["revisions"]:
                frozen = self.freeze(owner_id, item["id"], revision["revision"])
                graph = frozen["graph"]
                choices[item["kind"] + "s"].append(dict(id=item["id"], revision=str(revision["revision"]), name=frozen["name"], access=graph.get("access", "online"), domain=graph.get("domain", "float64"), parameters=graph.get("parameters", {}), shared=bool(revision["shared"]), owner_id=item["owner_id"], content_hash=frozen["content_hash"]))
        return choices

    def authorize_specs(self, owner_id, raw):
        """Replace all client-supplied packages with authorized frozen revisions."""
        raw = json.loads(canonical(raw))
        specifications = raw.get("algorithms", [])
        if isinstance(specifications, list):
            for spec in specifications:
                if not isinstance(spec, dict):
                    continue
                if str(spec.get("id", "")).startswith("custom:"):
                    spec["frozen"] = self.freeze(owner_id, spec["id"], spec.get("revision"))
                    if spec["frozen"]["graph"]["kind"] != "algorithm":
                        raise ValueError("Choose an algorithm revision")
                else:
                    spec.pop("frozen", None)
        generator = raw.get("generator")
        if isinstance(generator, dict):
            if str(generator.get("id", "")).startswith("custom:"):
                generator["frozen"] = self.freeze(owner_id, generator["id"], generator.get("revision"))
                if generator["frozen"]["graph"]["kind"] != "generator":
                    raise ValueError("Choose an item generator revision")
            else:
                generator.pop("frozen", None)
        return raw
