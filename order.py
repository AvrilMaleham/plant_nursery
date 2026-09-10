import uuid
from typing import Literal, Optional
from customer import Customer
from plant import Plant 
from datetime import datetime, date

# The three statuses come from Brent's notes and are treated as a fixed set.
# A Literal type is used so the allowed values are explicit even though status
# itself is only changed through collect_order() and cancel_order().
OrderStatus = Literal["pending", "collected", "cancelled"]

class Order:
    """Represents an order with an order ID, customer, plant, quantity"""
    
    def __init__(self, customer: Customer, plant: Plant, order_quantity: int, order_date: Optional[str] = None) -> None:
        """
        Initialise a new Order object

        :param customer: The Customer associated with the order
        :param plant: The plant associated with the order
        :param order_quantity: Number of plants in the order
        :param order_date: Optional order date in DD-MM-YYYY format, defaults to today
        
        :raises ValueError: If order quantity is not greater than 0, insufficient stock, or order date is invalid
        """
        
        # Customer and plant types are already in the method signature, so they are not
        # checked again here. NurserySystem still confirms both are registered first.
        # An order must be at least 1 item and within current stock.
        if order_quantity < 1:
            raise ValueError("Minimum order is 1")
        if not plant.check_stock(order_quantity):
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
        self.__plant = plant
        self.__order_quantity = order_quantity
        self.__order_total = self.__calculate_total(plant, order_quantity)
        
        # Stock is taken off immediately so two pending orders cannot sell the same plants.
        # If the order is later cancelled, restore_stock() puts this quantity back.
        plant.reduce_stock(order_quantity)
        
    # ---------- Getters and Setters ----------
    # Status has no setter because not every transition is legal (e.g. collected cannot
    # be cancelled, and cancelling also has to restore stock). collect_order() and
    # cancel_order() are the only way to change it. Order date does have a setter so
    # staff can record or correct a date rather than always using today.
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
    def plant(self) -> Plant:
        """Get the plant on the order"""
        return self.__plant
    
    @property
    def order_quantity(self) -> int:
        """Get the quanity of the order"""
        return self.__order_quantity
    
    @property
    def order_total(self) -> float:
        """Get the total price of the order"""
        return self.__order_total
        
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

    def __calculate_total(self, plant: Plant, quantity: int) -> float:
        """
        Calculate the order total, applying a 10% discount for quantities of 10 or more.

        :param plant: The plant being ordered
        :param quantity: The quantity being ordered
        :return: The order total after any applicable discount, rounded to 2 decimal places
        """
        # 10 or more of the same plant gets 10% off. The result is rounded to 2 decimal
        # places so the stored total is a money amount rather than a long float.
        subtotal = plant.plant_price * quantity
        if quantity >= 10:
            return round(subtotal * 0.9, 2)
        return round(subtotal, 2)

    def collect_order(self) -> None:
        """
        Update order status to collected
        :raises ValueError: If the order has already been collected or cancelled
        """
        if self.__order_status == "collected":
            raise ValueError("Order has already been collected")
        if self.__order_status == "cancelled":
            raise ValueError("Unable to collect cancelled order")
        # Pending is the only status that can move to collected.
        self.__order_status = "collected"
        
    def cancel_order(self) -> None:
        """
        Update order status to cancelled
        :raises ValueError: If the order has already been collected or cancelled
        """
        if self.__order_status == "collected":
            raise ValueError("Cannot cancel order that has already been collected")
        if self.__order_status == "cancelled":
            raise ValueError("Order has already been cancelled")
        # Stock is restored before the status changes so a cancelled pending order
        # puts the plants back on the shelf.
        self.__plant.restore_stock(self.__order_quantity)
        self.__order_status = "cancelled"
        
    def __str__(self) -> str:
        """Returns a readable string of the order details"""
        return (
            "Order ID: {}, Order Date: {}, Order Status: {},"
            " Customer: {}, Plant: {}, Order Quantity: {}, Order Total: {}"
            .format(
                self.__order_id, self.__order_date,
                self.__order_status, self.__customer.cust_name,
                self.__plant.plant_name, self.__order_quantity,
                self.__order_total
            )
        )