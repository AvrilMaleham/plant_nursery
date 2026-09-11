from plant import Plant


class OrderItem:
    """Represents one plant type within an order, with its quantity and line cost"""

    def __init__(self, plant: Plant, quantity: int) -> None:
        """
        Initialise a new OrderItem object.
        Stock is reduced immediately for this item's quantity.

        :param plant: The plant being ordered
        :param quantity: Quantity in that plant's sale unit, must be at least 1
        :raises ValueError: If quantity is not greater than 0, or there is not enough stock
        """
        if quantity < 1:
            raise ValueError("Minimum order is 1")
        if not plant.check_stock(quantity):
            raise ValueError(f"Insufficient stock: only {plant.plant_stock} available")

        self.__plant = plant
        self.__quantity = quantity
        self.__item_cost = self.__calculate_cost()
        plant.reduce_stock(quantity)

    # ---------- Getters and Setters ----------
    # Nothing on an item is changed after it is created. Quantity and plant are
    # what was ordered; cost is calculated once from those.

    @property
    def plant(self) -> Plant:
        """Get the plant on this item"""
        return self.__plant

    @property
    def quantity(self) -> int:
        """Get the quantity of this item, in the plant's sale unit"""
        return self.__quantity

    @property
    def item_cost(self) -> float:
        """Get the cost of this item after any bulk discount"""
        return self.__item_cost

    # ---------- Methods ----------

    def __calculate_cost(self) -> float:
        """
        Calculate the line cost, applying a 10% discount for quantities of 10 or more.

        :return: The item cost after any applicable discount, rounded to 2 decimal places
        """
        subtotal = self.__plant.plant_price * self.__quantity
        # 10 or more of the same plant (same catalog entry, so the same pot size
        # or the same seedling type) gets 10% off this line only.
        if self.__quantity >= 10:
            return round(subtotal * 0.9, 2)
        return round(subtotal, 2)

    def restore_stock(self) -> None:
        """Return this item's quantity to stock when the order is cancelled"""
        self.__plant.restore_stock(self.__quantity)

    def __str__(self) -> str:
        """Returns a readable string of the order item details"""
        return (
            "Plant: {} ({}), Quantity: {} {}, Item Cost: {}"
            .format(
                self.__plant.plant_name, self.__plant.plant_type(),
                self.__quantity, self.__plant.sale_unit(),
                self.__item_cost,
            )
        )
