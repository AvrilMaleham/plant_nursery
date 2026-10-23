import uuid
from datetime import date
from typing import Optional

from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from .customer import Customer
from .order import Order
from .order_item import OrderItem
from .plant import Plant


class OrderHistory:
    """Record of all orders placed at the nursery"""

    def __init__(self, session: Session) -> None:
        """
        Initialise a new OrderHistory object

        :param session (Session): The database session that stores the orders
        """
        self.__session = session

    # ---------- Getters and Setters ----------

    @property
    def order_list(self) -> list[Order]:
        """
        Get the list of orders, in the order they were placed

        :return (list[Order]): The list of orders
        """
        # A new list is returned so callers cannot change the history by
        # editing it. New orders still have to go through add_order(), which
        # checks for duplicate IDs. The database sorts them, so the order does
        # not depend on how Postgres happens to have stored the rows.
        orders = self.__session.scalars(
            select(Order).order_by(Order._created_at)
        ).all()
        return list(orders)

    # ---------- Methods ----------

    def add_order(self, order: Order) -> None:
        """
        Adds a new order to the list

        :param order (Order): Order to add to the list
        :raises TypeError: If order is not an Order object
        :raises ValueError: If an order with the same ID is already in the list
        """
        if not isinstance(order, Order):
            raise TypeError("Only orders may be added to the list")

        existing_order = self.__session.get(Order, order.order_id)
        if existing_order is not None:
            raise ValueError(
                f"Order with ID {order.order_id} is already in the list")

        self.__session.add(order)

    def find_order(self, order_id: uuid.UUID) -> Optional[Order]:
        """
        Look an order up by its ID

        :param order_id (uuid.UUID): The ID to look for
        :return (Optional[Order]): The order, or None if there is none
        """
        return self.__session.get(Order, order_id)

    def get_pending_order_count(self, customer: Customer) -> int:
        """
        Count how many pending orders a customer currently has

        :param customer (Customer): The customer to look up
        :return (int): The number of orders for that customer with status
            pending
        """
        return self.__session.scalar(
            select(func.count())
            .select_from(Order)
            .where(
                Order._customer_id == customer.cust_id,
                Order._order_status == "pending",
            )
        ) or 0

    def get_customer_order_history(self, customer: Customer) -> list[Order]:
        """
        Retrieve all orders placed by a specific customer, oldest first

        :param customer (Customer): The customer to look up
        :return (list[Order]): A list of Order objects belonging to that
            customer
        """
        # Matching is on the customer ID, so history still works if the caller
        # holds a different Python object with the same ID.
        orders = self.__session.scalars(
            select(Order)
            .where(Order._customer_id == customer.cust_id)
            .order_by(Order._order_date, Order._created_at)
        ).all()
        return list(orders)

    def get_orders_with_status(
        self,
        status: str,
        customer: Optional[Customer] = None,
    ) -> list[Order]:
        """
        Retrieve orders that have one status, oldest first

        :param status (str): pending, collected, or cancelled
        :param customer (Optional[Customer]): Limit the list to this customer.
            Leave it out for every customer
        :return (list[Order]): The matching orders
        """
        query = select(Order).where(Order._order_status == status)
        if customer is not None:
            query = query.where(Order._customer_id == customer.cust_id)
        orders = self.__session.scalars(
            query.order_by(Order._order_date, Order._created_at)
        ).all()
        return list(orders)

    def get_pending_orders_placed_by(self, cutoff: date) -> list[Order]:
        """
        Retrieve pending orders that were placed on or before a day

        :param cutoff (date): The latest order date to include
        :return (list[Order]): The matching orders, oldest first
        """
        orders = self.__session.scalars(
            select(Order)
            .where(
                Order._order_status == "pending",
                Order._order_date <= cutoff,
            )
            .order_by(Order._order_date, Order._created_at)
        ).all()
        return list(orders)

    def get_orders_for_plant(self, plant: Plant) -> list[Order]:
        """
        Retrieve every order that has a line for a plant, oldest first

        :param plant (Plant): The plant to look up
        :return (list[Order]): The matching orders, cancelled ones included
        """
        orders = self.__session.scalars(
            select(Order)
            .where(
                exists().where(
                    OrderItem._order_id == Order._order_id,
                    OrderItem._plant_id == plant.plant_id,
                )
            )
            .order_by(Order._order_date, Order._created_at)
        ).all()
        return list(orders)

    def has_orders_for_plant(self, plant: Plant) -> bool:
        """
        Say whether a plant is on any order, cancelled ones included

        :param plant (Plant): The plant to look up
        :return (bool): True if some order has a line for it
        """
        return bool(self.__session.scalar(
            select(exists().where(OrderItem._plant_id == plant.plant_id))
        ))

    def has_orders_for_customer(self, customer: Customer) -> bool:
        """
        Say whether a customer has placed any order, cancelled ones included

        :param customer (Customer): The customer to look up
        :return (bool): True if the customer has an order
        """
        return bool(self.__session.scalar(
            select(exists().where(Order._customer_id == customer.cust_id))
        ))

    def quantities_by_plant(self) -> dict[uuid.UUID, int]:
        """
        Total the quantity ordered of each plant, leaving out cancelled orders

        :return (dict[uuid.UUID, int]): Quantity by plant ID. A plant that was
            never ordered has no entry
        """
        rows = self.__session.execute(
            select(OrderItem._plant_id, func.sum(OrderItem._quantity))
            .join(Order, Order._order_id == OrderItem._order_id)
            .where(Order._order_status != "cancelled")
            .group_by(OrderItem._plant_id)
        ).all()
        return {plant_id: int(total) for plant_id, total in rows}

    # display_all_orders exists alongside the order_list getter so printing
    # stays inside the history. A caller can use one method instead of
    # looping itself.
    def display_all_orders(self) -> None:
        """Print a readable list of every order in the list"""
        orders = self.order_list
        if not orders:
            print("No orders yet")
            return

        for order in orders:
            print(order)
