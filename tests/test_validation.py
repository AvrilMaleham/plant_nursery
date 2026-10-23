"""
Integration tests for what the forms refuse, and the reason they give.

Brent wants a mistake caught where it is entered, and the person told why,
not quietly ignored. These tests submit the forms directly, as a browser
would after getting past the page's own checks.
"""

from io import BytesIO
from pathlib import Path

from flask.testing import FlaskClient
from sqlalchemy import text

from model.customer import CommunityCustomer
from model.database import session_scope
from model.nursery_system import NurserySystem
from model.plant import Perennial, TreeAndShrub
from web import PHOTO, Page, login, page, referred_from


def test_blank_names_and_bad_quantities_are_refused(
    client: FlaskClient, photo_dir: Path
) -> None:
    """
    The team cannot add a plant or a customer with a blank name, and an order
    form with a zero, negative, or non-whole quantity is refused with a reason
    instead of having that line dropped.
    """
    with session_scope() as session:
        system = NurserySystem(session)
        system.add_user("teamUsername", "TeamPassword", "team")
        system.login("teamUsername", "TeamPassword")
        rose = TreeAndShrub("Rose", 15.99, 10, "rose.png")
        lavender = Perennial("Lavender", 12.75, 10, "lavender.png")
        system.add_plant(rose)
        system.add_plant(lavender)
        sam = CommunityCustomer("Sam", cust_email="sam@email.com")
        system.add_customer(sam)
        rose_id = str(rose.plant_id)
        lavender_id = str(lavender.plant_id)
        sam_id = str(sam.cust_id)

    login(client, "teamUsername", "TeamPassword")

    # A name of only spaces is the same as no name.
    blank_plant = client.post(
        "/plants/new",
        data={
            "plant_name": "   ",
            "plant_type": "trees and shrubs",
            "price": "5.00",
            "stock": "5",
            "photo": (BytesIO(PHOTO), "blank.png"),
        },
    )
    assert "Plant name is required" in page(blank_plant)
    # The photo saved for the refused plant is not left behind.
    assert list(photo_dir.iterdir()) == []

    blank_customer = client.post(
        "/customers/new",
        data={
            "cust_name": "   ",
            "customer_type": "community",
            "cust_email": "blank@email.com",
            "cust_phone": "",
            "username": "blankUsername",
            "password": "BlankPassword",
        },
    )
    assert "Name is required" in page(blank_customer)

    # Each of these is refused with the plant named in the reason.
    refusals = (
        ("0", "Quantity for Rose must be at least 1"),
        ("-3", "Quantity for Rose must be at least 1"),
        ("abc", "Quantity for Rose must be a whole number"),
        ("2.5", "Quantity for Rose must be a whole number"),
    )
    for quantity, reason in refusals:
        refused = client.post(
            "/orders/new",
            data={"customer_id": sam_id, f"qty-{rose_id}": quantity},
        )
        assert reason in page(refused), quantity

    # One good line does not let a bad line be dropped quietly.
    mixed = client.post(
        "/orders/new",
        data={
            "customer_id": sam_id,
            f"qty-{rose_id}": "2",
            f"qty-{lavender_id}": "0",
        },
    )
    assert "Quantity for Lavender must be at least 1" in page(mixed)

    # Empty boxes mean nothing was chosen, and the person is told so.
    empty = client.post(
        "/orders/new",
        data={
            "customer_id": sam_id,
            f"qty-{rose_id}": "",
            f"qty-{lavender_id}": "  ",
        },
    )
    assert "Enter a quantity for at least one plant" in page(empty)

    # Nothing was added, ordered, or taken from stock by any refused form.
    with session_scope() as session:
        system = NurserySystem(session)
        system.login("teamUsername", "TeamPassword")
        assert len(system.history.order_list) == 0
        assert len(system.catalog.plant_list) == 2
        assert len(system.directory.customer_list) == 1
        assert system.find_plant(rose.plant_id).plant_stock == 10
        assert system.find_plant(lavender.plant_id).plant_stock == 10
        assert system.find_customer(sam.cust_id).balance == 0.0

    # A valid quantity still goes through.
    with client.application.test_client() as fresh:
        login(fresh, "teamUsername", "TeamPassword")
        placed = fresh.post(
            "/orders/new",
            data={"customer_id": sam_id, f"qty-{rose_id}": "2"},
            follow_redirects=True,
        )
        assert "Order placed." in page(placed)


def test_the_payment_form_refuses_junk_cards_and_keeps_four_digits(
    client: FlaskClient,
) -> None:
    """
    A card number, expiry, or bank that cannot be real is refused with a
    reason and records nothing. A good payment goes through, and only the
    last four digits of the card reach the database.
    """
    with session_scope() as session:
        system = NurserySystem(session)
        system.add_user("teamUsername", "TeamPassword", "team")
        system.login("teamUsername", "TeamPassword")
        rose = TreeAndShrub("Rose", 15.99, 10, "rose.png")
        system.add_plant(rose)
        sam = CommunityCustomer("Sam", cust_email="sam@email.com")
        system.add_customer(sam)
        order = system.place_order(sam, [(rose, 2)])
        order_path = f"/orders/{order.order_id}"
        owed = f"${order.remaining_balance:.2f}"

    login(client, "teamUsername", "TeamPassword")

    def attempt(**fields: str) -> Page:
        """Submit the payment form and read the page that comes back."""
        form = {"amount": "5.00", "method": "debit card"}
        form.update(fields)
        return page(client.post(
            f"{order_path}/pay",
            data=form,
            headers=referred_from(order_path),
            follow_redirects=True,
        ))

    debit = {"bank_name": "ANZ"}
    credit = {"method": "credit card", "expiry_date": "12-28"}
    refusals = (
        ({"card_number": "banana", **debit}, "can only contain digits"),
        ({"card_number": "1234", **debit}, "13 to 19 digits"),
        ({"card_number": "", **debit}, "Card number is required"),
        (
            {"card_number": "1111222233334444", "bank_name": "  "},
            "Bank name is required",
        ),
        (
            {"card_number": "1111222233334444", **credit,
             "expiry_date": "whenever"},
            "as MM-YY",
        ),
        (
            {"card_number": "1111222233334444", **credit,
             "expiry_date": "13-28"},
            "as MM-YY",
        ),
        (
            {"card_number": "1111222233334444", **credit,
             "expiry_date": "01-20"},
            "expired in 01-20",
        ),
        (
            {"card_number": "1111222233334444", **credit,
             "expiry_date": ""},
            "Expiry date is required",
        ),
    )
    for fields, reason in refusals:
        assert reason in attempt(**fields), fields

    # Nothing was recorded by any of them.
    assert page(client.get(order_path)).value("Outstanding") == owed
    assert "No payments yet." in page(client.get("/payments"))

    # Groups of digits are fine, and the receipt does not carry the card.
    receipt = attempt(card_number="1111 2222 3333 4444", **debit)
    assert "Payment recorded." in receipt
    assert "1111222233334444" not in receipt
    assert "1111 2222 3333 4444" not in receipt

    with session_scope() as session:
        saved = session.execute(
            text("SELECT * FROM payments")
        ).mappings().all()
    assert [row["card_last4"] for row in saved] == ["4444"]
    assert "1111222233334444" not in str(list(saved[0].values()))
