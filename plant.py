import uuid
from abc import ABC, abstractmethod
from typing import Literal, get_args

# Pot size is only used by PotPlant. A Literal is used so anything outside
# small, medium, or large is rejected on creation.
PotSize = Literal["small", "medium", "large"]


class Plant(ABC):
    """An abstract class representing a plant available for sale"""

    def __init__(self, plant_name: str, plant_price: float, plant_stock: int) -> None:
        """
        Initialise a new Plant object

        :param plant_name: Name of the plant (does not need to be unique, same name can have different price/stock)
        :param plant_price: Price of the plant, must be greater than 0
        :param plant_stock: Stock on hand for this plant, must be greater than 0
        :raises ValueError: If price is not greater than 0, or stock is not greater than 0
        """

        # Name and data types are assumed to be provided correctly by the caller.
        # Validation here is for the business rules: price above 0, and starting
        # stock above 0 (a new plant should not be created already sold out).
        if plant_price <= 0:
            raise ValueError("Plant price must be greater than 0")
        if plant_stock <= 0:
            raise ValueError("Plant stock must be greater than 0")

        # UUID is used so each plant batch gets a unique ID without a counter or database.
        # Two plants can share a name (different batches, different prices) and still be told apart.
        self.__plant_id = uuid.uuid4()
        self.__plant_name = plant_name
        self.__plant_price = plant_price
        self.__plant_stock = plant_stock

    # ---------- Getters and Setters ----------
    # Name identifies the plant and should not change once it is cataloged, so it
    # has a getter only. Price can be updated if a batch is repriced.
    # Stock can be restocked to a positive amount through this setter, but reaching
    # exactly zero is only allowed when reduce_stock() runs as part of an order.

    @property
    def plant_id(self) -> uuid.UUID:
        """Get the unique plant ID"""
        return self.__plant_id

    @property
    def plant_name(self) -> str:
        """Get the plant name"""
        return self.__plant_name

    @property
    def plant_price(self) -> float:
        """Get the plant price"""
        return self.__plant_price

    @plant_price.setter
    def plant_price(self, value: float) -> None:
        """
        Update the price of the plant

        :param value: New price, must be greater than 0
        :raises ValueError: If value is not greater than 0
        """
        if value <= 0:
            raise ValueError("Plant price must be greater than 0")
        self.__plant_price = value

    @property
    def plant_stock(self) -> int:
        """Get the current stock of the plant"""
        return self.__plant_stock

    @plant_stock.setter
    def plant_stock(self, value: int) -> None:
        """
        Directly set the plant stock level.
        Stock cannot be set to 0, it can only reach exactly zero when reduced through an order.

        :param value: New stock level, must be greater than 0
        :raises ValueError: If value is not greater than 0
        """
        # Blocking 0 (and negatives) here stops staff from marking a plant as sold out
        # without going through an order. reduce_stock() subtracts from the private field
        # directly, so it can still land on exactly zero when the last plant is sold.
        if value <= 0:
            raise ValueError("Plant stock must be greater than 0. Stock can only reach zero through an order")
        self.__plant_stock = value

    # ---------- Methods ----------

    def check_stock(self, quantity: int) -> bool:
        """
        Check whether there is enough stock to supply an order

        :param quantity: Quantity being requested, in this plant's sale unit
        :return: True if stock is greater than or equal to quantity, else False
        """
        return self.__plant_stock >= quantity

    def reduce_stock(self, quantity: int) -> None:
        """
        Reduce stock when an order goes through. Stock can never be below zero

        :param quantity: Quantity to remove from stock, in this plant's sale unit
        :raises ValueError: If quantity is not positive, or there isn't enough stock to cover it
        """
        if quantity <= 0:
            raise ValueError("Quantity to reduce must be greater than 0")
        # check_stock is used here so stock can never go below zero. Landing on 0 is allowed
        # because that is how a plant becomes unavailable after being fully ordered.
        if not self.check_stock(quantity):
            raise ValueError(f"Insufficient stock: only {self.__plant_stock} available")
        self.__plant_stock -= quantity

    def restore_stock(self, quantity: int) -> None:
        """
        Return stock when a pending order is cancelled

        :param quantity: Quantity to add back, in this plant's sale unit
        :raises ValueError: If quantity is not positive
        """
        if quantity <= 0:
            raise ValueError("Quantity to restore must be greater than 0")
        self.__plant_stock += quantity

    @abstractmethod
    def plant_type(self) -> str:
        """Return the type of plant"""
        pass

    @abstractmethod
    def sale_unit(self) -> str:
        """Return the unit this plant is sold and stocked in"""
        pass

    def __str__(self) -> str:
        """Returns a readable string of the plant details"""
        # plant_type() and sale_unit() are abstract, so whichever subclass this
        # object really is supplies the values
        return (
            "Plant ID: {}, Plant Name: {}, Plant Type: {}, Sale Unit: {},"
            " Plant Price: {}, Plant Stock: {}"
            .format(
                self.__plant_id, self.__plant_name,
                self.plant_type(), self.sale_unit(),
                self.__plant_price, self.__plant_stock,
            )
        )


