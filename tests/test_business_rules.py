"""
Unit tests for nursery rules.

Each test builds the objects it needs and calls the rule directly. Nothing
here opens PostgreSQL or the Flask screens.
"""

from datetime import date
from decimal import Decimal

import pytest

from model.customer import CommunityCustomer, StaffCustomer, StudentCustomer
from model.documents import Invoice, Receipt
from model.exceptions import (
    CustomerInUseError,
    InsufficientStockError,
    OrderCannotBeCancelledError,
    OrderCannotBeCollectedError,
    OrderNotPayableError,
    OverpaymentError,
    PlantInUseError,
)
from model.order import Order
from model.order_item import OrderItem
from model.payment import CreditCardPayment, DebitCardPayment
from model.plant import TreeAndShrub, VegetableSeedling
from model.user import User


def staff_customer() -> StaffCustomer:
    """
    Return a staff customer with an email address

    :return (StaffCustomer): A new staff customer
    """
    return StaffCustomer("Avril", cust_email="avril@email.com")


def student_customer() -> StudentCustomer:
    """
    Return a student customer with a phone number

    :return (StudentCustomer): A new student customer
    """
    return StudentCustomer("Jane", cust_phone="021-555-0199")


def community_customer() -> CommunityCustomer:
    """
    Return a community customer with an email address

    :return (CommunityCustomer): A new community customer
    """
    return CommunityCustomer("Sam", cust_email="sam@email.com")


def rose(stock: int = 25) -> TreeAndShrub:
    """
    Return a rose with the given stock

    :param stock (int): Plants on hand
    :return (TreeAndShrub): A new rose
    """
    return TreeAndShrub("Rose", 15.99, stock, "rose.png")


@pytest.mark.parametrize("name", ["", " ", "   \t"])
def test_plant_name_cannot_be_blank(name: str) -> None:
    """A plant needs a real name, not an empty one or only spaces."""
    with pytest.raises(ValueError, match="Plant name is required"):
        TreeAndShrub(name, 15.99, 5, "rose.png")


@pytest.mark.parametrize("name", ["", " ", "   \t"])
def test_customer_name_cannot_be_blank(name: str) -> None:
    """A customer needs a real name, at creation and when it is changed."""
    with pytest.raises(ValueError, match="Customer name is required"):
        StaffCustomer(name, cust_email="avril@email.com")

    customer = staff_customer()
    with pytest.raises(ValueError, match="Customer name is required"):
        customer.cust_name = name
    assert customer.cust_name == "Avril"


def test_names_lose_the_spaces_around_them() -> None:
    """Spaces typed before or after a name are not stored."""
    assert TreeAndShrub("  Rose ", 15.99, 5, "rose.png").plant_name == "Rose"
    assert StaffCustomer(" Avril ", cust_email="a@b.c").cust_name == "Avril"


def test_staff_discount_is_one_percent() -> None:
    """Staff get 1% off the order total."""
    assert staff_customer().apply_discount(100.00) == Decimal("99.00")


def test_student_discount_is_five_percent() -> None:
    """Students get 5% off the order total."""
    assert student_customer().apply_discount(100.00) == Decimal("95.00")


def test_community_customer_gets_no_discount() -> None:
    """Community customers pay the full order total."""
    assert community_customer().apply_discount(100.00) == Decimal("100.00")


def test_ten_or_more_gets_a_bulk_discount() -> None:
    """Ten or more of one plant gets 10% off that line."""
    plant = TreeAndShrub("Lavender", 10.00, 20, "lavender.png")
    assert OrderItem.line_cost(plant, 10) == Decimal("90.00")


def test_fewer_than_ten_has_no_bulk_discount() -> None:
    """Nine of one plant is charged at the full price."""
    plant = TreeAndShrub("Lavender", 10.00, 20, "lavender.png")
    assert OrderItem.line_cost(plant, 9) == Decimal("90.00")


def test_staff_cannot_order_past_one_hundred() -> None:
    """A new order is refused when it would take the balance over $100."""
    customer = staff_customer()
    customer.add_to_balance(90.00)
    assert customer.can_place_order(0, 10.00) is True
    assert customer.can_place_order(0, 10.01) is False


