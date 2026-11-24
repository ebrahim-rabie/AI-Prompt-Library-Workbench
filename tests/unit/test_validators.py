"""Account validation rules (FR-01, FR-03)."""
import pytest

from app.models import validators as v


@pytest.mark.parametrize("username", ["abc", "user_01", "A" * 30, "___"])
def test_valid_usernames(username):
    assert v.validate_username(username) is None


@pytest.mark.parametrize("username", ["", "ab", "A" * 31, "has space", "dash-name", "émile", "a.b"])
def test_invalid_usernames(username):
    assert v.validate_username(username) is not None


@pytest.mark.parametrize("email", ["a@b.co", "first.last@uni.edu.eg"])
def test_valid_emails(email):
    assert v.validate_email(email) is None


@pytest.mark.parametrize("email", ["", "no-at-sign", "a@b", "a b@c.com", "x@" + "a" * 250 + ".com"])
def test_invalid_emails(email):
    assert v.validate_email(email) is not None


@pytest.mark.parametrize("password", ["abcdefg1", "Passw0rd!", "1234567a"])
def test_valid_passwords(password):
    assert v.validate_password(password) is None


@pytest.mark.parametrize("password", ["", "short1a", "allletters", "12345678", "a1" * 65])
def test_invalid_passwords(password):
    assert v.validate_password(password) is not None


def test_password_confirmation():
    assert v.validate_password_confirmation("abc", "abc") is None
    assert v.validate_password_confirmation("abc", "abd") is not None


def test_display_name_rules():
    assert v.validate_display_name("Mo") is None
    assert v.validate_display_name("") is not None
    assert v.validate_display_name("x" * 101) is not None


def test_bio_rules():
    assert v.validate_bio("") is None
    assert v.validate_bio("x" * 300) is None
    assert v.validate_bio("x" * 301) is not None


def test_password_digit_must_be_ascii():
    assert v.validate_password("abcdefg\u0663") is not None  # Arabic-Indic digit three


def test_empty_database_url_falls_back_to_default(monkeypatch):
    from app.config import _database_url

    monkeypatch.setenv("DATABASE_URL", "")
    assert _database_url("sqlite:///x.db") == "sqlite:///x.db"
    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@h/db")
    assert _database_url("sqlite:///x.db") == "postgresql://u:p@h/db"
