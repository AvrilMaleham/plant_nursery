"""
Tests for the small security measures.

The secret key, the session cookie settings, the upload size limit, the check
that an uploaded photo really is an image, and the minimum password length.
Full CSRF tokens are not used, so these tests do not cover them. The cookie's
SameSite setting is the protection instead.

The first tests need no database. The rest sign in through the web pages and
save into PostgreSQL, like the other integration tests.
"""

from io import BytesIO
from pathlib import Path

import pytest
from flask.testing import FlaskClient

from app import MAX_UPLOAD_MB, create_app
from controller.plant_routes import image_kind
from model.database import session_scope
from model.nursery_system import NurserySystem
from web import PHOTO, Page, login, page

JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01"
GIF = b"GIF89a\x01\x00\x01\x00\x00\x00\x00;"
WEBP = b"RIFF\x1a\x00\x00\x00WEBPVP8 "
NOT_AN_IMAGE = b"<html><script>alert('hello')</script></html>"


def test_secret_key_is_random_unless_one_is_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Without FLASK_SECRET_KEY each start gets its own long random key, never a
    value written in the code. With it, that value is used.
    """
    monkeypatch.delenv("FLASK_SECRET_KEY", raising=False)
    first = create_app().secret_key
    second = create_app().secret_key
    assert first != second
    assert len(first) >= 32
    assert "lincoln-nursery-local" not in (first, second)

    monkeypatch.setenv("FLASK_SECRET_KEY", "chosen-by-the-team")
    assert create_app().secret_key == "chosen-by-the-team"

    # An empty variable counts as not set, not as an empty key.
    monkeypatch.setenv("FLASK_SECRET_KEY", "")
    assert len(create_app().secret_key) >= 32


def test_session_cookie_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    The cookie is SameSite Lax and HttpOnly, and Secure only when asked for
    with FLASK_COOKIE_SECURE=1.
    """
    monkeypatch.delenv("FLASK_COOKIE_SECURE", raising=False)
    config = create_app().config
    assert config["SESSION_COOKIE_SAMESITE"] == "Lax"
    assert config["SESSION_COOKIE_HTTPONLY"] is True
    assert config["SESSION_COOKIE_SECURE"] is False

    monkeypatch.setenv("FLASK_COOKIE_SECURE", "1")
    assert create_app().config["SESSION_COOKIE_SECURE"] is True


def test_the_cookie_sent_at_login_carries_the_flags(
    client: FlaskClient,
) -> None:
    """The browser is told Lax and HttpOnly when the session cookie is set."""
    team_exists()
    response = client.post(
        "/login",
        data={"username": "teamUsername", "password": "TeamPassword"},
    )
    cookie = response.headers["Set-Cookie"]
    assert "SameSite=Lax" in cookie
    assert "HttpOnly" in cookie


def team_exists() -> None:
    """Create the team login."""
    with session_scope() as session:
        NurserySystem(session).add_user("teamUsername", "TeamPassword", "team")


def plant_form(photo: tuple[BytesIO, str]) -> dict[str, object]:
    """
    Build a valid add-plant form around a photo.

    :param photo (tuple[BytesIO, str]): The file and the name it is sent as
    :return (dict[str, object]): The form fields
    """
    return {
        "plant_name": "Camellia",
        "plant_type": "trees and shrubs",
        "price": "5.00",
        "stock": "5",
        "photo": photo,
    }


def test_image_kind_reads_the_first_bytes() -> None:
    """Each allowed type is recognised, and anything else is not."""
    assert image_kind(PHOTO[:12]) == "png"
    assert image_kind(JPEG[:12]) == "jpeg"
    assert image_kind(GIF[:12]) == "gif"
    assert image_kind(WEBP[:12]) == "webp"
    assert image_kind(NOT_AN_IMAGE[:12]) is None
    assert image_kind(b"") is None
    # A RIFF file that is not WEBP, such as a WAV sound, is refused.
    assert image_kind(b"RIFF\x1a\x00\x00\x00WAVEfmt ") is None


