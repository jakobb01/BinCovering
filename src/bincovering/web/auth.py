"""Dashboard accounts, sessions and the shared authorization boundary."""

import hashlib
import hmac
import secrets
import time
from urllib.parse import urlsplit

from flask import abort, g, jsonify, redirect, render_template, request, session


def csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


def safe_redirect_target(target):
    try:
        parsed = urlsplit(target)
    except ValueError:
        return "/"
    if parsed.scheme or parsed.netloc or not target.startswith("/") or target.startswith("//") or "\\" in target or any(ord(c) < 32 for c in target):
        return "/"
    return target


def install_auth(app, store, *, required=True):
    app.secret_key = store.secret()
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        MAX_CONTENT_LENGTH=2_000_000,
        PERMANENT_SESSION_LIFETIME=8 * 60 * 60,
    )
    app.extensions["bincovering_auth_required"] = required
    if not required:
        users = [u for u in store.users() if u["username"] == "__local_test__"]
        local_user = users[0] if users else store.create_user("__local_test__", secrets.token_urlsafe(32), "admin")

    @app.before_request
    def authenticate_request():
        if not required:
            g.user = local_user
            return None
        g.user = store.user(session.get("user_id")) if session.get("user_id") else None
        if g.user and (not g.user["active"] or session.get("session_version") != g.user["session_version"]):
            session.clear()
            g.user = None
        public = request.endpoint in {"login", "register", "static"}
        if not g.user and not public:
            if request.path.startswith("/api/"):
                return jsonify(error="Sign in to use the dashboard", login_url="/login"), 401
            next_path = request.full_path.rstrip("?")
            return redirect("/login?next=" + next_path)
        if request.endpoint == "register" and request.method == "POST":
            retry_after = store.registration_attempt(request.remote_addr)
            if retry_after:
                response, status = registration_error("Too many registration attempts. Try again in five minutes.", 429)
                response.headers["Retry-After"] = str(retry_after)
                return response, status
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            supplied = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token", "")
            expected = session.get("csrf_token", "")
            if not expected or not hmac.compare_digest(str(supplied).encode(), str(expected).encode()):
                error = "Refresh this page and submit again; the session token changed"
                if request.endpoint == "register":
                    username = request.form.get("username", "")[:64] if not request.is_json else ""
                    return registration_error(error, 403, username=username)
                return jsonify(error=error), 403
        return None

    @app.after_request
    def private_responses(response):
        if request.endpoint != "static":
            response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    @app.context_processor
    def account_context():
        return {"current_user": getattr(g, "user", None), "csrf_token": csrf_token}

    @app.route("/login", methods=["GET", "POST"])
    def login():
        error = None
        if request.method == "POST":
            body = request.get_json(silent=True) if request.is_json else request.form
            body = body or {}
            if not hasattr(body, "get"):
                raise ValueError("Expected account name and password")
            username, password = body.get("username", ""), body.get("password", "")
            key = hashlib.sha256((str(request.remote_addr) + ":" + str(username).lower()).encode()).hexdigest()
            with store.connect() as db:
                attempt = db.execute("SELECT * FROM login_attempts WHERE key=?", (key,)).fetchone()
            locked = attempt and attempt["failures"] >= 8 and time.time() - attempt["last_attempt"] < 300
            user = None if locked else store.authenticate(username, password)
            if user:
                session.clear()
                session["user_id"] = user["id"]
                session["session_version"] = user["session_version"]
                session.permanent = True
                token = csrf_token()
                with store.connect() as db:
                    db.execute("DELETE FROM login_attempts WHERE key=?", (key,))
                target = safe_redirect_target(request.args.get("next", "/"))
                if request.is_json:
                    return jsonify(user=user, csrf_token=token, redirect=target)
                return redirect(target)
            with store.connect() as db:
                failures = attempt["failures"] + 1 if attempt and time.time() - attempt["last_attempt"] < 300 else 1
                db.execute("INSERT OR REPLACE INTO login_attempts VALUES (?,?,?)", (key, failures, time.time()))
            error = "Too many attempts. Try again in five minutes." if locked else "Account name or password is incorrect."
            if request.is_json:
                return jsonify(error=error), 429 if locked else 401
        return render_template("login.html", error=error, setup_needed=not store.users()), 401 if error else 200

    def registration_error(error, status, *, username="", setup_needed=None):
        if setup_needed is None:
            setup_needed = not store.has_active_administrator()
        if request.is_json:
            return jsonify(error=error, setup_needed=setup_needed), status
        return app.make_response(render_template("register.html", error=error, setup_needed=setup_needed, username=username)), status

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if g.user:
            if request.method == "GET":
                return redirect("/")
            return registration_error("Sign out before registering another account.", 409)
        setup_needed = not store.has_active_administrator()
        if request.method == "GET":
            csrf_token()
            return render_template("register.html", error=None, setup_needed=setup_needed, username="")
        if setup_needed:
            return registration_error("An administrator must finish workspace setup before researchers can register.", 403, setup_needed=True)
        body = request.get_json(silent=True) if request.is_json else request.form
        if not hasattr(body, "get") or not hasattr(body, "keys"):
            return registration_error("Enter an account name, password and matching confirmation.", 400)
        username = body.get("username", "")
        username_display = username[:64] if isinstance(username, str) else ""
        allowed = {"username", "password", "password_confirm"}
        if not request.is_json:
            allowed.add("csrf_token")
        if set(body.keys()) - allowed:
            return registration_error("Registration only accepts an account name, password and confirmation.", 400, username=username_display)
        if not request.is_json and any(len(body.getlist(field)) != 1 for field in ("username", "password", "password_confirm")):
            return registration_error("Enter one value for each registration field.", 400, username=username_display)
        password, confirmation = body.get("password"), body.get("password_confirm")
        if not isinstance(password, str) or not isinstance(confirmation, str) or password != confirmation:
            return registration_error("The password and confirmation must match.", 400, username=username_display)
        try:
            user = store.create_user(username, password, "user")
        except ValueError as exc:
            return registration_error(str(exc), 400, username=username_display)
        session.clear()
        session["user_id"] = user["id"]
        session["session_version"] = user["session_version"]
        session.permanent = True
        token = csrf_token()
        target = safe_redirect_target(request.args.get("next", "/"))
        if request.is_json:
            return jsonify(user=user, csrf_token=token, redirect=target), 201
        return redirect(target)

    @app.get("/api/session")
    def account_session():
        return jsonify(user=g.user, csrf_token=csrf_token())

    @app.post("/api/logout")
    @app.post("/logout")
    def logout():
        session.clear()
        if request.path.startswith("/api/"):
            return jsonify(ok=True)
        return redirect("/login")

    def administrator():
        if g.user["role"] != "admin":
            abort(403, description="Administrator access is required")

    def settings():
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            raise ValueError("Expected account settings")
        return body

    @app.get("/admin")
    def admin_page():
        administrator()
        return render_template("admin.html")

    @app.get("/api/admin/users")
    def users():
        administrator()
        return jsonify(users=store.users())

    @app.post("/api/admin/users")
    def create_account():
        administrator()
        body = settings()
        user = store.create_user(body.get("username"), body.get("password"), body.get("role", "user"))
        return jsonify(user=user), 201

    @app.patch("/api/admin/users/<user_id>")
    def edit_account(user_id):
        administrator()
        body = settings()
        unknown = set(body) - {"active", "role", "password"}
        if unknown:
            raise ValueError("Unknown account setting")
        return jsonify(user=store.change_user(user_id, **body))

    @app.post("/api/admin/reassign")
    def reassign():
        administrator()
        body = settings()
        run_id = body.get("run_id")
        if not isinstance(run_id, str):
            raise ValueError("Choose an experiment")
        path = (store.root / run_id).resolve()
        if path == store.root or not path.is_relative_to(store.root) or ".trash" in path.relative_to(store.root).parts or not (path / "manifest.json").is_file():
            raise ValueError("Unknown experiment")
        store.assign_run(run_id, body.get("owner_id"))
        return jsonify(run_id=run_id, owner_id=store.run_owner(run_id))
