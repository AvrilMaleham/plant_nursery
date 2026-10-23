"""
Tests for the rules NurserySystem enforces.

These call NurserySystem directly on a throwaway in-memory database, so they
need no PostgreSQL server and no web pages. They cover who is allowed to do
what, the refusals when an order is placed, removing plants and customers,
the price search, revenue periods, and receipts.
"""

from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Callable

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import app
from controller.plant_routes import search_filters
from model.customer import (
    CommunityCustomer,
    Customer,
    StaffCustomer,
    StudentCustomer,
)
from model.exceptions import (
    CustomerInUseError,
    InsufficientStockError,
    LoginFailedError,
    NotAuthorisedError,
    OrderCannotBeCancelledError,
    OrderCannotBeCollectedError,
    OrderNotAllowedError,
    OrderNotPayableError,
    OverpaymentError,
    PlantInUseError,
)
from model.nursery_system import NurserySystem
from model.order import Order
from model.payment import CreditCardPayment, DebitCardPayment, Payment
from model.plant import (
    Perennial,
    Plant,
    PotPlant,
    TreeAndShrub,
    VegetableSeedling,
)

TEAM_ONLY = "Only the nursery team can do that"
OWN_ACCOUNT_ONLY = "You can only do that for your own account"
PASSWORD = "Password1"


# ---------- Helpers ----------


def add_plant(
    system: NurserySystem,
    name: str = "Rose",
    price: Decimal | float = 15.99,
    stock: int = 25,
) -> Plant:
    """
    Add a shrub to the catalog as the team.

    :param system (NurserySystem): The system, logged in as the team
    :param name (str): Plant name
    :param price (Decimal | float): Price per plant
    :param stock (int): Stock on hand
    :return (Plant): The new plant
    """
    plant = TreeAndShrub(name, price, stock, f"{name.lower()}.png")
    system.add_plant(plant)
    return plant


def add_customer(
    system: NurserySystem,
    kind: type[Customer] = CommunityCustomer,
    name: str = "Sam",
) -> Customer:
    """
    Add a customer and a login for them, as the team.

    The login is the lower-case name followed by "User".

    :param system (NurserySystem): The system, logged in as the team
    :param kind (type[Customer]): The customer type
    :param name (str): Customer name
    :return (Customer): The new customer
    """
    customer = kind(name, cust_email=f"{name.lower()}@email.com")
    system.add_customer(customer)
    system.add_user(f"{name.lower()}User", PASSWORD, "customer", customer)
    return customer


def sign_in_as(system: NurserySystem, name: str) -> None:
    """
    Log a customer in on the system.

    :param system (NurserySystem): The system to log in on
    :param name (str): The customer's name, as given to add_customer
    """
    system.logout()
    system.login(f"{name.lower()}User", PASSWORD)


def sign_in_as_team(system: NurserySystem) -> None:
    """
    Log the nursery team in on the system.

    :param system (NurserySystem): The system to log in on
    """
    system.logout()
    system.login("teamUser", PASSWORD)


def day(days_ago: int = 0) -> str:
    """
    Return a date in DD-MM-YYYY form.

    :param days_ago (int): How many days before today
    :return (str): The date
    """
    return (date.today() - timedelta(days=days_ago)).strftime("%d-%m-%Y")


def pay(
    system: NurserySystem,
    order: Order,
    amount: Decimal | float,
    on: str,
    credit: bool = False,
) -> Payment:
    """
    Record a card payment toward an order.

    :param system (NurserySystem): The system to record it on
    :param order (Order): The order being paid
    :param amount (Decimal | float): The amount applied to the order
    :param on (str): The payment date in DD-MM-YYYY form
    :param credit (bool): Use a credit card, which adds a surcharge
    :return (Payment): The recorded payment
    """
    if credit:
        payment: Payment = CreditCardPayment(
            order.customer, order, amount, "5555666677778888", "12-28", on
        )
    else:
        payment = DebitCardPayment(
            order.customer, order, amount, "1111222233334444", "ANZ", on
        )
    system.record_payment(payment)
    return payment


# ---------- Fixtures ----------


