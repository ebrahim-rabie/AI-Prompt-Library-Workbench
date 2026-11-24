"""AuthMiddleware (Design 4.1.2 and Figure 3) - session, login, role and ownership checks.

Figure 3 methods: requireLogin(), requireAdmin(), checkOwnership(), notOwner(),
createSession(), enforceSessionTimeout().

Usage in a controller:

    from ..middleware.auth import AuthMiddleware

    @bp.route("/prompts/<int:prompt_id>/edit")
    @AuthMiddleware.require_login
    def edit_draft(prompt_id):
        prompt = ...
        AuthMiddleware.check_ownership(prompt.owner_id)   # 403 when not the owner

    # Rate / review / report / fork: nobody may do these on their own prompt.
    if not AuthMiddleware.not_owner(prompt.owner_id):
        abort(403)

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


class AuthMiddleware:
    @staticmethod
    def init_app(app):
        app.before_request(AuthMiddleware.enforce_session_timeout)

        @app.context_processor
        def inject_current_user():
            return {"current_user": g.get("user")}

    # --- sessions (FR-02, Figure 4) ------------------------------------------
    @staticmethod
    def create_session(user):
        """Start a session after a successful sign in (60 minutes of inactivity allowed)."""
        session.clear()  # drop anything from before sign in (no session fixation)
        session[SESSION_USER_KEY] = user.id
        session[SESSION_LAST_SEEN_KEY] = time.time()
        session[SESSION_PASSWORD_KEY] = _password_fingerprint(user)
        session.permanent = True

    @staticmethod
    def end_session():
        session.clear()

    @staticmethod
    def refresh_password_fingerprint(user):
        """Keep the current session valid after the user changes their own password."""
        session[SESSION_PASSWORD_KEY] = _password_fingerprint(user)

    @staticmethod
    def enforce_session_timeout():
        """Run before every request: set g.user, or end the session (Figure 4, A5).

        The session ends after 60 minutes without activity, when the account was
        suspended, or when the password was changed in another session.
        """
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
            AuthMiddleware.end_session()
            flash(f"Your session ended after {int(timeout // 60)} minutes without activity. Sign in again.",
                  "info")
            return

        user = db.session.get(User, user_id)
        if user is None or user.is_suspended:
            # Account removed or suspended by an administrator while signed in.
            AuthMiddleware.end_session()
            return
        if not hmac.compare_digest(session.get(SESSION_PASSWORD_KEY, ""), _password_fingerprint(user)):
            AuthMiddleware.end_session()
            flash("Your password was changed. Sign in again.", "info")
            return

        g.user = user
        session[SESSION_LAST_SEEN_KEY] = now

    # --- access checks (NFR-02b) ---------------------------------------------
    @staticmethod
    def require_login(view):
        """Decorator: 401 when nobody is signed in."""
        @wraps(view)
        def wrapped(*args, **kwargs):
            if g.get("user") is None:
                abort(401)
            return view(*args, **kwargs)

        return wrapped

    @staticmethod
    def require_admin(view):
        """Decorator: 401 when signed out, 403 when the user is not an Administrator."""
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = g.get("user")
            if user is None:
                abort(401)
            if not user.is_admin:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    @staticmethod
    def check_ownership(owner_id):
        """Abort with 401/403 unless the signed-in user owns the resource."""
        user = g.get("user")
        if user is None:
            abort(401)
        if user.id != owner_id:
            abort(403)

    @staticmethod
    def not_owner(owner_id):
        """True when a user is signed in and does NOT own the resource.

        Used for actions nobody may do on their own prompt: rate, review, report, fork.
        """
        user = g.get("user")
        return user is not None and user.id != owner_id
