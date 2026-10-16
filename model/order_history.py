from sqlalchemy import select
from sqlalchemy.orm import Session

from .customer import Customer
from .order import Order


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
        Get the list of orders

        :return (list[Order]): The list of orders
        """
        # A new list is returned so callers cannot change the history by
        # editing it. New orders still have to go through add_order(), which
        # checks for duplicate IDs.
        orders = self.__session.scalars(select(Order)).all()
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

    def get_pending_order_count(self, customer: Customer) -> int:
        """
        Count how many pending orders a customer currently has

        :param customer (Customer): The customer to look up
        :return (int): The number of orders for that customer with status
            pending
        """
        pending_count = 0
        for order in self.order_list:
            if (
                order.customer.cust_id == customer.cust_id
                and order.order_status == "pending"
            ):
                pending_count += 1
        return pending_count

    def get_customer_order_history(self, customer: Customer) -> list[Order]:
        """
        Retrieve all orders placed by a specific customer

        :param customer (Customer): The customer to look up
        :return (list[Order]): A list of Order objects belonging to that
            customer
        """
        matching_orders = []
        # Match on customer ID rather than the Customer object itself, so
        # history still works if the caller holds a different Python object
        # with the same ID.
        for order in self.order_list:
            if order.customer.cust_id == customer.cust_id:
                matching_orders.append(order)
        return matching_orders

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
