"""
Unit tests for what a payment accepts, and what it keeps.

Card numbers, expiry dates, bank names, and payment dates are checked when
the payment is made. Only the last four digits of the card are kept. Nothing
here opens PostgreSQL or the Flask screens.
"""

from datetime import date, timedelta

import pytest

from model.customer import CommunityCustomer
from model.order import Order
from model.payment import CreditCardPayment, DebitCardPayment
from model.plant import TreeAndShrub

CARD = "1111222233334444"
# Fixed and in the past, so the expiry tests do not depend on today's date.
PAID_ON = "15-10-2025"


def new_order() -> Order:
    """
    Return a $15.99 order for a community customer.

    :return (Order): A new order
    """
    customer = CommunityCustomer("Sam", cust_email="sam@email.com")
    return Order(customer, [(TreeAndShrub("Rose", 15.99, 25, "rose.png"), 1)])


def debit(
    card: str = CARD,
    bank: str = "ANZ",
    paid_on: str | None = None,
) -> DebitCardPayment:
    """
    Make a debit card payment of $5.00.

    :param card (str): The card number as typed
    :param bank (str): The bank name as typed
    :param paid_on (str | None): The payment date, or None for today
    :return (DebitCardPayment): The payment
    """
    order = new_order()
    return DebitCardPayment(order.customer, order, 5.00, card, bank, paid_on)


def credit(
    expiry: str, paid_on: str | None = PAID_ON, card: str = CARD
) -> CreditCardPayment:
    """
    Make a credit card payment of $5.00.

    :param expiry (str): The expiry as typed
    :param paid_on (str | None): The payment date, or None for today
    :param card (str): The card number as typed
    :return (CreditCardPayment): The payment
    """
    order = new_order()
    return CreditCardPayment(
        order.customer, order, 5.00, card, expiry, paid_on
    )


# ---------- Card numbers ----------


@pytest.mark.parametrize(
    "card",
    [
        "banana",
        "1111 2222 3333 abcd",
        "1111/2222/3333/4444",
        "1111222233334444x",
        "1111.2222.3333.44",
        # Digits from another script are not the digits a card has.
        "\u0661\u0662\u0663\u0664\u0665\u0666\u0667\u0668"
        "\u0669\u0660\u0661\u0662\u0663\u0664\u0665\u0666",
    ],
)
def test_a_card_number_with_anything_but_digits_is_refused(card: str) -> None:
    """Letters and symbols are not a card number."""
    with pytest.raises(ValueError, match="only contain digits"):
        debit(card)


@pytest.mark.parametrize("card", ["", "   ", "\t", "- - -"])
def test_a_missing_card_number_is_refused(card: str) -> None:
    """An empty box is the same as no card number, even with only spaces
    and dashes in it."""
    with pytest.raises(ValueError, match="Card number is required"):
        debit(card)


@pytest.mark.parametrize("card", ["1", "123456789012", "1" * 20])
def test_a_card_number_of_the_wrong_length_is_refused(card: str) -> None:
    """Too short and too long are both refused, with the length asked for."""
    with pytest.raises(ValueError, match="13 to 19 digits"):
        debit(card)


@pytest.mark.parametrize("length", [13, 16, 19])
def test_card_numbers_from_13_to_19_digits_are_accepted(length: int) -> None:
    """The shortest and longest real card numbers are both fine."""
    card = "4" * length
    assert debit(card).card_last4 == "4444"


@pytest.mark.parametrize(
    "card",
    [
        "1111 2222 3333 4444",
        "1111-2222-3333-4444",
        "  1111222233334444  ",
        "1111 - 2222 - 3333 - 4444",
    ],
)
def test_spaces_and_dashes_in_a_card_number_are_ignored(card: str) -> None:
    """A card number is often typed in groups of four."""
    assert debit(card).card_last4 == "4444"


# ---------- What is kept ----------


def test_only_the_last_four_digits_of_the_card_are_kept() -> None:
    """The full number is not an attribute and is not in the printed
    payment, so it cannot be saved or logged by accident."""
    payment = debit("1111 2222 3333 9876")

    assert payment.card_last4 == "9876"
    assert not hasattr(payment, "card_number")
    assert "1111222233339876" not in str(vars(payment))
    assert "1111 2222 3333 9876" not in str(vars(payment))
    assert "1111" not in str(payment)
    assert "Card ending: 9876" in str(payment)


def test_a_credit_card_keeps_only_the_last_four_digits_too() -> None:
    """Both card types go through the same check and the same storage."""
    payment = credit("12-28", card="5555-6666-7777-8888")
    assert payment.card_last4 == "8888"
    assert "5555666677778888" not in str(vars(payment))
    assert "5555" not in str(payment)


# ---------- Expiry dates ----------


