"""Database constraints from the data dictionary (Design 4.4.3)."""
import pytest
from sqlalchemy.exc import IntegrityError

from app.models import (Collection, ModerationAction, Prompt, PromptVariable, PromptVersion, Rating, Report,
                        Review, Tag, User)
from app.models.enums import PromptStatus


def _user(db, username="alice", email="alice@example.com"):
    user = User(username=username, email=email, display_name=username.title())
    user.set_password("Passw0rd!")
    db.session.add(user)
    db.session.commit()
    return user


def _prompt(db, owner, title="Summarize an article"):
    prompt = Prompt(owner=owner, title=title)
    prompt.versions.append(PromptVersion(version_number=1, template_body="Summarize {{topic}}"))
    db.session.add(prompt)
    db.session.commit()
    return prompt


def _expect_integrity_error(db, obj):
    db.session.add(obj)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_all_tables_exist(db):
    names = set(db.metadata.tables)
    assert names == {
        "users", "prompts", "prompt_versions", "prompt_variables", "tags", "prompt_tags",
        "collections", "collection_prompts", "ratings", "reviews", "reports", "moderation_actions",
    }


def test_user_defaults_and_password_is_hashed(db):
    user = _user(db)
    assert user.role == "Registered"
    assert user.status == "Active"
    assert user.failed_login_attempts == 0
    assert user.registered_at is not None
    assert "Passw0rd!" not in user.password_hash
    assert user.check_password("Passw0rd!")
    assert not user.check_password("wrong")


def test_username_unique_ignoring_case(db):
    _user(db, "Alice", "a1@example.com")
    _expect_integrity_error(db, User(username="alice", email="a2@example.com", display_name="x",
                                     password_hash="h"))


def test_email_unique_ignoring_case(db):
    _user(db, "alice", "Alice@Example.com")
    _expect_integrity_error(db, User(username="bob", email="alice@example.com", display_name="x",
                                     password_hash="h"))


def test_user_role_and_status_are_checked(db):
    _expect_integrity_error(db, User(username="x1", email="x1@e.com", display_name="x", password_hash="h",
                                     role="Superuser"))
    _expect_integrity_error(db, User(username="x2", email="x2@e.com", display_name="x", password_hash="h",
                                     status="Banned"))


def test_prompt_defaults_and_status_check(db):
    prompt = _prompt(db, _user(db))
    assert prompt.status == PromptStatus.DRAFT
    assert prompt.fork_count == 0
    assert prompt.average_rating == 0
    assert prompt.latest_version.version_number == 1
    _expect_integrity_error(db, Prompt(owner_id=prompt.owner_id, title="t", status="Deleted"))
    _expect_integrity_error(db, Prompt(owner_id=prompt.owner_id, title="t", target_model="Llama"))


def test_version_number_unique_per_prompt(db):
    prompt = _prompt(db, _user(db))
    _expect_integrity_error(db, PromptVersion(prompt_id=prompt.id, version_number=1, template_body=""))


def test_variable_name_unique_per_version_and_type_checked(db):
    version = _prompt(db, _user(db)).latest_version
    db.session.add(PromptVariable(version=version, name="topic", label="Topic", data_type="Text"))
    db.session.commit()
    _expect_integrity_error(db, PromptVariable(version_id=version.id, name="topic", label="Again",
                                               data_type="Text"))
    _expect_integrity_error(db, PromptVariable(version_id=version.id, name="n", label="N", data_type="Date"))


def test_fork_links_to_original(db):
    owner = _user(db)
    original = _prompt(db, owner)
    fork = Prompt(owner=_user(db, "bob", "bob@example.com"), title="My copy", original=original)
    db.session.add(fork)
    db.session.commit()
    assert fork.original_prompt_id == original.id
    assert original.forks.count() == 1


def test_tag_name_unique_ignoring_case_and_category_checked(db):
    db.session.add(Tag(name="Coding", category="Domain"))
    db.session.commit()
    _expect_integrity_error(db, Tag(name="coding", category="Task"))
    _expect_integrity_error(db, Tag(name="Other", category="Mood"))


