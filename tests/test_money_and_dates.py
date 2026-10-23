"""
Unit tests for money held as Decimal and dates held as dates.

Nothing here opens a database.
"""

from datetime import date, datetime
from decimal import Decimal

import pytest

from model.customer import CommunityCustomer, StaffCustomer
from model.dates import format_date, parse_date
from model.money import apply_rate, to_money
from model.order import Order
from model.order_item import OrderItem
from model.payment import CreditCardPayment
from model.plant import TreeAndShrub

# ---------- Money ----------


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        (15.99, "15.99"),
        (10, "10.00"),
        ("7.5", "7.50"),
        (Decimal("3.1"), "3.10"),
        # Halves round up. A float 2.675 is really 2.67499999..., so rounding
        # the float would give 2.67.
        (2.675, "2.68"),
        ("0.005", "0.01"),
        ("0.004", "0.00"),
    ],
)
def test_amounts_become_whole_cents(given: object, expected: str) -> None:
    """A float is read from how it prints, then rounded half up to cents."""
    assert to_money(given) == Decimal(expected)  # type: ignore[arg-type]
    assert to_money(given).as_tuple().exponent == -2  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "bad", ["banana", "", "1,5", "NaN", "Infinity", float("inf"), True, None]
)
def test_something_that_is_not_an_amount_is_refused(bad: object) -> None:
    """Text, infinity, nothing at all, and True are not amounts."""
    with pytest.raises(ValueError, match="must be a number"):
        to_money(bad)  # type: ignore[arg-type]


def test_an_amount_too_large_for_cents_is_refused() -> None:
    """Rounding an enormous number to cents fails, and says so plainly."""
    with pytest.raises(ValueError, match="must be a number"):
        to_money("1e40")


def test_the_label_names_the_field_in_the_message() -> None:
    """The caller says which field was wrong."""
    with pytest.raises(ValueError, match="Price must be a number"):
        to_money("abc", "Price")


def test_a_discount_is_taken_off_and_rounded_to_cents() -> None:
    """5% off 19.99 is 18.9905, which is 18.99."""
    assert apply_rate(Decimal("19.99"), Decimal("0.05")) == Decimal("18.99")


def test_cents_add_up_exactly() -> None:
    """Ten payments of 0.10 make exactly 1.00. As floats they make
    0.9999999999999999."""
    assert sum(to_money(0.10) for _ in range(10)) == Decimal("1.00")
    assert sum(0.10 for _ in range(10)) != 1.00


def test_an_order_total_is_exact_to_the_cent() -> None:
    """Three lines of 0.10 for a staff member: 0.30 less 1% is 0.297, and
    that rounds to 0.30."""
    customer = StaffCustomer("Avril", cust_email="avril@email.com")
    plants = [
        TreeAndShrub(f"Seed {n}", 0.10, 5, "seed.png") for n in range(3)
    ]

    order = Order(customer, [(plant, 1) for plant in plants])

    assert order.order_total == Decimal("0.30")
    assert customer.balance == Decimal("0.30")
    assert isinstance(order.order_total, Decimal)


def test_a_bulk_line_is_priced_in_cents() -> None:
    """Ten at 4.99 is 49.90, and 10% off is 44.91."""
    plant = TreeAndShrub("Herb", 4.99, 50, "herb.png")

    assert OrderItem.line_cost(plant, 10) == Decimal("44.91")


def test_a_price_is_kept_in_cents() -> None:
    """The price is rounded to cents when it is set, and a price that rounds
    to nothing is refused."""
    plant = TreeAndShrub("Herb", "4.999", 5, "herb.png")

    assert plant.plant_price == Decimal("5.00")
    with pytest.raises(ValueError, match="greater than 0"):
        plant.plant_price = "0.004"
    with pytest.raises(ValueError, match="Plant price must be a number"):
        plant.plant_price = "free"


def test_a_credit_card_surcharge_is_rounded_half_up() -> None:
    """1.5% of 0.50 is 0.0075, so 0.50 becomes 0.51 charged."""
    customer = CommunityCustomer("Sam", cust_email="sam@email.com")
    order = Order(customer, [(TreeAndShrub("Rose", 15.99, 5, "r.png"), 1)])

    payment = CreditCardPayment(
        customer, order, "0.50", "5555666677778888", "12-99"
    )

    assert payment.amount_charged() == Decimal("0.51")


def test_a_payment_is_refused_when_it_rounds_to_nothing() -> None:
    """Half a cent is not an amount."""
    customer = CommunityCustomer("Sam", cust_email="sam@email.com")
    order = Order(customer, [(TreeAndShrub("Rose", 15.99, 5, "r.png"), 1)])

    with pytest.raises(ValueError, match="greater than 0"):
        order.record_payment("0.004")


# ---------- Dates ----------


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("05-10-2025", date(2025, 10, 5)),
        (" 05-10-2025 ", date(2025, 10, 5)),
        ("29-02-2024", date(2024, 2, 29)),
        (date(2025, 10, 5), date(2025, 10, 5)),
        (datetime(2025, 10, 5, 13, 30), date(2025, 10, 5)),
    ],
)
def test_dates_are_read_from_text_or_taken_as_they_are(
    given: object, expected: date
) -> None:
    """DD-MM-YYYY text and real dates both work."""
    assert parse_date(given) == expected  # type: ignore[arg-type]


def test_no_date_means_today() -> None:
    """Leaving the date out is today."""
    assert parse_date(None) == date.today()


@pytest.mark.parametrize(
    "bad",
    [
        "2025-10-05", "31-02-2025", "29-02-2025", "5/10/2025", "soon", "",
        20251005,
    ],
)
def test_a_date_that_is_not_a_real_ddmmyyyy_date_is_refused(
    bad: object,
) -> None:
    """The wrong shape, a day that does not exist, and a number all fail,
    with the field name in the message."""
    with pytest.raises(ValueError, match="Order date must be a valid date"):
        parse_date(bad, "Order date")  # type: ignore[arg-type]


def test_a_date_is_shown_as_ddmmyyyy() -> None:
    """Screens show what staff type, with a blank for no date."""
    assert format_date(date(2025, 10, 5)) == "05-10-2025"
    assert format_date(None) == ""


def test_an_order_keeps_a_real_date_and_a_creation_time() -> None:
    """The order date is a date, however it was given, and created_at records
    when the order was made."""
    customer = CommunityCustomer("Sam", cust_email="sam@email.com")
    plant = TreeAndShrub("Rose", 15.99, 5, "r.png")
    before = datetime.now()

    from_text = Order(customer, [(plant, 1)], "05-10-2025")
    customer = CommunityCustomer("Kim", cust_email="kim@email.com")
    from_date = Order(customer, [(plant, 1)], date(2025, 10, 6))

    assert from_text.order_date == date(2025, 10, 5)
    assert from_date.order_date == date(2025, 10, 6)
    assert before <= from_text.created_at <= datetime.now()
    assert from_date.created_at >= from_text.created_at
    assert str(from_text).count("05-10-2025") == 1
