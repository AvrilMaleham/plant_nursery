"""Turn form and query text into values the model can check."""

from decimal import Decimal
from typing import Optional

from model.money import to_money


def text(raw: Optional[str]) -> str:
    """
    Trim a form field.

    :param raw (Optional[str]): The submitted text
    :return (str): The text with surrounding space removed, or an empty string
    """
    if raw is None:
        return ""
    return raw.strip()


def required_text(raw: Optional[str], label: str) -> str:
    """
    Read a form field that must be filled in.

    :param raw (Optional[str]): The submitted text
    :param label (str): The field name to use in the message
    :return (str): The trimmed text
    :raises ValueError: If the field is blank
    """
    value = text(raw)
    if not value:
        raise ValueError(f"{label} is required")
    return value


def read_money(raw: Optional[str], label: str) -> Decimal:
    """
    Read a required amount of money from a form field.

    :param raw (Optional[str]): The submitted text
    :param label (str): The field name to use in the message
    :return (Decimal): The amount, in whole cents
    :raises ValueError: If the field is blank or not a number
    """
    # The text goes straight to Decimal, so 15.99 never passes through a
    # float.
    return to_money(required_text(raw, label), label)


def read_optional_money(raw: Optional[str], label: str) -> Optional[Decimal]:
    """
    Read an amount of money from a form field that may be left blank.

    :param raw (Optional[str]): The submitted text
    :param label (str): The field name to use in the message
    :return (Optional[Decimal]): The amount in whole cents, or None when the
        field is blank
    :raises ValueError: If the field is not a number, or is below zero
    """
    if not text(raw):
        return None
    amount = read_money(raw, label)
    if amount < 0:
        raise ValueError(f"{label} cannot be below $0")
    return amount


def read_int(raw: Optional[str], label: str) -> int:
    """
    Read a required whole number from a form field.

    :param raw (Optional[str]): The submitted text
    :param label (str): The field name to use in the message
    :return (int): The whole number
    :raises ValueError: If the field is blank or not a whole number
    """
    value = required_text(raw, label)
    try:
        return int(value)
    except ValueError:
        raise ValueError(f"{label} must be a whole number") from None
