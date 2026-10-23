import uuid
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from werkzeug.security import check_password_hash, generate_password_hash

from .base import Base
from .customer import Customer

TEAM_ROLE = "team"
CUSTOMER_ROLE = "customer"


class User(Base):
    """
    A login for the nursery. The team shares one account. Each customer has
    their own. The password is stored only as a hash.
    """

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("username"),
        CheckConstraint(
            "role IN ('team', 'customer')",
            name="ck_users_role",
        ),
        CheckConstraint(
            "(role = 'customer' AND customer_id IS NOT NULL) "
            "OR (role = 'team' AND customer_id IS NULL)",
            name="ck_users_customer_link",
        ),
    )

    _user_id: Mapped[uuid.UUID] = mapped_column(
        "user_id", Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    _username: Mapped[str] = mapped_column(
        "username", String(50), nullable=False
    )
    # The hash is what gets stored. The typed password is never kept.
    _password_hash: Mapped[str] = mapped_column(
        "password_hash", String(512), nullable=False
    )
    _role: Mapped[str] = mapped_column("role", String(20), nullable=False)
    _customer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        "customer_id",
        Uuid(as_uuid=True),
        ForeignKey("customers.cust_id"),
        nullable=True,
    )
    _customer: Mapped[Optional[Customer]] = relationship()

    def __init__(
        self,
        username: str,
        password: str,
        role: str,
        customer: Optional[Customer] = None,
    ) -> None:
        """
        Initialise a new User object

        :param username (str): Login name, unique
        :param password (str): The password as typed. It is hashed before it
            is stored
        :param role (str): Either team or customer
        :param customer (Optional[Customer]): The customer this login belongs
            to. Required for a customer login, and omitted for the team
        :raises ValueError: If the username, password, role, or customer link
            is not valid
        """
        if not username:
            raise ValueError("Username is required")
        if not password:
            raise ValueError("Password is required")
        if role not in (TEAM_ROLE, CUSTOMER_ROLE):
            raise ValueError("Role must be team or customer")
        if role == CUSTOMER_ROLE and customer is None:
            raise ValueError("A customer login must be linked to a customer")
        if role == TEAM_ROLE and customer is not None:
            raise ValueError("The team login is not linked to a customer")

        self._user_id = uuid.uuid4()
        self._username = username
        self._password_hash = generate_password_hash(password)
        self._role = role
        self._customer = customer

    @property
    def user_id(self) -> uuid.UUID:
        """
        Get the unique user ID

        :return (uuid.UUID): The unique user ID
        """
        return self._user_id

    @property
    def username(self) -> str:
        """
        Get the login name

        :return (str): The login name
        """
        return self._username

    @property
    def role(self) -> str:
        """
        Get the role, team or customer

        :return (str): The role, team or customer
        """
        return self._role

    @property
    def customer(self) -> Optional[Customer]:
        """
        Get the customer this login belongs to

        :return (Optional[Customer]): The linked customer, or None for the team
        """
        return self._customer

    def check_password(self, password: str) -> bool:
        """
        Check a typed password against the stored hash

        :param password (str): The password as typed
        :return (bool): True if it matches the stored hash
        """
        return check_password_hash(self._password_hash, password)

    def __str__(self) -> str:
        """
        Returns a readable string of the login, without the password

        :return (str): A readable string of the login, without the password
        """
        linked = "none"
        if self.customer is not None:
            linked = self.customer.cust_name
        return "Username: {}, Role: {}, Customer: {}".format(
            self.username, self.role, linked
        )
