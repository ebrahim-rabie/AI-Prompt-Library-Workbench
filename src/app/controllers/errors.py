"""Error pages without stack traces (NFR-04)."""
from flask import render_template, request
from flask_wtf.csrf import CSRFError
from werkzeug.exceptions import HTTPException

from ..extensions import db

ERROR_TEXT = {
    400: ("Request not accepted", "Something in the request was not valid. Go back and try again."),
    401: ("Sign in required", "Sign in to use this page."),
    403: ("Not allowed", "Your account does not have permission to do this."),
    404: ("Page not found", "The page you asked for does not exist or was moved."),
    405: ("Action not allowed", "This page does not accept that kind of request."),
    413: ("Request too large", "The data you sent is too large. Shorten it and try again."),
    500: ("Something went wrong", "The server could not finish your request. Nothing was changed. Try again."),
}
GENERIC_TEXT = ("Request not completed", "The server could not complete this request. Try again later.")


def _render_error(code, message=None, headers=None):
    title, default_message = ERROR_TEXT.get(code, GENERIC_TEXT)
    # Offer "sign in and come back" only for pages that can be opened again with GET.
    next_url = request.full_path.rstrip("?") if code == 401 and request.method == "GET" else None
    body = render_template("errors/error.html", code=code, title=title,
                           message=message or default_message, next_url=next_url)
    return body, code, headers or []


def register_error_handlers(app):
    @app.errorhandler(CSRFError)
    def handle_csrf(error):
        return _render_error(400, "The form expired. Reload the page and submit it again.")

    @app.errorhandler(HTTPException)
    def handle_http(error):
        code = error.code or 500
        # Keep headers such as "Allow" (405); the body is replaced by our own page.
        headers = [(name, value) for name, value in error.get_headers() if name.lower() != "content-type"]
        return _render_error(code, headers=headers)

    @app.errorhandler(Exception)
    def handle_unexpected(error):
        db.session.rollback()
        if app.debug or app.testing:
            raise error  # show the real traceback while developing and testing
        app.logger.exception("Unhandled error")
        return _render_error(500)
