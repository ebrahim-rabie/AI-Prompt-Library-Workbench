"""ProfileController - view and edit the profile, change the password (FR-03; UC-03)."""
from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from ..middleware.auth import login_required, refresh_password_fingerprint
from ..services.auth_service import AuthService
from ..services.errors import ValidationError

profile_bp = Blueprint("profile", __name__, url_prefix="/profile")


def _render(profile_values=None, profile_errors=None, password_errors=None, status=200):
    user = g.user
    values = profile_values or {"display_name": user.display_name, "bio": user.bio or ""}
    return render_template(
        "profile.html",
        values=values,
        profile_errors=profile_errors or {},
        password_errors=password_errors or {},
    ), status


@profile_bp.route("", methods=["GET"])
@login_required
def show():
    return _render()


@profile_bp.route("", methods=["POST"])
@login_required
def update():
    values = {
        "display_name": request.form.get("display_name", ""),
        "bio": request.form.get("bio", ""),
    }
    try:
        AuthService.update_profile(g.user, values["display_name"], values["bio"])
    except ValidationError as exc:
        return _render(profile_values=values, profile_errors=exc.errors, status=400)

    flash("Profile saved.", "success")
    return redirect(url_for("profile.show"))


@profile_bp.route("/password", methods=["POST"])
@login_required
def change_password():
    try:
        AuthService.change_password(
            g.user,
            request.form.get("current_password", ""),
            request.form.get("new_password", ""),
            request.form.get("new_password_confirmation", ""),
        )
    except ValidationError as exc:
        return _render(password_errors=exc.errors, status=400)

    # This session stays signed in; sessions on other devices end on their next request.
    refresh_password_fingerprint(g.user)
    flash("Password changed. Other devices have been signed out.", "success")
    return redirect(url_for("profile.show"))
