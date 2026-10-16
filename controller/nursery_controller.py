"""Routes for the nursery application."""

from flask import Blueprint, render_template

nursery_bp = Blueprint("nursery", __name__)


@nursery_bp.route("/")
def home() -> str:
    """
    Show the nursery home page.

    :return (str): The rendered home page
    """
    return render_template("home.html")