def test_each_allowed_photo_type_is_accepted(
    client: FlaskClient, photo_dir: Path
) -> None:
    """A real PNG, JPG, GIF, and WEBP are saved whole under a new name."""
    team_exists()
    login(client, "teamUsername", "TeamPassword")
    uploads = (
        (PHOTO, "a.png"),
        (JPEG, "b.jpg"),
        (JPEG, "c.jpeg"),
        (GIF, "d.gif"),
        (WEBP, "e.webp"),
    )
    for content, name in uploads:
        client.post(
            "/plants/new", data=plant_form((BytesIO(content), name))
        )
    saved = sorted(photo_dir.iterdir())
    assert len(saved) == len(uploads)
    # The whole file was saved, not just what was read to check it.
    assert sorted(path.read_bytes() for path in saved) == sorted(
        content for content, _ in uploads
    )


def test_a_file_that_is_not_an_image_is_refused(
    client: FlaskClient, photo_dir: Path
) -> None:
    """
    A page or script renamed to .png is refused with a reason, and so is a
    real image sent under the extension of a different type. Nothing is
    saved, and no plant is added.
    """
    team_exists()
    login(client, "teamUsername", "TeamPassword")

    fake = client.post(
        "/plants/new",
        data=plant_form((BytesIO(NOT_AN_IMAGE), "innocent.png")),
    )
    assert "That file is not a real PNG, JPG, GIF, or WEBP image" in page(fake)

    wrong_type = client.post(
        "/plants/new", data=plant_form((BytesIO(PHOTO), "photo.gif"))
    )
    assert "That file is not a real PNG, JPG, GIF, or WEBP image" in page(
        wrong_type
    )

    empty = client.post(
        "/plants/new", data=plant_form((BytesIO(b""), "empty.png"))
    )
    assert "That file is not a real PNG, JPG, GIF, or WEBP image" in page(
        empty
    )

    assert list(photo_dir.iterdir()) == []
    with session_scope() as session:
        system = NurserySystem(session)
        system.login("teamUsername", "TeamPassword")
        assert system.catalog.count() == 0


def test_an_oversize_upload_gets_the_too_big_page(
    client: FlaskClient, photo_dir: Path
) -> None:
    """
    A file over the limit is stopped with a 413 in the site's own layout,
    and nothing is saved.
    """
    team_exists()
    login(client, "teamUsername", "TeamPassword")
    big = PHOTO + b"\x00" * (MAX_UPLOAD_MB * 1024 * 1024)

    response = client.post(
        "/plants/new", data=plant_form((BytesIO(big), "big.png"))
    )
    shown = Page(response.get_data(as_text=True))

    assert response.status_code == 413
    assert "That file is too big" in shown
    assert f"{MAX_UPLOAD_MB} MB" in shown
    assert "Error 413" in shown
    assert "Request Entity Too Large" not in shown
    assert list(photo_dir.iterdir()) == []

    # A photo under the limit still works.
    small = client.post(
        "/plants/new", data=plant_form((BytesIO(PHOTO), "small.png"))
    )
    assert small.status_code in (200, 302)
    assert len(list(photo_dir.iterdir())) == 1


def test_a_short_password_is_refused_on_the_customer_form(
    client: FlaskClient,
) -> None:
    """
    The team cannot give a customer a password under 8 characters. The reason
    is shown, and the customer is not added.
    """
    team_exists()
    login(client, "teamUsername", "TeamPassword")

    def add(password: str) -> Page:
        return page(
            client.post(
                "/customers/new",
                data={
                    "cust_name": "Sam",
                    "customer_type": "community",
                    "cust_email": "sam@email.com",
                    "cust_phone": "",
                    "username": "samUsername",
                    "password": password,
                },
                follow_redirects=True,
            )
        )

    assert "Password must be at least 8 characters" in add("1234567")
    with session_scope() as session:
        system = NurserySystem(session)
        system.login("teamUsername", "TeamPassword")
        assert system.directory.count() == 0

    add("12345678")
    with session_scope() as session:
        system = NurserySystem(session)
        system.login("teamUsername", "TeamPassword")
        assert system.directory.count() == 1
