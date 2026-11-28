"""AuthController - register(), login(), logout() (Design Figure 3; FR-01, FR-02; UC-01, UC-02)."""
from urllib.parse import urlsplit

from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from ..middleware.auth import AuthMiddleware
from ..services.auth_service import AuthService
from ..services.errors import AuthenticationError, ValidationError

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if g.user is not None:
        return redirect(url_for("pages.home"))

    if request.method == "GET":
        return render_template("auth/register.html", values={}, errors={})

    form = request.form
    values = {
        "username": form.get("username", ""),
        "email": form.get("email", ""),
        "display_name": form.get("display_name", ""),
    }
    try:
        AuthService.register_user(
            username=values["username"],
            email=values["email"],
            display_name=values["display_name"],
            password=form.get("password", ""),
            password_confirmation=form.get("password_confirmation", ""),
        )
    except ValidationError as exc:
        # Keep the typed values (never the passwords) so the user only fixes the marked fields.
        return render_template("auth/register.html", values=values, errors=exc.errors), 400

    flash("Account created. Sign in to continue.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if g.user is not None:
        return redirect(url_for("pages.home"))

    next_url = request.values.get("next", "")
    if request.method == "GET":
        return render_template("auth/login.html", identifier="", error=None, next_url=next_url)

    identifier = request.form.get("identifier", "")
    try:
        user = AuthService.authenticate(identifier, request.form.get("password", ""))
    except AuthenticationError as exc:
        return render_template("auth/login.html", identifier=identifier, error=exc.message,
                               next_url=next_url), 401

    AuthMiddleware.create_session(user)  # Figure 4: createSession(user, 60 min inactivity)
    flash(f"Signed in as {user.display_name}.", "success")
    return redirect(_safe_next(next_url) or url_for("pages.home"))


@auth_bp.route("/logout", methods=["POST"])
def logout():
    AuthMiddleware.end_session()
    flash("Signed out.", "success")
    return redirect(url_for("pages.home"))


def _safe_next(target):
    """Allow only same-site relative paths, so ?next= cannot redirect to another site."""
    if not target or not target.startswith("/") or target.startswith("//") or "\\" in target:
        return None
    if any(ord(char) < 32 or char.isspace() for char in target):
        return None  # browsers drop tabs/newlines, which could turn "/\t/evil" into "//evil"
    parts = urlsplit(target)
    if parts.scheme or parts.netloc:
        return None
    return target
