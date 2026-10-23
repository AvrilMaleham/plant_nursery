"""
Tests for how the data is stored.

These check that the database itself refuses bad data, instead of relying on
the Python code to have checked first, that real dates and cents are stored,
that every foreign key has an index, and that the date filtering and sorting
is done by the database. They use the throwaway in-memory database, so they
need no PostgreSQL server.
"""

from collections.abc import Callable, Iterator
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import Date, DateTime, Numeric, event, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from model.customer import CommunityCustomer, Customer, StaffCustomer
from model.order import Order
from model.order_history import OrderHistory
from model.order_item import OrderItem
from model.payment import DebitCardPayment
from model.payment_history import PaymentHistory
from model.plant import TreeAndShrub

# ---------- Helpers ----------


def make_order(
    session: Session,
    quantity: int = 2,
    order_date: str | None = None,
    customer: Customer | None = None,
    plant: TreeAndShrub | None = None,
) -> Order:
    """
    Save an order for a customer and a plant, making them when not given.

    :param session (Session): The session to save in
    :param quantity (int): How many of the plant
    :param order_date (str | None): The order date, or None for today
    :param customer (Customer | None): The customer, or None for a new
        community customer
    :param plant (TreeAndShrub | None): The plant, or None for a new one
    :return (Order): The saved order
    """
    customer = customer or CommunityCustomer("Sam", cust_email="sam@email.com")
    plant = plant or TreeAndShrub("Rose", 15.99, 50, "rose.png")
    order = Order(customer, [(plant, quantity)], order_date)
    session.add_all([customer, plant, order])
    session.flush()
    return order


def make_payment(
    session: Session, order: Order, paid_on: str, amount: float = 5.00
) -> DebitCardPayment:
    """
    Save a debit card payment on an order.

    :param session (Session): The session to save in
    :param order (Order): The order being paid
    :param paid_on (str): The payment date in DD-MM-YYYY form
    :param amount (float): The amount
    :return (DebitCardPayment): The saved payment
    """
    payment = DebitCardPayment(
        order.customer, order, amount, "1111222233334444", "ANZ", paid_on
    )
    session.add(payment)
    session.flush()
    return payment


@pytest.fixture
def statements(memory_session: Session) -> Iterator[list[str]]:
    """
    Collect the SQL the database is sent while a test runs.

    :param memory_session (Session): The session whose engine is watched
    :return (Iterator[list[str]]): The statements sent so far
    """
    seen: list[str] = []

    def record(connection, cursor, statement, *_rest) -> None:  # type: ignore
        """Remember one statement."""
        seen.append(statement)

    engine = memory_session.get_bind()
    event.listen(engine, "before_cursor_execute", record)
    yield seen
    event.remove(engine, "before_cursor_execute", record)


# ---------- The database refuses bad data ----------


def spoil_quantity(order: Order) -> None:
    """Put a quantity of 0 on a line."""
    order.items[0]._quantity = 0


def spoil_cost(order: Order) -> None:
    """Put a cost of 0 on a line."""
    order.items[0]._item_cost = Decimal("0.00")


def overpay(order: Order) -> None:
    """Record one cent more than the order came to."""
    order._amount_paid = order._order_total + Decimal("0.01")


def collect_without_a_date(order: Order) -> None:
    """Make an order collected but leave no collection date."""
    order._order_status = "collected"


def date_without_collecting(order: Order) -> None:
    """Give a pending order a collection date."""
    order._collected_date = date(2025, 10, 1)


def cancel_without_a_date(order: Order) -> None:
    """Make an order cancelled but leave no cancellation date."""
    order._order_status = "cancelled"


def date_without_cancelling(order: Order) -> None:
    """Give a pending order a cancellation date."""
    order._cancelled_date = date(2025, 10, 1)


@pytest.mark.parametrize(
    ("spoil", "constraint"),
    [
        (spoil_quantity, "ck_order_items_quantity"),
        (spoil_cost, "ck_order_items_cost"),
        (overpay, "ck_orders_not_overpaid"),
        (collect_without_a_date, "ck_orders_collected_date"),
        (date_without_collecting, "ck_orders_collected_date"),
        (cancel_without_a_date, "ck_orders_cancelled_date"),
        (date_without_cancelling, "ck_orders_cancelled_date"),
    ],
)
def test_the_database_refuses_an_order_that_breaks_a_rule(
    memory_session: Session,
    spoil: Callable[[Order], None],
    constraint: str,
) -> None:
    """The model checks these first. These write the bad value past the model
    to show the database says no even so, and names the rule."""
    order = make_order(memory_session)

    spoil(order)
    with pytest.raises(IntegrityError, match=constraint):
        memory_session.flush()


def test_the_database_refuses_the_same_plant_twice_on_one_order(
    memory_session: Session,
) -> None:
    """A plant is one line on an order, whatever the code does."""
    order = make_order(memory_session)
    plant = order.items[0].plant

    order._items.append(OrderItem(plant, 1))
    with pytest.raises(IntegrityError, match="order_items"):
        memory_session.flush()


