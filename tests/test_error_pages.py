"""
Tests for what a person sees when something goes wrong.

A missing page, a wrong kind of request, and a failure nobody expected each
get a page in the site's own layout, not the plain default from Flask. A
refusal from the model is shown as its reason on the page the person came
from.

The first two tests need no database. The rest sign in through the web pages
and save into PostgreSQL, like the other integration tests.
"""

import logging

import pytest
from flask.testing import FlaskClient

from app import app
from model.customer import StaffCustomer
from model.database import session_scope
from model.nursery_system import NurserySystem
from model.payment import DebitCardPayment
from model.plant import TreeAndShrub
from web import Page, login, page, referred_from


def test_a_missing_page_gets_the_nursery_not_found_page() -> None:
    """An address that does not exist says so, and offers a way back."""
    response = app.test_client().get("/no-such-page")
    shown = Page(response.get_data(as_text=True))

    assert response.status_code == 404
    assert "Page not found" in shown
    assert "Error 404" in shown
    assert "/" in shown.links
    assert "Lincoln University Nursery" in shown
    # Not Flask's own wording.
    assert "requested URL was not found" not in shown


def test_a_button_address_opened_directly_gets_a_clear_page() -> None:
    """Typing the address of a button, such as Log out, is a 405 in Flask."""
    response = app.test_client().get("/logout")
    shown = Page(response.get_data(as_text=True))

    assert response.status_code == 405
    assert "That cannot be done from here" in shown
    assert "Error 405" in shown
    assert "Method Not Allowed" not in shown


def team_logs_in(client: FlaskClient) -> None:
    """
    Create the team login and sign it in through the login form.

    :param client (FlaskClient): The browser session
    """
    with session_scope() as session:
        NurserySystem(session).add_user("teamUsername", "TeamPassword", "team")
    login(client, "teamUsername", "TeamPassword")


def test_an_unexpected_failure_shows_a_safe_page_and_is_logged(
    client: FlaskClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    The person sees an apology with no detail. The detail goes to the log.

    Tests normally let an error escape so it is noticed. Switching testing off
    here makes Flask behave as it does when the site is really running.
    """
    team_logs_in(client)

    def explode(*args: object, **kwargs: object) -> None:
        """Fail the way an unexpected bug would."""
        raise RuntimeError("secret internal detail")

    with monkeypatch.context() as patch:
        patch.setitem(app.config, "TESTING", False)
        patch.setattr(
            NurserySystem, "orders_uncollected_for_seven_days", explode
        )
        with caplog.at_level(logging.ERROR):
            response = client.get("/")

    shown = Page(response.get_data(as_text=True))
    assert response.status_code == 500
    assert "Something went wrong" in shown
    assert "Nothing from that request was saved" in shown
    assert "Error 500" in shown
    assert "secret internal detail" not in shown
    assert "Traceback" not in shown
    assert "/" in shown.links
    # The traceback is still recorded for whoever looks after the site.
    assert "secret internal detail" in caplog.text

    # The failure did not damage the login or the next request.
    assert "Nursery desk" in page(client.get("/"))


def test_a_failure_after_a_change_saves_nothing(
    client: FlaskClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    A request that fails part way does not leave half of itself behind.

    The customer is added to the session, and then the request crashes before
    it finishes. The 500 page says nothing was saved, so it must be true.
    """
    team_logs_in(client)

    def explode(*args: object, **kwargs: object) -> None:
        """Fail after the customer has been added."""
        raise RuntimeError("crash after the change")

    with monkeypatch.context() as patch:
        patch.setitem(app.config, "TESTING", False)
        patch.setattr("controller.customer_routes.redirect", explode)
        response = client.post(
            "/customers/new",
            data={
                "cust_name": "Sam",
                "customer_type": "community",
                "cust_email": "sam@email.com",
                "cust_phone": "",
                "username": "samUsername",
                "password": "SamPassword",
            },
        )
    assert response.status_code == 500

    assert "Sam" not in page(client.get("/customers"))
    # The login that was added with the customer is gone too.
    with client.application.test_client() as fresh:
        refused = fresh.post(
            "/login",
            data={"username": "samUsername", "password": "SamPassword"},
        )
        assert "Username or password is incorrect" in page(refused)


def test_refusals_are_explained_on_the_page(client: FlaskClient) -> None:
    """
    Each rule the model refuses comes back as its own reason on the page.

    A plant or customer that is on an order cannot be removed. A cancelled
    order, a paid order, and an over-large payment each get a different
    explanation, instead of all being "more than what is still owed".
    """
    with session_scope() as session:
        system = NurserySystem(session)
        system.add_user("teamUsername", "TeamPassword", "team")
        system.login("teamUsername", "TeamPassword")
        rose = TreeAndShrub("Rose", 15.99, 25, "rose.png")
        system.add_plant(rose)
        avril = StaffCustomer("Avril", cust_email="avril@email.com")
        system.add_customer(avril)
        cancelled = system.place_order(avril, [(rose, 1)])
        system.cancel_order(cancelled)
        settled = system.place_order(avril, [(rose, 1)])
        system.record_payment(
            DebitCardPayment(
                avril,
                settled,
                settled.remaining_balance,
                "1111222233334444",
                "ANZ",
            )
        )
        open_order = system.place_order(avril, [(rose, 1)])
        rose_path = f"/plants/{rose.plant_id}"
        avril_path = f"/customers/{avril.cust_id}"
        cancelled_path = f"/orders/{cancelled.order_id}"
        settled_path = f"/orders/{settled.order_id}"
        open_path = f"/orders/{open_order.order_id}"
        owed = f"${open_order.remaining_balance:.2f}"
        too_much = f"{open_order.remaining_balance + 0.01:.2f}"

    login(client, "teamUsername", "TeamPassword")

    def refused(path: str, data: dict[str, str], back_to: str) -> Page:
        """Post a form and read the page the refusal sends the person to."""
        return page(client.post(
            path,
            data=data,
            headers=referred_from(back_to),
            follow_redirects=True,
        ))

    def card(amount: str) -> dict[str, str]:
        """The payment form, filled in for a debit card."""
        return {
            "amount": amount,
            "method": "debit card",
            "card_number": "1111222233334444",
            "bank_name": "ANZ",
        }

    assert "Cannot remove a plant that has been ordered" in refused(
        f"{rose_path}/remove", {}, rose_path
    )
    assert "Cannot remove a customer who has placed an order" in refused(
        f"{avril_path}/remove", {}, avril_path
    )

    cancelled_page = refused(
        f"{cancelled_path}/pay", card("5.00"), cancelled_path
    )
    assert "has been cancelled, so nothing can be paid" in cancelled_page
    assert "still owed" not in cancelled_page

    settled_page = refused(f"{settled_path}/pay", card("5.00"), settled_path)
    assert "already been paid in full" in settled_page
    assert "still owed" not in settled_page

    overpaid_page = refused(f"{open_path}/pay", card(too_much), open_path)
    assert (
        "Payment cannot be more than what is still owed on this order "
        f"({owed})" in overpaid_page
    )

    # Nothing above changed what is owed on the open order, and the plant
    # and customer are still there.
    assert page(client.get(open_path)).value("Outstanding") == owed
    assert page(client.get(rose_path)).value("Stock")
    assert page(client.get(avril_path)).value("Owes")
