"""Seed script (Design 4.4.2): creates the first administrator and the initial tags.

Run from the repository root after `flask --app src/wsgi.py db upgrade`:

    python deployment/seed.py

The administrator is read from ADMIN_USERNAME, ADMIN_EMAIL and ADMIN_PASSWORD
(environment or .env). Running the script again changes nothing that already exists.
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

# Load .env BEFORE importing the app: app/config.py reads DATABASE_URL and SECRET_KEY at import time.
# Variables already set in the environment win over the file.
load_dotenv(ROOT / ".env")

from sqlalchemy import func  # noqa: E402

from app.extensions import db  # noqa: E402
from app.models import Tag, User  # noqa: E402
from app.models.enums import Role, TagCategory  # noqa: E402
from app.services.auth_service import AuthService  # noqa: E402
from app.services.errors import ValidationError  # noqa: E402

INITIAL_TAGS = [
    ("Coding", TagCategory.DOMAIN),
    ("Writing", TagCategory.DOMAIN),
    ("Data Science", TagCategory.DOMAIN),
    ("Education", TagCategory.DOMAIN),
    ("Marketing", TagCategory.DOMAIN),
    ("Research", TagCategory.DOMAIN),
    ("Business", TagCategory.DOMAIN),
    ("Summarization", TagCategory.TASK),
    ("Translation", TagCategory.TASK),
    ("Classification", TagCategory.TASK),
    ("Extraction", TagCategory.TASK),
    ("Brainstorming", TagCategory.TASK),
    ("Code Review", TagCategory.TASK),
    ("Question Answering", TagCategory.TASK),
    ("Rewriting", TagCategory.TASK),
]


def seed_tags():
    created = 0
    for name, category in INITIAL_TAGS:
        exists = db.session.query(Tag.id).filter(func.lower(Tag.name) == name.lower()).first()
        if not exists:
            db.session.add(Tag(name=name, category=category))
            created += 1
    db.session.commit()
    return created


def seed_admin(username, email, password):
    """Create the first administrator. Returns a short message describing what happened."""
    if not (username and email and password):
        return "Administrator skipped: set ADMIN_USERNAME, ADMIN_EMAIL and ADMIN_PASSWORD."

    existing = (
        db.session.query(User)
        .filter((func.lower(User.username) == username.lower()) | (func.lower(User.email) == email.lower()))
        .first()
    )
    if existing:
        if existing.is_admin:
            return f"Administrator '{existing.username}' already exists."
        return (f"Administrator skipped: the account '{existing.username}' already exists and is not an "
                "administrator. Choose another ADMIN_USERNAME / ADMIN_EMAIL.")

    try:
        # One transaction: the account is created with the Administrator role directly.
        admin = AuthService.register_user(username, email, "Administrator", password, password,
                                          role=Role.ADMINISTRATOR)
    except ValidationError as exc:
        problems = "; ".join(f"{field}: {message}" for field, message in exc.errors.items())
        return f"Administrator not created: {problems}"
    return f"Administrator '{admin.username}' created. You can now remove ADMIN_PASSWORD from .env."


def run_seed(admin_username, admin_email, admin_password):
    tags_created = seed_tags()
    admin_message = seed_admin(admin_username, admin_email, admin_password)
    return f"{tags_created} tag(s) added. {admin_message}"


def main():
    from app import create_app

    app = create_app()
    with app.app_context():
        print(run_seed(os.environ.get("ADMIN_USERNAME"), os.environ.get("ADMIN_EMAIL"),
                       os.environ.get("ADMIN_PASSWORD")))


if __name__ == "__main__":
    main()
