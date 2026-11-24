"""PageController - faq() (Design Figure 3; SRS 2.7 User Documentation).

home() is a temporary landing page: the Home / Search page belongs to
SearchController.search() (FR-09), which replaces it. Keep the endpoint name
"pages.home" until then so redirects keep working.
"""
from flask import Blueprint, render_template

page_bp = Blueprint("pages", __name__)


@page_bp.route("/")
def home():
    return render_template("home.html")


@page_bp.route("/faq")
def faq():
    return render_template("faq.html")
