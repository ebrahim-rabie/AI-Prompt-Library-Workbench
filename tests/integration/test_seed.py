"""Seed script (deployment/seed.py) and migrations."""
import importlib.util
from pathlib import Path

import pytest
from flask_migrate import downgrade, upgrade
from sqlalchemy import inspect, text

from app import create_app
from app.extensions import db as _db
from app.models import Collection, Tag, User

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def seed_module():
    spec = importlib.util.spec_from_file_location("seed", ROOT / "deployment" / "seed.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_seed_creates_admin_and_tags(db, seed_module):
    message = seed_module.run_seed("admin", "admin@example.com", "AdminPass1")
    assert "created" in message
    admin = db.session.query(User).filter_by(username="admin").one()
    assert admin.is_admin
    assert db.session.query(Collection).filter_by(user_id=admin.id, is_default=True).count() == 1
    assert db.session.query(Tag).count() == len(seed_module.INITIAL_TAGS)


def test_seed_is_safe_to_run_twice(db, seed_module):
    seed_module.run_seed("admin", "admin@example.com", "AdminPass1")
    message = seed_module.run_seed("admin", "admin@example.com", "AdminPass1")
    assert message.startswith("0 tag(s) added.")
    assert "already exists" in message
    assert db.session.query(User).count() == 1


def test_seed_without_admin_settings_still_adds_tags(db, seed_module):
    message = seed_module.run_seed(None, None, None)
    assert "Administrator skipped" in message
    assert db.session.query(Tag).count() == len(seed_module.INITIAL_TAGS)


def test_seed_does_not_promote_an_existing_regular_account(db, make_user, seed_module):
    make_user("admin", "someone@example.com")
    message = seed_module.run_seed("admin", "admin@example.com", "AdminPass1")
    assert "is not an administrator" in message
    assert not db.session.query(User).filter_by(username="admin").one().is_admin


def test_seed_rejects_weak_admin_password(db, seed_module):
    message = seed_module.run_seed("admin", "admin@example.com", "weak")
    assert "not created" in message
    assert db.session.query(User).count() == 0


def test_migration_upgrade_and_downgrade(tmp_path, monkeypatch):
    from app.config import TestingConfig

    monkeypatch.setattr(TestingConfig, "SQLALCHEMY_DATABASE_URI", f"sqlite:///{(tmp_path / 'm.db').as_posix()}")
    app = create_app("testing")
    with app.app_context():
        upgrade()
        tables = set(inspect(_db.engine).get_table_names())
        assert set(_db.metadata.tables) <= tables
        with _db.engine.connect() as conn:
            indexes = {row[0] for row in conn.execute(text("select name from sqlite_master where type='index'"))}
        assert {"uq_users_username_lower", "uq_users_email_lower", "uq_tags_name_lower"} <= indexes
        downgrade(revision="base")
        assert inspect(_db.engine).get_table_names() == ["alembic_version"]
        _db.engine.dispose()


def test_migrated_database_enforces_the_data_dictionary_rules(tmp_path, monkeypatch):
    """The migration must create the same constraints as the models, not just the tables."""
    from sqlalchemy.exc import IntegrityError

    from app.config import TestingConfig

    monkeypatch.setattr(TestingConfig, "SQLALCHEMY_DATABASE_URI", f"sqlite:///{(tmp_path / 'r.db').as_posix()}")
    app = create_app("testing")
    with app.app_context():
        upgrade()
        user_sql = ("insert into users(username, email, password_hash, display_name, registered_at) "
                    "values (:u, :e, 'h', 'Name', '2026-01-01')")
        violations = [
            (user_sql, {"u": "ALICE", "e": "other@example.com"}),          # username, any case
            (user_sql, {"u": "bob", "e": "Alice@Example.com"}),            # email, any case
            ("update users set role = 'Boss'", {}),                         # role CHECK
            ("insert into prompts(owner_id, title, created_at) values (999, 't', '2026-01-01')", {}),  # FK
            ("insert into reports(reporter_id, reason, status, created_at) "
             "values (1, 'Spam', 'Pending', '2026-01-01')", {}),             # exactly one target
            ("insert into collections(user_id, name, is_default, created_at) "
             "values (1, 'Second favorites', 1, '2026-01-01')", {}),         # one Favorites per user
        ]
        with _db.engine.connect() as conn:
            conn.execute(text("PRAGMA foreign_keys=ON"))
            conn.execute(text(user_sql), {"u": "alice", "e": "alice@example.com"})
            conn.execute(text("insert into collections(user_id, name, is_default, created_at) "
                              "values (1, 'Favorites', 1, '2026-01-01')"))
            conn.commit()
            for sql, params in violations:
                with pytest.raises(IntegrityError):
                    conn.execute(text(sql), params)
                conn.rollback()
        downgrade(revision="base")
        _db.engine.dispose()