def test_balance_of_one_hundred_blocks_another_order() -> None:
    """Owing exactly $100 already blocks the next order."""
    customer = student_customer()
    customer.add_to_balance(100.00)
    assert customer.can_place_order(0, 0.01) is False


def test_community_customer_can_have_one_pending_order() -> None:
    """A community customer with a pending order cannot place another."""
    customer = community_customer()
    assert customer.can_place_order(0, 500.00) is True
    assert customer.can_place_order(1, 1.00) is False


def test_community_order_must_be_paid_before_collection() -> None:
    """A community order still owing money cannot be collected."""
    customer = community_customer()
    plant = rose()
    order = Order(customer, [(plant, 1)])
    with pytest.raises(OrderCannotBeCollectedError):
        order.collect_order()
    assert order.order_status == "pending"


def test_staff_can_collect_while_owing() -> None:
    """Staff can collect an order before it is paid."""
    order = Order(staff_customer(), [(rose(), 1)])
    order.collect_order("17-10-2026")
    assert order.order_status == "collected"
    assert order.collected_date == date(2026, 10, 17)
    assert order.remaining_balance > 0


def test_cancelling_an_unpaid_order_restores_stock_and_balance() -> None:
    """Cancelling a pending unpaid order puts the stock and balance back."""
    customer = staff_customer()
    plant = rose(stock=5)
    order = Order(customer, [(plant, 2)])
    assert plant.plant_stock == 3
    assert customer.balance == Decimal("31.66")

    order.cancel_order("17-10-2026")

    assert order.order_status == "cancelled"
    assert order.cancelled_date == date(2026, 10, 17)
    assert plant.plant_stock == 5
    assert customer.balance == Decimal("0.00")


def test_paid_order_cannot_be_cancelled() -> None:
    """Any payment toward an order stops it from being cancelled."""
    customer = community_customer()
    plant = rose(stock=5)
    order = Order(customer, [(plant, 1)])
    order.record_payment(10.00)

    with pytest.raises(OrderCannotBeCancelledError):
        order.cancel_order()

    assert order.order_status == "pending"
    assert plant.plant_stock == 4
    assert order.amount_paid == Decimal("10.00")


def test_payment_cannot_exceed_what_is_still_owed() -> None:
    """A payment larger than the remaining balance is refused, and the
    message says how much is owed."""
    order = Order(community_customer(), [(rose(), 1)])
    with pytest.raises(OverpaymentError, match=r"still owed.*\$15\.99"):
        order.record_payment(order.remaining_balance + Decimal("0.01"))
    assert order.amount_paid == Decimal("0.00")


def test_a_payment_of_nothing_is_bad_input_not_an_overpayment() -> None:
    """A zero payment is invalid data, so it stays a ValueError."""
    order = Order(community_customer(), [(rose(), 1)])
    with pytest.raises(ValueError, match="greater than 0"):
        order.record_payment(0)
    assert order.amount_paid == Decimal("0.00")


def test_a_cancelled_order_says_it_was_cancelled() -> None:
    """Paying a cancelled order is refused for that reason, not as an
    overpayment."""
    order = Order(community_customer(), [(rose(), 1)])
    order.cancel_order()
    with pytest.raises(OrderNotPayableError, match="has been cancelled"):
        order.record_payment(5.00)
    assert order.amount_paid == Decimal("0.00")


def test_a_paid_order_says_it_is_paid_in_full() -> None:
    """Paying an order that is settled is refused for that reason, even for
    a small amount."""
    order = Order(community_customer(), [(rose(), 1)])
    order.record_payment(order.remaining_balance)
    with pytest.raises(OrderNotPayableError, match="paid in full"):
        order.record_payment(0.01)
    assert order.amount_paid == Decimal("15.99")


@pytest.mark.parametrize(
    ("error_type", "default"),
    [
        (PlantInUseError, "Cannot remove a plant that has been ordered"),
        (
            CustomerInUseError,
            "Cannot remove a customer who has placed an order",
        ),
        (
            OverpaymentError,
            "Payment cannot be more than what is still owed on this order",
        ),
        (OrderNotPayableError, "Nothing can be paid toward this order"),
    ],
)
def test_the_payment_and_removal_errors_carry_their_message(
    error_type: type[Exception], default: str
) -> None:
    """Each has a default message, accepts its own, and is not a ValueError,
    so a caller can tell it from bad input."""
    assert str(error_type()) == default
    assert str(error_type("A reason")) == "A reason"
    assert not issubclass(error_type, ValueError)


