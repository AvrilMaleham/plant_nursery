"""Plant search, detail, and the team's catalog changes."""

import uuid
from pathlib import Path
from typing import Optional

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
from controller.parsing import (
    read_int,
    read_money,
    read_optional_money,
    required_text,
    text,
)
from model.plant import Perennial, PotPlant, TreeAndShrub, VegetableSeedling

IMAGE_DIR = Path(__file__).resolve().parents[1] / "view" / "static" / "images"
PHOTO_TYPES = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
# What each kind of image file starts with, and the extensions that go with
# it. A file name can say anything, but the first bytes say what the file is.
IMAGE_EXTENSIONS = {
    "png": {".png"},
    "jpeg": {".jpg", ".jpeg"},
    "gif": {".gif"},
    "webp": {".webp"},
}
PLANT_TYPES = (
    TreeAndShrub.TYPE_NAME,
    Perennial.TYPE_NAME,
    PotPlant.TYPE_NAME,
    VegetableSeedling.TYPE_NAME,
)


def image_kind(header: bytes) -> Optional[str]:
    """
    Say what kind of image a file is from its first bytes.

    :param header (bytes): The first 12 bytes of the file
    :return (Optional[str]): png, jpeg, gif, or webp, or None if the bytes
        are none of those
    """
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if header.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if header.startswith((b"GIF87a", b"GIF89a")):
        return "gif"
    if header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return "webp"
    return None


def save_photo(upload: object) -> str:
    """
    Store an uploaded plant photo and return its file name.

    :param upload (object): The file field from the form
    :return (str): The stored file name
    :raises ValueError: If the photo is missing, is not an image, or is a
        different kind of image from the one its file name says
    """
    filename = ""
    if upload is not None and getattr(upload, "filename", ""):
        filename = secure_filename(upload.filename)
    suffix = Path(filename).suffix.lower()
    if not filename or suffix not in PHOTO_TYPES:
        raise ValueError(
            "A plant photo is required, as a PNG, JPG, GIF, or WEBP file"
        )
    # The extension alone proves nothing. Read the start of the file, then
    # put the read position back so the whole file is still saved.
    header = upload.stream.read(12)
    upload.stream.seek(0)
    kind = image_kind(header)
    if kind is None or suffix not in IMAGE_EXTENSIONS[kind]:
        raise ValueError(
            "That file is not a real PNG, JPG, GIF, or WEBP image"
        )
    stored = f"{uuid.uuid4().hex}{suffix}"
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    upload.save(IMAGE_DIR / stored)
    return stored


def search_filters() -> dict[str, object]:
    """
    Read the plant search form.

    Brent asks for searches such as everything under $10, or between $10 and
    $30. The two price boxes are each optional, so a person can give a
    minimum, a maximum, both, or neither. The model includes both ends, so a
    plant priced exactly on a limit is found.

    :return (dict[str, object]): The values to show again, and the model
        filters
    :raises ValueError: If a price is not a number, or is below zero
    """
    return {
        "name": text(request.args.get("name")),
        "plant_type": text(request.args.get("plant_type")) or None,
        "min_price": text(request.args.get("min_price")),
        "max_price": text(request.args.get("max_price")),
        "in_stock": request.args.get("in_stock") == "on",
        "model_min": read_optional_money(
            request.args.get("min_price"), "Minimum price"
        ),
        "model_max": read_optional_money(
            request.args.get("max_price"), "Maximum price"
        ),
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
        # Show the search again as it was typed, with the reason.
        return render_template(
            "plants.html",
            plants=[],
            filters={
                "name": text(request.args.get("name")),
                "plant_type": text(request.args.get("plant_type")),
                "min_price": text(request.args.get("min_price")),
                "max_price": text(request.args.get("max_price")),
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
        name = required_text(request.form.get("plant_name"), "Plant name")
        price = read_money(request.form.get("price"), "Price")
        stock = read_int(request.form.get("stock"), "Stock")
        plant_type = text(request.form.get("plant_type"))
        if plant_type == PotPlant.TYPE_NAME:
            pot_size = text(request.form.get("pot_size"))
            plant = PotPlant(name, price, stock, filename, pot_size)
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


@nursery_bp.route("/plants/<uuid:plant_id>/price", methods=["POST"])
@signed_in
def update_plant_price(plant_id: uuid.UUID) -> str:
    """
    Change a plant's price. Stock is not touched, so a sold-out plant can
    still be repriced.

    :param plant_id (uuid.UUID): The plant to reprice
    :return (str): The plant page, with the model's confirmation or refusal
    """
    try:
        plant = system().find_plant(plant_id)
        system().update_plant_price(
            plant, read_money(request.form.get("price"), "Price")
        )
    except RULE_ERRORS as error:
        return explain(error)
    flash(f"{plant.plant_name} price updated.", "success")
    return redirect(url_for("nursery.plant_detail", plant_id=plant.plant_id))


@nursery_bp.route("/plants/<uuid:plant_id>/stock", methods=["POST"])
@signed_in
def update_plant_stock(plant_id: uuid.UUID) -> str:
    """
    Change a plant's stock, for example when a new batch comes out of the
    greenhouse. Price is not touched.

    :param plant_id (uuid.UUID): The plant to restock
    :return (str): The plant page, with the model's confirmation or refusal
    """
    try:
        plant = system().find_plant(plant_id)
        system().update_plant_stock(
            plant, read_int(request.form.get("stock"), "Stock")
        )
    except RULE_ERRORS as error:
        return explain(error)
    flash(f"{plant.plant_name} stock updated.", "success")
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
