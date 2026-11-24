"""AuthMiddleware (Design 4.1.2) - session, login, role and ownership checks.

Usage in a controller:

    from ..middleware.auth import login_required, admin_required, require_owner

    @bp.route("/prompts/<int:prompt_id>/edit")
    @login_required
    def edit(prompt_id):
        prompt = ...
        require_owner(prompt.owner_id)   # 403 when the signed-in user is not the owner

Responses: 401 when not signed in, 403 when signed in but not allowed (NFR-02b).
"""
import hashlib
import hmac
import time
from functools import wraps

from flask import abort, current_app, flash, g, request, session

from ..extensions import db
from ..models import User

SESSION_USER_KEY = "user_id"
SESSION_LAST_SEEN_KEY = "last_seen"
SESSION_PASSWORD_KEY = "pw"


def _password_fingerprint(user):
    """Short keyed digest of the password hash.

    Stored in the session and checked on every request, so changing the password
    ends every other session that was started with the old one.
    """
    key = current_app.config["SECRET_KEY"].encode()
    return hmac.new(key, user.password_hash.encode(), hashlib.sha256).hexdigest()[:32]


def init_app(app):
    app.before_request(load_current_user)

    @app.context_processor
    def inject_current_user():
        return {"current_user": g.get("user")}


def load_current_user():
    """Set g.user for this request and end the session after inactivity (FR-02, Figure 4 A5)."""
    g.user = None
    if request.endpoint == "static":
        return

    user_id = session.get(SESSION_USER_KEY)
    if user_id is None:
        return

    now = time.time()
    last_seen = session.get(SESSION_LAST_SEEN_KEY)
    timeout = current_app.config["SESSION_INACTIVITY_TIMEOUT"].total_seconds()
    if last_seen is None or now - last_seen > timeout:
        end_session()
        flash(f"Your session ended after {int(timeout // 60)} minutes without activity. Sign in again.", "info")
        return

    user = db.session.get(User, user_id)
    if user is None or user.is_suspended:
        # Account removed or suspended by an administrator while signed in.
        end_session()
        return
    if not hmac.compare_digest(session.get(SESSION_PASSWORD_KEY, ""), _password_fingerprint(user)):
        # The password was changed in another session.
        end_session()
        flash("Your password was changed. Sign in again.", "info")
        return

    g.user = user
    session[SESSION_LAST_SEEN_KEY] = now


def start_session(user):
    session.clear()  # drop anything from before sign in
    session[SESSION_USER_KEY] = user.id
    session[SESSION_LAST_SEEN_KEY] = time.time()
    session[SESSION_PASSWORD_KEY] = _password_fingerprint(user)
    session.permanent = True


def refresh_password_fingerprint(user):
    """Keep the current session valid after the user changes their own password."""
    session[SESSION_PASSWORD_KEY] = _password_fingerprint(user)


def end_session():
    session.clear()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.get("user") is None:
            abort(401)
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = g.get("user")
        if user is None:
            abort(401)
        if not user.is_admin:
            abort(403)
        return view(*args, **kwargs)

    return wrapped


def require_owner(owner_id):
    """Abort with 401/403 unless the signed-in user owns the resource."""
    user = g.get("user")
    if user is None:
        abort(401)
    if user.id != owner_id:
        abort(403)
