"""Customer lists, a customer's own record, and the team's changes."""

import uuid

from flask import flash, g, redirect, render_template, request, url_for

from controller.blueprint import (
    RULE_ERRORS,
    explain,
    is_team,
    nursery_bp,
    signed_in,
    system,
)
from controller.parsing import text
from model.customer import CommunityCustomer, StaffCustomer, StudentCustomer
from model.exceptions import NotAuthorisedError
from model.user import CUSTOMER_ROLE

CUSTOMER_TYPES = (
    StaffCustomer.TYPE_NAME,
    StudentCustomer.TYPE_NAME,
    CommunityCustomer.TYPE_NAME,
)
CUSTOMER_CLASSES = {
    StaffCustomer.TYPE_NAME: StaffCustomer,
    StudentCustomer.TYPE_NAME: StudentCustomer,
    CommunityCustomer.TYPE_NAME: CommunityCustomer,
}


def every_customer() -> list:
    """
    Return staff, students, and community customers.

    Each call goes through the model, so a customer login is refused.

    :return (list): Every customer
    """
    found = []
    for customer_type in CUSTOMER_TYPES:
        found.extend(system().filter_customers(customer_type))
    found.sort(key=lambda customer: customer.cust_name.casefold())
    return found


@nursery_bp.route("/customers")
@signed_in
def customers() -> str:
    """
    List customers, optionally one type at a time.

    :return (str): The customer list, or a redirect when refused
    """
    chosen = text(request.args.get("customer_type"))
    try:
        if chosen:
            listed = system().filter_customers(chosen)
        else:
            listed = every_customer()
    except RULE_ERRORS as error:
        return explain(error)
    listed.sort(key=lambda customer: customer.cust_name.casefold())
    return render_template(
        "customers.html",
        customers=listed,
        customer_types=CUSTOMER_TYPES,
        chosen=chosen,
    )


@nursery_bp.route("/customers/new", methods=["GET", "POST"])
@signed_in
def add_customer() -> str:
    """
    Add a customer and the login they will use.

    :return (str): The form, or the new customer's page
    """
    if request.method == "GET" and not is_team():
        return explain(NotAuthorisedError("Only the nursery team can do that"))
    if request.method == "GET":
        return render_template(
            "customer_form.html", customer_types=CUSTOMER_TYPES, form={}
        )

    try:
        name = text(request.form.get("cust_name"))
        email = text(request.form.get("cust_email"))
        phone = text(request.form.get("cust_phone"))
        customer_type = text(request.form.get("customer_type"))
        kind = CUSTOMER_CLASSES.get(customer_type)
        if kind is None:
            raise ValueError(
                "Customer type must be staff, student, or community"
            )
        customer = kind(name, email, phone)
        system().add_customer(customer)
        system().add_user(
            text(request.form.get("username")),
            request.form.get("password") or "",
            CUSTOMER_ROLE,
            customer,
        )
    except RULE_ERRORS as error:
        g.db.rollback()
        return render_template(
            "customer_form.html",
            error=str(error),
            customer_types=CUSTOMER_TYPES,
            form=request.form,
        )

    flash(f"{customer.cust_name} added.", "success")
    return redirect(
        url_for("nursery.customer_detail", customer_id=customer.cust_id)
    )


@nursery_bp.route("/customers/<uuid:customer_id>")
@signed_in
def customer_detail(customer_id: uuid.UUID) -> str:
    """
    Show one customer, their orders, payments, and activity.

    :param customer_id (uuid.UUID): The customer to show
    :return (str): The customer page, or a redirect when refused
    """
    try:
        customer = system().find_customer(customer_id)
        orders = [
            (order, order.is_uncollected_too_long())
            for order in system().get_customer_order_history(customer)
        ]
        payments = system().get_customer_payments(customer)
        activity = system().customer_activity(customer)
    except RULE_ERRORS as error:
        return explain(error)
    return render_template(
        "customer.html",
        customer=customer,
        orders=orders,
        payments=payments,
        activity=activity,
        allow_remove=is_team(),
    )


@nursery_bp.route("/customers/<uuid:customer_id>/remove", methods=["POST"])
@signed_in
def remove_customer(customer_id: uuid.UUID) -> str:
    """
    Remove a customer who has never placed an order.

    :param customer_id (uuid.UUID): The customer to remove
    :return (str): The customer list, or the customer page when refused
    """
    try:
        customer = system().find_customer(customer_id)
        name = customer.cust_name
        system().remove_customer(customer)
    except RULE_ERRORS as error:
        return explain(error)
    flash(f"{name} removed.", "success")
    return redirect(url_for("nursery.customers"))
