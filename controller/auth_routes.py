"""Login, logout, and the dashboard."""

from flask import flash, redirect, render_template, request, session, url_for

from controller.blueprint import is_team, nursery_bp, signed_in, system
from controller.parsing import text
from model.exceptions import LoginFailedError
from model.user import TEAM_ROLE


@nursery_bp.route("/")
def home() -> str:
    """
    Show the dashboard for the logged-in person, or the login screen.

    :return (str): The rendered dashboard or login page
    """
    if system().current_user is None:
        return render_template("login.html")
    if is_team():
        follow_up = system().orders_uncollected_for_seven_days()
        return render_template(
            "dashboard.html",
            follow_up=follow_up,
            plant_count=len(system().catalog.plant_list),
            customer_count=len(system().directory.customer_list),
            order_count=len(system().history.order_list),
            payment_count=len(system().payment_history.payment_list),
        )
    customer = system().current_user.customer
    orders = system().get_customer_order_history(customer)
    follow_up = [
        order for order in orders if order.is_uncollected_too_long()
    ]
    return render_template(
        "dashboard.html",
        customer=customer,
        orders=orders,
        payments=system().get_customer_payments(customer),
        follow_up=follow_up,
    )


@nursery_bp.route("/login", methods=["GET", "POST"])
def login() -> str:
    """
    Check a username and password, then open that person's dashboard.

    :return (str): The login page, or a redirect after a successful login
    """
    if system().current_user is not None:
        return redirect(url_for("nursery.home"))
    if request.method == "GET":
        return render_template("login.html")

    username = text(request.form.get("username"))
    password = request.form.get("password") or ""
    try:
        user = system().login(username, password)
    except LoginFailedError as error:
        return render_template(
            "login.html", error=str(error), username=username
        )

    session.clear()
    session["user_id"] = str(user.user_id)
    if user.role == TEAM_ROLE:
        flash("Logged in as the nursery team.", "success")
    else:
        flash(f"Logged in as {user.customer.cust_name}.", "success")
    return redirect(url_for("nursery.home"))


@nursery_bp.route("/logout", methods=["POST"])
def logout() -> str:
    """
    End the current login.

    :return (str): A redirect to the login page
    """
    system().logout()
    session.clear()
    flash("You have logged out.", "success")
    return redirect(url_for("nursery.login"))


@nursery_bp.route("/account")
@signed_in
def account() -> str:
    """
    Show the logged-in customer's own details.

    :return (str): The customer page, or a redirect for the team login
    """
    if is_team():
        return redirect(url_for("nursery.customers"))
    customer = system().current_user.customer
    return render_template(
        "customer.html",
        customer=system().find_customer(customer.cust_id),
        orders=[
            (order, order.is_uncollected_too_long())
            for order in system().get_customer_order_history(customer)
        ],
        payments=system().get_customer_payments(customer),
        activity=system().customer_activity(customer),
        allow_remove=False,
    )
