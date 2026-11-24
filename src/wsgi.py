"""Entry point for the Flask CLI and WSGI servers.

Run from the repository root:
    flask --app src/wsgi.py run
"""
from app import create_app

app = create_app()
