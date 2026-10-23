import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .customer import Customer
from .order import Order

# Added to what the customer pays. Debit cards have no surcharge.
CREDIT_CARD_SURCHARGE_RATE = 0.015
DEBIT_CARD_SURCHARGE_RATE = 0.0


class Payment(Base):
    """
    An abstract class representing a payment made by a customer toward a
    specific order
    """

    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_payments_amount"),
        CheckConstraint(
            "payment_type <> 'credit card' OR expiry_date IS NOT NULL",
            name="ck_payments_expiry",
        ),
        CheckConstraint(
            "payment_type = 'credit card' OR expiry_date IS NULL",
            name="ck_payments_expiry_only",
        ),
        CheckConstraint(
            "payment_type <> 'debit card' OR bank_name IS NOT NULL",
            name="ck_payments_bank",
        ),
        CheckConstraint(
            "payment_type = 'debit card' OR bank_name IS NULL",
            name="ck_payments_bank_only",
        ),
    )

    # Single-table inheritance. Expiry date and bank name sit on this table
    # and stay null for the other card type. kind is the payment_type column.
    _payment_id: Mapped[uuid.UUID] = mapped_column(
        "payment_id", Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kind: Mapped[str] = mapped_column(
        "payment_type", String(20), nullable=False
    )
    _customer_id: Mapped[uuid.UUID] = mapped_column(
        "customer_id",
        Uuid(as_uuid=True),
        ForeignKey("customers.cust_id"),
        nullable=False,
    )
    _order_id: Mapped[uuid.UUID] = mapped_column(
        "order_id",
        Uuid(as_uuid=True),
        ForeignKey("orders.order_id"),
        nullable=False,
    )
    _amount: Mapped[float] = mapped_column(
        "amount", Numeric(10, 2), nullable=False
    )
    _card_number: Mapped[str] = mapped_column(
        "card_number", String(30), nullable=False
    )
    _payment_date: Mapped[str] = mapped_column(
        "payment_date", String(10), nullable=False
    )
    # payment_date is a day with no time, so two payments on one day cannot be
    # told apart by it. This is when the payment was entered, so receipts can
    # list payments in the order they happened.
    _recorded_at: Mapped[datetime] = mapped_column(
        "recorded_at", DateTime, nullable=False
    )
    _expiry_date: Mapped[Optional[str]] = mapped_column(
        "expiry_date", String(20), nullable=True
    )
    _bank_name: Mapped[Optional[str]] = mapped_column(
        "bank_name", String(100), nullable=True
    )
    _customer: Mapped[Customer] = relationship()
    _order: Mapped[Order] = relationship()

    __mapper_args__ = {
        "polymorphic_on": "kind",
        "polymorphic_abstract": True,
    }
    _ABSTRACT_METHODS = "payment_type, surcharge_rate"

    def __new__(cls, *args: object, **kwargs: object) -> "Payment":
        """
        Stop Payment from being created directly.

        :raises TypeError: If this class is abstract
        """
        # Raised here so the error is a TypeError. SQLAlchemy would otherwise
        # raise its own error while setting the type column.
        if cls.__mapper_args__.get("polymorphic_abstract"):
            raise TypeError(
                f"Can't instantiate abstract class {cls.__name__} "
                f"with abstract methods {cls._ABSTRACT_METHODS}"
            )
        return super().__new__(cls)

    def __init__(
        self,
        customer: Customer,
        order: Order,
        amount: float,
        card_number: str,
        payment_date: Optional[str] = None,
    ) -> None:
        """
        Initialise a new Payment object

        :param customer (Customer): The customer making the payment
        :param order (Order): The order this payment is toward
        :param amount (float): Amount applied to the order, must be greater
            than 0
        :param card_number (str): Card number for this payment
        :param payment_date (Optional[str]): Optional payment date in
            DD-MM-YYYY format, defaults to today
        :raises ValueError: If amount is not greater than 0, card number is
            missing, or the payment date is invalid
        """
        if amount <= 0:
            raise ValueError("Payment amount must be greater than 0")
        # Both credit and debit payments record a card number, so the check
        # lives here.
        if not card_number:
            raise ValueError("Card number is required")

        # UUID keeps payment IDs unique without a running counter.
        self._payment_id = uuid.uuid4()
        self._customer = customer
        self._order = order
        self._amount = round(amount, 2)
        self._card_number = card_number
        if payment_date is None:
            payment_date = date.today().strftime("%d-%m-%Y")
        self._payment_date = self.__validate_payment_date(payment_date)
        self._recorded_at = datetime.now()

    # ---------- Getters and Setters ----------
    # A recorded payment is a snapshot. ID, customer, order, amount, card
    # number, and date are not changed after creation.

    @property
    def payment_id(self) -> uuid.UUID:
        """
        Get the unique payment ID

        :return (uuid.UUID): The unique payment ID
        """
        return self._payment_id

    @property
    def customer(self) -> Customer:
        """
        Get the customer who made the payment

        :return (Customer): The customer who made the payment
        """
        return self._customer

    @property
    def order(self) -> Order:
        """
        Get the order this payment is toward

        :return (Order): The order this payment is toward
        """
        return self._order

    @property
    def amount(self) -> float:
        """
        Get the amount applied to the order, not including any surcharge

        :return (float): The amount applied to the order, not including any
            surcharge
        """
        return float(self._amount)

    @property
    def payment_date(self) -> str:
        """
        Get the date of the payment

        :return (str): The date of the payment
        """
        return self._payment_date

    @property
    def recorded_at(self) -> datetime:
        """
        Get when the payment was entered into the system

        :return (datetime): The date and time the payment was entered
        """
        return self._recorded_at

    @property
    def card_number(self) -> str:
        """
        Get the card number

        :return (str): The card number
        """
        return self._card_number

    # ---------- Methods ----------

    def __validate_payment_date(self, payment_date: str) -> str:
        """
        Validate that the payment date is a real calendar date in DD-MM-YYYY
        format

        :param payment_date (str): Date string to validate
        :return (str): The validated date string
        :raises ValueError: If the date is not a valid calendar date in
            DD-MM-YYYY format
        """
        try:
            datetime.strptime(payment_date, "%d-%m-%Y")
        except ValueError:
            raise ValueError(
                "Payment date must be a valid date in DD-MM-YYYY format")
        return payment_date

    def amount_charged(self) -> float:
        """
        Return what the customer is charged, including any surcharge

        :return (float): The charged amount, rounded to 2 decimal places
        """
        # surcharge_rate() is supplied by the concrete subclass, the same way
        # apply_discount() uses discount_rate().
        return round(self.amount * (1 + self.surcharge_rate()), 2)

    def payment_type(self) -> str:
        """
        Return the type of payment

        :return (str): The type of payment
        """
        return self.kind

    def surcharge_rate(self) -> float:
        """
        Return this payment's surcharge rate as a decimal

        :return (float): This payment's surcharge rate as a decimal
        """
        raise NotImplementedError

    def __str__(self) -> str:
        """
        Returns a readable string of the payment details

        :return (str): A readable string of the payment details
        """
        return (
            "Payment ID: {}, Payment Type: {}, Amount: {}, Amount Charged: {},"
            " Customer: {}, Order ID: {}, Payment Date: {}"
            .format(
                self.payment_id, self.payment_type(),
                self.amount, self.amount_charged(),
                self.customer.cust_name, self.order.order_id,
                self.payment_date,
            )
        )


class CreditCardPayment(Payment):
    """
    Represents a subclass of payment called CreditCardPayment, with a 1.5%
    surcharge
    """

    TYPE_NAME = "credit card"

    __mapper_args__ = {"polymorphic_identity": TYPE_NAME}

    def __init__(
        self,
        customer: Customer,
        order: Order,
        amount: float,
        card_number: str,
        expiry_date: str,
        payment_date: Optional[str] = None,
    ) -> None:
        """
        Initialise a new CreditCardPayment object

        :param customer (Customer): The customer making the payment
        :param order (Order): The order this payment is toward
        :param amount (float): Amount applied to the order, must be greater
            than 0
        :param card_number (str): Credit card number
        :param expiry_date (str): Card expiry date
        :param payment_date (Optional[str]): Optional payment date in
            DD-MM-YYYY format, defaults to today
        :raises ValueError: If amount is not greater than 0, card number or
            expiry is missing, or the payment date is invalid
        """
        if not expiry_date:
            raise ValueError("Expiry date is required")

        super().__init__(customer, order, amount, card_number, payment_date)
        self._expiry_date = expiry_date

    @property
    def expiry_date(self) -> str:
        """
        Get the card expiry date

        :return (str): The card expiry date
        """
        return self._expiry_date or ""

    def payment_type(self) -> str:
        """
        Return the type of payment

        :return (str): The type of payment
        """
        return self.TYPE_NAME

    def surcharge_rate(self) -> float:
        """
        Return this payment's surcharge rate as a decimal

        :return (float): This payment's surcharge rate as a decimal
        """
        return CREDIT_CARD_SURCHARGE_RATE

    def __str__(self) -> str:
        """
        Returns a readable string of the credit card payment details

        :return (str): A readable string of the credit card payment details
        """
        return "{}, Card Number: {}, Expiry Date: {}".format(
            super().__str__(), self.card_number, self.expiry_date
        )


class DebitCardPayment(Payment):
    """
    Represents a subclass of payment called DebitCardPayment, with no surcharge
    """

    TYPE_NAME = "debit card"

    __mapper_args__ = {"polymorphic_identity": TYPE_NAME}

    def __init__(
        self,
        customer: Customer,
        order: Order,
        amount: float,
        card_number: str,
        bank_name: str,
        payment_date: Optional[str] = None,
    ) -> None:
        """
        Initialise a new DebitCardPayment object

        :param customer (Customer): The customer making the payment
        :param order (Order): The order this payment is toward
        :param amount (float): Amount applied to the order, must be greater
            than 0
        :param card_number (str): Debit card number
        :param bank_name (str): Name of the bank the card is with
        :param payment_date (Optional[str]): Optional payment date in
            DD-MM-YYYY format, defaults to today
        :raises ValueError: If amount is not greater than 0, card number or
            bank name is missing, or the payment date is invalid
        """
        if not bank_name:
            raise ValueError("Bank name is required")

        super().__init__(customer, order, amount, card_number, payment_date)
        self._bank_name = bank_name

    @property
    def bank_name(self) -> str:
        """
        Get the name of the bank the card is with

        :return (str): The name of the bank the card is with
        """
        return self._bank_name or ""

    def payment_type(self) -> str:
        """
        Return the type of payment

        :return (str): The type of payment
        """
        return self.TYPE_NAME

    def surcharge_rate(self) -> float:
        """
        Return this payment's surcharge rate as a decimal

        :return (float): This payment's surcharge rate as a decimal
        """
        return DEBIT_CARD_SURCHARGE_RATE

    def __str__(self) -> str:
        """
        Returns a readable string of the debit card payment details

        :return (str): A readable string of the debit card payment details
        """
        return "{}, Card Number: {}, Bank: {}".format(
            super().__str__(), self.card_number, self.bank_name
        )