def test_an_order_paid_in_full_is_accepted(memory_session: Session) -> None:
    """The overpayment rule stops at the total. Paying exactly it is fine."""
    order = make_order(memory_session)

    order.record_payment(order.order_total)
    memory_session.flush()

    assert order.amount_paid == order.order_total


# ---------- Indexes ----------


def test_every_foreign_key_has_an_index_that_starts_with_it(
    memory_session: Session,
) -> None:
    """Joins and 'orders for this customer' go through the foreign key, so
    each one needs an index (or a unique constraint) that leads with it."""
    inspector = inspect(memory_session.get_bind())
    unindexed = []
    for table in inspector.get_table_names():
        covers = [
            index["column_names"] for index in inspector.get_indexes(table)
        ] + [
            unique["column_names"]
            for unique in inspector.get_unique_constraints(table)
        ]
        for key in inspector.get_foreign_keys(table):
            columns = key["constrained_columns"]
            if not any(cover[: len(columns)] == columns for cover in covers):
                unindexed.append(f"{table}.{', '.join(columns)}")

    assert unindexed == []


def test_the_report_columns_are_indexed(memory_session: Session) -> None:
    """Revenue and the follow-up list filter on these."""
    inspector = inspect(memory_session.get_bind())
    orders = {
        i["name"]: i["column_names"] for i in inspector.get_indexes("orders")
    }
    payments = {
        i["name"]: i["column_names"] for i in inspector.get_indexes("payments")
    }

    assert orders["ix_orders_status_order_date"] == [
        "order_status", "order_date"
    ]
    assert payments["ix_payments_payment_date"] == ["payment_date"]
    assert payments["ix_payments_order_id_when"] == [
        "order_id", "payment_date", "created_at"
    ]


# ---------- Column types ----------


@pytest.mark.parametrize(
    ("table", "column", "kind"),
    [
        ("orders", "order_date", Date),
        ("orders", "collected_date", Date),
        ("orders", "cancelled_date", Date),
        ("orders", "created_at", DateTime),
        ("payments", "payment_date", Date),
        ("payments", "created_at", DateTime),
        ("orders", "order_total", Numeric),
        ("orders", "amount_paid", Numeric),
        ("order_items", "item_cost", Numeric),
        ("payments", "amount", Numeric),
        ("plants", "plant_price", Numeric),
        ("customers", "balance", Numeric),
    ],
)
def test_dates_and_money_are_stored_as_dates_and_numbers(
    memory_session: Session, table: str, column: str, kind: type
) -> None:
    """No date is kept as DD-MM-YYYY text, and no amount as a float."""
    columns = {
        c["name"]: c["type"]
        for c in inspect(memory_session.get_bind()).get_columns(table)
    }

    assert isinstance(columns[column], kind)


def test_dates_come_back_as_dates_and_money_as_decimals(
    memory_session: Session,
) -> None:
    """What is read back is typed, not text or a float."""
    order = make_order(memory_session, order_date="05-10-2025")
    payment = make_payment(memory_session, order, "06-10-2025")
    memory_session.expire_all()

    assert order.order_date == date(2025, 10, 5)
    assert payment.payment_date == date(2025, 10, 6)
    assert isinstance(order.created_at, datetime)
    assert isinstance(order.order_total, Decimal)
    assert isinstance(payment.amount, Decimal)
    assert order.order_total == Decimal("31.98")


# ---------- The database does the filtering and sorting ----------


def test_payments_in_a_period_are_picked_by_the_database(
    memory_session: Session, statements: list[str]
) -> None:
    """Only the payments in the period come back, from a date comparison in
    SQL, not from loading every payment and parsing its text."""
    order = make_order(memory_session)
    before = make_payment(memory_session, order, "30-09-2025")
    first = make_payment(memory_session, order, "01-10-2025")
    last = make_payment(memory_session, order, "31-10-2025")
    make_payment(memory_session, order, "01-11-2025")
    statements.clear()

    found = PaymentHistory(memory_session).get_payments_between(
        date(2025, 10, 1), date(2025, 10, 31)
    )

    assert found == [first, last]
    assert before not in found
    assert "payment_date BETWEEN" in statements[-1]


def test_an_orders_payments_are_sorted_by_date_then_created_at(
    memory_session: Session, statements: list[str]
) -> None:
    """Payments on one day are told apart by created_at, and the database
    sorts them, so nothing depends on how the rows were stored."""
    order = make_order(memory_session)
    saved_first = make_payment(memory_session, order, "10-10-2025")
    saved_second = make_payment(memory_session, order, "10-10-2025")
    earlier_day = make_payment(memory_session, order, "09-10-2025")
    # Make the order they were entered in the opposite of the order they were
    # saved in, so only the column can explain the result.
    saved_first._created_at = saved_second.created_at + timedelta(seconds=5)
    memory_session.flush()
    statements.clear()

    found = PaymentHistory(memory_session).get_order_payments(order)

    assert found == [earlier_day, saved_second, saved_first]
    assert (
        "ORDER BY payments.payment_date, payments.created_at"
        in statements[-1]
    )