def test_prompt_tags_and_collections_link_tables(db):
    owner = _user(db)
    prompt = _prompt(db, owner)
    tag = Tag(name="Summarization", category="Task")
    prompt.tags.append(tag)
    collection = Collection(user=owner, name="Study", is_default=False)
    collection.prompts.append(prompt)
    db.session.add(collection)
    db.session.commit()
    assert tag.prompts == [prompt]
    assert collection.prompts.all() == [prompt]


def test_rating_value_range_and_one_per_user(db):
    owner = _user(db)
    rater = _user(db, "bob", "bob@example.com")
    prompt = _prompt(db, owner)
    db.session.add(Rating(user=rater, prompt=prompt, value=4))
    db.session.commit()
    _expect_integrity_error(db, Rating(user_id=rater.id, prompt_id=prompt.id, value=5))
    _expect_integrity_error(db, Rating(user_id=owner.id, prompt_id=prompt.id, value=6))


def test_review_one_per_user_and_status_checked(db):
    owner = _user(db)
    reviewer = _user(db, "bob", "bob@example.com")
    prompt = _prompt(db, owner)
    db.session.add(Review(user=reviewer, prompt=prompt, comment="Very useful prompt."))
    db.session.commit()
    _expect_integrity_error(db, Review(user_id=reviewer.id, prompt_id=prompt.id, comment="Second review"))
    _expect_integrity_error(db, Review(user_id=owner.id, prompt_id=prompt.id, comment="Some text here",
                                       status="Deleted"))


def test_report_needs_exactly_one_target(db):
    owner = _user(db)
    reporter = _user(db, "bob", "bob@example.com")
    prompt = _prompt(db, owner)
    review = Review(user=reporter, prompt=prompt, comment="Very useful prompt.")
    db.session.add(review)
    db.session.commit()

    _expect_integrity_error(db, Report(reporter_id=reporter.id, reason="Spam"))
    _expect_integrity_error(db, Report(reporter_id=reporter.id, reason="Spam",
                                       target_prompt_id=prompt.id, target_review_id=review.id))
    db.session.add(Report(reporter_id=reporter.id, reason="Spam", target_prompt_id=prompt.id))
    db.session.commit()


def test_report_once_per_item_and_reason_checked(db):
    owner = _user(db)
    reporter = _user(db, "bob", "bob@example.com")
    prompt = _prompt(db, owner)
    db.session.add(Report(reporter_id=reporter.id, reason="Spam", target_prompt_id=prompt.id))
    db.session.commit()
    _expect_integrity_error(db, Report(reporter_id=reporter.id, reason="Other", target_prompt_id=prompt.id))
    _expect_integrity_error(db, Report(reporter_id=owner.id, reason="Boring", target_prompt_id=prompt.id))


def test_moderation_action_resolves_reports(db):
    admin = _user(db, "admin", "admin@example.com")
    reporter = _user(db, "bob", "bob@example.com")
    prompt = _prompt(db, _user(db, "carol", "carol@example.com"))
    action = ModerationAction(admin=admin, action_type="Hide", note="Spam content")
    report = Report(reporter_id=reporter.id, reason="Spam", target_prompt_id=prompt.id,
                    moderation_action=action, status="Resolved")
    db.session.add(report)
    db.session.commit()
    assert action.reports == [report]
    _expect_integrity_error(db, ModerationAction(admin_id=admin.id, action_type="Ban"))


def test_foreign_keys_are_enforced(db):
    _expect_integrity_error(db, Prompt(owner_id=999, title="Orphan prompt"))


def test_only_one_favorites_collection_per_user(db):
    user = _user(db)
    db.session.add(Collection(user=user, name="Favorites", is_default=True))
    db.session.add(Collection(user=user, name="Study", is_default=False))
    db.session.add(Collection(user=user, name="Coding", is_default=False))
    db.session.commit()
    _expect_integrity_error(db, Collection(user_id=user.id, name="Favorites 2", is_default=True))
