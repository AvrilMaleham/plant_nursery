from sqlalchemy import select
from sqlalchemy.orm import Session

from .customer import Customer
from .order import Order
from .payment import Payment


class PaymentHistory:
    """Record of all payments made at the nursery"""

    def __init__(self, session: Session) -> None:
        """
        Initialise a new PaymentHistory object

        :param session (Session): The database session that stores the payments
        """
        self.__session = session

    # ---------- Getters and Setters ----------

    @property
    def payment_list(self) -> list[Payment]:
        """
        Get the list of payments

        :return (list[Payment]): The list of payments
        """
        # A new list is returned so callers cannot change the history by
        # editing it. New payments still have to go through add_payment(),
        # which checks for duplicate IDs.
        payments = self.__session.scalars(select(Payment)).all()
        return list(payments)

    # ---------- Methods ----------

    def add_payment(self, payment: Payment) -> None:
        """
        Adds a new payment to the list

        :param payment (Payment): Payment to add to the list
        :raises ValueError: If a payment with the same ID is already in the
            list
        """
        existing_payment = self.__session.get(Payment, payment.payment_id)
        if existing_payment is not None:
            raise ValueError(
                f"Payment with ID {payment.payment_id} is already in the list"
            )

        self.__session.add(payment)

    def get_customer_payments(self, customer: Customer) -> list[Payment]:
        """
        Retrieve all payments made by a specific customer

        :param customer (Customer): The customer to look up
        :return (list[Payment]): A list of Payment objects belonging to that
            customer
        """
        matching_payments = []
        for payment in self.payment_list:
            if payment.customer.cust_id == customer.cust_id:
                matching_payments.append(payment)
        return matching_payments

    def get_order_payments(self, order: Order) -> list[Payment]:
        """
        Retrieve all payments made toward a specific order

        :param order (Order): The order to look up
        :return (list[Payment]): A list of Payment objects for that order
        """
        matching_payments = []
        for payment in self.payment_list:
            if payment.order.order_id == order.order_id:
                matching_payments.append(payment)
        return matching_payments

    def display_all_payments(self) -> None:
        """Print a readable list of every payment in the list"""
        payments = self.payment_list
        if not payments:
            print("No payments yet")
            return

        for payment in payments:
            print(payment)

    def display_customer_payments(self, customer: Customer) -> None:
        """
        Print a readable list of payments made by a specific customer

        :param customer (Customer): The customer to look up
        """
        matching_payments = self.get_customer_payments(customer)
        if not matching_payments:
            print("No payments for this customer")
            return

        for payment in matching_payments:
            print(payment)

    def display_order_payments(self, order: Order) -> None:
        """
        Print a readable list of payments made toward a specific order

        :param order (Order): The order to look up
        """
        matching_payments = self.get_order_payments(order)
        if not matching_payments:
            print("No payments for this order")
            return

        for payment in matching_payments:
            print(payment)
