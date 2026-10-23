import uuid
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from .customer import Customer
from .documents import ActivityRecord, Invoice, Receipt
from .exceptions import (
    LoginFailedError,
    NotAuthorisedError,
    OrderNotAllowedError,
)
from .order import Order
from .order_item import OrderItem
from .payment import Payment
from .plant import Plant
from .plant_catalog import PlantCatalog
from .customer_directory import CustomerDirectory
from .order_history import OrderHistory
from .payment_history import PaymentHistory
from .user import CUSTOMER_ROLE, TEAM_ROLE, User


class NurserySystem:
    """
    A central system class that manages the collections of plants, customers,
    orders, and payments, and is responsible for adding, searching, updating,
    and reporting across them. The collections are stored in the database.
    """

    def __init__(self, session: Session) -> None:
        """
        Initialise a new NurserySystem for an open database session.

        :param session (Session): The session that reads and writes the
            nursery tables
        """
        # The collections live here so the rest of the application talks to one object.
        # Orders can then only be created for plants and customers that are
        # already registered.
        self.__session = session
        self.__current_user: Optional[User] = None
        self.__catalog: PlantCatalog = PlantCatalog(session)
        self.__directory: CustomerDirectory = CustomerDirectory(session)
        self.__history: OrderHistory = OrderHistory(session)
        self.__payment_history: PaymentHistory = PaymentHistory(session)

    # ---------- Getters and Setters ----------

    @property
    def catalog(self) -> PlantCatalog:
        """
        Get the plant catalog

        :return (PlantCatalog): The plant catalog
        """
        return self.__catalog

    @property
    def directory(self) -> CustomerDirectory:
        """
        Get the customer directory

        :return (CustomerDirectory): The customer directory
        """
        return self.__directory

    @property
    def history(self) -> OrderHistory:
        """
        Get the order history

        :return (OrderHistory): The order history
        """
        return self.__history

    @property
    def payment_history(self) -> PaymentHistory:
        """
        Get the payment history

        :return (PaymentHistory): The payment history
        """
        return self.__payment_history

    @property
    def current_user(self) -> Optional[User]:
        """
        Get whoever is logged in

        :return (Optional[User]): The logged-in user, or None
        """
        return self.__current_user

    # ---------- Login Methods ----------

    def add_user(
        self,
        username: str,
        password: str,
        role: str,
        customer: Optional[Customer] = None,
    ) -> User:
        """
        Add a login. The first account has to be the team. After that, only
        the team can add one.

        :param username (str): Login name, unique
        :param password (str): The password as typed. It is stored as a hash
        :param role (str): Either team or customer
        :param customer (Optional[Customer]): The customer this login belongs
            to
        :return (User): The new login
        :raises NotAuthorisedError: If the first account is not the team, or
            a later account is added by someone who is not the team
        :raises ValueError: If the username is already in use, or a customer
            login is not linked to a registered customer
        """
        account_count = self.__session.scalar(
            select(func.count()).select_from(User)
        )
        if account_count == 0:
            if role != TEAM_ROLE:
                raise NotAuthorisedError(
                    "The first account must be the nursery team"
                )
        else:
            self.__require_team()

        if self.__find_user(username) is not None:
            raise ValueError("That username is already in use")
        if role == CUSTOMER_ROLE:
            if customer is None:
                raise ValueError(
                    "A customer login must be linked to a customer"
                )
            self.__require_registered_customer(customer)

        user = User(username, password, role, customer)
        self.__session.add(user)
        return user

    def login(self, username: str, password: str) -> User:
        """
        Log in with a username and password

        :param username (str): Login name
        :param password (str): The password as typed
        :return (User): The logged-in user
        :raises LoginFailedError: If the username and password do not match
        """
        user = self.__find_user(username)
        # One message covers a missing username and a wrong password, so a
        # caller cannot tell which of the two was wrong.
        if user is None or not user.check_password(password):
            raise LoginFailedError()
        self.__current_user = user
        return user

    def logout(self) -> None:
        """Log out the current user"""
        self.__current_user = None

    def resume(self, user_id: uuid.UUID) -> bool:
        """
        Continue an existing login without asking for the password again.

        A controller keeps the user id after login. The next request calls
        this so later role checks still run as that person.

        :param user_id (uuid.UUID): The id of the person who logged in
        :return (bool): True if that login still exists
        """
        user = self.__session.get(User, user_id)
        if user is None:
            self.__current_user = None
            return False
        self.__current_user = user
        return True

    def __find_user(self, username: str) -> Optional[User]:
        """
        Find a login by username

        :param username (str): Login name
        :return (Optional[User]): The matching login, or None
        """
        return self.__session.scalar(
            select(User).where(User._username == username)
        )

    def __require_login(self) -> User:
        """
        Confirm someone is logged in

        :return (User): The logged-in user
        :raises NotAuthorisedError: If nobody is logged in
        """
        if self.__current_user is None:
            raise NotAuthorisedError("You need to log in first")
        return self.__current_user

    def __require_team(self) -> User:
        """
        Confirm the logged-in user is the nursery team

        :return (User): The logged-in team user
        :raises NotAuthorisedError: If nobody is logged in, or the user is a
            customer
        """
        user = self.__require_login()
        if user.role != TEAM_ROLE:
            raise NotAuthorisedError("Only the nursery team can do that")
        return user

    def __require_self_or_team(self, customer: Customer) -> None:
        """
        Confirm the logged-in user is the team, or this customer

        :param customer (Customer): The customer the action is about
        :raises NotAuthorisedError: If a customer tries to act for someone else
        """
        user = self.__require_login()
        if user.role == TEAM_ROLE:
            return
        linked = user.customer
        if linked is None or linked.cust_id != customer.cust_id:
            raise NotAuthorisedError(
                "You can only do that for your own account"
            )

    def __require_known_order(self, order: Order) -> Order:
        """
        Confirm the order is in this nursery, matching by ID

        :param order (Order): The order to look up
        :return (Order): The stored order
        :raises ValueError: If the order is not in the system
        """
        for existing in self.__history.order_list:
            if existing.order_id == order.order_id:
                return existing
        raise ValueError("Order is not in the system")

    def __payments_in_time_order(self, order: Order) -> list[Payment]:
        """
        Return the payments on an order, earliest first.

        Payments on the same date stay in the order they were recorded.

        :param order (Order): The order the payments belong to
        :return (list[Payment]): Payments from first to last
        """
        payments = self.__payment_history.get_order_payments(order)
        recorded = {
            payment_id: index
            for index, payment_id in enumerate(
                self.__session.scalars(
                    select(Payment._payment_id)
                    .where(Payment._order_id == order.order_id)
                    .order_by(text("ctid"))
                )
            )
        }
        payments.sort(
            key=lambda payment: (
                self.__parse_date(payment.payment_date),
                recorded.get(payment.payment_id, 0),
            )
        )
        return payments

    def __parse_date(self, value: str) -> date:
        """
        Parse a DD-MM-YYYY date

        :param value (str): Date string
        :return (date): The parsed date
        :raises ValueError: If the date is not a real DD-MM-YYYY date
        """
        try:
            return datetime.strptime(value, "%d-%m-%Y").date()
        except ValueError:
            raise ValueError("Date must be in DD-MM-YYYY format") from None

    # ---------- Plant Methods ----------

    def add_plant(self, plant: Plant) -> None:
        """
        Add a new plant to the catalog

        :param plant (Plant): Plant to add
        :raises NotAuthorisedError: If the user is not the nursery team
        :raises TypeError: If plant is not a Plant object
        :raises ValueError: If a plant with the same ID already exists
        """
        self.__require_team()
        self.__catalog.catalog_plant(plant)

    def remove_plant(self, plant: Plant) -> None:
        """
        Remove a plant that has never been ordered

        :param plant (Plant): Plant to remove
        :raises NotAuthorisedError: If the user is not the nursery team
        :raises ValueError: If the plant is not in the catalog, or it is on
            an order
        """
        self.__require_team()
        stored = self.find_plant(plant.plant_id)
        for order in self.__history.order_list:
            for item in order.items:
                if item.plant.plant_id == stored.plant_id:
                    raise ValueError(
                        "Cannot remove a plant that has been ordered"
                    )
        self.__session.delete(stored)

    def update_plant_price(self, plant: Plant, price: float) -> None:
        """
        Change the price of a plant in the catalog

        :param plant (Plant): Plant to reprice
        :param price (float): New price, must be greater than 0
        :raises NotAuthorisedError: If the user is not the nursery team
        :raises ValueError: If the plant is not in the catalog, or the price
            is not greater than 0
        """
        self.__require_team()
        stored = self.find_plant(plant.plant_id)
        stored.plant_price = price

    def update_plant_stock(self, plant: Plant, stock: int) -> None:
        """
        Restock a plant. Stock still cannot be set to 0 here; it reaches 0
        only when an order uses the last of it.

        :param plant (Plant): Plant to restock
        :param stock (int): New stock, must be greater than 0
        :raises NotAuthorisedError: If the user is not the nursery team
        :raises ValueError: If the plant is not in the catalog, or stock is
            not greater than 0
        """
        self.__require_team()
        stored = self.find_plant(plant.plant_id)
        stored.plant_stock = stock

    def search_plants(
        self,
        name: Optional[str] = None,
        plant_type: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        in_stock_only: bool = False,
    ) -> list[Plant]:
        """
        Search the catalog by common name and optional filters

        :param name (Optional[str]): Part of the common name. Matching ignores
            letter case
        :param plant_type (Optional[str]): trees and shrubs, perennials, pot
            plants, or vegetable seedlings
        :param min_price (Optional[float]): Lowest price to include
        :param max_price (Optional[float]): Highest price to include
        :param in_stock_only (bool): When true, plants with no stock are left
            out
        :return (list[Plant]): Plants that match every filter that was set
        :raises NotAuthorisedError: If nobody is logged in
        :raises ValueError: If the type is unknown, or the price range is
            backwards
        """
        self.__require_login()
        allowed_types = (
            "trees and shrubs",
            "perennials",
            "pot plants",
            "vegetable seedlings",
        )
        if plant_type is not None and plant_type not in allowed_types:
            raise ValueError(
                "Plant type must be trees and shrubs, perennials, "
                "pot plants, or vegetable seedlings"
            )
        if (
            min_price is not None
            and max_price is not None
            and min_price > max_price
        ):
            raise ValueError("Minimum price cannot be above maximum price")

        matches = []
        for plant in self.__catalog.plant_list:
            if name and name.casefold() not in plant.plant_name.casefold():
                continue
            if plant_type is not None and plant.plant_type() != plant_type:
                continue
            if min_price is not None and plant.plant_price < min_price:
                continue
            if max_price is not None and plant.plant_price > max_price:
                continue
            if in_stock_only and plant.plant_stock <= 0:
                continue
            matches.append(plant)
        return matches

    def find_plant(self, plant_id: uuid.UUID) -> Plant:
        """
        Search for a plant by its ID

        :param plant_id (uuid.UUID): The UUID of the plant to find
        :return (Plant): The matching Plant object
        :raises NotAuthorisedError: If nobody is logged in
        :raises ValueError: If no plant with that ID is found
        """
        self.__require_login()
        for plant in self.__catalog.plant_list:
            # Search is by ID because plant names are not unique (two batches
            # can share a name).
            if plant.plant_id == plant_id:
                return plant
        raise ValueError(f"No plant found with ID {plant_id}")

    def display_all_plants(self) -> None:
        """
        Print a readable list of every plant in the catalog

        :raises NotAuthorisedError: If nobody is logged in
        """
        self.__require_login()
        self.__catalog.display_all_plants()

    def get_available_plants(self) -> list[Plant]:
        """
        Return plants that currently have stock available to sell

        :return (list[Plant]): A list of Plant objects with current stock
            greater than 0
        :raises NotAuthorisedError: If nobody is logged in
        """
        self.__require_login()
        return self.__catalog.get_available_plants()

    def display_available_plants(self) -> None:
        """
        Print a readable list of plants with non-zero current stock

        :raises NotAuthorisedError: If nobody is logged in
        """
        self.__require_login()
        self.__catalog.display_available_plants()

    # ---------- Customer Methods ----------

    def add_customer(self, customer: Customer) -> None:
        """
        Add a new customer to the directory

        :param customer (Customer): Customer to add
        :raises NotAuthorisedError: If the user is not the nursery team
        :raises TypeError: If customer is not a Customer object
        :raises ValueError: If a customer with the same ID already exists
        """
        self.__require_team()
        self.__directory.add_customer(customer)

    def remove_customer(self, customer: Customer) -> None:
        """
        Remove a customer who has never placed an order

        :param customer (Customer): Customer to remove
        :raises NotAuthorisedError: If the user is not the nursery team
        :raises ValueError: If the customer is not registered, or they have
            an order
        """
        self.__require_team()
        stored = self.find_customer(customer.cust_id)
        for order in self.__history.order_list:
            if order.customer.cust_id == stored.cust_id:
                raise ValueError(
                    "Cannot remove a customer who has placed an order"
                )
        linked_users = [
            user
            for user in self.__session.scalars(select(User)).all()
            if user.customer is not None
            and user.customer.cust_id == stored.cust_id
        ]
        for user in linked_users:
            self.__session.delete(user)
        self.__session.flush()
        self.__session.delete(stored)

    def filter_customers(self, customer_type: str) -> list[Customer]:
        """
        Return customers of one type

        :param customer_type (str): staff, student, or community
        :return (list[Customer]): Customers of that type
        :raises NotAuthorisedError: If the user is not the nursery team
        :raises ValueError: If the type is not staff, student, or community
        """
        self.__require_team()
        if customer_type not in ("staff", "student", "community"):
            raise ValueError(
                "Customer type must be staff, student, or community"
            )
        return [
            customer
            for customer in self.__directory.customer_list
            if customer.customer_type() == customer_type
        ]

    def find_customer(self, customer_id: uuid.UUID) -> Customer:
        """
        Search for a customer by their ID

        :param customer_id (uuid.UUID): The UUID of the customer to find
        :return (Customer): The matching Customer object
        :raises NotAuthorisedError: If the user is not the team and not this
            customer
        :raises ValueError: If no customer with that ID is found
        """
        for customer in self.__directory.customer_list:
            if customer.cust_id == customer_id:
                self.__require_self_or_team(customer)
                return customer
        raise ValueError(f"No customer found with ID {customer_id}")

    def __lookup_customer(self, customer_id: uuid.UUID) -> Customer:
        """
        Find a customer by ID without checking who is logged in

        :param customer_id (uuid.UUID): The UUID of the customer to find
        :return (Customer): The matching Customer object
        :raises ValueError: If no customer with that ID is found
        """
        for customer in self.__directory.customer_list:
            # Search is by ID because customer names are not unique.
            if customer.cust_id == customer_id:
                return customer
        raise ValueError(f"No customer found with ID {customer_id}")

    def __require_registered_customer(self, customer: Customer) -> None:
        """
        Confirm the customer is registered, matching by ID rather than object
        identity

        :param customer (Customer): The customer to look up
        :raises ValueError: If the customer is not registered in the system
        """
        # Lookup matches on ID, so a different Python object with the same ID
        # still counts as registered. The message here is the registration
        # error, separate from whether this user may see that customer.
        try:
            self.__lookup_customer(customer.cust_id)
        except ValueError:
            raise ValueError(
                "Customer is not registered in the system") from None

    def display_all_customers(self) -> None:
        """
        Print a readable list of every customer in the directory

        :raises NotAuthorisedError: If the user is not the nursery team
        """
        self.__require_team()
        self.__directory.display_all_customers()

    def display_staff_customers(self) -> None:
        """
        Print a readable list of staff customers

        :raises NotAuthorisedError: If the user is not the nursery team
        """
        self.__require_team()
        self.__directory.display_staff_customers()

    def display_student_customers(self) -> None:
        """
        Print a readable list of student customers

        :raises NotAuthorisedError: If the user is not the nursery team
        """
        self.__require_team()
        self.__directory.display_student_customers()

    def display_community_customers(self) -> None:
        """
        Print a readable list of community customers

        :raises NotAuthorisedError: If the user is not the nursery team
        """
        self.__require_team()
        self.__directory.display_community_customers()

    # ---------- Order Methods ----------

    def place_order(
        self,
        customer: Customer,
        items: list[tuple[Plant, int]],
        order_date: Optional[str] = None,
    ) -> Order:
        """
        Place a new order after validating the customer and plants are
        registered by ID. The customer's place-order rules are checked before
        the order is created. Stock is reduced immediately when the order is
        created.

        :param customer (Customer): The Customer placing the order
        :param items (list[tuple[Plant, int]]): A list of (plant, quantity)
            pairs to include on the order
        :param order_date (Optional[str]): Optional order date in DD-MM-YYYY
            format, defaults to today
        :return (Order): The newly created Order object
        :raises NotAuthorisedError: If the user is not the team and not this
            customer
        :raises ValueError: If customer or a plant is not registered, the same
            plant is listed twice, or the order date is invalid
        :raises OrderNotAllowedError: If the customer is not allowed to place
            an order
        :raises InsufficientStockError: If there is not enough stock for an
            item
        """
        # The team can order for a customer. A customer can only order for
        # themselves.
        self.__require_self_or_team(customer)
        # Registration is checked by ID rather than `customer in list` / `plant
        # in list`. That way a Customer or Plant with the same ID is accepted
        # even if it is not the exact same Python object that was originally
        # added.
        self.__require_registered_customer(customer)

        # Price the lines before the order is created. Creating it would
        # already reduce stock and add the total to the balance.
        seen_plant_ids = []
        items_subtotal = 0.0
        for plant, quantity in items:
            plant_found = False
            for existing_plant in self.__catalog.plant_list:
                if existing_plant.plant_id == plant.plant_id:
                    plant_found = True
                    break
            if not plant_found:
                raise ValueError("Plant is not registered in the system")
            if plant.plant_id in seen_plant_ids:
                raise ValueError("Each plant can only appear once on an order")
            seen_plant_ids.append(plant.plant_id)
            items_subtotal += OrderItem.line_cost(plant, quantity)
        order_total = customer.apply_discount(items_subtotal)

        # Staff and students are blocked when this order would take what they
        # owe over $100. Community customers are blocked by a pending order.
        pending_count = self.__history.get_pending_order_count(customer)
        if not customer.can_place_order(pending_count, order_total):
            if customer.customer_type() == "community":
                raise OrderNotAllowedError(
                    "Community customers may only have "
                    "one pending order at a time"
                )
            raise OrderNotAllowedError(
                "Staff and students cannot place an order that would "
                "take what they owe over $100"
            )

        # Creating the Order reduces stock and adds the total to the customer
        # balance.
        order = Order(customer, items, order_date)
        self.__history.add_order(order)
        return order

    def find_order(self, order_id: uuid.UUID) -> Order:
        """
        Search for an order by its ID

        :param order_id (uuid.UUID): The UUID of the order to find
        :return (Order): The matching Order object
        :raises NotAuthorisedError: If the user is not the team and not the
            customer on the order
        :raises ValueError: If no order with that ID is found
        """
        for order in self.__history.order_list:
            if order.order_id == order_id:
                self.__require_self_or_team(order.customer)
                return order
        raise ValueError(f"No order found with ID {order_id}")

    def collect_order(
        self,
        order: Order,
        collected_date: Optional[str] = None,
    ) -> None:
        """
        Mark an order as collected. Only the team can do this.

        :param order (Order): The Order to collect
        :param collected_date (Optional[str]): Collection date in DD-MM-YYYY
            format, defaults to today
        :raises NotAuthorisedError: If the user is not the nursery team
        :raises ValueError: If the order is not in the system
        :raises OrderCannotBeCollectedError: If the order cannot be collected
        """
        self.__require_team()
        stored = self.__require_known_order(order)
        # collect_order() on Order enforces the legal status change, this only
        # confirms the order belongs to this nursery first.
        stored.collect_order(collected_date)

    def cancel_order(
        self,
        order: Order,
        cancelled_date: Optional[str] = None,
    ) -> None:
        """
        Cancel a pending unpaid order, restore the stock, and take the total
        off the customer balance. A customer can cancel their own. The team
        can cancel one for them.

        :param order (Order): The Order to cancel
        :param cancelled_date (Optional[str]): Cancellation date in DD-MM-YYYY
            format, defaults to today
        :raises NotAuthorisedError: If the user is not the team and not the
            customer on the order
        :raises ValueError: If the order is not in the system
        :raises OrderCannotBeCancelledError: If the order cannot be cancelled
        """
        stored = self.__require_known_order(order)
        self.__require_self_or_team(stored.customer)
        # cancel_order() on Order restores stock if the order is still pending.
        stored.cancel_order(cancelled_date)

    def filter_orders(
        self,
        status: str,
        customer: Optional[Customer] = None,
    ) -> list[Order]:
        """
        Return orders with one status. The team can see everyone's. A customer
        can see their own.

        :param status (str): pending, collected, or cancelled
        :param customer (Optional[Customer]): Limit the list to this customer.
            Omit it to see every customer, which only the team can do
        :return (list[Order]): Orders with that status
        :raises NotAuthorisedError: If the user may not see those orders
        :raises ValueError: If the status is not pending, collected, or
            cancelled
        """
        if status not in ("pending", "collected", "cancelled"):
            raise ValueError(
                "Order status must be pending, collected, or cancelled"
            )
        if customer is None:
            self.__require_team()
            source = self.__history.order_list
        else:
            self.__require_self_or_team(customer)
            self.__require_registered_customer(customer)
            source = self.__history.get_customer_order_history(customer)
        return [order for order in source if order.order_status == status]

    def orders_uncollected_for_seven_days(self) -> list[Order]:
        """
        Return pending orders placed at least seven days ago

        :return (list[Order]): Orders the team and the customer still need to
            follow up
        :raises NotAuthorisedError: If the user is not the nursery team
        """
        self.__require_team()
        return [
            order
            for order in self.__history.order_list
            if order.is_uncollected_too_long()
        ]

    def get_customer_order_history(self, customer: Customer) -> list[Order]:
        """
        Retrieve all orders for a specific customer

        :param customer (Customer): The Customer to look up
        :return (list[Order]): A list of Order objects belonging to that
            customer
        :raises NotAuthorisedError: If the user is not the team and not this
            customer
        :raises ValueError: If customer is not registered in the system
        """
        self.__require_self_or_team(customer)
        self.__require_registered_customer(customer)
        return self.__history.get_customer_order_history(customer)

    def display_all_orders(self) -> None:
        """
        Print a readable list of every order on record

        :raises NotAuthorisedError: If the user is not the nursery team
        """
        self.__require_team()
        self.__history.display_all_orders()

    # ---------- Payment Methods ----------

    def record_payment(self, payment: Payment) -> None:
        """
        Record a payment toward an order. The amount is applied to the order
        and taken off the customer balance. A payment is accepted whenever the
        order still has a remaining balance.

        :param payment (Payment): The Payment to record
        :raises ValueError: If the customer or order is not in the system, the
            customer does not own the order, or the amount is more than what is
            still owed
        :raises NotAuthorisedError: If the user is not the team and not this
            customer
        """
        self.__require_self_or_team(payment.customer)
        self.__require_registered_customer(payment.customer)

        stored = self.__require_known_order(payment.order)

        if payment.customer.cust_id != stored.customer.cust_id:
            raise ValueError(
                "Payment customer must be the customer on the order")

        # record_payment() on Order enforces amount > 0 and not more than
        # remaining. The order is reduced by the amount paid, not by a card
        # surcharge.
        stored.record_payment(payment.amount)
        self.__payment_history.add_payment(payment)

    def find_payment(self, payment_id: uuid.UUID) -> Payment:
        """
        Search for a payment by its ID

        :param payment_id (uuid.UUID): The UUID of the payment to find
        :return (Payment): The matching Payment object
        :raises NotAuthorisedError: If the user is not the team and not the
            customer who paid
        :raises ValueError: If no payment with that ID is found
        """
        for payment in self.__payment_history.payment_list:
            if payment.payment_id == payment_id:
                self.__require_self_or_team(payment.customer)
                return payment
        raise ValueError(f"No payment found with ID {payment_id}")

    def get_customer_payments(self, customer: Customer) -> list[Payment]:
        """
        Retrieve all payments made by a specific customer

        :param customer (Customer): The Customer to look up
        :return (list[Payment]): A list of Payment objects belonging to that
            customer
        :raises NotAuthorisedError: If the user is not the team and not this
            customer
        :raises ValueError: If customer is not registered in the system
        """
        self.__require_self_or_team(customer)
        self.__require_registered_customer(customer)
        return self.__payment_history.get_customer_payments(customer)

    def get_order_payments(self, order: Order) -> list[Payment]:
        """
        Retrieve all payments made toward a specific order

        :param order (Order): The Order to look up
        :return (list[Payment]): A list of Payment objects for that order
        :raises NotAuthorisedError: If the user is not the team and not the
            customer on the order
        :raises ValueError: If the order is not in the system
        """
        stored = self.__require_known_order(order)
        self.__require_self_or_team(stored.customer)
        return self.__payments_in_time_order(stored)

    def display_all_payments(self) -> None:
        """
        Print a readable list of every payment on record

        :raises NotAuthorisedError: If the user is not the nursery team
        """
        self.__require_team()
        self.__payment_history.display_all_payments()

    def display_customer_payments(self, customer: Customer) -> None:
        """
        Print a readable list of payments made by a specific customer

        :param customer (Customer): The customer to look up
        :raises NotAuthorisedError: If the user is not the team and not this
            customer
        """
        self.__require_self_or_team(customer)
        self.__payment_history.display_customer_payments(customer)

    def display_order_payments(self, order: Order) -> None:
        """
        Print a readable list of payments made toward a specific order

        :param order (Order): The order to look up
        :raises NotAuthorisedError: If the user is not the team and not the
            customer on the order
        :raises ValueError: If the order is not in the system
        """
        stored = self.__require_known_order(order)
        self.__require_self_or_team(stored.customer)
        self.__payment_history.display_order_payments(stored)

    def invoice_for(self, order: Order) -> Invoice:
        """
        Build an invoice for an order

        :param order (Order): The order to list
        :return (Invoice): Lines, the customer discount, and the total
        :raises NotAuthorisedError: If the user is not the team and not the
            customer on the order
        :raises ValueError: If the order is not in the system
        """
        stored = self.__require_known_order(order)
        self.__require_self_or_team(stored.customer)
        return Invoice(stored)

    def receipt_for(self, payment: Payment) -> Receipt:
        """
        Build a receipt for a payment

        :param payment (Payment): The payment to show
        :return (Receipt): The amount, method, surcharge, and what is left
        :raises NotAuthorisedError: If the user is not the team and not the
            customer who paid
        :raises ValueError: If the payment is not in the system
        """
        stored = self.find_payment(payment.payment_id)
        # Each receipt shows what was left after that payment, not the
        # balance once later payments have also been recorded.
        paid_so_far = 0.0
        remaining = stored.order.order_total
        for earlier in self.__payments_in_time_order(stored.order):
            paid_so_far = round(paid_so_far + earlier.amount, 2)
            remaining = round(stored.order.order_total - paid_so_far, 2)
            if earlier.payment_id == stored.payment_id:
                break
        return Receipt(stored, remaining)

    # ---------- Report Methods ----------

    def plant_order_history(self, plant: Plant) -> list[Order]:
        """
        Return every order that includes this plant, oldest first

        :param plant (Plant): The plant to look up
        :return (list[Order]): Orders that include the plant, including
            cancelled ones
        :raises NotAuthorisedError: If the user is not the nursery team
        :raises ValueError: If the plant is not in the catalog
        """
        self.__require_team()
        stored = self.find_plant(plant.plant_id)
        matches = [
            order
            for order in self.__history.order_list
            if any(
                item.plant.plant_id == stored.plant_id for item in order.items
            )
        ]
        matches.sort(key=lambda order: self.__parse_date(order.order_date))
        return matches

    def customer_activity(self, customer: Customer) -> list[ActivityRecord]:
        """
        Return a customer's placed, paid, collected, and cancelled events,
        oldest first

        :param customer (Customer): The customer to look up
        :return (list[ActivityRecord]): The timeline
        :raises NotAuthorisedError: If the user is not the team and not this
            customer
        :raises ValueError: If the customer is not registered
        """
        self.__require_self_or_team(customer)
        self.__require_registered_customer(customer)
        # History order is the tie-break when several things happen on one
        # day, so a cancelled order stays with the order it belongs to.
        recorded = {
            order.order_id: index
            for index, order in enumerate(self.__history.order_list)
        }
        action_order = {
            "placed": 0,
            "paid": 1,
            "collected": 2,
            "cancelled": 3,
        }
        timed: list[tuple[int, ActivityRecord]] = []
        for order in self.__history.get_customer_order_history(customer):
            position = recorded[order.order_id]
            timed.append((
                position,
                ActivityRecord(
                    order.order_date,
                    "placed",
                    "Order {} placed".format(order.order_id),
                ),
            ))
            if order.collected_date is not None:
                timed.append((
                    position,
                    ActivityRecord(
                        order.collected_date,
                        "collected",
                        "Order {} collected".format(order.order_id),
                    ),
                ))
            if order.cancelled_date is not None:
                timed.append((
                    position,
                    ActivityRecord(
                        order.cancelled_date,
                        "cancelled",
                        "Order {} cancelled".format(order.order_id),
                    ),
                ))
        for payment in self.__payment_history.get_customer_payments(customer):
            timed.append((
                recorded[payment.order.order_id],
                ActivityRecord(
                    payment.payment_date,
                    "paid",
                    "Paid ${:.2f} toward order {}".format(
                        payment.amount, payment.order.order_id
                    ),
                ),
            ))
        timed.sort(
            key=lambda pair: (
                self.__parse_date(pair[1].happened_on),
                pair[0],
                action_order[pair[1].action],
            )
        )
        return [record for _position, record in timed]

    def __quantities_ordered(self) -> list[tuple[Plant, int]]:
        """
        Count how many of each plant have been ordered, leaving out cancelled
        orders. Plants that were never ordered are included as 0.

        :return (list[tuple[Plant, int]]): Each plant and the quantity ordered
        """
        counts = {
            plant.plant_id: 0 for plant in self.__catalog.plant_list
        }
        for order in self.__history.order_list:
            if order.order_status == "cancelled":
                continue
            for item in order.items:
                counts[item.plant.plant_id] += item.quantity
        return [
            (plant, counts[plant.plant_id])
            for plant in self.__catalog.plant_list
        ]

    def most_ordered_plants(self) -> list[tuple[Plant, int]]:
        """
        Return plants from most ordered to least. Ties are alphabetical.

        :return (list[tuple[Plant, int]]): Each plant and the quantity ordered
            on orders that were not cancelled
        :raises NotAuthorisedError: If the user is not the nursery team
        """
        self.__require_team()
        ranked = self.__quantities_ordered()
        ranked.sort(key=lambda pair: (-pair[1], pair[0].plant_name.casefold()))
        return ranked

    def least_ordered_plants(self) -> list[tuple[Plant, int]]:
        """
        Return plants from least ordered to most. Ties are alphabetical.
        A plant that has never been ordered is included.

        :return (list[tuple[Plant, int]]): Each plant and the quantity ordered
            on orders that were not cancelled
        :raises NotAuthorisedError: If the user is not the nursery team
        """
        self.__require_team()
        ranked = self.__quantities_ordered()
        ranked.sort(key=lambda pair: (pair[1], pair[0].plant_name.casefold()))
        return ranked

    def revenue(self, period: str, on_date: str) -> float:
        """
        Total the amount charged for payments in a day, week, or month. Card
        surcharges are included. A week is the given date plus the next six
        days. A month is the calendar month that contains the date.

        :param period (str): day, week, or month
        :param on_date (str): A date in DD-MM-YYYY format
        :return (float): The amount charged in that period
        :raises NotAuthorisedError: If the user is not the nursery team
        :raises ValueError: If the period or the date is invalid
        """
        self.__require_team()
        if period not in ("day", "week", "month"):
            raise ValueError("Period must be day, week, or month")
        chosen = self.__parse_date(on_date)
        if period == "day":
            start = chosen
            end = chosen
        elif period == "week":
            start = chosen
            end = chosen + timedelta(days=6)
        else:
            start = chosen.replace(day=1)
            if chosen.month == 12:
                next_month = date(chosen.year + 1, 1, 1)
            else:
                next_month = date(chosen.year, chosen.month + 1, 1)
            end = next_month - timedelta(days=1)

        total = 0.0
        for payment in self.__payment_history.payment_list:
            paid_on = self.__parse_date(payment.payment_date)
            if start <= paid_on <= end:
                total += payment.amount_charged()
        return round(total, 2)

    # ---------- String Method ----------

    def __str__(self) -> str:
        """
        Returns a summary of the nursery system

        :return (str): A summary of the nursery system
        """
        return (
            "Nursery System: {} plants, {} customers, {} orders, {} payments"
            .format(
                len(self.__catalog.plant_list),
                len(self.__directory.customer_list),
                len(self.__history.order_list),
                len(self.__payment_history.payment_list),
            )
        )
