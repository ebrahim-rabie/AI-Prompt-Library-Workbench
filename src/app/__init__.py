"""AI Prompt Library & Workbench - Flask application factory.

MVC layout (Design 4.1.2):
    models/       Model layer: ORM entities and validation rules
    services/     Model layer: business rules used by the controllers
    controllers/  Controller layer: Flask Blueprints (one per feature)
    middleware/   Controller layer: session, login, role and ownership checks
    templates/    View layer: Jinja2 templates
    static/       View layer: CSS and JavaScript
"""
import os
import secrets

from flask import Flask, redirect, request
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import (BASE_DIR, CONFIGS, INSTANCE_DIR, MIN_PRODUCTION_SECRET_LENGTH,
                     PLACEHOLDER_SECRET_KEYS)
from .extensions import csrf, db, migrate

# Content-Security-Policy: scripts and styles only from this site (plus Google Fonts CSS/fonts).
# Teammates: put JavaScript in static/js/*.js - inline <script> blocks are blocked by this policy.
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "style-src 'self' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "img-src 'self' data:; "
    "form-action 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'"
)


def create_app(config_name=None):
    config_name = config_name or os.environ.get("FLASK_CONFIG", "development")
    if config_name not in CONFIGS:
        raise ValueError(f"Unknown FLASK_CONFIG '{config_name}'. Use one of: {', '.join(CONFIGS)}")

    app = Flask(__name__, instance_path=str(INSTANCE_DIR))
    app.config.from_object(CONFIGS[config_name])

    if config_name == "production":
        _check_production_settings(app)
        # Trust only the proxy's client-IP and protocol headers so HTTPS is detected.
        # The Host header is not taken from the proxy, so it cannot be spoofed through it.
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
    elif not app.config.get("SECRET_KEY"):
        # Development without a SECRET_KEY: use a random key so no shared key can forge sessions.
        # Sessions are lost when the server restarts; set SECRET_KEY in .env to keep them.
        app.config["SECRET_KEY"] = secrets.token_hex(32)

    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db, directory=str(BASE_DIR / "migrations"), render_as_batch=True)
    csrf.init_app(app)

    from . import models  # noqa: F401  (registers every table with SQLAlchemy and Alembic)

    _register_https_redirect(app)
    _register_security_headers(app)

    from .middleware.auth import AuthMiddleware
    AuthMiddleware.init_app(app)

    _register_blueprints(app)

    from .controllers.errors import register_error_handlers
    register_error_handlers(app)

    return app


def _register_blueprints(app):
    from .controllers.auth_controller import auth_bp
    from .controllers.page_controller import page_bp
    from .controllers.profile_controller import profile_bp

    app.register_blueprint(page_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(profile_bp)
    # Teammates register their Blueprints here (prompts, search, workbench, ...).


def _check_production_settings(app):
    key = app.config.get("SECRET_KEY") or ""
    if key.lower() in PLACEHOLDER_SECRET_KEYS or len(key) < MIN_PRODUCTION_SECRET_LENGTH:
        raise RuntimeError(
            f"Set SECRET_KEY to a random value of at least {MIN_PRODUCTION_SECRET_LENGTH} characters "
            "for production (python -c \"import secrets; print(secrets.token_hex(32))\")."
        )


def _register_https_redirect(app):
    """SRS 3.5.4: plain HTTP requests are redirected to HTTPS (production only)."""

    @app.before_request
    def redirect_to_https():
        if app.config.get("FORCE_HTTPS") and not request.is_secure:
            # 308 keeps the method, so a POST stays a POST after the redirect.
            return redirect(request.url.replace("http://", "https://", 1), code=308)
        return None


def _register_security_headers(app):
    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        if app.config.get("FORCE_HTTPS"):
            # Browsers remember to use HTTPS for a year, so the first request is not sent in clear.
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
        return response
