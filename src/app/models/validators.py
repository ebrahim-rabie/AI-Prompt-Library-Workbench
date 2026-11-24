"""Validation rules of the Model layer (Design 4.1.2: models/validators.py).

Account rules (FR-01, FR-03) are implemented here. Teammates add the
placeholder-parsing, publish and tag-name rules to this module.

Each validator returns an error message (str) or None when the value is valid.
"""
import re

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,30}$")
# Pragmatic email check: something@something.tld, no spaces. Emails are not verified (SRS 2.8).
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

USERNAME_MAX = 30
EMAIL_MAX = 255
DISPLAY_NAME_MAX = 100
BIO_MAX = 300
PASSWORD_MIN = 8
PASSWORD_MAX = 128  # upper bound so a huge input cannot slow down hashing


def validate_username(username):
    if not username:
        return "Enter a username."
    if not USERNAME_RE.fullmatch(username):
        return "Use 3 to 30 letters, digits or underscores."
    return None


def validate_email(email):
    if not email:
        return "Enter an email address."
    if len(email) > EMAIL_MAX or not EMAIL_RE.fullmatch(email):
        return "Enter a valid email address, like name@example.com."
    return None


def validate_display_name(display_name):
    if not display_name:
        return "Enter a display name."
    if len(display_name) > DISPLAY_NAME_MAX:
        return f"Use at most {DISPLAY_NAME_MAX} characters."
    return None


def validate_bio(bio):
    if bio and len(bio) > BIO_MAX:
        return f"Keep the bio to {BIO_MAX} characters or fewer."
    return None


def validate_password(password):
    if not password or len(password) < PASSWORD_MIN:
        return f"Use at least {PASSWORD_MIN} characters."
    if len(password) > PASSWORD_MAX:
        return f"Use at most {PASSWORD_MAX} characters."
    if not re.search(r"[A-Za-z]", password) or not re.search(r"[0-9]", password):
        return "Include at least one letter and one digit."
    return None


def validate_password_confirmation(password, confirmation):
    if password != confirmation:
        return "The passwords do not match."
    return None
