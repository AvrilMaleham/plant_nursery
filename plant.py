import uuid
from typing import Literal, get_args

# The four categories come from Brent's notes and are treated as a fixed set.
# A Literal type is used so anything outside that list is rejected on creation
# rather than being stored as an invalid category string.
PlantCategory = Literal["trees and shrubs", "perennials", "pot plants", "vegetable seedlings"]

class Plant:
    """Represents a plant with an ID, category, price and stock level"""
    
    def __init__(self, plant_name: str, plant_category: PlantCategory, plant_price: float, plant_stock: int) -> None:
        """
        Initialise a new Plant object

        :param plant_name: Name of the plant (does not need to be unique, same name can have different price/stock)
        :param plant_category: Category of the plant, must be one of the four allowed PlantCategory values
        :param plant_price: Price of the plant, must be greater than 0
        :param plant_stock: Stock on hand for this plant, must be greater than 0
        :raises ValueError: If category is invalid, price is not greater than 0, or stock is not greater than 0
        """
        
        # Name and data types are assumed to be provided correctly by the caller.
        # Validation here is for the business rules: allowed category, price above 0,
        # and starting stock above 0 (a new plant should not be created already sold out).
        if plant_category not in get_args(PlantCategory):
            raise ValueError(f"Plant category must be one of {get_args(PlantCategory)}")
        if plant_price <= 0:
            raise ValueError("Plant price must be greater than 0")
        if plant_stock <= 0:
            raise ValueError("Plant stock must be greater than 0")
        
        # UUID is used so each plant batch gets a unique ID without a counter or database.
        # Two plants can share a name (different batches, different prices) and still be told apart.
        self.__plant_id = uuid.uuid4()
        self.__plant_name = plant_name
        self.__plant_category = plant_category
        self.__plant_price = plant_price
        self.__plant_stock = plant_stock
        
    # ---------- Getters and Setters ----------
    # Name and category identify the plant and should not change once it is cataloged,
    # so those have getters only. Price can be updated if a batch is repriced.
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
    def plant_category(self) -> PlantCategory:
        """Get the plant category"""
        return self.__plant_category

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

        :param quantity: Quantity being requested
        :return: True if stock is greater than or equal to quantity, else False
        """
        return self.__plant_stock >= quantity

    def reduce_stock(self, quantity: int) -> None:
        """
        Reduce stock when an order goes through. Stock can never be below zero

        :param quantity: Quantity to remove from stock
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

        :param quantity: Quantity to add back
        :raises ValueError: If quantity is not positive
        """
        if quantity <= 0:
            raise ValueError("Quantity to restore must be greater than 0")
        self.__plant_stock += quantity
        
    def __str__(self) -> str:
        """Returns a readable string of the plant details"""
        return (
            "Plant ID: {}, Plant Name: {}, Plant Category: {},"
            " Plant Price: {}, Plant Stock: {}"
            .format(
                self.__plant_id, self.__plant_name,
                self.__plant_category, self.__plant_price,
                self.__plant_stock
            )
        )