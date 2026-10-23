"""
Shared setup for the integration tests.

The tests sign in through the web pages and save into PostgreSQL. They use
their own database, plant_nursery_test, on the same server as DATABASE_URL.
The sample data in plant_nursery is not changed.
"""

import os

from sqlalchemy.engine import make_url

# Point the engine at the test database before the application is imported.
# model.database reads DATABASE_URL once, when it is first imported.
_source = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://postgres@127.0.0.1:5432/plant_nursery",
)
os.environ["DATABASE_URL"] = make_url(_source).set(
    database="plant_nursery_test"
).render_as_string(hide_password=False)

import pytest

from app import app
from model.database import reset_database


@pytest.fixture
def client():
    """
    Give a test an empty nursery and a browser session.

    :return: A Flask test client for one workflow
    """
    reset_database()
    app.config.update(TESTING=True)
    with app.test_client() as test_client:
        yield test_client
