"""Plant search, detail, and the team's catalog changes."""

import uuid
from pathlib import Path

from flask import flash, g, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

from controller.blueprint import (
    RULE_ERRORS,
    explain,
    is_team,
    nursery_bp,
    signed_in,
    system,
)
from model.exceptions import NotAuthorisedError
from controller.parsing import read_float, read_int, text
from model.plant import Perennial, PotPlant, TreeAndShrub, VegetableSeedling

IMAGE_DIR = Path(__file__).resolve().parents[1] / "view" / "static" / "images"
PHOTO_TYPES = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
PLANT_TYPES = (
    TreeAndShrub.TYPE_NAME,
    Perennial.TYPE_NAME,
    PotPlant.TYPE_NAME,
    VegetableSeedling.TYPE_NAME,
)


def save_photo(upload: object) -> str:
    """
    Store an uploaded plant photo and return its file name.

    :param upload (object): The file field from the form
    :return (str): The stored file name
    :raises ValueError: If the photo is missing or is not an image
    """
    filename = ""
    if upload is not None and getattr(upload, "filename", ""):
        filename = secure_filename(upload.filename)
    suffix = Path(filename).suffix.lower()
    if not filename or suffix not in PHOTO_TYPES:
        raise ValueError(
            "A plant photo is required, as a PNG, JPG, GIF, or WEBP file"
        )
    stored = f"{uuid.uuid4().hex}{suffix}"
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    upload.save(IMAGE_DIR / stored)
    return stored


def search_filters() -> dict[str, object]:
    """
    Read the plant search form.

    Brent asks for one price range, such as under $10 or between $10 and
    $30. Under $10 stops just below $10, so a $10 plant stays in the other
    band. The model includes its maximum.

    :return (dict[str, object]): The values to show again, and the model filters
    """
    band = text(request.args.get("price_band"))
    min_price = None
    max_price = None
    if band == "under-10":
        max_price = 9.99
    elif band == "10-30":
        min_price, max_price = 10.0, 30.0
    else:
        band = ""
    plant_type = text(request.args.get("plant_type")) or None
    return {
        "name": text(request.args.get("name")),
        "plant_type": plant_type,
        "price_band": band,
        "in_stock": request.args.get("in_stock") == "on",
        "model_min": min_price,
        "model_max": max_price,
    }


@nursery_bp.route("/plants")
@signed_in
def plants() -> str:
    """
    Search the catalog by name, type, price, and stock.

    :return (str): The plant list
    """
    try:
        filters = search_filters()
        matches = system().search_plants(
            name=filters["name"] or None,
            plant_type=filters["plant_type"],
            min_price=filters["model_min"],
            max_price=filters["model_max"],
            in_stock_only=bool(filters["in_stock"]),
        )
    except RULE_ERRORS as error:
        return render_template(
            "plants.html",
            plants=[],
            filters={
                "name": text(request.args.get("name")),
                "plant_type": text(request.args.get("plant_type")),
                "price_band": text(request.args.get("price_band")),
                "in_stock": request.args.get("in_stock") == "on",
            },
            plant_types=PLANT_TYPES,
            error=str(error),
        )
    matches.sort(key=lambda plant: plant.plant_name.casefold())
    return render_template(
        "plants.html",
        plants=matches,
        filters=filters,
        plant_types=PLANT_TYPES,
    )


@nursery_bp.route("/plants/new", methods=["GET", "POST"])
@signed_in
def add_plant() -> str:
    """
    Add a plant, including its photo. Only the team can do this.

    :return (str): The plant form, the new plant, or a redirect when refused
    """
    # The empty form is a team screen. A POST still goes through add_plant,
    # which refuses anyone who is not the team.
    if request.method == "GET" and not is_team():
        return explain(NotAuthorisedError("Only the nursery team can do that"))
    if request.method == "GET":
        return render_template(
            "plant_form.html", plant_types=PLANT_TYPES, form={}
        )

    filename = ""
    try:
        filename = save_photo(request.files.get("photo"))
        name = text(request.form.get("plant_name"))
        price = read_float(request.form.get("price"), "Price")
        stock = read_int(request.form.get("stock"), "Stock")
        plant_type = text(request.form.get("plant_type"))
        if plant_type == PotPlant.TYPE_NAME:
            plant = PotPlant(
                name, price, stock, filename, text(request.form.get("pot_size"))
            )
        elif plant_type == VegetableSeedling.TYPE_NAME:
            seedlings_raw = text(request.form.get("seedlings"))
            seedlings = (
                read_int(seedlings_raw, "Seedlings per punnet")
                if seedlings_raw
                else 6
            )
            plant = VegetableSeedling(name, price, stock, filename, seedlings)
        elif plant_type == Perennial.TYPE_NAME:
            plant = Perennial(name, price, stock, filename)
        elif plant_type == TreeAndShrub.TYPE_NAME:
            plant = TreeAndShrub(name, price, stock, filename)
        else:
            raise ValueError(
                "Plant type must be trees and shrubs, perennials, "
                "pot plants, or vegetable seedlings"
            )
        system().add_plant(plant)
    except RULE_ERRORS as error:
        g.db.rollback()
        if filename:
            (IMAGE_DIR / filename).unlink(missing_ok=True)
        return render_template(
            "plant_form.html",
            error=str(error),
            plant_types=PLANT_TYPES,
            form=request.form,
        )

    flash(f"{plant.plant_name} added to the catalog.", "success")
    return redirect(url_for("nursery.plant_detail", plant_id=plant.plant_id))


@nursery_bp.route("/plants/<uuid:plant_id>")
@signed_in
def plant_detail(plant_id: uuid.UUID) -> str:
    """
    Show one plant, including its photo.

    :param plant_id (uuid.UUID): The plant to show
    :return (str): The plant page, or a redirect when it is missing
    """
    try:
        plant = system().find_plant(plant_id)
    except RULE_ERRORS as error:
        return explain(error)
    return render_template("plant_detail.html", plant=plant)


@nursery_bp.route("/plants/<uuid:plant_id>/update", methods=["POST"])
@signed_in
def update_plant(plant_id: uuid.UUID) -> str:
    """
    Change a plant's price and stock.

    :param plant_id (uuid.UUID): The plant to update
    :return (str): The plant page, with the model's confirmation or refusal
    """
    try:
        plant = system().find_plant(plant_id)
        system().update_plant_price(
            plant, read_float(request.form.get("price"), "Price")
        )
        system().update_plant_stock(
            plant, read_int(request.form.get("stock"), "Stock")
        )
    except RULE_ERRORS as error:
        return explain(error)
    flash(f"{plant.plant_name} price and stock updated.", "success")
    return redirect(url_for("nursery.plant_detail", plant_id=plant.plant_id))


@nursery_bp.route("/plants/<uuid:plant_id>/remove", methods=["POST"])
@signed_in
def remove_plant(plant_id: uuid.UUID) -> str:
    """
    Remove a plant that has never been ordered.

    :param plant_id (uuid.UUID): The plant to remove
    :return (str): The catalog, or the plant page when removal is refused
    """
    try:
        plant = system().find_plant(plant_id)
        name = plant.plant_name
        system().remove_plant(plant)
    except RULE_ERRORS as error:
        return explain(error)
    flash(f"{name} removed from the catalog.", "success")
    return redirect(url_for("nursery.plants"))