def test_credit_card_adds_a_surcharge_and_debit_does_not() -> None:
    """Credit cards add 1.5%. Debit cards charge the amount paid."""
    customer = community_customer()
    order = Order(customer, [(rose(), 1)])
    credit = CreditCardPayment(
        customer, order, 10.00, "5555666677778888", "12-28"
    )
    debit = DebitCardPayment(
        customer, order, 10.00, "1111222233334444", "ANZ"
    )
    assert credit.amount_charged() == Decimal("10.15")
    assert debit.amount_charged() == Decimal("10.00")


def test_same_plant_cannot_appear_twice_on_an_order() -> None:
    """One order can contain a plant only once."""
    plant = rose()
    with pytest.raises(ValueError, match="once"):
        Order(community_customer(), [(plant, 1), (plant, 2)])
    assert plant.plant_stock == 25


def test_order_cannot_take_more_stock_than_is_on_hand() -> None:
    """An order line is refused when the plant does not have the quantity."""
    plant = rose(stock=2)
    with pytest.raises(InsufficientStockError):
        Order(community_customer(), [(plant, 3)])
    assert plant.plant_stock == 2


def test_pending_order_is_flagged_after_seven_days() -> None:
    """A pending order is flagged once seven days have passed."""
    order = Order(staff_customer(), [(rose(), 1)], "01-10-2026")
    assert order.is_uncollected_too_long(date(2026, 10, 7)) is False
    assert order.is_uncollected_too_long(date(2026, 10, 8)) is True

    order.collect_order("08-10-2026")
    assert order.is_uncollected_too_long(date(2026, 10, 20)) is False


def test_invoice_lists_bulk_and_customer_discounts() -> None:
    """
    An invoice shows the line discount, the customer discount, and the total.
    """
    plant = VegetableSeedling("Tomato", 4.50, 50, "tomato.png")
    order = Order(student_customer(), [(plant, 12)])
    invoice = Invoice(order)

    assert invoice.lines[0].quantity == 12
    assert invoice.lines[0].line_cost == Decimal("48.60")
    assert invoice.lines[0].bulk_discount == Decimal("5.40")
    assert invoice.customer_discount == Decimal("2.43")
    assert invoice.total_to_pay == Decimal("46.17")
    # The invoice carries a short order number that stays the same for the
    # order, and the total to pay does not fall when payments are made.
    assert invoice.order_number == order.order_number
    assert len(invoice.order_number) == 8
    assert invoice.order_number == invoice.order_number.upper()
    order.record_payment(46.17)
    assert Invoice(order).total_to_pay == Decimal("46.17")


def test_receipt_shows_the_surcharge_and_what_is_left() -> None:
    """A receipt shows the amount, the surcharge, and the order balance."""
    customer = community_customer()
    order = Order(
        customer,
        [(TreeAndShrub("Lavender", 36.75, 5, "lavender.png"), 1)],
    )
    order.record_payment(36.75)
    payment = CreditCardPayment(
        customer, order, 36.75, "5555666677778888", "12-28"
    )
    receipt = Receipt(payment)

    assert receipt.amount == Decimal("36.75")
    assert receipt.surcharge == Decimal("0.55")
    assert receipt.amount_charged == Decimal("37.30")
    assert receipt.remaining_on_order == Decimal("0.00")


def test_password_is_stored_as_a_hash() -> None:
    """
    The typed password is checked against a hash, and the hash is not
    the password.
    """
    user = User("team", "nursery", "team")
    assert user.check_password("nursery") is True
    assert user.check_password("wrong") is False
    assert user._password_hash != "nursery"


def test_team_login_is_not_linked_to_a_customer() -> None:
    """
    The shared team account has no customer, and a customer account must
    have one.
    """
    team = User("team", "nursery", "team")
    assert team.role == "team"
    assert team.customer is None

    customer = staff_customer()
    linked = User("avril", "avril", "customer", customer)
    assert linked.role == "customer"
    assert linked.customer is customer

    with pytest.raises(ValueError):
        User("extra", "extra", "customer")
