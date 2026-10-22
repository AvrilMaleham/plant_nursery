"""
Nursery controllers.

Each route calls the model, then chooses a template. The templates show
the result and send the next action back here.
"""

from controller.blueprint import nursery_bp
from controller import (  # noqa: F401
    auth_routes,
    customer_routes,
    order_routes,
    plant_routes,
    report_routes,
)

__all__ = ["nursery_bp"]
