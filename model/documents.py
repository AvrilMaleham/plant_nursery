"""Invoices, receipts, and customer activity records."""

from datetime import date
from decimal import Decimal
from typing import Optional

from .dates import format_date
from .money import ZERO, MoneyInput, to_money
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
        unit_price: MoneyInput,
        line_cost: MoneyInput,
        bulk_discount: MoneyInput,
    ) -> None:
        """
        Initialise a new InvoiceLine object

        :param plant_name (str): Name of the plant
        :param quantity (int): Quantity in the plant's sale unit
        :param sale_unit (str): The unit, such as plant, pot, or punnet
        :param unit_price (MoneyInput): The price of one sale unit
        :param line_cost (MoneyInput): The line cost after any bulk discount
        :param bulk_discount (MoneyInput): How much the bulk discount took off
            this line, or 0
        """
        self.plant_name = plant_name
        self.quantity = quantity
        self.sale_unit = sale_unit
        self.unit_price = to_money(unit_price)
        self.line_cost = to_money(line_cost)
        self.bulk_discount = to_money(bulk_discount)

    @property
    def full_cost(self) -> Decimal:
        """
        Return the line cost before the bulk discount

        :return (Decimal): The line cost before the bulk discount
        """
        return self.line_cost + self.bulk_discount

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
        line_total = ZERO
        for item in order.items:
            # The stored line cost is after the 10% bulk discount. The
            # discount amount is the difference from the full line.
            full_line = to_money(item.plant.plant_price * item.quantity)
            bulk_discount = ZERO
            if item.quantity >= BULK_DISCOUNT_QUANTITY:
                bulk_discount = full_line - item.item_cost
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
        self.customer_discount = line_total - order.order_total
        self.total_to_pay = order.order_total

    @property
    def cost(self) -> Decimal:
        """
        Return the cost of the lines before any discount

        :return (Decimal): The cost of the lines before any discount
        """
        return sum((line.full_cost for line in self.lines), ZERO)

    @property
    def bulk_discount(self) -> Decimal:
        """
        Return the bulk discount across every line

        :return (Decimal): The bulk discount across every line
        """
        return sum((line.bulk_discount for line in self.lines), ZERO)

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
        remaining_on_order: Optional[MoneyInput] = None,
    ) -> None:
        """
        Build a receipt from a payment

        :param payment (Payment): The payment to show
        :param remaining_on_order (Optional[MoneyInput]): What was still owed
            on the order after this payment. When omitted, the order's current
            balance is used
        """
        self.payment_id = payment.payment_id
        self.order_id = payment.order.order_id
        self.order_number = payment.order.order_number
        self.customer_name = payment.customer.cust_name
        self.customer_number = payment.customer.customer_number
        self.payment_type = payment.payment_type()
        self.amount = payment.amount
        self.surcharge = payment.amount_charged() - payment.amount
        self.amount_charged = payment.amount_charged()
        if remaining_on_order is None:
            remaining_on_order = payment.order.remaining_balance
        self.remaining_on_order = to_money(remaining_on_order)

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

    def __init__(self, happened_on: date, action: str, detail: str) -> None:
        """
        Initialise a new ActivityRecord object

        :param happened_on (date): The day it happened
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
        return "{}: {} ({})".format(
            format_date(self.happened_on), self.detail, self.action
        )
