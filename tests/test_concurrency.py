"""
Integration tests for two people working at the same time.

Each test opens two separate database sessions, the way two staff at two
screens would. The first session places an order and holds its changes open.
The second session tries to place a conflicting order from another thread. It
has to wait for the first to finish, and then see what the first one did.
"""

import threading
import uuid
from decimal import Decimal
from typing import Callable, Optional

import pytest
from flask.testing import FlaskClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from model.customer import CommunityCustomer
from model.database import SessionLocal, session_scope
from model.exceptions import (
    InsufficientStockError,
    OrderNotAllowedError,
    OverpaymentError,
)
from model.nursery_system import NurserySystem
from model.order import Order
from model.plant import Plant, TreeAndShrub

# How long to let the second session try before checking that it is waiting.
WAIT_SECONDS = 0.7
# The most any step may take. Only reached if something is stuck.
GIVE_UP_SECONDS = 15


def team_system() -> tuple[NurserySystem, object]:
    """
    Open a new session and log the nursery team in on it.

    :return (tuple[NurserySystem, object]): The system and its open session
    """
    session = SessionLocal()
    system = NurserySystem(session)
    system.login("teamUsername", "TeamPassword")
    return system, session


class Attempt:
    """The outcome of an action run on its own thread."""

    def __init__(self, action: Callable[[], None]) -> None:
        """
        Start the action on a new thread.

        :param action (Callable[[], None]): What to run
        """
        self.error: Optional[BaseException] = None
        self.finished = threading.Event()
        self.__action = action
        self.__thread = threading.Thread(target=self.__run, daemon=True)
        self.__thread.start()

    def __run(self) -> None:
        """Run the action and keep any error for the test to look at."""
        try:
            self.__action()
        except BaseException as error:  # noqa: BLE001
            self.error = error
        finally:
            self.finished.set()

    def is_waiting(self) -> bool:
        """
        Return whether the action is still running after a short wait.

        :return (bool): True if it has not finished
        """
        return not self.finished.wait(WAIT_SECONDS)

    def wait(self) -> None:
        """
        Wait for the action to finish.

        :raises AssertionError: If it never finishes
        """
        assert self.finished.wait(GIVE_UP_SECONDS), "The second order is stuck"


def sample_nursery(plant_stock: int) -> dict[str, uuid.UUID]:
    """
    Store a team login, one plant, and two community customers.

    :param plant_stock (int): Stock of the plant
    :return (dict[str, uuid.UUID]): The ids of the plant and the customers
    """
    with session_scope() as session:
        system = NurserySystem(session)
        system.add_user("teamUsername", "TeamPassword", "team")
        system.login("teamUsername", "TeamPassword")
        rose = TreeAndShrub("Rose", 15.99, plant_stock, "rose.png")
        system.add_plant(rose)
        sam = CommunityCustomer("Sam", cust_email="sam@email.com")
        tia = CommunityCustomer("Tia", cust_email="tia@email.com")
        system.add_customer(sam)
        system.add_customer(tia)
        return {
            "rose": rose.plant_id,
            "sam": sam.cust_id,
            "tia": tia.cust_id,
        }


def place(
    system: NurserySystem,
    customer_id: uuid.UUID,
    plant_id: uuid.UUID,
    quantity: int,
) -> Order:
    """
    Place an order for one plant through a system's own session.

    :param system (NurserySystem): The system to use
    :param customer_id (uuid.UUID): The customer ordering
    :param plant_id (uuid.UUID): The plant ordered
    :param quantity (int): How many
    :return (Order): The new order
    """
    customer = system.find_customer(customer_id)
    plant = system.find_plant(plant_id)
    return system.place_order(customer, [(plant, quantity)])


def test_last_plant_cannot_be_sold_to_two_people(fresh_database: None) -> None:
    """
    Two staff order the last plant at the same moment. The second has to wait,
    and is then told there is no stock, so stock never goes below zero.
    """
    ids = sample_nursery(plant_stock=1)

    first, first_session = team_system()
    second, second_session = team_system()
    try:
        place(first, ids["sam"], ids["rose"], 1)

        late = Attempt(lambda: place(second, ids["tia"], ids["rose"], 1))
        # The first order is not saved yet, so the second must be waiting
        # for it rather than reading the old stock of 1.
        assert late.is_waiting()

        first_session.commit()
        late.wait()
        assert isinstance(late.error, InsufficientStockError)
        assert "only 0 available" in str(late.error)
    finally:
        second_session.rollback()
        second_session.close()
        first_session.close()

    with session_scope() as session:
        system = NurserySystem(session)
        system.login("teamUsername", "TeamPassword")
        assert system.find_plant(ids["rose"]).plant_stock == 0
        assert len(system.history.order_list) == 1


