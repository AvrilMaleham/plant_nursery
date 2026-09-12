import uuid
from abc import ABC, abstractmethod
from typing import Optional


class Customer(ABC):
    """An abstract class representing a customer buying plants from the nursery"""

    def __init__(self, cust_name: str, cust_email: str = "", cust_phone: str = "") -> None:
        """
        Initialise a new Customer object

        :param cust_name: Name of the customer (does not need to be unique, different customers can have the same name)
        :param cust_email: Contact email address of the customer
        :param cust_phone: Contact phone number of the customer
        :raises ValueError: If there is not at least one of cust_email or cust_phone
        """

        # At least one contact method is required so the nursery can still reach the customer.
        if not cust_email and not cust_phone:
            raise ValueError("Please provide at least an email or a phone number")

        # UUID is used so two customers with the same name still have distinct IDs.
        self.__cust_id = uuid.uuid4()
        self.__cust_name = cust_name
        # Empty strings are stored as None so a missing email or phone is consistent.
        self.__cust_email = cust_email if cust_email else None
        self.__cust_phone = cust_phone if cust_phone else None
        # Every customer starts owing nothing. Placing an order adds to this,
        # paying or cancelling takes it back down.
        self.__balance = 0.0

    # ---------- Getters and Setters ----------
    # ID is generated once and has no setter, so it cannot be changed later.
    # Name, email, and phone can be updated if details change. Clearing email or phone
    # is only allowed if the other contact method is still set, matching the create rule.
    # Balance has a getter only. It is changed through add_to_balance() and
    # reduce_balance() so it cannot be set to an arbitrary value.

    @property
    def cust_id(self) -> uuid.UUID:
        """Get the unique customer ID"""
        return self.__cust_id

    @property
    def cust_name(self) -> str:
        """Get the customer name"""
        return self.__cust_name

    @cust_name.setter
    def cust_name(self, value: str) -> None:
        """
        Update the customer name

        :param value: New customer name
        """
        self.__cust_name = value

    @property
    def cust_email(self) -> Optional[str]:
        """Get the customer email"""
        return self.__cust_email

    @cust_email.setter
    def cust_email(self, value: Optional[str]) -> None:
        """
        Update the customer email. At least one contact method must remain.

        :param value: New email address, or empty/None to clear it
        :raises ValueError: If clearing the email would leave the customer with no contact details
        """
        new_email = value if value else None
        # Reject clearing email if there is no phone, otherwise the customer would have
        # no way to be contacted.
        if not new_email and not self.__cust_phone:
            raise ValueError("Please provide at least an email or a phone number")
        self.__cust_email = new_email

    @property
    def cust_phone(self) -> Optional[str]:
        """Get the customer phone number"""
        return self.__cust_phone

    @cust_phone.setter
    def cust_phone(self, value: Optional[str]) -> None:
        """
        Update the customer phone number. At least one contact method must remain.

        :param value: New phone number, or empty/None to clear it
        :raises ValueError: If clearing the phone would leave the customer with no contact details
        """
        new_phone = value if value else None
        # Same rule as the email setter: one of email or phone must remain.
        if not self.__cust_email and not new_phone:
            raise ValueError("Please provide at least an email or a phone number")
        self.__cust_phone = new_phone

    @property
    def balance(self) -> float:
        """Get the amount the customer currently owes"""
        return self.__balance

    # ---------- Methods ----------

    def add_to_balance(self, amount: float) -> None:
        """
        Add to the amount the customer owes when an order is placed

        :param amount: Amount to add, must be greater than 0
        :raises ValueError: If amount is not greater than 0
        """
        if amount <= 0:
            raise ValueError("Amount to add must be greater than 0")
        self.__balance = round(self.__balance + amount, 2)

    def reduce_balance(self, amount: float) -> None:
        """
        Reduce the amount the customer owes when they pay or an order is cancelled

        :param amount: Amount to take off, must be greater than 0 and not more than the current balance
        :raises ValueError: If amount is not greater than 0, or is more than the current balance
        """
        if amount <= 0:
            raise ValueError("Amount to reduce must be greater than 0")
        if amount > self.__balance:
            raise ValueError("Cannot reduce balance below 0")
        self.__balance = round(self.__balance - amount, 2)

    def apply_discount(self, subtotal: float) -> float:
        """
        Apply this customer's discount to an order subtotal

        :param subtotal: The order total after any item discounts
        :return: The total after the customer discount, rounded to 2 decimal places
        """
        # discount_rate() is abstract, so whichever subclass this object really is
        # supplies the rate.
        return round(subtotal * (1 - self.discount_rate()), 2)

    @abstractmethod
    def customer_type(self) -> str:
        """Return the type of customer"""
        pass

    @abstractmethod
    def discount_rate(self) -> float:
        """Return this customer's discount rate as a decimal"""
        pass

    @abstractmethod
    def can_place_order(self, pending_order_count: int) -> bool:
        """
        Return whether this customer is allowed to place a new order

        :param pending_order_count: How many pending orders this customer already has
        :return: True if a new order is allowed, else False
        """
        pass

    @abstractmethod
    def can_collect_order(self, amount_owing_on_order: float) -> bool:
        """
        Return whether this customer is allowed to collect an order

        :param amount_owing_on_order: What is still unpaid on that order
        :return: True if the order may be collected, else False
        """
        pass

    def __str__(self) -> str:
        """Returns a readable string of the customer details"""
        return (
            "Customer ID: {}, Customer Type: {}, Customer Name: {},"
            " Customer Email: {}, Customer Phone Number: {}, Balance: {}"
            .format(
                self.__cust_id, self.customer_type(), self.__cust_name,
                self.__cust_email, self.__cust_phone, self.__balance,
            )
        )


