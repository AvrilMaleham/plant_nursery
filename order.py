import uuid
from typing import Literal, Optional
from datetime import datetime, date
from customer import Customer
from plant import Plant
from order_item import OrderItem

# The three statuses come from Brent's notes and are treated as a fixed set.
# A Literal type is used so the allowed values are explicit even though status
# itself is only changed through collect_order() and cancel_order().
OrderStatus = Literal["pending", "collected", "cancelled"]


class Order:
    """Represents an order made by a customer, bringing together one or more order items"""

    def __init__(
        self,
        customer: Customer,
        items: list[tuple[Plant, int]],
        order_date: Optional[str] = None,
    ) -> None:
        """
        Initialise a new Order object

        :param customer: The Customer associated with the order
        :param items: A list of (plant, quantity) pairs, at least one, with no plant repeated
        :param order_date: Optional order date in DD-MM-YYYY format, defaults to today
        :raises ValueError: If there are no items, a plant is repeated, a quantity is not greater
            than 0, there is insufficient stock, or the order date is invalid
        """

        # Customer type is already in the method signature. NurserySystem still confirms
        # the customer and plants are registered, and that this customer may place an order.
        if not items:
            raise ValueError("An order must contain at least one item")

        # Stock is checked for every item before any OrderItem is created, so a later
        # line running out of stock cannot leave an earlier line already reduced.
        seen_plant_ids = []
        for plant, quantity in items:
            if quantity < 1:
                raise ValueError("Minimum order is 1")
            if plant.plant_id in seen_plant_ids:
                raise ValueError("Each plant can only appear once on an order")
            seen_plant_ids.append(plant.plant_id)
            if not plant.check_stock(quantity):
                raise ValueError(f"Insufficient stock: only {plant.plant_stock} available")

        # UUID keeps order IDs unique without a running counter.
        self.__order_id = uuid.uuid4()
        # Date defaults to today if none is supplied, then is validated as a real calendar date.
        if order_date is None:
            order_date = date.today().strftime("%d-%m-%Y")
        self.__order_date = self.__validate_order_date(order_date)
        # New orders always start as pending. Status is not settable directly after this.
        self.__order_status: OrderStatus = "pending"
        self.__customer = customer
        self.__items = []
        for plant, quantity in items:
            self.__items.append(OrderItem(plant, quantity))

        items_subtotal = 0.0
        for item in self.__items:
            items_subtotal += item.item_cost
        # Item bulk discounts are already in each line. The customer discount comes
        # off the order as a whole, using whichever rate the customer subclass supplies.
        self.__order_total = customer.apply_discount(items_subtotal)
        self.__amount_paid = 0.0
        customer.add_to_balance(self.__order_total)

    # ---------- Getters and Setters ----------
    # Status has no setter because not every transition is legal (e.g. collected cannot
    # be cancelled, and cancelling also has to restore stock and the customer balance).
    # collect_order() and cancel_order() are the only way to change it. Order date does
    # have a setter so staff can record or correct a date rather than always using today.

    @property
    def order_id(self) -> uuid.UUID:
        """Get the unique order ID"""
        return self.__order_id

    @property
    def order_date(self) -> str:
        """Get date of the order"""
        return self.__order_date

    @order_date.setter
    def order_date(self, value: str) -> None:
        """
        Update the order date

        :param value: New date in DD-MM-YYYY format
        :raises ValueError: If the date is not a valid calendar date in DD-MM-YYYY format
        """
        self.__order_date = self.__validate_order_date(value)

    @property
    def order_status(self) -> OrderStatus:
        """Get the status of the order"""
        return self.__order_status

    @property
    def customer(self) -> Customer:
        """Get the customer on the order"""
        return self.__customer

    @property
    def items(self) -> list[OrderItem]:
        """Get the items on the order"""
        # A copy is returned so callers cannot add or remove items on a placed order.
        return self.__items.copy()

    @property
    def order_total(self) -> float:
        """Get the total price of the order after item and customer discounts"""
        return self.__order_total

    @property
    def amount_paid(self) -> float:
        """Get how much has been paid toward this order"""
        return self.__amount_paid

    @property
    def remaining_balance(self) -> float:
        """Get how much is still owed on this order"""
        # A cancelled order has already had its total taken back off the customer.
        if self.__order_status == "cancelled":
            return 0.0
        return round(self.__order_total - self.__amount_paid, 2)

    # ---------- Methods ----------

    def __validate_order_date(self, order_date: str) -> str:
        """
        Validate that the order date is a real calendar date in DD-MM-YYYY format

        :param order_date: Date string to validate
        :return: The validated date string
        :raises ValueError: If the date is not a valid calendar date in DD-MM-YYYY format
        """
        # strptime is used so the format and the calendar date are both checked.
        # That rejects values like 32-13-2026, not just strings that look the wrong shape.
        if not isinstance(order_date, str):
            raise ValueError("Order date must be a valid date in DD-MM-YYYY format")
        try:
            datetime.strptime(order_date, "%d-%m-%Y")
        except ValueError:
            raise ValueError("Order date must be a valid date in DD-MM-YYYY format")
        return order_date

    def record_payment(self, amount: float) -> None:
        """
        Record an amount paid toward this order and take it off the customer balance

        :param amount: Amount to apply to this order, must be greater than 0 and not more than remaining
        :raises ValueError: If amount is not greater than 0, or is more than what is still owed
        """
        if amount <= 0:
            raise ValueError("Payment amount must be greater than 0")
        if amount > self.remaining_balance:
            raise ValueError("Payment cannot be more than what is still owed on this order")
        self.__amount_paid = round(self.__amount_paid + amount, 2)
        self.__customer.reduce_balance(amount)

    def collect_order(self) -> None:
        """
        Update order status to collected

        :raises ValueError: If the order has already been collected or cancelled, or the
            customer is not allowed to collect it yet
        """
        if self.__order_status == "collected":
            raise ValueError("Order has already been collected")
        if self.__order_status == "cancelled":
            raise ValueError("Unable to collect cancelled order")
        # Pending is the only status that can move to collected. Whether this customer
        # may collect while still owing is answered by the customer subclass.
        if not self.__customer.can_collect_order(self.remaining_balance):
            raise ValueError("Order must be paid in full before it can be collected")
        self.__order_status = "collected"

    def cancel_order(self) -> None:
        """
        Update order status to cancelled, restore stock, and take the total off the customer balance

        :raises ValueError: If the order has already been collected or cancelled, or anything
            has been paid toward it
        """
        if self.__order_status == "collected":
            raise ValueError("Cannot cancel order that has already been collected")
        if self.__order_status == "cancelled":
            raise ValueError("Order has already been cancelled")
        if self.__amount_paid > 0:
            raise ValueError("Cannot cancel an order that has already been paid toward")
        # Stock is restored on every item, and the order total comes off what they owe,
        # matching how placing the order added it.
        for item in self.__items:
            item.restore_stock()
        self.__customer.reduce_balance(self.__order_total)
        self.__order_status = "cancelled"

    def __str__(self) -> str:
        """Returns a readable string of the order details"""
        item_text = "; ".join(str(item) for item in self.__items)
        return (
            "Order ID: {}, Order Date: {}, Order Status: {}, Customer: {},"
            " Items: [{}], Order Total: {}, Amount Paid: {}, Remaining Balance: {}"
            .format(
                self.__order_id, self.__order_date,
                self.__order_status, self.__customer.cust_name,
                item_text, self.__order_total,
                self.__amount_paid, self.remaining_balance,
            )
        )
