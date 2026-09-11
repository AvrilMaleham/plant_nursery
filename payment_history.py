from payment import Payment
from customer import Customer
from order import Order


class PaymentHistory:
    """Record of all payments made at the nursery"""

    def __init__(self) -> None:
        """Initialise a new PaymentHistory object"""

        self.__payment_list = []

    # ---------- Getters and Setters ----------

    @property
    def payment_list(self) -> list[Payment]:
        """Get the list of payments"""
        # A copy is returned so callers cannot change the internal list directly.
        # New payments still have to go through add_payment(), which checks for duplicate IDs.
        return self.__payment_list.copy()

    # ---------- Methods ----------

    def add_payment(self, payment: Payment) -> None:
        """
        Adds a new payment to the list

        :param payment: Payment to add to the list
        :raises ValueError: If a payment with the same ID is already in the list
        """
        for existing_payment in self.__payment_list:
            if existing_payment.payment_id == payment.payment_id:
                raise ValueError(f"Payment with ID {payment.payment_id} is already in the list")

        self.__payment_list.append(payment)

    def get_customer_payments(self, customer: Customer) -> list[Payment]:
        """
        Retrieve all payments made by a specific customer

        :param customer: The customer to look up
        :return: A list of Payment objects belonging to that customer
        """
        matching_payments = []
        for payment in self.__payment_list:
            if payment.customer.cust_id == customer.cust_id:
                matching_payments.append(payment)
        return matching_payments

    def get_order_payments(self, order: Order) -> list[Payment]:
        """
        Retrieve all payments made toward a specific order

        :param order: The order to look up
        :return: A list of Payment objects for that order
        """
        matching_payments = []
        for payment in self.__payment_list:
            if payment.order.order_id == order.order_id:
                matching_payments.append(payment)
        return matching_payments

    def display_all_payments(self) -> None:
        """Print a readable list of every payment in the list"""
        if not self.__payment_list:
            print("No payments yet")
            return

        for payment in self.__payment_list:
            print(payment)

    def display_customer_payments(self, customer: Customer) -> None:
        """
        Print a readable list of payments made by a specific customer

        :param customer: The customer to look up
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

        :param order: The order to look up
        """
        matching_payments = self.get_order_payments(order)
        if not matching_payments:
            print("No payments for this order")
            return

        for payment in matching_payments:
            print(payment)