def test_stock_taken_by_both_orders_is_counted(fresh_database: None) -> None:
    """
    Two staff order from a plant with enough for both. Neither order's
    reduction is lost, even though they overlap.
    """
    ids = sample_nursery(plant_stock=10)

    first, first_session = team_system()
    second, second_session = team_system()
    try:
        place(first, ids["sam"], ids["rose"], 3)
        late = Attempt(lambda: place(second, ids["tia"], ids["rose"], 4))
        assert late.is_waiting()

        first_session.commit()
        late.wait()
        assert late.error is None
        second_session.commit()
    finally:
        second_session.close()
        first_session.close()

    with session_scope() as session:
        system = NurserySystem(session)
        system.login("teamUsername", "TeamPassword")
        # 10 - 3 - 4. Without a lock the second order would start from 10 and
        # leave 6, so three plants would be sold twice.
        assert system.find_plant(ids["rose"]).plant_stock == 3
        assert len(system.history.order_list) == 2


def test_community_customer_cannot_get_two_pending_orders(
    fresh_database: None,
) -> None:
    """
    The same community customer is served at two screens at once. The second
    order is refused because the first is now pending.
    """
    ids = sample_nursery(plant_stock=10)

    first, first_session = team_system()
    second, second_session = team_system()
    try:
        place(first, ids["sam"], ids["rose"], 1)
        late = Attempt(lambda: place(second, ids["sam"], ids["rose"], 1))
        assert late.is_waiting()

        first_session.commit()
        late.wait()
        assert isinstance(late.error, OrderNotAllowedError)
    finally:
        second_session.rollback()
        second_session.close()
        first_session.close()

    with session_scope() as session:
        system = NurserySystem(session)
        system.login("teamUsername", "TeamPassword")
        assert len(system.history.order_list) == 1
        assert system.find_plant(ids["rose"]).plant_stock == 9


def test_two_payments_cannot_both_overpay_an_order(
    fresh_database: None,
) -> None:
    """
    Two payments for the same order arrive together. Together they are more
    than is owed, so the second is refused after the first is saved.
    """
    from model.payment import DebitCardPayment

    ids = sample_nursery(plant_stock=5)
    with session_scope() as session:
        system = NurserySystem(session)
        system.login("teamUsername", "TeamPassword")
        order = place(system, ids["sam"], ids["rose"], 1)
        order_id = order.order_id

    def pay(system: NurserySystem, amount: float) -> None:
        """Take a debit card payment for the order, through one session."""
        order = system.find_order(order_id)
        system.record_payment(
            DebitCardPayment(
                order.customer, order, amount, "1111222233334444", "ANZ"
            )
        )

    first, first_session = team_system()
    second, second_session = team_system()
    try:
        pay(first, 10.00)
        late = Attempt(lambda: pay(second, 10.00))
        assert late.is_waiting()

        first_session.commit()
        late.wait()
        # $15.99 is owed. The first $10.00 leaves $5.99, so a second $10.00
        # is more than what is still owed.
        assert isinstance(late.error, OverpaymentError)
        assert "still owed" in str(late.error)
    finally:
        second_session.rollback()
        second_session.close()
        first_session.close()

    with session_scope() as session:
        system = NurserySystem(session)
        system.login("teamUsername", "TeamPassword")
        stored = system.find_order(order_id)
        assert stored.amount_paid == Decimal("10.00")
        assert stored.customer.balance == Decimal("5.99")


def test_failed_save_is_reported_not_hidden(
    client: FlaskClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    If the database refuses the final save of a request, the person is told
    and nothing is kept. They are not shown a success message for a record
    that was never stored.
    """
    with session_scope() as session:
        NurserySystem(session).add_user("teamUsername", "TeamPassword", "team")
    client.post(
        "/login",
        data={"username": "teamUsername", "password": "TeamPassword"},
    )

    real_commit = Session.commit
    attempts = {"count": 0}

    def refuse_once(self: Session) -> None:
        """Fail the first save, then behave normally."""
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise OperationalError("COMMIT", {}, Exception("save refused"))
        real_commit(self)

    monkeypatch.setattr(Session, "commit", refuse_once)
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
        headers={"Referer": "http://localhost/customers/new"},
        follow_redirects=True,
    )
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "nothing was saved" in html
    assert "Sam added." not in html

    monkeypatch.undo()
    with session_scope() as session:
        system = NurserySystem(session)
        system.login("teamUsername", "TeamPassword")
        assert system.directory.customer_list == []


@pytest.mark.parametrize("quantity", [2])
def test_database_refuses_negative_stock_as_a_last_resort(
    fresh_database: None, quantity: int
) -> None:
    """
    If stock somehow went below zero, the database check stops it and the
    system reports it as a stock problem rather than a database error.
    """
    ids = sample_nursery(plant_stock=1)
    system, session = team_system()
    try:
        plant: Plant = system.find_plant(ids["rose"])
        # Bypass the model's own check to reach the database check.
        plant._plant_stock = -quantity
        with pytest.raises(InsufficientStockError, match="stock"):
            system.save_changes()
    finally:
        session.rollback()
        session.close()