class StaffCustomer(Customer):
    """Represents a subclass of customer called StaffCustomer, with 1% off the order total"""

    def __init__(self, cust_name: str, cust_email: str = "", cust_phone: str = "") -> None:
        """
        Initialise a new StaffCustomer object

        :param cust_name: Name of the customer
        :param cust_email: Contact email address of the customer
        :param cust_phone: Contact phone number of the customer
        :raises ValueError: If there is not at least one of cust_email or cust_phone
        """
        super().__init__(cust_name, cust_email, cust_phone)

    def customer_type(self) -> str:
        """Return the type of customer"""
        return "staff"

    def discount_rate(self) -> float:
        """Return this customer's discount rate as a decimal"""
        return 0.01

    def can_place_order(self, pending_order_count: int) -> bool:
        """
        Staff may place another order unless their amount owing is already above $100

        :param pending_order_count: Not used for staff; balances can accumulate across orders
        :return: True if balance is $100 or less, else False
        """
        return self.balance <= 100

    def can_collect_order(self, amount_owing_on_order: float) -> bool:
        """
        Staff may collect an order while still owing money

        :param amount_owing_on_order: Not used for staff
        :return: True
        """
        return True


class StudentCustomer(Customer):
    """Represents a subclass of customer called StudentCustomer, with 5% off the order total"""

    def __init__(self, cust_name: str, cust_email: str = "", cust_phone: str = "") -> None:
        """
        Initialise a new StudentCustomer object

        :param cust_name: Name of the customer
        :param cust_email: Contact email address of the customer
        :param cust_phone: Contact phone number of the customer
        :raises ValueError: If there is not at least one of cust_email or cust_phone
        """
        super().__init__(cust_name, cust_email, cust_phone)

    def customer_type(self) -> str:
        """Return the type of customer"""
        return "student"

    def discount_rate(self) -> float:
        """Return this customer's discount rate as a decimal"""
        return 0.05

    def can_place_order(self, pending_order_count: int) -> bool:
        """
        Students may place another order unless their amount owing is already above $100

        :param pending_order_count: Not used for students; balances can accumulate across orders
        :return: True if balance is $100 or less, else False
        """
        return self.balance <= 100

    def can_collect_order(self, amount_owing_on_order: float) -> bool:
        """
        Students may collect an order while still owing money

        :param amount_owing_on_order: Not used for students
        :return: True
        """
        return True


class CommunityCustomer(Customer):
    """Represents a subclass of customer called CommunityCustomer, with no discount"""

    def __init__(self, cust_name: str, cust_email: str = "", cust_phone: str = "") -> None:
        """
        Initialise a new CommunityCustomer object

        :param cust_name: Name of the customer
        :param cust_email: Contact email address of the customer
        :param cust_phone: Contact phone number of the customer
        :raises ValueError: If there is not at least one of cust_email or cust_phone
        """
        super().__init__(cust_name, cust_email, cust_phone)

    def customer_type(self) -> str:
        """Return the type of customer"""
        return "community"

    def discount_rate(self) -> float:
        """Return this customer's discount rate as a decimal"""
        return 0.0

    def can_place_order(self, pending_order_count: int) -> bool:
        """
        Community customers may only have one pending order at a time

        :param pending_order_count: How many pending orders this customer already has
        :return: True if they have no pending order, else False
        """
        return pending_order_count == 0

    def can_collect_order(self, amount_owing_on_order: float) -> bool:
        """
        Community customers must pay an order off in full before it can be collected

        :param amount_owing_on_order: What is still unpaid on that order
        :return: True if nothing is still owed on the order, else False
        """
        return amount_owing_on_order <= 0
