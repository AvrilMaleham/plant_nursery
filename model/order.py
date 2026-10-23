import uuid
from datetime import date, datetime
from typing import Literal, Optional

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .customer import Customer
from .exceptions import (
    OrderCannotBeCancelledError,
    OrderCannotBeCollectedError,
    OrderNotPayableError,
    OverpaymentError,
)
from .order_item import OrderItem
from .plant import Plant

# The three statuses come from Brent's notes and are treated as a fixed set.
# A Literal type is used so the allowed values are explicit even though status
# itself is only changed through collect_order() and cancel_order().
OrderStatus = Literal["pending", "collected", "cancelled"]

# An order that is still pending this many days after it was placed needs
# follow-up from the team and from the customer.
UNCOLLECTED_AFTER_DAYS = 7


class Order(Base):
    """
    Represents an order made by a customer, bringing together one or more order
    items
    """

    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint("order_total > 0", name="ck_orders_total"),
        CheckConstraint("amount_paid >= 0", name="ck_orders_amount_paid"),
        CheckConstraint(
            "order_status IN ('pending', 'collected', 'cancelled')",
            name="ck_orders_status",
        ),
    )

    _order_id: Mapped[uuid.UUID] = mapped_column(
        "order_id", Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    _customer_id: Mapped[uuid.UUID] = mapped_column(
        "customer_id",
        Uuid(as_uuid=True),
        ForeignKey("customers.cust_id"),
        nullable=False,
    )
    _order_date: Mapped[str] = mapped_column(
        "order_date", String(10), nullable=False
    )
    _order_status: Mapped[str] = mapped_column(
        "order_status", String(20), nullable=False, default="pending"
    )
    _order_total: Mapped[float] = mapped_column(
        "order_total", Numeric(10, 2), nullable=False
    )
    _amount_paid: Mapped[float] = mapped_column(
        "amount_paid", Numeric(10, 2), nullable=False, default=0
    )
    _collected_date: Mapped[Optional[str]] = mapped_column(
        "collected_date", String(10), nullable=True
    )
    _cancelled_date: Mapped[Optional[str]] = mapped_column(
        "cancelled_date", String(10), nullable=True
    )
    _customer: Mapped[Customer] = relationship()
    _items: Mapped[list[OrderItem]] = relationship(
        back_populates="_order",
        cascade="all, delete-orphan",
    )

    def __init__(
        self,
        customer: Customer,
        items: list[tuple[Plant, int]],
        order_date: Optional[str] = None,
    ) -> None:
        """
        Initialise a new Order object

        :param customer (Customer): The Customer associated with the order
        :param items (list[tuple[Plant, int]]): A list of (plant, quantity)
            pairs, at least one, with no plant repeated
        :param order_date (Optional[str]): Optional order date in DD-MM-YYYY
            format, defaults to today
        :raises ValueError: If there are no items, a plant is repeated, a
            quantity is not greater than 0, or the order date is invalid
        :raises InsufficientStockError: If there is not enough stock for an
            item
        """

        # Customer type is already in the method signature. NurserySystem still
        # confirms the customer and plants are registered, and that this
        # customer may place an order.
        if not items:
            raise ValueError("An order must contain at least one item")

        # Every line is checked before any OrderItem is created, so a later
        # line failing cannot leave an earlier line's stock already reduced.
        seen_plant_ids = []
        for plant, quantity in items:
            OrderItem.validate(plant, quantity)
            if plant.plant_id in seen_plant_ids:
                raise ValueError("Each plant can only appear once on an order")
            seen_plant_ids.append(plant.plant_id)

        # UUID keeps order IDs unique without a running counter.
        self._order_id = uuid.uuid4()
        # Date defaults to today if none is supplied, then is validated as a
        # real calendar date.
        if order_date is None:
            order_date = date.today().strftime("%d-%m-%Y")
        self._order_date = self.__validate_order_date(order_date)
        # New orders always start as pending. Status is not settable directly
        # after this.
        self._order_status = "pending"
        self._customer = customer
        self._amount_paid = 0.0
        for plant, quantity in items:
            # Append to the mapped collection so each line is saved with the
            # order. Replacing the collection with a plain list would drop that
            # link.
            self._items.append(OrderItem(plant, quantity))

        items_subtotal = 0.0
        for item in self._items:
            items_subtotal += item.item_cost
        # Item bulk discounts are already in each line. The customer discount
        # comes off the order as a whole, using whichever rate the customer
        # subclass supplies.
        self._order_total = customer.apply_discount(items_subtotal)
        customer.add_to_balance(self.order_total)

    # ---------- Getters and Setters ----------
    # Status has no setter because not every transition is legal (e.g.
    # collected cannot be cancelled, and cancelling also has to restore stock
    # and the customer balance). collect_order() and cancel_order() are the
    # only way to change it. Order date does have a setter so staff can record
    # or correct a date rather than always using today.

    @property
    def order_id(self) -> uuid.UUID:
        """
        Get the unique order ID

        :return (uuid.UUID): The unique order ID
        """
        return self._order_id

    @property
    def order_number(self) -> str:
        """
        Get a short number for this order, for invoices and receipts

        The stored ID is a UUID, which is awkward to read out or print. These
        eight characters come from that ID, the same way a customer number
        does, so they stay the same for this order.

        :return (str): Eight uppercase characters taken from the order ID
        """
        return str(self._order_id).replace("-", "")[:8].upper()

    @property
    def order_date(self) -> str:
        """
        Get date of the order

        :return (str): Date of the order
        """
        return self._order_date

    @order_date.setter
    def order_date(self, value: str) -> None:
        """
        Update the order date

        :param value (str): New date in DD-MM-YYYY format
        :raises ValueError: If the date is not a valid calendar date in
            DD-MM-YYYY format
        """
        self._order_date = self.__validate_order_date(value)

    @property
    def order_status(self) -> OrderStatus:
        """
        Get the status of the order

        :return (OrderStatus): The status of the order
        """
        return self._order_status  # type: ignore[return-value]

    @property
    def customer(self) -> Customer:
        """
        Get the customer on the order

        :return (Customer): The customer on the order
        """
        return self._customer

    @property
    def items(self) -> list[OrderItem]:
        """
        Get the items on the order

        :return (list[OrderItem]): The items on the order
        """
        # A copy is returned so callers cannot add or remove items on a placed
        # order.
        return list(self._items)

    @property
    def order_total(self) -> float:
        """
        Get the total price of the order after item and customer discounts

        :return (float): The total price of the order after item and customer
            discounts
        """
        return float(self._order_total)

    @property
    def amount_paid(self) -> float:
        """
        Get how much has been paid toward this order

        :return (float): How much has been paid toward this order
        """
        return float(self._amount_paid)

    @property
    def remaining_balance(self) -> float:
        """
        Get how much is still owed on this order

        :return (float): How much is still owed on this order
        """
        # A cancelled order has already had its total taken back off the
        # customer.
        if self._order_status == "cancelled":
            return 0.0
        return round(self.order_total - self.amount_paid, 2)

    @property
    def collected_date(self) -> Optional[str]:
        """
        Get the date the order was collected

        :return (Optional[str]): The collection date, or None if it has not
            been collected
        """
        return self._collected_date

    @property
    def cancelled_date(self) -> Optional[str]:
        """
        Get the date the order was cancelled

        :return (Optional[str]): The cancellation date, or None if it has not
            been cancelled
        """
        return self._cancelled_date

    # ---------- Methods ----------

    def __validate_order_date(self, order_date: str) -> str:
        """
        Validate that the order date is a real calendar date in DD-MM-YYYY
        format

        :param order_date (str): Date string to validate
        :return (str): The validated date string
        :raises ValueError: If the date is not a valid calendar date in
            DD-MM-YYYY format
        """
        # strptime is used so the format and the calendar date are both
        # checked. That rejects values like 32-13-2026, not just strings that
        # look the wrong shape.
        if not isinstance(order_date, str):
            raise ValueError(
                "Order date must be a valid date in DD-MM-YYYY format")
        try:
            datetime.strptime(order_date, "%d-%m-%Y")
        except ValueError:
            raise ValueError(
                "Order date must be a valid date in DD-MM-YYYY format")
        return order_date

    def record_payment(self, amount: float) -> None:
        """
        Record an amount paid toward this order and take it off the customer
        balance

        :param amount (float): Amount to apply to this order, must be greater
            than 0 and not more than remaining
        :raises OrderNotPayableError: If the order has been cancelled, or is
            already paid in full
        :raises OverpaymentError: If the amount is more than what is still
            owed
        :raises ValueError: If amount is not greater than 0
        """
        # Say why the order cannot be paid before comparing amounts. A
        # cancelled or settled order owes nothing, and "more than what is
        # still owed" would be true but would not explain that.
        if self._order_status == "cancelled":
            raise OrderNotPayableError(
                "This order has been cancelled, so nothing can be paid "
                "toward it")
        if self.remaining_balance <= 0:
            raise OrderNotPayableError(
                "This order has already been paid in full")
        if amount <= 0:
            raise ValueError("Payment amount must be greater than 0")
        if amount > self.remaining_balance:
            raise OverpaymentError(
                "Payment cannot be more than what is still owed on this "
                f"order (${self.remaining_balance:.2f})")
        self._amount_paid = round(self.amount_paid + amount, 2)
        self.customer.reduce_balance(amount)

    def is_uncollected_too_long(self, today: Optional[date] = None) -> bool:
        """
        Return whether this pending order was placed at least seven days ago

        :param today (Optional[date]): The date to compare with, defaults to
            today
        :return (bool): True if it is still pending and at least seven days
            have passed since it was placed
        """
        if self._order_status != "pending":
            return False
        placed = datetime.strptime(self.order_date, "%d-%m-%Y").date()
        current = today or date.today()
        return (current - placed).days >= UNCOLLECTED_AFTER_DAYS

    def collect_order(self, collected_date: Optional[str] = None) -> None:
        """
        Update order status to collected

        :param collected_date (Optional[str]): Collection date in DD-MM-YYYY
            format, defaults to today
        :raises OrderCannotBeCollectedError: If the order has already been
            collected or cancelled, or the customer is not allowed to collect
            it yet
        :raises ValueError: If the collection date is invalid
        """
        if self._order_status == "collected":
            raise OrderCannotBeCollectedError(
                "Order has already been collected")
        if self._order_status == "cancelled":
            raise OrderCannotBeCollectedError(
                "Unable to collect cancelled order")
        # Pending is the only status that can move to collected. Whether this
        # customer may collect while still owing is answered by the customer
        # subclass.
        if not self.customer.can_collect_order(self.remaining_balance):
            raise OrderCannotBeCollectedError(
                "Community customers must pay an order in full "
                "before it can be collected"
            )
        if collected_date is None:
            collected_date = date.today().strftime("%d-%m-%Y")
        self._collected_date = self.__validate_order_date(collected_date)
        self._order_status = "collected"

    def cancel_order(self, cancelled_date: Optional[str] = None) -> None:
        """
        Update order status to cancelled, restore stock, and take the total off
        the customer balance

        :param cancelled_date (Optional[str]): Cancellation date in DD-MM-YYYY
            format, defaults to today
        :raises OrderCannotBeCancelledError: If the order has already been
            collected or cancelled, or anything has been paid toward it
        :raises ValueError: If the cancellation date is invalid
        """
        if self._order_status == "collected":
            raise OrderCannotBeCancelledError(
                "Cannot cancel order that has already been collected")
        if self._order_status == "cancelled":
            raise OrderCannotBeCancelledError(
                "Order has already been cancelled")
        if self.amount_paid > 0:
            raise OrderCannotBeCancelledError(
                "Cannot cancel an order that has already been paid toward")
        # Stock is restored on every item, and the order total comes off what
        # they owe, matching how placing the order added it.
        for item in self._items:
            item.restore_stock()
        self.customer.reduce_balance(self.order_total)
        if cancelled_date is None:
            cancelled_date = date.today().strftime("%d-%m-%Y")
        self._cancelled_date = self.__validate_order_date(cancelled_date)
        self._order_status = "cancelled"

    def __str__(self) -> str:
        """
        Returns a readable string of the order details

        :return (str): A readable string of the order details
        """
        item_text = "; ".join(str(item) for item in self._items)
        text = (
            "Order ID: {}, Order Date: {}, Order Status: {}, Customer: {},"
            " Items: [{}], Order Total: {}, Amount Paid: {}, "
            "Remaining Balance: {}"
            .format(
                self.order_id, self.order_date,
                self.order_status, self.customer.cust_name,
                item_text, self.order_total,
                self.amount_paid, self.remaining_balance,
            )
        )
        if self.is_uncollected_too_long():
            return text + ", Follow-up: uncollected for 7 days or more"
        return text
