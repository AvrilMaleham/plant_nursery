"""Team reports: plant history, customer activity, popularity, and revenue."""

import uuid
from datetime import date

from flask import render_template, request

from controller.blueprint import RULE_ERRORS, explain, nursery_bp, signed_in, system
from controller.customer_routes import every_customer
from controller.parsing import text

PERIODS = ("day", "week", "month")


@nursery_bp.route("/reports")
@signed_in
def reports() -> str:
    """
    Show the nursery reports. Only the team can open this screen.

    :return (str): The reports page, or a redirect when refused
    """
    period = text(request.args.get("period")) or "day"
    on_date = text(request.args.get("on_date")) or date.today().strftime("%d-%m-%Y")
    plant_id = text(request.args.get("plant_id"))
    customer_id = text(request.args.get("customer_id"))
    try:
        # most_ordered_plants refuses anyone who is not the team, so the rest
        # of this screen is never built for a customer.
        most = system().most_ordered_plants()
        least = system().least_ordered_plants()
        plants = system().search_plants()
        plants.sort(key=lambda plant: plant.plant_name.casefold())
        customers = every_customer()
        total = None
        if request.args.get("period"):
            total = system().revenue(period, on_date)
        history = None
        chosen_plant = None
        if plant_id:
            try:
                chosen_id = uuid.UUID(plant_id)
            except ValueError:
                raise ValueError("Choose a plant") from None
            chosen_plant = system().find_plant(chosen_id)
            history = system().plant_order_history(chosen_plant)
        activity = None
        chosen_customer = None
        if customer_id:
            try:
                chosen_id = uuid.UUID(customer_id)
            except ValueError:
                raise ValueError("Choose a customer") from None
            chosen_customer = system().find_customer(chosen_id)
            activity = system().customer_activity(chosen_customer)
    except RULE_ERRORS as error:
        return explain(error)

    return render_template(
        "reports.html",
        most=most,
        least=least,
        plants=plants,
        customers=customers,
        period=period,
        periods=PERIODS,
        on_date=on_date,
        total=total,
        history=history,
        chosen_plant=chosen_plant,
        activity=activity,
        chosen_customer=chosen_customer,
    )
