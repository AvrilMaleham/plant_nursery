"""
Database connection for the nursery.

PostgreSQL on port 5432 is the server pgAdmin opens. It asks for the
password chosen when PostgreSQL was installed. Pass that password in
DATABASE_URL. The password is not stored in this project.
"""

import os
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from .base import Base

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://postgres@127.0.0.1:5432/plant_nursery",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# Objects stay usable after commit so a script can save a plant and then
# print it without the session loading it again.
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def ensure_database() -> None:
    """
    Create the nursery database if it is not there yet.

    :raises ValueError: If the database name is not a plain identifier
    """
    url = make_url(DATABASE_URL)
    database_name = url.database
    if database_name is None or not database_name.replace("_", "").isalnum():
        raise ValueError("Database name must be a plain identifier")

    admin_engine = create_engine(
        url.set(database="postgres"),
        isolation_level="AUTOCOMMIT",
        pool_pre_ping=True,
    )
    with admin_engine.connect() as connection:
        exists = connection.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"),
            {"name": database_name},
        ).scalar()
        if exists is None:
            connection.execute(text(f'CREATE DATABASE "{database_name}"'))
    admin_engine.dispose()


def init_db() -> None:
    """Create any nursery tables that are not in the database yet."""
    # Importing the model modules registers every subclass with the mapper,
    # including the plant, customer, and payment types.
    import model.customer  # noqa: F401
    import model.order  # noqa: F401
    import model.order_item  # noqa: F401
    import model.payment  # noqa: F401
    import model.plant  # noqa: F401
    import model.user  # noqa: F401

    ensure_database()
    Base.metadata.create_all(engine)


def reset_database() -> None:
    """Drop the nursery tables and create them again."""
    init_db()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


@contextmanager
def session_scope() -> Iterator[Session]:
    """
    Open a session, commit if the block finishes, and close it either way.

    :return (Iterator[Session]): The open session
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
