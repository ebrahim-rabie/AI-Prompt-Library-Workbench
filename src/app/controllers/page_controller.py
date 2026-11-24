"""PageController - simple pages.

The home page is a placeholder until the search page (FR-09, SearchController)
replaces it; keep the endpoint name "pages.home" so redirects keep working.
"""
from flask import Blueprint, render_template

page_bp = Blueprint("pages", __name__)


@page_bp.route("/")
def home():
    return render_template("home.html")
