import uuid
from abc import ABC, abstractmethod
from typing import Optional
from datetime import datetime, date
from customer import Customer
from order import Order


class Payment(ABC):
    """An abstract class representing a payment made by a customer toward a specific order"""

    def __init__(self, customer: Customer, order: Order, amount: float, payment_date: Optional[str] = None) -> None:
        """
        Initialise a new Payment object

        :param customer: The customer making the payment
        :param order: The order this payment is toward
        :param amount: Amount applied to the order, must be greater than 0
        :param payment_date: Optional payment date in DD-MM-YYYY format, defaults to today
        :raises ValueError: If amount is not greater than 0, or the payment date is invalid
        """
        if amount <= 0:
            raise ValueError("Payment amount must be greater than 0")

        # UUID keeps payment IDs unique without a running counter.
        self.__payment_id = uuid.uuid4()
        self.__customer = customer
        self.__order = order
        self.__amount = round(amount, 2)
        if payment_date is None:
            payment_date = date.today().strftime("%d-%m-%Y")
        self.__payment_date = self.__validate_payment_date(payment_date)

    # ---------- Getters and Setters ----------
    # A recorded payment is a snapshot. ID, customer, order, amount, and date
    # are not changed after creation.

    @property
    def payment_id(self) -> uuid.UUID:
        """Get the unique payment ID"""
        return self.__payment_id

    @property
    def customer(self) -> Customer:
        """Get the customer who made the payment"""
        return self.__customer

    @property
    def order(self) -> Order:
        """Get the order this payment is toward"""
        return self.__order

    @property
    def amount(self) -> float:
        """Get the amount applied to the order, not including any surcharge"""
        return self.__amount

    @property
    def payment_date(self) -> str:
        """Get the date of the payment"""
        return self.__payment_date

    # ---------- Methods ----------

    def __validate_payment_date(self, payment_date: str) -> str:
        """
        Validate that the payment date is a real calendar date in DD-MM-YYYY format

        :param payment_date: Date string to validate
        :return: The validated date string
        :raises ValueError: If the date is not a valid calendar date in DD-MM-YYYY format
        """
        try:
            datetime.strptime(payment_date, "%d-%m-%Y")
        except ValueError:
            raise ValueError("Payment date must be a valid date in DD-MM-YYYY format")
        return payment_date

    def amount_charged(self) -> float:
        """
        Return what the customer is charged, including any surcharge

        :return: The charged amount, rounded to 2 decimal places
        """
        # surcharge_rate() is abstract, so whichever subclass this object really is
        # supplies the rate, the same way apply_discount() uses discount_rate().
        return round(self.__amount * (1 + self.surcharge_rate()), 2)

    @abstractmethod
    def payment_type(self) -> str:
        """Return the type of payment"""
        pass

    @abstractmethod
    def surcharge_rate(self) -> float:
        """Return this payment's surcharge rate as a decimal"""
        pass

    def __str__(self) -> str:
        """Returns a readable string of the payment details"""
        return (
            "Payment ID: {}, Payment Type: {}, Amount: {}, Amount Charged: {},"
            " Customer: {}, Order ID: {}, Payment Date: {}"
            .format(
                self.__payment_id, self.payment_type(),
                self.__amount, self.amount_charged(),
                self.__customer.cust_name, self.__order.order_id,
                self.__payment_date,
            )
        )


class CreditCardPayment(Payment):
    """Represents a subclass of payment called CreditCardPayment, with a 1.5% surcharge"""

    def __init__(self, customer: Customer, order: Order, amount: float, card_number: str, expiry_date: str, payment_date: Optional[str] = None) -> None:
        """
        Initialise a new CreditCardPayment object

        :param customer: The customer making the payment
        :param order: The order this payment is toward
        :param amount: Amount applied to the order, must be greater than 0
        :param card_number: Credit card number
        :param expiry_date: Card expiry date
        :param payment_date: Optional payment date in DD-MM-YYYY format, defaults to today
        :raises ValueError: If amount is not greater than 0, card number or expiry is missing,
            or the payment date is invalid
        """
        if not card_number:
            raise ValueError("Card number is required")
        if not expiry_date:
            raise ValueError("Expiry date is required")

        super().__init__(customer, order, amount, payment_date)
        self.__card_number = card_number
        self.__expiry_date = expiry_date

    @property
    def card_number(self) -> str:
        """Get the credit card number"""
        return self.__card_number

    @property
    def expiry_date(self) -> str:
        """Get the card expiry date"""
        return self.__expiry_date

    def payment_type(self) -> str:
        """Return the type of payment"""
        return "credit card"

    def surcharge_rate(self) -> float:
        """Return this payment's surcharge rate as a decimal"""
        return 0.015

    def __str__(self) -> str:
        """Returns a readable string of the credit card payment details"""
        return "{}, Card Number: {}, Expiry Date: {}".format(
            super().__str__(), self.__card_number, self.__expiry_date
        )


class DebitCardPayment(Payment):
    """Represents a subclass of payment called DebitCardPayment, with no surcharge"""

    def __init__(self, customer: Customer, order: Order, amount: float, card_number: str, bank_name: str, payment_date: Optional[str] = None) -> None:
        """
        Initialise a new DebitCardPayment object

        :param customer: The customer making the payment
        :param order: The order this payment is toward
        :param amount: Amount applied to the order, must be greater than 0
        :param card_number: Debit card number
        :param bank_name: Name of the bank the card is with
        :param payment_date: Optional payment date in DD-MM-YYYY format, defaults to today
        :raises ValueError: If amount is not greater than 0, card number or bank name is missing,
            or the payment date is invalid
        """
        if not card_number:
            raise ValueError("Card number is required")
        if not bank_name:
            raise ValueError("Bank name is required")

        super().__init__(customer, order, amount, payment_date)
        self.__card_number = card_number
        self.__bank_name = bank_name

    @property
    def card_number(self) -> str:
        """Get the debit card number"""
        return self.__card_number

    @property
    def bank_name(self) -> str:
        """Get the name of the bank the card is with"""
        return self.__bank_name

    def payment_type(self) -> str:
        """Return the type of payment"""
        return "debit card"

    def surcharge_rate(self) -> float:
        """Return this payment's surcharge rate as a decimal"""
        return 0.0

    def __str__(self) -> str:
        """Returns a readable string of the debit card payment details"""
        return "{}, Card Number: {}, Bank: {}".format(
            super().__str__(), self.__card_number, self.__bank_name
        )
