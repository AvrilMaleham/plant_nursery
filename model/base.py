"""Shared SQLAlchemy base for the nursery tables."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for every table in the nursery database."""
