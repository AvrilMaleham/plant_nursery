"""
Unit tests for the check that the tables match the code.

A database made by an older version must be refused with a plain reason,
instead of failing later inside a payment with an unclear SQL error. These
tests use the throwaway in-memory database, so they need no PostgreSQL server.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

import model.database


def test_tables_that_match_the_code_pass(
    memory_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nothing is raised when every column is there."""
    monkeypatch.setattr(model.database, "engine", memory_session.get_bind())
    model.database.check_tables_match()


def test_tables_from_an_older_version_are_refused_with_the_fix(
    memory_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A payments table that still has card_number and no card_last4 is the
    shape the old version made. The message says what to run."""
    memory_session.execute(
        text("ALTER TABLE payments RENAME COLUMN card_last4 TO card_number")
    )
    monkeypatch.setattr(model.database, "engine", memory_session.get_bind())

    with pytest.raises(RuntimeError) as refused:
        model.database.check_tables_match()
    message = str(refused.value)
    assert "'payments' table" in message
    assert "card_last4" in message
    assert "python seed.py" in message


def test_a_database_with_no_tables_yet_passes(
    memory_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A table that is not there is for create_all() to make, not an error."""
    from model.base import Base

    Base.metadata.drop_all(memory_session.get_bind())
    monkeypatch.setattr(model.database, "engine", memory_session.get_bind())
    model.database.check_tables_match()
