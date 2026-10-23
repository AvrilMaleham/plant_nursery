import re
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

# Card numbers are 13 to 19 digits long. Only the last four are kept.
MIN_CARD_DIGITS = 13
MAX_CARD_DIGITS = 19
CARD_DIGITS_KEPT = 4
# MM-YY with a two-digit month from 01 to 12, as the payment form asks.
EXPIRY_PATTERN = re.compile(r"(0[1-9]|1[0-2])-(\d{2})")
MAX_BANK_NAME_LENGTH = 100


class Payment(Base):
    """
    An abstract class representing a payment made by a customer toward a
    specific order
    """

    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_payments_amount"),
        CheckConstraint(
            "length(card_last4) = 4", name="ck_payments_card_last4"
        ),
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
    # Only the last four digits of the card are stored, never the whole
    # number. A receipt and a payment record do not need more than that.
    _card_last4: Mapped[str] = mapped_column(
        "card_last4", String(4), nullable=False
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
        :param card_number (str): The full card number, as typed. It is
            checked here, and only its last four digits are kept
        :param payment_date (Optional[str]): Optional payment date in
            DD-MM-YYYY format, defaults to today. It cannot be in the future
        :raises ValueError: If amount is not greater than 0, the card number
            is missing or is not 13 to 19 digits, or the payment date is
            invalid or in the future
        """
        if amount <= 0:
            raise ValueError("Payment amount must be greater than 0")
        # Both credit and debit payments record a card, so the check lives
        # here.
        digits = self.__clean_card_number(card_number)
        paid_on = self._parse_payment_date(payment_date)

        # UUID keeps payment IDs unique without a running counter.
        self._payment_id = uuid.uuid4()
        self._customer = customer
        self._order = order
        self._amount = round(amount, 2)
        # The full number is not kept on the object, so it cannot be saved or
        # printed by accident later.
        self._card_last4 = digits[-CARD_DIGITS_KEPT:]
        self._payment_date = paid_on.strftime("%d-%m-%Y")
        self._recorded_at = datetime.now()

    # ---------- Getters and Setters ----------
    # A recorded payment is a snapshot. ID, customer, order, amount, card
    # digits, and date are not changed after creation.

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
    def card_last4(self) -> str:
        """
        Get the last four digits of the card. The rest is not stored.

        :return (str): The last four digits of the card number
        """
        return self._card_last4

    # ---------- Methods ----------

    @staticmethod
    def __clean_card_number(card_number: str) -> str:
        """
        Check a card number and return just its digits

        :param card_number (str): The card number as typed. Spaces and dashes
            are allowed between the digits
        :return (str): The digits of the card number
        :raises ValueError: If it is missing, has anything but digits, spaces,
            and dashes in it, or is not 13 to 19 digits long
        """
        if not isinstance(card_number, str) or not card_number.strip():
            raise ValueError("Card number is required")
        digits = card_number.replace(" ", "").replace("-", "")
        if not digits:
            raise ValueError("Card number is required")
        # isascii() because isdigit() also accepts digits from other scripts.
        if not (digits.isascii() and digits.isdigit()):
            raise ValueError(
                "Card number can only contain digits, spaces, and dashes")
        if not MIN_CARD_DIGITS <= len(digits) <= MAX_CARD_DIGITS:
            raise ValueError(
                f"Card number must have {MIN_CARD_DIGITS} to "
                f"{MAX_CARD_DIGITS} digits")
        return digits

    @staticmethod
    def _parse_payment_date(payment_date: Optional[str]) -> date:
        """
        Check a payment date and return it as a date

        :param payment_date (Optional[str]): Date string in DD-MM-YYYY format,
            or None for today
        :return (date): The payment date
        :raises ValueError: If the date is not a valid calendar date in
            DD-MM-YYYY format, or is in the future
        """
        if payment_date is None:
            return date.today()
        try:
            paid_on = datetime.strptime(payment_date, "%d-%m-%Y").date()
        except (TypeError, ValueError):
            raise ValueError(
                "Payment date must be a valid date in DD-MM-YYYY format")
        # A payment is recorded when it is taken, so it cannot be ahead of
        # today.
        if paid_on > date.today():
            raise ValueError("Payment date cannot be in the future")
        return paid_on

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
            " Customer: {}, Order ID: {}, Payment Date: {}, Card ending: {}"
            .format(
                self.payment_id, self.payment_type(),
                self.amount, self.amount_charged(),
                self.customer.cust_name, self.order.order_id,
                self.payment_date, self.card_last4,
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
        :param expiry_date (str): Card expiry date as MM-YY. The card is good
            until the end of that month
        :param payment_date (Optional[str]): Optional payment date in
            DD-MM-YYYY format, defaults to today
        :raises ValueError: If amount is not greater than 0, the card number
            is missing or not 13 to 19 digits, the expiry is missing, is not
            a real MM-YY, or has passed by the payment date, or the payment
            date is invalid or in the future
        """
        expiry = self.__clean_expiry(expiry_date, payment_date)

        super().__init__(customer, order, amount, card_number, payment_date)
        self._expiry_date = expiry

    @classmethod
    def __clean_expiry(
        cls, expiry_date: str, payment_date: Optional[str]
    ) -> str:
        """
        Check an expiry date against the day the payment is made

        :param expiry_date (str): The expiry as typed, in MM-YY form
        :param payment_date (Optional[str]): The payment date in DD-MM-YYYY
            form, or None for today
        :return (str): The expiry, with any spaces around it removed
        :raises ValueError: If it is missing, is not MM-YY with a month from
            01 to 12, or the card had expired by the payment date
        """
        if not isinstance(expiry_date, str) or not expiry_date.strip():
            raise ValueError("Expiry date is required")
        expiry = expiry_date.strip()
        found = EXPIRY_PATTERN.fullmatch(expiry)
        if found is None:
            raise ValueError(
                "Expiry date must be a month and year as MM-YY, "
                "such as 09-28")
        paid_on = cls._parse_payment_date(payment_date)
        month, year = int(found.group(1)), 2000 + int(found.group(2))
        # A card works until the end of the month printed on it.
        if (year, month) < (paid_on.year, paid_on.month):
            raise ValueError(f"This card expired in {expiry}")
        return expiry

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
        return "{}, Expiry Date: {}".format(
            super().__str__(), self.expiry_date
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
        :raises ValueError: If amount is not greater than 0, the card number
            is missing or not 13 to 19 digits, the bank name is missing or
            longer than 100 characters, or the payment date is invalid or in
            the future
        """
        bank = bank_name.strip() if isinstance(bank_name, str) else ""
        if not bank:
            raise ValueError("Bank name is required")
        if len(bank) > MAX_BANK_NAME_LENGTH:
            raise ValueError(
                f"Bank name must be {MAX_BANK_NAME_LENGTH} characters or "
                "fewer")

        super().__init__(customer, order, amount, card_number, payment_date)
        self._bank_name = bank

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
        return "{}, Bank: {}".format(super().__str__(), self.bank_name)
