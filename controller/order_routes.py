"""Orders, payments, invoices, and receipts."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from flask import flash, g, redirect, render_template, request, url_for

from controller.blueprint import (
    RULE_ERRORS,
    explain,
    is_team,
    nursery_bp,
    signed_in,
    system,
)
from controller.customer_routes import every_customer
from controller.parsing import read_float, text
from model.order import Order
from model.payment import CreditCardPayment, DebitCardPayment


@dataclass
class ShownOrder:
    """An order plus the follow-up flag the model calculated."""

    order: Order
    needs_follow_up: bool


def show_order(order: Order) -> ShownOrder:
    """
    Pair an order with whether it has been waiting at least seven days.

    :param order (Order): The order to show
    :return (ShownOrder): The order and the flag
    """
    return ShownOrder(order, order.is_uncollected_too_long())


def order_form_page(error: str = "", selected: str = "") -> str:
    """
    Render the place-order form.

    :param error (str): A reason from the model, when the last attempt failed
    :param selected (str): A plant id to start with a quantity of 1
    :return (str): The rendered form
    """
    plants = system().search_plants()
    plants.sort(key=lambda plant: plant.plant_name.casefold())
    customers = every_customer() if is_team() else []
    return render_template(
        "order_form.html",
        plants=plants,
        customers=customers,
        error=error,
        selected_plant_id=selected,
        selected_customer_id=text(request.args.get("customer_id")),
        form=request.form,
    )


@nursery_bp.route("/orders")
@signed_in
def orders() -> str:
    """
    List orders. The team can narrow them by status. A customer sees their own.

    :return (str): The order list
    """
    status = text(request.args.get("status"))
    try:
        if is_team():
            if status:
                found = system().filter_orders(status)
            else:
                found = []
                for order_status in ("pending", "collected", "cancelled"):
                    found.extend(system().filter_orders(order_status))
        else:
            customer = system().current_user.customer
            if status:
                found = system().filter_orders(status, customer)
            else:
                found = system().get_customer_order_history(customer)
    except RULE_ERRORS as error:
        return explain(error)

    shown = [show_order(order) for order in found]
    shown.sort(
        key=lambda row: (
            not row.needs_follow_up,
            datetime.strptime(row.order.order_date, "%d-%m-%Y"),
        )
    )
    return render_template("orders.html", orders=shown, status=status)


@nursery_bp.route("/orders/new", methods=["GET", "POST"])
@signed_in
def place_order() -> str:
    """
    Place an order. A customer orders for themselves. The team chooses who.

    :return (str): The form, or the new order once it is accepted
    """
    if request.method == "GET":
        try:
            return order_form_page(selected=text(request.args.get("plant_id")))
        except RULE_ERRORS as error:
            return explain(error)

    try:
        if is_team():
            raw_id = text(request.form.get("customer_id"))
            try:
                customer_id = uuid.UUID(raw_id)
            except ValueError:
                raise ValueError("Choose a customer") from None
            customer = system().find_customer(customer_id)
        else:
            customer = system().current_user.customer
        items = []
        for plant in system().search_plants():
            raw = text(request.form.get(f"qty-{plant.plant_id}"))
            # A blank box means this plant is not part of the order.
            if not raw:
                continue
            try:
                quantity = int(raw)
            except ValueError:
                raise ValueError(
                    f"Quantity for {plant.plant_name} must be a whole "
                    "number"
                ) from None
            # Anything typed has to be a real quantity. Dropping a 0 or a
            # negative number quietly would leave the person thinking they
            # had ordered it.
            if quantity < 1:
                raise ValueError(
                    f"Quantity for {plant.plant_name} must be at least 1. "
                    "Leave the box empty if you do not want it"
                )
            items.append((plant, quantity))
        if not items:
            raise ValueError("Enter a quantity for at least one plant")
        order = system().place_order(customer, items)
    except RULE_ERRORS as error:
        g.db.rollback()
        return order_form_page(error=str(error))

    flash("Order placed.", "success")
    return redirect(url_for("nursery.order_detail", order_id=order.order_id))


@nursery_bp.route("/orders/<uuid:order_id>")
@signed_in
def order_detail(order_id: uuid.UUID) -> str:
    """
    Show an order, its invoice, and the actions for it.

    :param order_id (uuid.UUID): The order to show
    :return (str): The order page
    """
    try:
        order = system().find_order(order_id)
        invoice = system().invoice_for(order)
        payments = system().get_order_payments(order)
    except RULE_ERRORS as error:
        return explain(error)
    pending = order.order_status == "pending"
    # Community customers have to pay an order off before it can be collected.
    # Staff and students can collect while they still owe. The button stays
    # visible either way; collect_order() refuses the ones that are not ready.
    collect_allowed = order.customer.can_collect_order(order.remaining_balance)
    return render_template(
        "order_detail.html",
        order=order,
        invoice=invoice,
        payments=payments,
        needs_follow_up=order.is_uncollected_too_long(),
        awaiting_payment=pending and not collect_allowed,
        can_pay=order.remaining_balance > 0,
    )


@nursery_bp.route("/orders/<uuid:order_id>/pay", methods=["POST"])
@signed_in
def pay_order(order_id: uuid.UUID) -> str:
    """
    Record a payment toward an order and show the receipt.

    :param order_id (uuid.UUID): The order being paid
    :return (str): The receipt, or the order page when the payment is refused
    """
    try:
        order = system().find_order(order_id)
        amount = read_float(request.form.get("amount"), "Amount")
        card = text(request.form.get("card_number"))
        method = text(request.form.get("method"))
        # The payment subclass owns the surcharge. This only picks which one
        # was chosen on the form, then the model applies it to the order.
        if method == "credit card":
            payment = CreditCardPayment(
                order.customer,
                order,
                amount,
                card,
                text(request.form.get("expiry_date")),
            )
        elif method == "debit card":
            payment = DebitCardPayment(
                order.customer,
                order,
                amount,
                card,
                text(request.form.get("bank_name")),
            )
        else:
            raise ValueError(
                "Payment method must be credit card or debit card"
            )
        system().record_payment(payment)
    except RULE_ERRORS as error:
        return explain(error)
    flash("Payment recorded.", "success")
    return redirect(url_for("nursery.receipt", payment_id=payment.payment_id))


@nursery_bp.route("/orders/<uuid:order_id>/cancel", methods=["POST"])
@signed_in
def cancel_order(order_id: uuid.UUID) -> str:
    """
    Cancel a pending unpaid order.

    :param order_id (uuid.UUID): The order to cancel
    :return (str): The order page
    """
    try:
        order = system().find_order(order_id)
        system().cancel_order(order)
    except RULE_ERRORS as error:
        return explain(error)
    flash("Order cancelled.", "success")
    return redirect(url_for("nursery.order_detail", order_id=order.order_id))


@nursery_bp.route("/orders/<uuid:order_id>/collect", methods=["POST"])
@signed_in
def collect_order(order_id: uuid.UUID) -> str:
    """
    Mark an order collected. Only the team can do this.

    :param order_id (uuid.UUID): The order to collect
    :return (str): The order page
    """
    try:
        order = system().find_order(order_id)
        system().collect_order(order)
    except RULE_ERRORS as error:
        return explain(error)
    flash("Order marked as collected.", "success")
    return redirect(url_for("nursery.order_detail", order_id=order.order_id))


@nursery_bp.route("/payments")
@signed_in
def payments() -> str:
    """
    List payments. The team sees everyone's. A customer sees their own.

    :return (str): The payment list
    """
    try:
        if is_team():
            found = []
            for customer in every_customer():
                found.extend(system().get_customer_payments(customer))
        else:
            customer = system().current_user.customer
            found = system().get_customer_payments(customer)
    except RULE_ERRORS as error:
        return explain(error)
    return render_template("payments.html", payments=found)


@nursery_bp.route("/payments/<uuid:payment_id>")
@signed_in
def receipt(payment_id: uuid.UUID) -> str:
    """
    Show the receipt for one payment.

    :param payment_id (uuid.UUID): The payment to show
    :return (str): The receipt
    """
    try:
        payment = system().find_payment(payment_id)
        printed = system().receipt_for(payment)
    except RULE_ERRORS as error:
        return explain(error)
    return render_template("receipt.html", receipt=printed, payment=payment)
