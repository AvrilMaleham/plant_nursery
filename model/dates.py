"""Dates are stored as real dates and shown as DD-MM-YYYY."""

from datetime import date, datetime
from typing import Optional, Union

DISPLAY_FORMAT = "%d-%m-%Y"

# What a caller may hand over as a date. Text must be DD-MM-YYYY.
DateInput = Union[date, str]


def parse_date(
    value: Optional[DateInput],
    label: str = "Date",
) -> date:
    """
    Turn a date or DD-MM-YYYY text into a date. None means today.

    :param value (Optional[DateInput]): A date, DD-MM-YYYY text, or None
    :param label (str): The name to use in the message
    :return (date): The date
    :raises ValueError: If the text is not a real date in DD-MM-YYYY format
    """
    if value is None:
        return date.today()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(value.strip(), DISPLAY_FORMAT).date()
    except (ValueError, AttributeError):
        raise ValueError(
            f"{label} must be a valid date in DD-MM-YYYY format"
        ) from None


def format_date(value: Optional[date]) -> str:
    """
    Show a date as DD-MM-YYYY

    :param value (Optional[date]): The date
    :return (str): The text, or an empty string when there is no date
    """
    if value is None:
        return ""
    return value.strftime(DISPLAY_FORMAT)
