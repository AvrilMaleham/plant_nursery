"""Turn form and query text into values the model can check."""

from typing import Optional


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


def read_float(raw: Optional[str], label: str) -> float:
    """
    Read a required number from a form field.

    :param raw (Optional[str]): The submitted text
    :param label (str): The field name to use in the message
    :return (float): The number
    :raises ValueError: If the field is blank or not a number
    """
    value = required_text(raw, label)
    try:
        return float(value)
    except ValueError:
        raise ValueError(f"{label} must be a number") from None


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


def optional_float(raw: Optional[str], label: str) -> Optional[float]:
    """
    Read a number when the field was filled in.

    :param raw (Optional[str]): The submitted text
    :param label (str): The field name to use in the message
    :return (Optional[float]): The number, or None when the field is blank
    :raises ValueError: If the field is not a number
    """
    value = text(raw)
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        raise ValueError(f"{label} must be a number") from None
