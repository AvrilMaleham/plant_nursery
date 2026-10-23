"""Money is held as Decimal, rounded to whole cents."""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Union

# Anything the rest of the app may hand over as an amount. Floats are accepted
# so callers can write 15.99, but they are never added up as floats.
MoneyInput = Union[Decimal, int, float, str]

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def to_money(value: MoneyInput, label: str = "Amount") -> Decimal:
    """
    Turn an amount into a Decimal rounded to cents (halves round up)

    A float is read from its printed form, so 15.99 becomes exactly 15.99
    instead of the long binary value a float really holds.

    :param value (MoneyInput): The amount
    :param label (str): The name to use in the message
    :return (Decimal): The amount in whole cents
    :raises ValueError: If the value is not a finite number
    """
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a number")
    try:
        amount = value if isinstance(value, Decimal) else Decimal(str(value))
        if not amount.is_finite():
            raise InvalidOperation
        return amount.quantize(CENT, rounding=ROUND_HALF_UP)
    except InvalidOperation:
        # Not a number, infinity, or too large to hold in cents.
        raise ValueError(f"{label} must be a number") from None


def to_rate(value: Union[Decimal, int, float, str]) -> Decimal:
    """
    Turn a rate such as 0.015 into a Decimal without float noise

    :param value (Union[Decimal, int, float, str]): The rate
    :return (Decimal): The rate
    """
    return value if isinstance(value, Decimal) else Decimal(str(value))


def apply_rate(amount: Decimal, rate: Decimal) -> Decimal:
    """
    Work out amount x (1 - rate), rounded to cents

    :param amount (Decimal): The amount before the rate
    :param rate (Decimal): A discount as a fraction, 0.05 for 5 percent
    :return (Decimal): The amount after the discount
    """
    return to_money(amount * (Decimal(1) - rate))