class TreeAndShrub(Plant):
    """Represents a subclass of plant called TreeAndShrub, priced and stocked per plant"""

    def __init__(self, plant_name: str, plant_price: float, plant_stock: int) -> None:
        """
        Initialise a new TreeAndShrub object

        :param plant_name: Name of the plant
        :param plant_price: Price per plant, must be greater than 0
        :param plant_stock: Number of plants on hand, must be greater than 0
        :raises ValueError: If price is not greater than 0, or stock is not greater than 0
        """
        super().__init__(plant_name, plant_price, plant_stock)

    def plant_type(self) -> str:
        """Return the type of plant"""
        return "trees and shrubs"

    def sale_unit(self) -> str:
        """Return the unit this plant is sold and stocked in"""
        return "plant"


class Perennial(Plant):
    """Represents a subclass of plant called Perennial, priced and stocked per plant"""

    def __init__(self, plant_name: str, plant_price: float, plant_stock: int) -> None:
        """
        Initialise a new Perennial object

        :param plant_name: Name of the plant
        :param plant_price: Price per plant, must be greater than 0
        :param plant_stock: Number of plants on hand, must be greater than 0
        :raises ValueError: If price is not greater than 0, or stock is not greater than 0
        """
        super().__init__(plant_name, plant_price, plant_stock)

    def plant_type(self) -> str:
        """Return the type of plant"""
        return "perennials"

    def sale_unit(self) -> str:
        """Return the unit this plant is sold and stocked in"""
        return "plant"


class PotPlant(Plant):
    """Represents a subclass of plant called PotPlant, priced and stocked by pot size"""

    def __init__(self, plant_name: str, plant_price: float, plant_stock: int, pot_size: PotSize) -> None:
        """
        Initialise a new PotPlant object

        :param plant_name: Name of the plant
        :param plant_price: Price for this pot size, must be greater than 0
        :param plant_stock: Number of pots on hand, must be greater than 0
        :param pot_size: Pot size, must be small, medium, or large
        :raises ValueError: If pot size is invalid, price is not greater than 0, or stock is not greater than 0
        """
        if pot_size not in get_args(PotSize):
            raise ValueError(f"Pot size must be one of {get_args(PotSize)}")

        super().__init__(plant_name, plant_price, plant_stock)
        self.__pot_size = pot_size

    @property
    def pot_size(self) -> PotSize:
        """Get the pot size"""
        return self.__pot_size

    def plant_type(self) -> str:
        """Return the type of plant"""
        return "pot plants"

    def sale_unit(self) -> str:
        """Return the unit this plant is sold and stocked in"""
        return "pot"

    def __str__(self) -> str:
        """Returns a readable string of the pot plant details"""
        return "{}, Pot Size: {}".format(super().__str__(), self.__pot_size)


class VegetableSeedling(Plant):
    """Represents a subclass of plant called VegetableSeedling, priced and stocked per punnet"""

    def __init__(self, plant_name: str, plant_price: float, plant_stock: int, seedlings_per_punnet: int = 6) -> None:
        """
        Initialise a new VegetableSeedling object

        :param plant_name: Name of the plant
        :param plant_price: Price per punnet, must be greater than 0
        :param plant_stock: Number of punnets on hand, must be greater than 0
        :param seedlings_per_punnet: Seedlings in each punnet, defaults to 6, must be greater than 0
        :raises ValueError: If seedlings per punnet is not greater than 0, price is not greater than 0, or stock is not greater than 0
        """
        if seedlings_per_punnet <= 0:
            raise ValueError("Seedlings per punnet must be greater than 0")

        super().__init__(plant_name, plant_price, plant_stock)
        self.__seedlings_per_punnet = seedlings_per_punnet

    @property
    def seedlings_per_punnet(self) -> int:
        """Get the number of seedlings in each punnet"""
        return self.__seedlings_per_punnet

    def plant_type(self) -> str:
        """Return the type of plant"""
        return "vegetable seedlings"

    def sale_unit(self) -> str:
        """Return the unit this plant is sold and stocked in"""
        return "punnet"

    def __str__(self) -> str:
        """Returns a readable string of the vegetable seedling details"""
        return "{}, Seedlings Per Punnet: {}".format(
            super().__str__(), self.__seedlings_per_punnet
        )