@pytest.mark.parametrize(
    "expiry",
    ["whenever", "banana", "13-28", "00-28", "9-28", "09/28", "09-2028",
     "0928", "09-28-01", "09-2", "09 28", "09-28x", "--"],
)
def test_an_expiry_that_is_not_mm_yy_is_refused(expiry: str) -> None:
    """The form asks for MM-YY, and the model holds it to that."""
    with pytest.raises(ValueError, match="as MM-YY"):
        credit(expiry)


@pytest.mark.parametrize("expiry", ["", "   "])
def test_a_missing_expiry_is_refused(expiry: str) -> None:
    """A credit card needs an expiry date."""
    with pytest.raises(ValueError, match="Expiry date is required"):
        credit(expiry)


def test_a_card_is_good_until_the_end_of_the_month_on_it() -> None:
    """Paying on 15 October 2025 works with an expiry of 10-25, and not
    with 09-25."""
    assert credit("10-25", "15-10-2025").expiry_date == "10-25"
    assert credit("10-25", "31-10-2025").expiry_date == "10-25"
    with pytest.raises(ValueError, match="expired in 09-25"):
        credit("09-25", "15-10-2025")
    with pytest.raises(ValueError, match="expired in 10-25"):
        credit("10-25", "01-11-2025")


def test_expiry_is_compared_across_a_year_end() -> None:
    """December still works in December, and not in January."""
    assert credit("12-25", "31-12-2025").expiry_date == "12-25"
    assert credit("01-26", "31-12-2025").expiry_date == "01-26"
    with pytest.raises(ValueError, match="expired in 12-25"):
        credit("12-25", "01-01-2026")


def test_expiry_is_compared_with_the_payment_date_not_the_clock() -> None:
    """An old payment can be recorded with the card it was paid with."""
    assert credit("03-20", "10-03-2020").expiry_date == "03-20"


def test_an_expired_card_is_refused_when_paying_today() -> None:
    """With no date given, the payment is today."""
    with pytest.raises(ValueError, match="expired in 01-20"):
        credit("01-20", None)


def test_an_expiry_with_spaces_round_it_is_tidied() -> None:
    """The stored expiry has no spaces."""
    assert credit("  12-28  ").expiry_date == "12-28"


# ---------- Payment dates ----------


def test_a_payment_dated_in_the_future_is_refused() -> None:
    """A payment is entered when it is taken, so tomorrow is too late."""
    tomorrow = (date.today() + timedelta(days=1)).strftime("%d-%m-%Y")
    with pytest.raises(ValueError, match="cannot be in the future"):
        debit(paid_on=tomorrow)
    with pytest.raises(ValueError, match="cannot be in the future"):
        credit("12-99", tomorrow)


def test_a_payment_dated_today_or_earlier_is_accepted() -> None:
    """Today, yesterday, and long ago are all fine."""
    today = date.today().strftime("%d-%m-%Y")
    yesterday = (date.today() - timedelta(days=1)).strftime("%d-%m-%Y")
    assert debit(paid_on=today).payment_date == today
    assert debit(paid_on=yesterday).payment_date == yesterday
    assert debit(paid_on="01-01-2020").payment_date == "01-01-2020"
    assert debit().payment_date == today


@pytest.mark.parametrize(
    "paid_on", ["2025-10-15", "31-02-2025", "15/10/2025", "soon", ""]
)
def test_a_payment_date_that_is_not_a_real_date_is_refused(
    paid_on: str,
) -> None:
    """The date must be a real DD-MM-YYYY date."""
    with pytest.raises(ValueError, match="DD-MM-YYYY"):
        debit(paid_on=paid_on)


# ---------- Bank names ----------


@pytest.mark.parametrize("bank", ["", "   ", "\t"])
def test_a_missing_bank_name_is_refused(bank: str) -> None:
    """A debit card needs a bank."""
    with pytest.raises(ValueError, match="Bank name is required"):
        debit(bank=bank)


def test_a_bank_name_that_will_not_fit_is_refused() -> None:
    """The column holds 100 characters, so a longer name is refused with a
    reason, not by a database error."""
    assert len(debit(bank="B" * 100).bank_name) == 100
    with pytest.raises(ValueError, match="100 characters or fewer"):
        debit(bank="B" * 101)


def test_a_bank_name_is_stored_without_spaces_round_it() -> None:
    """Leading and trailing spaces are dropped."""
    assert debit(bank="  ANZ  ").bank_name == "ANZ"


# ---------- Order of checks ----------


def test_a_refused_payment_leaves_the_order_untouched() -> None:
    """The checks run when the payment is made, before it can be recorded."""
    order = new_order()
    with pytest.raises(ValueError):
        CreditCardPayment(
            order.customer, order, 5.00, "banana", "whenever", PAID_ON
        )
    assert order.amount_paid == 0.0
    assert order.customer.balance == order.order_total