def test_orders_and_payments_are_listed_in_the_order_they_were_made(
    memory_session: Session,
) -> None:
    """The full lists are sorted by created_at, not left to the database's
    storage order."""
    customer = CommunityCustomer("Sam", cust_email="sam@email.com")
    plant = TreeAndShrub("Rose", 15.99, 50, "rose.png")
    first = make_order(memory_session, 1, customer=customer, plant=plant)
    second = make_order(memory_session, 1, customer=customer, plant=plant)
    first._created_at = second.created_at + timedelta(seconds=5)
    paid_second = make_payment(memory_session, first, "10-10-2025")
    paid_first = make_payment(memory_session, second, "10-10-2025")
    paid_second._created_at = paid_first.created_at + timedelta(seconds=5)
    memory_session.flush()

    assert OrderHistory(memory_session).order_list == [second, first]
    assert PaymentHistory(memory_session).payment_list == [
        paid_first, paid_second
    ]


def test_old_pending_orders_are_picked_by_the_database(
    memory_session: Session, statements: list[str]
) -> None:
    """Pending orders on or before the cutoff, oldest first. Collected
    orders and newer ones are left out by the query."""
    # Staff, who can collect an order without paying for it first.
    customer = StaffCustomer("Sam", cust_email="sam@email.com")
    plant = TreeAndShrub("Rose", 15.99, 50, "rose.png")
    on_cutoff = make_order(memory_session, 1, "10-10-2025", customer, plant)
    older = make_order(memory_session, 1, "01-10-2025", customer, plant)
    make_order(memory_session, 1, "11-10-2025", customer, plant)
    collected = make_order(memory_session, 1, "02-10-2025", customer, plant)
    collected.collect_order("03-10-2025")
    memory_session.flush()
    statements.clear()

    found = OrderHistory(memory_session).get_pending_orders_placed_by(
        date(2025, 10, 10)
    )

    assert found == [older, on_cutoff]
    assert collected not in found
    assert "order_date <=" in statements[-1]


def test_a_customers_orders_come_back_oldest_first(
    memory_session: Session,
) -> None:
    """Sorted by the real date, so 02-01-2026 is not before 10-12-2025 the way
    it would be as text sorted by its first digits."""
    customer = CommunityCustomer("Sam", cust_email="sam@email.com")
    plant = TreeAndShrub("Rose", 15.99, 50, "rose.png")
    january = make_order(memory_session, 1, "02-01-2026", customer, plant)
    december = make_order(memory_session, 1, "10-12-2025", customer, plant)
    other = make_order(memory_session, 1, "01-01-2020")

    history = OrderHistory(memory_session)

    assert history.get_customer_order_history(customer) == [
        december, january
    ]
    assert other not in history.get_customer_order_history(customer)


def test_quantities_are_added_up_by_the_database_without_cancelled_orders(
    memory_session: Session, statements: list[str]
) -> None:
    """Each plant's total comes from one grouped query."""
    customer = CommunityCustomer("Sam", cust_email="sam@email.com")
    rose = TreeAndShrub("Rose", 15.99, 50, "rose.png")
    fern = TreeAndShrub("Fern", 8.00, 50, "fern.png")
    make_order(memory_session, 2, None, customer, rose)
    make_order(memory_session, 3, None, customer, rose)
    cancelled = make_order(memory_session, 7, None, customer, fern)
    cancelled.cancel_order()
    memory_session.flush()
    statements.clear()

    totals = OrderHistory(memory_session).quantities_by_plant()

    assert totals == {rose.plant_id: 5}
    assert "GROUP BY" in statements[-1]


def test_the_pending_count_is_counted_by_the_database(
    memory_session: Session, statements: list[str]
) -> None:
    """A customer's pending orders are counted in SQL, not loaded and looped
    over."""
    # Staff, who can collect an order without paying for it first.
    customer = StaffCustomer("Sam", cust_email="sam@email.com")
    plant = TreeAndShrub("Rose", 15.99, 50, "rose.png")
    make_order(memory_session, 1, None, customer, plant)
    done = make_order(memory_session, 1, None, customer, plant)
    done.collect_order()
    make_order(memory_session, 1)
    memory_session.flush()
    statements.clear()

    assert OrderHistory(memory_session).get_pending_order_count(customer) == 1
    assert "count(" in statements[-1].lower()


def test_plants_and_customers_in_use_are_found_by_the_database(
    memory_session: Session,
) -> None:
    """The remove checks ask whether a row exists, whatever the order's
    status."""
    order = make_order(memory_session)
    order.cancel_order()
    other_plant = TreeAndShrub("Fern", 8.00, 5, "fern.png")
    other_customer = CommunityCustomer("Kim", cust_email="kim@email.com")
    memory_session.add_all([other_plant, other_customer])
    memory_session.flush()
    history = OrderHistory(memory_session)

    assert history.has_orders_for_plant(order.items[0].plant) is True
    assert history.has_orders_for_customer(order.customer) is True
    assert history.has_orders_for_plant(other_plant) is False
    assert history.has_orders_for_customer(other_customer) is False
    assert history.get_orders_for_plant(order.items[0].plant) == [order]
