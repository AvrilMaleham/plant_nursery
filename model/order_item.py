import uuid

from sqlalchemy import ForeignKey, Integer, Numeric, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .exceptions import InsufficientStockError
from .plant import Plant

# Ten or more of the same plant on one line gets this discount.
BULK_DISCOUNT_QUANTITY = 10
BULK_DISCOUNT_RATE = 0.10


class OrderItem(Base):
    """
    Represents one plant type within an order, with its quantity and line cost
    """

    __tablename__ = "order_items"

    _item_id: Mapped[uuid.UUID] = mapped_column(
        "item_id", Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    _order_id: Mapped[uuid.UUID] = mapped_column(
        "order_id",
        Uuid(as_uuid=True),
        ForeignKey("orders.order_id"),
        nullable=False,
    )
    _plant_id: Mapped[uuid.UUID] = mapped_column(
        "plant_id",
        Uuid(as_uuid=True),
        ForeignKey("plants.plant_id"),
        nullable=False,
    )
    _quantity: Mapped[int] = mapped_column("quantity", Integer, nullable=False)
    _item_cost: Mapped[float] = mapped_column(
        "item_cost", Numeric(10, 2), nullable=False
    )
    _plant: Mapped[Plant] = relationship()
    _order: Mapped["Order"] = relationship("Order", back_populates="_items")

    def __init__(self, plant: Plant, quantity: int) -> None:
        """
        Initialise a new OrderItem object. Stock is reduced immediately for
        this item's quantity.

        :param plant (Plant): The plant being ordered
        :param quantity (int): Quantity in that plant's sale unit, must be at
            least 1
        :raises ValueError: If quantity is not greater than 0
        :raises InsufficientStockError: If there is not enough stock
        """
        # Quantity and stock are checked here so an order line owns that rule,
        # whether it is created on its own or as part of an order.
        OrderItem.validate(plant, quantity)

        self._item_id = uuid.uuid4()
        self._plant = plant
        self._quantity = quantity
        self._item_cost = self.__calculate_cost()
        plant.reduce_stock(quantity)

    # ---------- Getters and Setters ----------
    # Nothing on an item is changed after it is created. Quantity and plant are
    # what was ordered; cost is calculated once from those.

    @property
    def plant(self) -> Plant:
        """
        Get the plant on this item

        :return (Plant): The plant on this item
        """
        return self._plant

    @property
    def quantity(self) -> int:
        """
        Get the quantity of this item, in the plant's sale unit

        :return (int): The quantity of this item, in the plant's sale unit
        """
        return int(self._quantity)

    @property
    def item_cost(self) -> float:
        """
        Get the cost of this item after any bulk discount

        :return (float): The cost of this item after any bulk discount
        """
        return float(self._item_cost)

    # ---------- Methods ----------

    @staticmethod
    def validate(plant: Plant, quantity: int) -> None:
        """
        Check that this quantity of the plant can be ordered

        :param plant (Plant): The plant being ordered
        :param quantity (int): Quantity in that plant's sale unit, must be at
            least 1
        :raises ValueError: If quantity is not greater than 0
        :raises InsufficientStockError: If there is not enough stock
        """
        if quantity < 1:
            raise ValueError("Minimum order is 1")
        if not plant.check_stock(quantity):
            raise InsufficientStockError(
                f"Insufficient stock: only {plant.plant_stock} available")

    def __calculate_cost(self) -> float:
        """
        Calculate the line cost, applying a 10% discount for quantities of 10
        or more.

        :return (float): The item cost after any applicable discount, rounded
            to 2 decimal places
        """
        subtotal = self.plant.plant_price * self.quantity
        # 10 or more of the same plant (same catalog entry, so the same pot
        # size or the same seedling type) gets 10% off this line only.
        if self.quantity >= BULK_DISCOUNT_QUANTITY:
            return round(subtotal * (1 - BULK_DISCOUNT_RATE), 2)
        return round(subtotal, 2)

    def restore_stock(self) -> None:
        """Return this item's quantity to stock when the order is cancelled"""
        self.plant.restore_stock(self.quantity)

    def __str__(self) -> str:
        """
        Returns a readable string of the order item details

        :return (str): A readable string of the order item details
        """
        return (
            "Plant: {} ({}), Quantity: {} {}, Item Cost: {}"
            .format(
                self.plant.plant_name, self.plant.plant_type(),
                self.quantity, self.plant.sale_unit(),
                self.item_cost,
            )
        )
