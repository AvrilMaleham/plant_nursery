"""
Shared setup for the tests.

There are two kinds of fixture here.

- memory_session gives the rule tests a throwaway in-memory database, so they
  need no PostgreSQL server and leave nothing behind.
- client and fresh_database are for the integration tests. They sign in
  through the web pages and save into PostgreSQL, in their own database,
  plant_nursery_test, on the same server as DATABASE_URL. The sample data in
  plant_nursery is not changed.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from flask.testing import FlaskClient
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

# Point the engine at the test database before the application is imported.
# model.database reads DATABASE_URL once, when it is first imported.
_source = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://postgres@127.0.0.1:5432/plant_nursery",
)
os.environ["DATABASE_URL"] = make_url(_source).set(
    database="plant_nursery_test"
).render_as_string(hide_password=False)


@pytest.fixture
def memory_session() -> Iterator[Session]:
    """
    Give a test its own empty nursery in memory.

    The same mapped classes are used as with PostgreSQL, so the rules run on
    real tables, but nothing outside the test is read or written.

    :return (Iterator[Session]): An open session on an in-memory database
    """
    # Importing the modules registers every table, including the plant,
    # customer, and payment subclasses.
    import model.customer  # noqa: F401
    import model.order  # noqa: F401
    import model.order_item  # noqa: F401
    import model.payment  # noqa: F401
    import model.plant  # noqa: F401
    import model.user  # noqa: F401
    from model.base import Base

    # StaticPool keeps one connection, so the in-memory database is not lost
    # between statements.
    engine = create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture
def fresh_database() -> None:
    """
    Give a test an empty set of nursery tables in the test database.
    """
    from model.database import reset_database

    reset_database()


@pytest.fixture
def photo_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """
    Send uploaded plant photos to a temporary folder for this test.

    The sample photos stay where they are, in view/static/images. Photos that
    a test uploads go here instead, and are deleted with the folder.

    :return (Path): The folder uploaded photos are saved in
    """
    import controller.plant_routes

    uploads = tmp_path / "uploaded-photos"
    uploads.mkdir()
    monkeypatch.setattr(controller.plant_routes, "IMAGE_DIR", uploads)
    return uploads


@pytest.fixture
def client(photo_dir: Path) -> Iterator[FlaskClient]:
    """
    Give a test an empty nursery and a browser session.

    :param photo_dir (Path): Where this test's uploaded photos go
    :return (Iterator[FlaskClient]): A Flask test client for one workflow
    """
    # Imported after the address above is set. A module-level import would
    # run first and miss the test database.
    from app import app
    from model.database import reset_database

    reset_database()
    app.config.update(TESTING=True)
    with app.test_client() as test_client:
        yield test_client