@pytest.fixture(autouse=True)
def quick_password_hashing(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Hash passwords with a cheap setting in these tests only.

    The real setting is deliberately slow, and every login created here
    would pay for it. The unit test for password hashing in
    test_business_rules.py still uses the real one.
    """
    import model.user

    real = model.user.generate_password_hash
    monkeypatch.setattr(
        model.user,
        "generate_password_hash",
        lambda password: real(password, method="pbkdf2:sha256:1000"),
    )


@pytest.fixture
def system(memory_session: Session) -> NurserySystem:
    """
    Give a test a nursery with the team logged in.

    :param memory_session (Session): The in-memory database
    :return (NurserySystem): A system with one team login, signed in
    """
    nursery = NurserySystem(memory_session)
    nursery.add_user("teamUser", PASSWORD, "team")
    nursery.login("teamUser", PASSWORD)
    return nursery


@pytest.fixture
def world(system: NurserySystem) -> SimpleNamespace:
    """
    Give a test a rose, a community customer, a staff customer, and an order
    for each.

    :param system (NurserySystem): The system, logged in as the team
    :return (SimpleNamespace): The system and the records created
    """
    rose = add_plant(system)
    sam = add_customer(system, CommunityCustomer, "Sam")
    avril = add_customer(system, StaffCustomer, "Avril")
    sam_order = system.place_order(sam, [(rose, 2)])
    avril_order = system.place_order(avril, [(rose, 1)])
    return SimpleNamespace(
        system=system,
        rose=rose,
        sam=sam,
        avril=avril,
        sam_order=sam_order,
        avril_order=avril_order,
    )


# ---------- Login and the two access exceptions ----------


def test_login_and_access_errors_have_a_default_and_a_custom_message() -> None:
    """Both exceptions carry a message the screen can show as it is."""
    assert str(LoginFailedError()) == "Username or password is incorrect"
    assert str(NotAuthorisedError()) == "You are not allowed to do that"
    assert str(LoginFailedError("Try again")) == "Try again"
    assert str(NotAuthorisedError("Not yours")) == "Not yours"
    assert isinstance(LoginFailedError(), Exception)
    assert isinstance(NotAuthorisedError(), Exception)


def test_wrong_password_and_unknown_user_give_the_same_error(
    world: SimpleNamespace,
) -> None:
    """The error does not reveal which of the two was wrong."""
    nursery = world.system
    nursery.logout()
    with pytest.raises(LoginFailedError) as wrong_password:
        nursery.login("samUser", "not-the-password")
    with pytest.raises(LoginFailedError) as unknown_user:
        nursery.login("nobodyUser", PASSWORD)
    assert str(wrong_password.value) == str(unknown_user.value)
    assert nursery.current_user is None


def test_login_logout_and_resume_track_who_is_signed_in(
    world: SimpleNamespace,
) -> None:
    """A good login signs someone in, logout ends it, resume restores it."""
    nursery = world.system
    user = nursery.login("samUser", PASSWORD)
    assert nursery.current_user is user
    assert user.role == "customer"

    nursery.logout()
    assert nursery.current_user is None

    assert nursery.resume(user.user_id) is True
    assert nursery.current_user is user


def test_resume_with_an_unknown_login_signs_nobody_in(
    world: SimpleNamespace,
) -> None:
    """A stale cookie for a login that no longer exists does not sign in."""
    import uuid

    assert world.system.resume(uuid.uuid4()) is False
    assert world.system.current_user is None


def test_first_account_must_be_the_team(memory_session: Session) -> None:
    """On an empty system, only the team login can be created."""
    nursery = NurserySystem(memory_session)
    customer = CommunityCustomer("Sam", cust_email="sam@email.com")
    with pytest.raises(NotAuthorisedError, match="first account"):
        nursery.add_user("samUser", PASSWORD, "customer", customer)


def test_only_the_team_can_add_accounts(world: SimpleNamespace) -> None:
    """After the first account, a customer or a stranger cannot add one."""
    nursery = world.system
    other = CommunityCustomer("Tia", cust_email="tia@email.com")

    sign_in_as(nursery, "Sam")
    with pytest.raises(NotAuthorisedError, match=TEAM_ONLY):
        nursery.add_user("tiaUser", PASSWORD, "customer", other)

    nursery.logout()
    with pytest.raises(NotAuthorisedError, match="log in"):
        nursery.add_user("tiaUser", PASSWORD, "customer", other)


def test_nobody_signed_in_is_refused(memory_session: Session) -> None:
    """Searching and finding need a login, and say so."""
    nursery = NurserySystem(memory_session)
    with pytest.raises(NotAuthorisedError, match="log in first"):
        nursery.search_plants()


def test_a_username_cannot_be_used_twice(world: SimpleNamespace) -> None:
    """Two logins cannot share a username."""
    other = CommunityCustomer("Tia", cust_email="tia@email.com")
    world.system.add_customer(other)
    with pytest.raises(ValueError, match="already in use"):
        world.system.add_user("samUser", PASSWORD, "customer", other)


# ---------- Who can do what ----------


# Each action takes the world and does one thing only the team may do. The
# names become the test ids, so a failure says which action was allowed.
TEAM_ONLY_ACTIONS: dict[str, Callable[[SimpleNamespace], object]] = {
    "add_plant": lambda w: w.system.add_plant(
        TreeAndShrub("Fig", 5.00, 5, "fig.png")
    ),
    "remove_plant": lambda w: w.system.remove_plant(w.rose),
    "update_plant_price": lambda w: w.system.update_plant_price(w.rose, 9.99),
    "update_plant_stock": lambda w: w.system.update_plant_stock(w.rose, 50),
    "add_customer": lambda w: w.system.add_customer(
        CommunityCustomer("Tia", cust_email="tia@email.com")
    ),
    "remove_customer": lambda w: w.system.remove_customer(w.avril),
    "filter_customers": lambda w: w.system.filter_customers("staff"),
    "collect_order": lambda w: w.system.collect_order(w.avril_order),
    "filter_orders_for_everyone": lambda w: w.system.filter_orders("pending"),
    "orders_uncollected": lambda w: (
        w.system.orders_uncollected_for_seven_days()
    ),
    "plant_order_history": lambda w: w.system.plant_order_history(w.rose),
    "most_ordered_plants": lambda w: w.system.most_ordered_plants(),
    "least_ordered_plants": lambda w: w.system.least_ordered_plants(),
    "revenue": lambda w: w.system.revenue("day", day()),
}


@pytest.mark.parametrize("action", TEAM_ONLY_ACTIONS)
def test_a_customer_cannot_use_the_team_screens(
    world: SimpleNamespace, action: str
) -> None:
    """Every team-only action refuses a signed-in customer."""
    sign_in_as(world.system, "Avril")
    with pytest.raises(NotAuthorisedError, match=TEAM_ONLY):
        TEAM_ONLY_ACTIONS[action](world)


# Each action is something Avril, a customer, tries on Sam's records.
OTHER_CUSTOMER_ACTIONS: dict[str, Callable[[SimpleNamespace], object]] = {
    "find_customer": lambda w: w.system.find_customer(w.sam.cust_id),
    "update_customer": lambda w: w.system.update_customer(
        w.sam, "Sam", "sam@email.com", ""
    ),
    "place_order": lambda w: w.system.place_order(w.sam, [(w.rose, 1)]),
    "order_history": lambda w: w.system.get_customer_order_history(w.sam),
    "find_order": lambda w: w.system.find_order(w.sam_order.order_id),
    "cancel_order": lambda w: w.system.cancel_order(w.sam_order),
    "invoice_for": lambda w: w.system.invoice_for(w.sam_order),
    "get_order_payments": lambda w: w.system.get_order_payments(w.sam_order),
    "find_payment": lambda w: w.system.find_payment(w.sam_payment.payment_id),
    "receipt_for": lambda w: w.system.receipt_for(w.sam_payment),
    "customer_payments": lambda w: w.system.get_customer_payments(w.sam),
    "customer_activity": lambda w: w.system.customer_activity(w.sam),
    "filter_orders": lambda w: w.system.filter_orders("pending", w.sam),
    "record_payment": lambda w: w.system.record_payment(
        DebitCardPayment(
            w.sam, w.sam_order, 5.00, "1111222233334444", "ANZ"
        )
    ),
}


@pytest.mark.parametrize("action", OTHER_CUSTOMER_ACTIONS)
def test_a_customer_cannot_touch_another_customers_records(
    world: SimpleNamespace, action: str
) -> None:
    """Orders, payments, and details belong to the customer they are for."""
    world.sam_payment = pay(world.system, world.sam_order, 10.00, day())
    sign_in_as(world.system, "Avril")
    with pytest.raises(NotAuthorisedError, match=OWN_ACCOUNT_ONLY):
        OTHER_CUSTOMER_ACTIONS[action](world)


def test_a_customer_can_use_their_own_records(world: SimpleNamespace) -> None:
    """The same actions work when they are for the signed-in customer."""
    nursery = world.system
    sign_in_as(nursery, "Avril")

    assert nursery.find_customer(world.avril.cust_id) is world.avril
    assert nursery.find_order(world.avril_order.order_id) is world.avril_order
    assert nursery.invoice_for(world.avril_order).total_to_pay == (
        world.avril_order.order_total
    )
    payment = pay(nursery, world.avril_order, 5.00, day())
    assert nursery.receipt_for(payment).remaining_on_order == (
        world.avril_order.order_total - Decimal("5.00")
    )
    assert nursery.get_customer_order_history(world.avril) == [
        world.avril_order
    ]
    assert nursery.filter_orders("pending", world.avril) == [
        world.avril_order
    ]
    # Searching the catalog is for everyone who is signed in.
    assert world.rose in nursery.search_plants(name="rose")


def test_only_the_team_can_collect_an_order(world: SimpleNamespace) -> None:
    """A customer cannot mark their own order collected."""
    nursery = world.system
    sign_in_as(nursery, "Avril")
    with pytest.raises(NotAuthorisedError, match=TEAM_ONLY):
        nursery.collect_order(world.avril_order)
    assert world.avril_order.order_status == "pending"

    sign_in_as_team(nursery)
    nursery.collect_order(world.avril_order)
    assert world.avril_order.order_status == "collected"


def test_a_customer_can_cancel_their_own_unpaid_order(
    world: SimpleNamespace,
) -> None:
    """Cancelling returns the stock and the amount owed."""
    nursery = world.system
    stock_before = world.rose.plant_stock
    sign_in_as(nursery, "Avril")
    nursery.cancel_order(world.avril_order)
    assert world.avril_order.order_status == "cancelled"
    assert world.rose.plant_stock == stock_before + 1
    assert world.avril.balance == Decimal("0.0")


# ---------- place_order refusals ----------


def test_staff_cannot_place_an_order_that_takes_them_over_100(
    system: NurserySystem,
) -> None:
    """The refusal says why, and nothing is kept: no stock, balance, order."""
    plant = add_plant(system, "Orchid", price=40.00, stock=10)
    avril = add_customer(system, StaffCustomer, "Avril")
    avril.add_to_balance(70.00)
    stock_before = plant.plant_stock

    with pytest.raises(OrderNotAllowedError, match=r"over \$100"):
        # 3 x $40.00 less 1% is $118.80, which would take $70 to $188.80.
        system.place_order(avril, [(plant, 3)])

    assert plant.plant_stock == stock_before
    assert avril.balance == Decimal("70.00")
    assert system.history.order_list == []


def test_an_order_that_reaches_exactly_100_is_allowed(
    system: NurserySystem,
) -> None:
    """The limit is "over $100", so owing exactly $100 is allowed."""
    plant = add_plant(system, "Orchid", price=40.40, stock=10)
    avril = add_customer(system, StaffCustomer, "Avril")
    avril.add_to_balance(60.00)

    order = system.place_order(avril, [(plant, 1)])

    # $40.40 less 1% is $40.00, so the balance is $100.00 exactly.
    assert order.order_total == Decimal("40.00")
    assert avril.balance == Decimal("100.00")
    # Owing $100 now blocks any further order.
    with pytest.raises(OrderNotAllowedError, match=r"over \$100"):
        system.place_order(avril, [(plant, 1)])


def test_a_student_is_held_to_the_same_100_limit(
    system: NurserySystem,
) -> None:
    """Students share the staff rule."""
    plant = add_plant(system, "Orchid", price=60.00, stock=10)
    jane = add_customer(system, StudentCustomer, "Jane")
    system.place_order(jane, [(plant, 1)])
    with pytest.raises(OrderNotAllowedError, match=r"over \$100"):
        system.place_order(jane, [(plant, 1)])


def test_community_customer_cannot_have_two_pending_orders(
    world: SimpleNamespace,
) -> None:
    """Sam already has a pending order, so a second one is refused."""
    stock_before = world.rose.plant_stock
    with pytest.raises(OrderNotAllowedError, match="one pending order"):
        world.system.place_order(world.sam, [(world.rose, 1)])
    assert world.rose.plant_stock == stock_before
    assert len(world.system.get_customer_order_history(world.sam)) == 1


def test_a_community_customer_can_order_again_once_it_is_settled(
    world: SimpleNamespace,
) -> None:
    """Cancelling, or paying and collecting, frees the next order."""
    nursery = world.system
    nursery.cancel_order(world.sam_order)
    second = nursery.place_order(world.sam, [(world.rose, 1)])

    pay(nursery, second, second.remaining_balance, day())
    nursery.collect_order(second)
    third = nursery.place_order(world.sam, [(world.rose, 1)])
    assert third.order_status == "pending"


def test_an_order_for_more_than_the_stock_is_refused(
    system: NurserySystem,
) -> None:
    """The message gives what is left, and nothing changes."""
    plant = add_plant(system, "Fern", price=8.00, stock=3)
    sam = add_customer(system)
    with pytest.raises(InsufficientStockError, match="only 3 available"):
        system.place_order(sam, [(plant, 4)])
    assert plant.plant_stock == 3
    assert sam.balance == Decimal("0.0")
    assert system.history.order_list == []


def test_a_later_line_with_too_little_stock_leaves_the_earlier_one_alone(
    system: NurserySystem,
) -> None:
    """One order is all or nothing: no earlier line is taken from stock."""
    rose = add_plant(system, "Rose", stock=10)
    fern = add_plant(system, "Fern", price=8.00, stock=1)
    sam = add_customer(system)
    with pytest.raises(InsufficientStockError):
        system.place_order(sam, [(rose, 5), (fern, 2)])
    assert rose.plant_stock == 10
    assert fern.plant_stock == 1
    assert sam.balance == Decimal("0.0")


@pytest.mark.parametrize("quantity", [0, -1])
def test_an_order_for_zero_or_fewer_is_refused(
    system: NurserySystem, quantity: int
) -> None:
    """A zero or negative quantity never becomes an order."""
    plant = add_plant(system)
    sam = add_customer(system)
    with pytest.raises(ValueError, match="Minimum order is 1"):
        system.place_order(sam, [(plant, quantity)])
    assert plant.plant_stock == 25
    assert system.history.order_list == []


def test_an_order_needs_a_registered_customer_and_plant(
    system: NurserySystem,
) -> None:
    """Orders cannot be made for someone or something that is not stored."""
    plant = add_plant(system)
    sam = add_customer(system)
    stranger = CommunityCustomer("Ghost", cust_email="ghost@email.com")
    unlisted = TreeAndShrub("Unlisted", 5.00, 5, "unlisted.png")

    with pytest.raises(ValueError, match="not registered"):
        system.place_order(stranger, [(plant, 1)])
    with pytest.raises(ValueError, match="Plant is not registered"):
        system.place_order(sam, [(unlisted, 1)])
    assert system.history.order_list == []


def test_an_order_cannot_repeat_a_plant_or_be_empty_or_misdated(
    system: NurserySystem,
) -> None:
    """The remaining refusals leave stock and balance as they were."""
    plant = add_plant(system)
    sam = add_customer(system)

    with pytest.raises(ValueError, match="once"):
        system.place_order(sam, [(plant, 1), (plant, 2)])
    with pytest.raises(ValueError, match="at least one item"):
        system.place_order(sam, [])
    with pytest.raises(ValueError, match="DD-MM-YYYY"):
        system.place_order(sam, [(plant, 1)], "31-02-2026")

    assert plant.plant_stock == 25
    assert sam.balance == Decimal("0.0")


def test_a_team_order_gets_the_same_rules_as_the_customers_own(
    world: SimpleNamespace,
) -> None:
    """Selling at the counter does not get around the pending-order rule."""
    sign_in_as_team(world.system)
    with pytest.raises(OrderNotAllowedError, match="one pending order"):
        world.system.place_order(world.sam, [(world.rose, 1)])


# ---------- Cancelling, collecting, and paying ----------


def test_an_order_cannot_be_cancelled_after_a_payment(
    world: SimpleNamespace,
) -> None:
    """Stock and balance stay as they are when cancelling is refused."""
    nursery = world.system
    pay(nursery, world.sam_order, 10.00, day())
    stock = world.rose.plant_stock
    with pytest.raises(OrderCannotBeCancelledError, match="paid toward"):
        nursery.cancel_order(world.sam_order)
    assert world.rose.plant_stock == stock
    assert world.sam.balance == world.sam_order.order_total - Decimal("10.00")


def test_a_community_order_is_not_collected_until_paid(
    world: SimpleNamespace,
) -> None:
    """Staff may collect while owing, but community customers may not."""
    nursery = world.system
    with pytest.raises(OrderCannotBeCollectedError, match="pay an order"):
        nursery.collect_order(world.sam_order)
    pay(nursery, world.sam_order, world.sam_order.remaining_balance, day())
    nursery.collect_order(world.sam_order)
    assert world.sam_order.order_status == "collected"

    nursery.collect_order(world.avril_order)
    assert world.avril_order.order_status == "collected"
    assert world.avril.balance > 0


def test_payments_are_checked_against_the_order(
    world: SimpleNamespace,
) -> None:
    """A payment must be for the order's own customer, and not too large."""
    nursery = world.system
    wrong_customer = DebitCardPayment(
        world.avril, world.sam_order, 5.00, "1111222233334444", "ANZ"
    )
    with pytest.raises(ValueError, match="customer on the order"):
        nursery.record_payment(wrong_customer)

    too_much = DebitCardPayment(
        world.sam,
        world.sam_order,
        world.sam_order.order_total + Decimal("0.01"),
        "1111222233334444",
        "ANZ",
    )
    with pytest.raises(OverpaymentError, match="still owed"):
        nursery.record_payment(too_much)
    assert world.sam_order.amount_paid == Decimal("0.0")


def test_only_the_last_four_card_digits_reach_the_database(
    world: SimpleNamespace, memory_session: Session
) -> None:
    """The saved payment row has no full card number in any column."""
    nursery = world.system
    nursery.record_payment(
        DebitCardPayment(
            world.sam,
            world.sam_order,
            10.00,
            "1111 2222 3333 4444",
            "ANZ",
            day(),
        )
    )
    nursery.record_payment(
        CreditCardPayment(
            world.sam,
            world.sam_order,
            10.00,
            "5555-6666-7777-8888",
            "12-28",
            day(),
        )
    )
    memory_session.flush()

    rows = memory_session.execute(
        text("SELECT * FROM payments ORDER BY created_at")
    ).mappings().all()
    assert [row["card_last4"] for row in rows] == ["4444", "8888"]
    assert "card_number" not in rows[0].keys()
    saved = " ".join(str(value) for row in rows for value in row.values())
    for whole in ("1111222233334444", "5555666677778888"):
        assert whole not in saved
    # A receipt is built without the card number, and still has everything.
    first = nursery.get_order_payments(world.sam_order)[0]
    assert nursery.receipt_for(first).amount == Decimal("10.00")


def test_a_cancelled_order_cannot_be_paid(world: SimpleNamespace) -> None:
    """A cancelled order says it was cancelled. It does not say the payment
    was too large."""
    nursery = world.system
    nursery.cancel_order(world.sam_order)
    with pytest.raises(OrderNotPayableError, match="has been cancelled"):
        pay(nursery, world.sam_order, 1.00, day())
    assert world.sam_order.amount_paid == Decimal("0.0")


def test_a_fully_paid_order_cannot_be_paid_again(
    world: SimpleNamespace,
) -> None:
    """Once the balance is nil the order says it is paid in full, and the
    customer's balance is not reduced a second time."""
    nursery = world.system
    pay(nursery, world.sam_order, world.sam_order.remaining_balance, day())
    owed_after_paying = world.sam.balance

    with pytest.raises(OrderNotPayableError, match="paid in full"):
        pay(nursery, world.sam_order, 1.00, day())
    assert world.sam.balance == owed_after_paying


def test_overpaying_names_what_is_still_owed(world: SimpleNamespace) -> None:
    """An order part-paid by $10.00 says how much is left."""
    nursery = world.system
    pay(nursery, world.sam_order, 10.00, day())
    left = world.sam_order.remaining_balance

    with pytest.raises(OverpaymentError, match=rf"\${left:.2f}"):
        pay(nursery, world.sam_order, left + Decimal("0.01"), day())
    # Paying exactly what is left is still fine.
    pay(nursery, world.sam_order, left, day())
    assert world.sam_order.remaining_balance == Decimal("0.0")


def test_orders_waiting_seven_days_are_listed(system: NurserySystem) -> None:
    """Only pending orders at least seven days old need a follow-up."""
    plant = add_plant(system)
    avril = add_customer(system, StaffCustomer, "Avril")
    old = system.place_order(avril, [(plant, 1)], day(7))
    system.place_order(avril, [(plant, 1)], day(6))
    collected = system.place_order(avril, [(plant, 1)], day(30))
    system.collect_order(collected)

    assert system.orders_uncollected_for_seven_days() == [old]


# ---------- Removing plants and customers ----------


def test_a_plant_that_is_on_an_order_cannot_be_removed(
    world: SimpleNamespace,
) -> None:
    """Even a cancelled order keeps its plant, so history stays readable."""
    nursery = world.system
    with pytest.raises(PlantInUseError, match="has been ordered"):
        nursery.remove_plant(world.rose)

    nursery.cancel_order(world.sam_order)
    nursery.collect_order(world.avril_order)
    with pytest.raises(PlantInUseError, match="has been ordered"):
        nursery.remove_plant(world.rose)
    assert world.rose in nursery.search_plants()


def test_a_plant_that_was_never_ordered_can_be_removed(
    system: NurserySystem,
) -> None:
    """Removing it takes it out of the catalog."""
    fig = add_plant(system, "Fig")
    system.remove_plant(fig)
    with pytest.raises(ValueError, match="No plant found"):
        system.find_plant(fig.plant_id)
    assert system.search_plants() == []


def test_removing_a_plant_that_is_not_in_the_catalog_is_refused(
    system: NurserySystem,
) -> None:
    """A plant that was never added cannot be removed."""
    never_added = TreeAndShrub("Ghost", 5.00, 5, "ghost.png")
    with pytest.raises(ValueError, match="No plant found"):
        system.remove_plant(never_added)


def test_a_customer_who_has_ordered_cannot_be_removed(
    world: SimpleNamespace,
) -> None:
    """Even a cancelled order keeps the customer on record."""
    nursery = world.system
    with pytest.raises(CustomerInUseError, match="placed an order"):
        nursery.remove_customer(world.sam)

    nursery.cancel_order(world.sam_order)
    with pytest.raises(CustomerInUseError, match="placed an order"):
        nursery.remove_customer(world.sam)
    assert world.sam in nursery.filter_customers("community")


def test_removing_a_customer_also_removes_their_login(
    system: NurserySystem,
) -> None:
    """A customer who never ordered goes, and so does their way to log in."""
    tia = add_customer(system, CommunityCustomer, "Tia")
    system.remove_customer(tia)

    assert system.filter_customers("community") == []
    system.logout()
    with pytest.raises(LoginFailedError):
        system.login("tiaUser", PASSWORD)


def test_removing_a_customer_who_is_not_registered_is_refused(
    system: NurserySystem,
) -> None:
    """A customer who was never added cannot be removed."""
    stranger = CommunityCustomer("Ghost", cust_email="ghost@email.com")
    with pytest.raises(ValueError, match="No customer found"):
        system.remove_customer(stranger)


def test_customer_details_can_change_but_keep_one_way_to_contact(
    world: SimpleNamespace,
) -> None:
    """Swapping email for phone works, and a blank name is refused."""
    nursery = world.system
    nursery.update_customer(world.sam, " Samuel ", "", "021 555 0100")
    assert world.sam.cust_name == "Samuel"
    assert world.sam.cust_email is None
    assert world.sam.cust_phone == "021 555 0100"

    with pytest.raises(ValueError, match="Name is required"):
        nursery.update_customer(world.sam, "   ", "", "021 555 0100")
    with pytest.raises(ValueError, match="email or a phone"):
        nursery.update_customer(world.sam, "Samuel", "", "")


# ---------- Searching and the price bands ----------

PRICES = [
    Decimal(price)
    for price in (
        "0.01", "9.99", "10.00", "10.01", "29.99", "30.00", "30.01", "100.00"
    )
]


@pytest.fixture
def priced_plants(system: NurserySystem) -> dict[Decimal, Plant]:
    """
    Give a test one plant at each boundary price.

    :param system (NurserySystem): The system, logged in as the team
    :return (dict[Decimal, Plant]): The plants, by price
    """
    return {
        price: add_plant(system, f"Plant {price}", price=price, stock=5)
        for price in PRICES
    }


def band_limits(band: str) -> tuple[object, object]:
    """
    Read the price limits the search form turns a band into.

    :param band (str): under-10, 10-30, over-30, or something else
    :return (tuple[object, object]): The minimum and maximum price
    """
    with app.test_request_context(f"/plants?price_band={band}"):
        filters = search_filters()
    return filters["model_min"], filters["model_max"]


def test_each_price_band_turns_into_the_right_limits() -> None:
    """The search form's bands become the limits Brent described."""
    assert band_limits("under-10") == (None, Decimal("9.99"))
    assert band_limits("10-30") == (Decimal("10.00"), Decimal("30.00"))
    assert band_limits("over-30") == (Decimal("30.01"), None)
    assert band_limits("") == (None, None)
    assert band_limits("nonsense") == (None, None)


@pytest.mark.parametrize(
    ("price", "band"),
    [
        (Decimal("0.01"), "under-10"),
        (Decimal("9.99"), "under-10"),
        (Decimal("10.00"), "10-30"),
        (Decimal("10.01"), "10-30"),
        (Decimal("29.99"), "10-30"),
        (Decimal("30.00"), "10-30"),
        (Decimal("30.01"), "over-30"),
        (Decimal("100.00"), "over-30"),
    ],
)
def test_a_price_on_a_boundary_is_in_exactly_one_band(
    system: NurserySystem,
    priced_plants: dict[Decimal, Plant],
    price: Decimal,
    band: str,
) -> None:
    """$10.00 and $30.00 are in the middle band, and never in two bands."""
    found_in = []
    for name in ("under-10", "10-30", "over-30"):
        low, high = band_limits(name)
        matches = system.search_plants(min_price=low, max_price=high)
        if priced_plants[price] in matches:
            found_in.append(name)
    assert found_in == [band]


def test_price_limits_include_the_price_they_name(
    system: NurserySystem, priced_plants: dict[Decimal, Plant]
) -> None:
    """A search from $10 to $30 includes a plant at exactly $10 and $30."""
    found = system.search_plants(min_price=10.00, max_price=30.00)
    assert {plant.plant_price for plant in found} == {
        Decimal("10.00"),
        Decimal("10.01"),
        Decimal("29.99"),
        Decimal("30.00"),
    }


def test_search_rejects_a_backwards_range_and_an_unknown_type(
    system: NurserySystem,
) -> None:
    """A search that cannot make sense says so."""
    with pytest.raises(ValueError, match="Minimum price"):
        system.search_plants(min_price=30.00, max_price=10.00)
    with pytest.raises(ValueError, match="Plant type must be"):
        system.search_plants(plant_type="cacti")


def test_search_combines_name_type_price_and_stock(
    system: NurserySystem,
) -> None:
    """Every filter given has to match, and the name ignores letter case."""
    rose = add_plant(system, "Climbing Rose", price=15.99, stock=5)
    system.add_plant(Perennial("Rosemary", 4.50, 5, "rosemary.png"))
    system.add_plant(PotPlant("Fern", 8.00, 5, "fern.png", "small"))
    system.add_plant(VegetableSeedling("Tomato", 4.50, 5, "tomato.png"))
    sold_out = PotPlant("Rose Cactus", 6.00, 1, "cactus.png", "small")
    sold_out.reduce_stock(1)
    system.add_plant(sold_out)

    def names(found: list[Plant]) -> list[str]:
        """Return the plant names, sorted, so the order does not matter."""
        return sorted(plant.plant_name for plant in found)

    assert names(system.search_plants(name="ROSE")) == [
        "Climbing Rose",
        "Rose Cactus",
        "Rosemary",
    ]
    assert names(system.search_plants(name="rose", in_stock_only=True)) == [
        "Climbing Rose",
        "Rosemary",
    ]
    trees = system.search_plants(name="rose", plant_type="trees and shrubs")
    assert trees == [rose]
    assert names(system.search_plants(plant_type="pot plants")) == [
        "Fern",
        "Rose Cactus",
    ]
    assert names(system.search_plants(max_price=5.00)) == [
        "Rosemary",
        "Tomato",
    ]
    assert system.search_plants(name="orchid") == []


# ---------- Revenue periods ----------


@pytest.fixture
def big_order(system: NurserySystem) -> Order:
    """
    Give a test one large unpaid order that payments can be recorded against.

    :param system (NurserySystem): The system, logged in as the team
    :return (Order): A $1000.00 community order
    """
    plant = add_plant(system, "Tree", price=1000.00, stock=5)
    return system.place_order(add_customer(system), [(plant, 1)])


def pay_on(
    system: NurserySystem, order: Order, payments: dict[str, float]
) -> None:
    """
    Record a debit card payment on each date.

    :param system (NurserySystem): The system to record them on
    :param order (Order): The order being paid
    :param payments (dict[str, float]): Amount to pay, by payment date
    """
    for on, amount in payments.items():
        pay(system, order, amount, on)


def test_revenue_for_a_day_counts_only_that_day(
    system: NurserySystem, big_order: Order
) -> None:
    """The day before and the day after are left out."""
    pay_on(
        system,
        big_order,
        {"14-10-2025": 1, "15-10-2025": 10, "16-10-2025": 100},
    )
    assert system.revenue("day", "15-10-2025") == Decimal("10.00")


def test_revenue_for_a_week_is_seven_days_from_the_date(
    system: NurserySystem, big_order: Order
) -> None:
    """The date and the next six days count. The day before the date and the
    day after the seventh do not."""
    pay_on(
        system,
        big_order,
        {
            "14-10-2025": 1,
            "15-10-2025": 10,
            "21-10-2025": 100,
            "22-10-2025": 500,
        },
    )
    assert system.revenue("week", "15-10-2025") == Decimal("110.00")


def test_revenue_for_a_month_runs_from_the_first_to_the_last_day(
    system: NurserySystem, big_order: Order
) -> None:
    """The month containing the date counts, whatever day it is asked on."""
    pay_on(
        system,
        big_order,
        {
            "30-09-2025": 1,
            "01-10-2025": 10,
            "31-10-2025": 100,
            "01-11-2025": 200,
        },
    )
    assert system.revenue("month", "15-10-2025") == Decimal("110.00")
    assert system.revenue("month", "01-10-2025") == Decimal("110.00")
    assert system.revenue("month", "31-10-2025") == Decimal("110.00")


def test_revenue_for_a_month_handles_december_and_leap_years(
    system: NurserySystem, big_order: Order
) -> None:
    """The last day of December and of a leap February are included."""
    pay_on(
        system,
        big_order,
        {
            "31-12-2024": 10,
            "01-01-2025": 1,
            "28-02-2025": 20,
            "01-03-2025": 2,
            "29-02-2024": 30,
            "01-03-2024": 3,
        },
    )
    assert system.revenue("month", "01-12-2024") == Decimal("10.00")
    assert system.revenue("month", "10-02-2025") == Decimal("20.00")
    assert system.revenue("month", "10-02-2024") == Decimal("30.00")


def test_revenue_includes_the_card_surcharge(
    system: NurserySystem, big_order: Order
) -> None:
    """Revenue is what was charged, so a credit card adds 1.5%."""
    pay(system, big_order, 100.00, "15-10-2025", credit=True)
    pay(system, big_order, 100.00, "15-10-2025")
    assert system.revenue("day", "15-10-2025") == Decimal("201.50")


def test_revenue_with_nothing_paid_is_zero(system: NurserySystem) -> None:
    """A quiet period totals $0.00."""
    assert system.revenue("month", "15-10-2025") == Decimal("0.0")


def test_revenue_rejects_a_bad_period_or_date(system: NurserySystem) -> None:
    """The reason is given, not a crash."""
    with pytest.raises(ValueError, match="day, week, or month"):
        system.revenue("year", "15-10-2026")
    with pytest.raises(ValueError, match="DD-MM-YYYY"):
        system.revenue("day", "2026-10-15")
    with pytest.raises(ValueError, match="DD-MM-YYYY"):
        system.revenue("day", "31-02-2026")


# ---------- Receipts and reports ----------


@pytest.fixture
def forty_dollar_order(system: NurserySystem) -> Order:
    """
    Give a test a $40.00 community order that nothing has been paid toward.

    :param system (NurserySystem): The system, logged in as the team
    :return (Order): The order
    """
    plant = add_plant(system, "Orchid", price=40.00, stock=5)
    return system.place_order(add_customer(system), [(plant, 1)])


def test_an_earlier_receipt_still_shows_the_balance_at_that_time(
    system: NurserySystem, forty_dollar_order: Order
) -> None:
    """Later payments do not change what an earlier receipt says is left."""
    first = pay(system, forty_dollar_order, 10.00, "10-10-2025")
    second = pay(system, forty_dollar_order, 20.00, "10-10-2025", True)
    third = pay(system, forty_dollar_order, 10.00, "10-10-2025")

    assert system.receipt_for(first).remaining_on_order == Decimal("30.00")
    assert system.receipt_for(second).remaining_on_order == Decimal("10.00")
    assert system.receipt_for(third).remaining_on_order == Decimal("0.00")
    # The order itself now has nothing left, but the first receipt does not.
    assert forty_dollar_order.remaining_balance == Decimal("0.00")

    credit_receipt = system.receipt_for(second)
    assert credit_receipt.amount == Decimal("20.00")
    assert credit_receipt.surcharge == Decimal("0.30")
    assert credit_receipt.amount_charged == Decimal("20.30")
    assert credit_receipt.payment_type == "credit card"
    assert credit_receipt.order_number == forty_dollar_order.order_number


def test_receipts_follow_the_payment_date_not_the_order_entered(
    system: NurserySystem, forty_dollar_order: Order
) -> None:
    """A payment dated earlier counts first, even if it was entered later."""
    entered_first = pay(system, forty_dollar_order, 10.00, "05-10-2025")
    entered_second = pay(system, forty_dollar_order, 20.00, "01-10-2025")

    assert system.get_order_payments(forty_dollar_order) == [
        entered_second,
        entered_first,
    ]
    second_receipt = system.receipt_for(entered_second)
    first_receipt = system.receipt_for(entered_first)
    assert second_receipt.remaining_on_order == Decimal("20.00")
    assert first_receipt.remaining_on_order == Decimal("10.00")


def test_most_and_least_ordered_leave_out_cancelled_orders(
    system: NurserySystem,
) -> None:
    """Never-ordered plants count as 0, and ties are in name order."""
    # Cheap plants keep the staff customer under the $100 limit.
    rose = add_plant(system, "Rose", price=2.00, stock=50)
    lavender = add_plant(system, "Lavender", price=2.00, stock=50)
    daisy = add_plant(system, "Daisy", price=2.00, stock=50)
    cactus = add_plant(system, "Cactus", price=2.00, stock=50)
    avril = add_customer(system, StaffCustomer, "Avril")
    system.place_order(avril, [(rose, 5), (lavender, 2)])
    cancelled = system.place_order(avril, [(daisy, 9)])
    system.cancel_order(cancelled)

    most = [(plant.plant_name, n) for plant, n in system.most_ordered_plants()]
    least = [
        (plant.plant_name, n) for plant, n in system.least_ordered_plants()
    ]
    assert most == [("Rose", 5), ("Lavender", 2), ("Cactus", 0), ("Daisy", 0)]
    assert least == [("Cactus", 0), ("Daisy", 0), ("Lavender", 2), ("Rose", 5)]
    assert cactus.plant_stock == 50


def test_plant_history_includes_cancelled_orders_oldest_first(
    system: NurserySystem,
) -> None:
    """A plant's history lists every order it was on, in date order."""
    rose = add_plant(system, "Rose", stock=50)
    avril = add_customer(system, StaffCustomer, "Avril")
    newer = system.place_order(avril, [(rose, 1)], "10-10-2025")
    older = system.place_order(avril, [(rose, 1)], "01-10-2025")
    system.cancel_order(older)

    assert system.plant_order_history(rose) == [older, newer]


def test_customer_activity_lists_each_event_in_date_order(
    system: NurserySystem,
) -> None:
    """Placed, paid, collected, and cancelled all appear, oldest first."""
    plant = add_plant(system, "Rose", stock=50)
    avril = add_customer(system, StaffCustomer, "Avril")
    kept = system.place_order(avril, [(plant, 1)], "01-10-2025")
    dropped = system.place_order(avril, [(plant, 1)], "02-10-2025")
    system.cancel_order(dropped, "03-10-2025")
    pay(system, kept, 5.00, "04-10-2025")
    system.collect_order(kept, "05-10-2025")

    records = system.customer_activity(avril)
    assert [(r.happened_on, r.action) for r in records] == [
        (date(2025, 10, 1), "placed"),
        (date(2025, 10, 2), "placed"),
        (date(2025, 10, 3), "cancelled"),
        (date(2025, 10, 4), "paid"),
        (date(2025, 10, 5), "collected"),
    ]


def test_orders_can_be_filtered_by_status(world: SimpleNamespace) -> None:
    """The team sees every order with a status, and a bad status is refused."""
    nursery = world.system
    nursery.cancel_order(world.sam_order)

    assert nursery.filter_orders("cancelled") == [world.sam_order]
    assert nursery.filter_orders("pending") == [world.avril_order]
    assert nursery.filter_orders("collected") == []
    with pytest.raises(ValueError, match="pending, collected, or cancelled"):
        nursery.filter_orders("lost")


def test_customers_can_be_filtered_by_type(world: SimpleNamespace) -> None:
    """The team can list one type at a time."""
    nursery = world.system
    assert nursery.filter_customers("staff") == [world.avril]
    assert nursery.filter_customers("community") == [world.sam]
    assert nursery.filter_customers("student") == []
    with pytest.raises(ValueError, match="staff, student, or community"):
        nursery.filter_customers("visitor")


def test_plant_price_and_stock_are_updated_separately(
    system: NurserySystem,
) -> None:
    """A sold-out plant can be repriced, and a restock cannot be 0."""
    sold_out = PotPlant("Cactus", 6.00, 1, "cactus.png", "small")
    sold_out.reduce_stock(1)
    system.add_plant(sold_out)

    system.update_plant_price(sold_out, 7.50)
    assert sold_out.plant_price == Decimal("7.50")
    assert sold_out.plant_stock == 0

    with pytest.raises(ValueError, match="greater than 0"):
        system.update_plant_stock(sold_out, 0)
    system.update_plant_stock(sold_out, 12)
    assert sold_out.plant_stock == 12
    assert sold_out.plant_price == Decimal("7.50")
