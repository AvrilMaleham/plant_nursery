"""Invoices, receipts, and customer activity records."""

from typing import Optional

from .order import Order
from .order_item import BULK_DISCOUNT_QUANTITY
from .payment import Payment


class InvoiceLine:
    """One line on an invoice, after any bulk discount"""

    def __init__(
        self,
        plant_name: str,
        quantity: int,
        sale_unit: str,
        unit_price: float,
        line_cost: float,
        bulk_discount: float,
    ) -> None:
        """
        Initialise a new InvoiceLine object

        :param plant_name (str): Name of the plant
        :param quantity (int): Quantity in the plant's sale unit
        :param sale_unit (str): The unit, such as plant, pot, or punnet
        :param unit_price (float): The price of one sale unit
        :param line_cost (float): The line cost after any bulk discount
        :param bulk_discount (float): How much the bulk discount took off this
            line, or 0
        """
        self.plant_name = plant_name
        self.quantity = quantity
        self.sale_unit = sale_unit
        self.unit_price = unit_price
        self.line_cost = line_cost
        self.bulk_discount = bulk_discount

    @property
    def full_cost(self) -> float:
        """
        Return the line cost before the bulk discount

        :return (float): The line cost before the bulk discount
        """
        return round(self.line_cost + self.bulk_discount, 2)

    def __str__(self) -> str:
        """
        Returns a readable string of the invoice line

        :return (str): A readable string of the invoice line
        """
        return (
            "{}: {} {}, cost {}, bulk discount {}"
            .format(
                self.plant_name, self.quantity, self.sale_unit,
                self.line_cost, self.bulk_discount,
            )
        )


class Invoice:
    """A printable invoice for one order"""

    def __init__(self, order: Order) -> None:
        """
        Build an invoice from an order

        :param order (Order): The order to list
        """
        self.order_id = order.order_id
        self.order_number = order.order_number
        self.order_date = order.order_date
        self.customer_name = order.customer.cust_name
        self.customer_number = order.customer.customer_number
        self.lines: list[InvoiceLine] = []
        line_total = 0.0
        for item in order.items:
            # The stored line cost is after the 10% bulk discount. The
            # discount amount is the difference from the full line.
            full_line = round(item.plant.plant_price * item.quantity, 2)
            bulk_discount = 0.0
            if item.quantity >= BULK_DISCOUNT_QUANTITY:
                bulk_discount = round(full_line - item.item_cost, 2)
            self.lines.append(
                InvoiceLine(
                    item.plant.plant_name,
                    item.quantity,
                    item.plant.sale_unit(),
                    item.plant.plant_price,
                    item.item_cost,
                    bulk_discount,
                )
            )
            line_total += item.item_cost
        # The customer discount is whatever is left between the lines and the
        # order total. Community customers have a discount of 0.
        self.customer_discount = round(line_total - order.order_total, 2)
        self.total_to_pay = order.order_total

    @property
    def cost(self) -> float:
        """
        Return the cost of the lines before any discount

        :return (float): The cost of the lines before any discount
        """
        return round(sum(line.full_cost for line in self.lines), 2)

    @property
    def bulk_discount(self) -> float:
        """
        Return the bulk discount across every line

        :return (float): The bulk discount across every line
        """
        return round(sum(line.bulk_discount for line in self.lines), 2)

    def __str__(self) -> str:
        """
        Returns a readable invoice

        :return (str): A readable invoice
        """
        line_text = "; ".join(str(line) for line in self.lines)
        return (
            "Invoice for order {} ({}): Customer: {}, Customer number: {}, "
            "Items: [{}], Customer discount: {}, Total to pay: {}"
            .format(
                self.order_number, self.order_id,
                self.customer_name, self.customer_number,
                line_text, self.customer_discount, self.total_to_pay,
            )
        )


class Receipt:
    """A printable receipt for one payment"""

    def __init__(
        self,
        payment: Payment,
        remaining_on_order: Optional[float] = None,
    ) -> None:
        """
        Build a receipt from a payment

        :param payment (Payment): The payment to show
        :param remaining_on_order (Optional[float]): What was still owed on
            the order after this payment. When omitted, the order's current
            balance is used
        """
        self.payment_id = payment.payment_id
        self.order_id = payment.order.order_id
        self.order_number = payment.order.order_number
        self.customer_name = payment.customer.cust_name
        self.customer_number = payment.customer.customer_number
        self.payment_type = payment.payment_type()
        self.amount = payment.amount
        self.surcharge = round(payment.amount_charged() - payment.amount, 2)
        self.amount_charged = payment.amount_charged()
        if remaining_on_order is None:
            remaining_on_order = payment.order.remaining_balance
        self.remaining_on_order = remaining_on_order

    def __str__(self) -> str:
        """
        Returns a readable receipt

        :return (str): A readable receipt
        """
        return (
            "Receipt {}: Customer: {}, Customer number: {}, Order: {}, "
            "Paid: {}, How: {}, Surcharge: {}, Charged: {}, "
            "Still to pay on order: {}"
            .format(
                self.payment_id, self.customer_name, self.customer_number,
                self.order_id, self.amount, self.payment_type,
                self.surcharge, self.amount_charged, self.remaining_on_order,
            )
        )


class ActivityRecord:
    """One dated event in a customer's history"""

    def __init__(self, happened_on: str, action: str, detail: str) -> None:
        """
        Initialise a new ActivityRecord object

        :param happened_on (str): The date in DD-MM-YYYY format
        :param action (str): placed, paid, collected, or cancelled
        :param detail (str): A short description of the event
        """
        self.happened_on = happened_on
        self.action = action
        self.detail = detail

    def __str__(self) -> str:
        """
        Returns a readable activity line

        :return (str): A readable activity line
        """
        return "{}: {} ({})".format(self.happened_on, self.detail, self.action)
