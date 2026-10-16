import uuid
from typing import Optional

from sqlalchemy import CheckConstraint, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base

# Staff and students cannot place another order while owing more than this.
CREDIT_LIMIT = 100

# These come off the order total. Community customers get no discount.
STAFF_DISCOUNT_RATE = 0.01
STUDENT_DISCOUNT_RATE = 0.05
COMMUNITY_DISCOUNT_RATE = 0.0


class Customer(Base):
    """
    An abstract class representing a customer buying plants from the nursery
    """

    __tablename__ = "customers"
    __table_args__ = (
        CheckConstraint("balance >= 0", name="ck_customers_balance"),
        CheckConstraint(
            "customer_type IN ('staff', 'student', 'community')",
            name="ck_customers_type",
        ),
    )

    # Single-table inheritance. Staff, students, and community customers store
    # the same columns. kind is written to the customer_type column.
    _cust_id: Mapped[uuid.UUID] = mapped_column(
        "cust_id", Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kind: Mapped[str] = mapped_column(
        "customer_type", String(20), nullable=False
    )
    _cust_name: Mapped[str] = mapped_column(
        "cust_name", String(200), nullable=False
    )
    _cust_email: Mapped[Optional[str]] = mapped_column(
        "cust_email", String(200), nullable=True
    )
    _cust_phone: Mapped[Optional[str]] = mapped_column(
        "cust_phone", String(50), nullable=True
    )
    _balance: Mapped[float] = mapped_column(
        "balance", Numeric(10, 2), nullable=False, default=0
    )

    __mapper_args__ = {
        "polymorphic_on": "kind",
        "polymorphic_abstract": True,
    }

    def __new__(cls, *args: object, **kwargs: object) -> "Customer":
        """
        Block a direct Customer or UniversityCustomer. SQLAlchemy raises its
        own error for a polymorphic abstract class before __init__ runs, so
        the check has to happen here to stay a TypeError.

        :raises TypeError: If Customer or UniversityCustomer is created
            directly
        """
        if cls.__mapper_args__.get("polymorphic_abstract"):
            if cls is Customer:
                message = (
                    "Can't instantiate abstract class Customer with abstract "
                    "methods can_collect_order, can_place_order, "
                    "customer_type, discount_rate"
                )
            else:
                message = (
                    "Can't instantiate abstract class UniversityCustomer "
                    "with abstract methods customer_type, discount_rate"
                )
            raise TypeError(message)
        return super().__new__(cls)

    def __init__(
        self,
        cust_name: str,
        cust_email: str = "",
        cust_phone: str = "",
    ) -> None:
        """
        Initialise a new Customer object

        :param cust_name (str): Name of the customer (does not need to be
            unique, different customers can have the same name)
        :param cust_email (str): Contact email address of the customer
        :param cust_phone (str): Contact phone number of the customer
        :raises ValueError: If there is not at least one of cust_email or
            cust_phone
        """
        # At least one contact method is required so the nursery can still
        # reach the customer.
        if not cust_email and not cust_phone:
            raise ValueError(
                "Please provide at least an email or a phone number")

        # UUID is used so two customers with the same name still have distinct
        # IDs.
        self._cust_id = uuid.uuid4()
        self._cust_name = cust_name
        # Empty strings are stored as None so a missing email or phone is
        # consistent.
        self._cust_email = cust_email if cust_email else None
        self._cust_phone = cust_phone if cust_phone else None
        # Every customer starts owing nothing. Placing an order adds to this,
        # paying or cancelling takes it back down.
        self._balance = 0.0

    # ---------- Getters and Setters ----------
    # ID is generated once and has no setter, so it cannot be changed later.
    # Name, email, and phone can be updated if details change. Clearing email
    # or phone is only allowed if the other contact method is still set,
    # matching the create rule. Balance has a getter only. It is changed
    # through add_to_balance() and reduce_balance() so it cannot be set to an
    # arbitrary value.

    @property
    def cust_id(self) -> uuid.UUID:
        """
        Get the unique customer ID

        :return (uuid.UUID): The unique customer ID
        """
        return self._cust_id

    @property
    def cust_name(self) -> str:
        """
        Get the customer name

        :return (str): The customer name
        """
        return self._cust_name

    @cust_name.setter
    def cust_name(self, value: str) -> None:
        """
        Update the customer name

        :param value (str): New customer name
        """
        self._cust_name = value

    @property
    def cust_email(self) -> Optional[str]:
        """
        Get the customer email

        :return (Optional[str]): The customer email
        """
        return self._cust_email

    @cust_email.setter
    def cust_email(self, value: Optional[str]) -> None:
        """
        Update the customer email. At least one contact method must remain.

        :param value (Optional[str]): New email address, or empty/None to clear
            it
        :raises ValueError: If clearing the email would leave the customer with
            no contact details
        """
        new_email = value if value else None
        # Reject clearing email if there is no phone, otherwise the customer
        # would have no way to be contacted.
        if not new_email and not self._cust_phone:
            raise ValueError(
                "Please provide at least an email or a phone number")
        self._cust_email = new_email

    @property
    def cust_phone(self) -> Optional[str]:
        """
        Get the customer phone number

        :return (Optional[str]): The customer phone number
        """
        return self._cust_phone

    @cust_phone.setter
    def cust_phone(self, value: Optional[str]) -> None:
        """
        Update the customer phone number. At least one contact method must
        remain.

        :param value (Optional[str]): New phone number, or empty/None to clear
            it
        :raises ValueError: If clearing the phone would leave the customer with
            no contact details
        """
        new_phone = value if value else None
        # Same rule as the email setter: one of email or phone must remain.
        if not self._cust_email and not new_phone:
            raise ValueError(
                "Please provide at least an email or a phone number")
        self._cust_phone = new_phone

    @property
    def balance(self) -> float:
        """
        Get the amount the customer currently owes

        :return (float): The amount the customer currently owes
        """
        return float(self._balance)

    # ---------- Methods ----------

    def add_to_balance(self, amount: float) -> None:
        """
        Add to the amount the customer owes when an order is placed

        :param amount (float): Amount to add, must be greater than 0
        :raises ValueError: If amount is not greater than 0
        """
        if amount <= 0:
            raise ValueError("Amount to add must be greater than 0")
        self._balance = round(self.balance + amount, 2)

    def reduce_balance(self, amount: float) -> None:
        """
        Reduce the amount the customer owes when they pay or an order is
        cancelled

        :param amount (float): Amount to take off, must be greater than 0 and
            not more than the current balance
        :raises ValueError: If amount is not greater than 0, or is more than
            the current balance
        """
        if amount <= 0:
            raise ValueError("Amount to reduce must be greater than 0")
        if amount > self.balance:
            raise ValueError("Cannot reduce balance below 0")
        self._balance = round(self.balance - amount, 2)

    def apply_discount(self, subtotal: float) -> float:
        """
        Apply this customer's discount to an order subtotal

        :param subtotal (float): The order total after any item discounts
        :return (float): The total after the customer discount, rounded to 2
            decimal places
        """
        # discount_rate() is supplied by the concrete subclass.
        return round(subtotal * (1 - self.discount_rate()), 2)

    def customer_type(self) -> str:
        """
        Return the type of customer

        :return (str): The type of customer
        """
        return self.kind

    def discount_rate(self) -> float:
        """
        Return this customer's discount rate as a decimal

        :return (float): This customer's discount rate as a decimal
        """
        raise NotImplementedError

    def can_place_order(self, pending_order_count: int) -> bool:
        """
        Return whether this customer is allowed to place a new order

        :param pending_order_count (int): How many pending orders this customer
            already has
        :return (bool): True if a new order is allowed, else False
        """
        raise NotImplementedError

    def can_collect_order(self, amount_owing_on_order: float) -> bool:
        """
        Return whether this customer is allowed to collect an order

        :param amount_owing_on_order (float): What is still unpaid on that
            order
        :return (bool): True if the order may be collected, else False
        """
        raise NotImplementedError

    def __str__(self) -> str:
        """
        Returns a readable string of the customer details

        :return (str): A readable string of the customer details
        """
        return (
            "Customer ID: {}, Customer Type: {}, Customer Name: {},"
            " Customer Email: {}, Customer Phone Number: {}, Balance: {}"
            .format(
                self.cust_id, self.customer_type(), self.cust_name,
                self.cust_email, self.cust_phone, self.balance,
            )
        )


class UniversityCustomer(Customer):
    """
    An abstract subclass of Customer for university staff and students, who
    share ordering rules
    """

    __mapper_args__ = {"polymorphic_abstract": True}

    def can_place_order(self, pending_order_count: int) -> bool:
        """
        University customers may place another order unless their amount owing
        is already above $100

        :param pending_order_count (int): Not used; balances can accumulate
            across orders
        :return (bool): True if balance is $100 or less, else False
        """
        return self.balance <= CREDIT_LIMIT

    def can_collect_order(self, amount_owing_on_order: float) -> bool:
        """
        University customers may collect an order while still owing money

        :param amount_owing_on_order (float): Not used for university customers
        :return (bool): True
        """
        return True


class StaffCustomer(UniversityCustomer):
    """
    Represents a subclass of customer called StaffCustomer, with 1% off the
    order total
    """

    TYPE_NAME = "staff"

    __mapper_args__ = {"polymorphic_identity": TYPE_NAME}

    def customer_type(self) -> str:
        """
        Return the type of customer

        :return (str): The type of customer
        """
        return self.TYPE_NAME

    def discount_rate(self) -> float:
        """
        Return this customer's discount rate as a decimal

        :return (float): This customer's discount rate as a decimal
        """
        return STAFF_DISCOUNT_RATE


class StudentCustomer(UniversityCustomer):
    """
    Represents a subclass of customer called StudentCustomer, with 5% off the
    order total
    """

    TYPE_NAME = "student"

    __mapper_args__ = {"polymorphic_identity": TYPE_NAME}

    def customer_type(self) -> str:
        """
        Return the type of customer

        :return (str): The type of customer
        """
        return self.TYPE_NAME

    def discount_rate(self) -> float:
        """
        Return this customer's discount rate as a decimal

        :return (float): This customer's discount rate as a decimal
        """
        return STUDENT_DISCOUNT_RATE


class CommunityCustomer(Customer):
    """
    Represents a subclass of customer called CommunityCustomer, with no
    discount
    """

    TYPE_NAME = "community"

    __mapper_args__ = {"polymorphic_identity": TYPE_NAME}

    def customer_type(self) -> str:
        """
        Return the type of customer

        :return (str): The type of customer
        """
        return self.TYPE_NAME

    def discount_rate(self) -> float:
        """
        Return this customer's discount rate as a decimal

        :return (float): This customer's discount rate as a decimal
        """
        return COMMUNITY_DISCOUNT_RATE

    def can_place_order(self, pending_order_count: int) -> bool:
        """
        Community customers may only have one pending order at a time

        :param pending_order_count (int): How many pending orders this customer
            already has
        :return (bool): True if they have no pending order, else False
        """
        return pending_order_count == 0

    def can_collect_order(self, amount_owing_on_order: float) -> bool:
        """
        Community customers must pay an order off in full before it can be
        collected

        :param amount_owing_on_order (float): What is still unpaid on that
            order
        :return (bool): True if nothing is still owed on the order, else False
        """
        return amount_owing_on_order <= 0
