import uuid
from typing import Literal, Optional, get_args

from sqlalchemy import CheckConstraint, Integer, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
from .exceptions import InsufficientStockError

# Pot size is only used by PotPlant. A Literal is used so anything outside
# small, medium, or large is rejected on creation.
PotSize = Literal["small", "medium", "large"]


class Plant(Base):
    """An abstract class representing a plant available for sale"""

    __tablename__ = "plants"
    __table_args__ = (
        CheckConstraint("plant_price > 0", name="ck_plants_price"),
        CheckConstraint("plant_stock >= 0", name="ck_plants_stock"),
        CheckConstraint(
            "plant_type <> 'pot plants' OR pot_size IS NOT NULL",
            name="ck_plants_pot_size",
        ),
        CheckConstraint(
            "plant_type = 'pot plants' OR pot_size IS NULL",
            name="ck_plants_pot_size_only",
        ),
        CheckConstraint(
            "pot_size IS NULL OR pot_size IN ('small', 'medium', 'large')",
            name="ck_plants_pot_size_value",
        ),
        CheckConstraint(
            "plant_type <> 'vegetable seedlings' "
            "OR seedlings_per_punnet IS NOT NULL",
            name="ck_plants_seedlings",
        ),
        CheckConstraint(
            "plant_type = 'vegetable seedlings' "
            "OR seedlings_per_punnet IS NULL",
            name="ck_plants_seedlings_only",
        ),
        CheckConstraint(
            "seedlings_per_punnet IS NULL OR seedlings_per_punnet > 0",
            name="ck_plants_seedlings_positive",
        ),
        CheckConstraint(
            "image_filename <> ''",
            name="ck_plants_image",
        ),
    )

    # Single-table inheritance: every plant type is one row in plants.
    # kind is stored in the plant_type column. The plant_type() method keeps
    # that name, so the column uses a different attribute name.
    _plant_id: Mapped[uuid.UUID] = mapped_column(
        "plant_id", Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kind: Mapped[str] = mapped_column("plant_type", String(50), nullable=False)
    _plant_name: Mapped[str] = mapped_column(
        "plant_name", String(200), nullable=False
    )
    _plant_price: Mapped[float] = mapped_column(
        "plant_price", Numeric(10, 2), nullable=False
    )
    _plant_stock: Mapped[int] = mapped_column(
        "plant_stock", Integer, nullable=False
    )
    # These two columns belong to one subclass each. Other plant types leave
    # them null. The checks above keep that split.
    _pot_size: Mapped[Optional[str]] = mapped_column(
        "pot_size", String(20), nullable=True
    )
    _seedlings_per_punnet: Mapped[Optional[int]] = mapped_column(
        "seedlings_per_punnet", Integer, nullable=True
    )
    _image_filename: Mapped[str] = mapped_column(
        "image_filename", String(200), nullable=False
    )

    __mapper_args__ = {
        "polymorphic_on": "kind",
        "polymorphic_abstract": True,
    }

    def __new__(cls, *args: object, **kwargs: object) -> "Plant":
        """
        Block a direct Plant or IndividualPlant. SQLAlchemy raises its own
        error for a polymorphic abstract class before __init__ runs, so the
        check has to happen here to stay a TypeError.

        :raises TypeError: If Plant or IndividualPlant is created directly
        """
        if cls.__mapper_args__.get("polymorphic_abstract"):
            if cls is Plant:
                message = (
                    "Can't instantiate abstract class Plant with abstract "
                    "methods plant_type, sale_unit"
                )
            else:
                message = (
                    "Can't instantiate abstract class IndividualPlant with "
                    "abstract methods plant_type"
                )
            raise TypeError(message)
        return super().__new__(cls)

    def __init__(
        self,
        plant_name: str,
        plant_price: float,
        plant_stock: int,
        image_filename: str,
    ) -> None:
        """
        Initialise a new Plant object

        :param plant_name (str): Name of the plant (does not need to be unique,
            same name can have different price/stock)
        :param plant_price (float): Price of the plant, must be greater than 0
        :param plant_stock (int): Stock on hand for this plant, must be greater
            than 0
        :param image_filename (str): File name of the plant photo
        :raises ValueError: If price is not greater than 0, stock is not
            greater than 0, or the photo file name is missing
        """
        if not image_filename:
            raise ValueError("A plant photo is required")

        # Name and data types are assumed to be provided correctly by the
        # caller. UUID is used so each plant batch gets a unique ID without a
        # counter. Two plants can share a name (different batches, different
        # prices) and still be told apart.
        self._plant_id = uuid.uuid4()
        self._plant_name = plant_name
        self._image_filename = image_filename
        # Price and stock go through their setters, so creation uses the same
        # checks as an update.
        self.plant_price = plant_price
        self.plant_stock = plant_stock

    # ---------- Getters and Setters ----------
    # Name identifies the plant and should not change once it is cataloged, so
    # it has a getter only. Price can be updated if a batch is repriced. Stock
    # can be restocked to a positive amount through this setter, but reaching
    # exactly zero is only allowed when reduce_stock() runs as part of an
    # order.

    @property
    def plant_id(self) -> uuid.UUID:
        """
        Get the unique plant ID

        :return (uuid.UUID): The unique plant ID
        """
        return self._plant_id

    @property
    def plant_name(self) -> str:
        """
        Get the plant name

        :return (str): The plant name
        """
        return self._plant_name

    @property
    def image_filename(self) -> str:
        """
        Get the file name of the plant photo

        :return (str): The file name of the plant photo
        """
        return self._image_filename

    @property
    def plant_price(self) -> float:
        """
        Get the plant price

        :return (float): The plant price
        """
        return float(self._plant_price)

    @plant_price.setter
    def plant_price(self, value: float) -> None:
        """
        Update the price of the plant

        :param value (float): New price, must be greater than 0
        :raises ValueError: If value is not greater than 0
        """
        if value <= 0:
            raise ValueError("Plant price must be greater than 0")
        self._plant_price = value

    @property
    def plant_stock(self) -> int:
        """
        Get the current stock of the plant

        :return (int): The current stock of the plant
        """
        return int(self._plant_stock)

    @plant_stock.setter
    def plant_stock(self, value: int) -> None:
        """
        Directly set the plant stock level. Stock cannot be set to 0, it can
        only reach exactly zero when reduced through an order.

        :param value (int): New stock level, must be greater than 0
        :raises ValueError: If value is not greater than 0
        """
        # Blocking 0 (and negatives) here stops staff from marking a plant as
        # sold out without going through an order. reduce_stock() subtracts
        # from the mapped column directly, so it can still land on exactly zero
        # when the last plant is sold.
        if value <= 0:
            raise ValueError(
                "Plant stock must be greater than 0. "
                "Stock can only reach zero through an order"
            )
        self._plant_stock = value

    # ---------- Methods ----------

    def check_stock(self, quantity: int) -> bool:
        """
        Check whether there is enough stock to supply an order

        :param quantity (int): Quantity being requested, in this plant's sale
            unit
        :return (bool): True if stock is greater than or equal to quantity,
            else False
        """
        return self.plant_stock >= quantity

    def reduce_stock(self, quantity: int) -> None:
        """
        Reduce stock when an order goes through. Stock can never be below zero

        :param quantity (int): Quantity to remove from stock, in this plant's
            sale unit
        :raises ValueError: If quantity is not positive
        :raises InsufficientStockError: If there isn't enough stock to cover it
        """
        if quantity <= 0:
            raise ValueError("Quantity to reduce must be greater than 0")
        # check_stock is used here so stock can never go below zero. Landing on
        # 0 is allowed because that is how a plant becomes unavailable after
        # being fully ordered. The column is updated directly so the setter's
        # ban on zero does not apply.
        if not self.check_stock(quantity):
            raise InsufficientStockError(
                f"Insufficient stock: only {self.plant_stock} available"
            )
        self._plant_stock = self.plant_stock - quantity

    def restore_stock(self, quantity: int) -> None:
        """
        Return stock when a pending order is cancelled

        :param quantity (int): Quantity to add back, in this plant's sale unit
        :raises ValueError: If quantity is not positive
        """
        if quantity <= 0:
            raise ValueError("Quantity to restore must be greater than 0")
        self._plant_stock = self.plant_stock + quantity

    def plant_type(self) -> str:
        """
        Return the type of plant

        :return (str): The type of plant
        """
        return self.kind

    def sale_unit(self) -> str:
        """
        Return the unit this plant is sold and stocked in

        :return (str): The unit this plant is sold and stocked in
        """
        raise NotImplementedError

    def __str__(self) -> str:
        """
        Returns a readable string of the plant details

        :return (str): A readable string of the plant details
        """
        return (
            "Plant ID: {}, Plant Name: {}, Plant Type: {}, Sale Unit: {},"
            " Plant Price: {}, Plant Stock: {}, Photo: {}"
            .format(
                self.plant_id, self.plant_name,
                self.plant_type(), self.sale_unit(),
                self.plant_price, self.plant_stock,
                self.image_filename,
            )
        )


class IndividualPlant(Plant):
    """An abstract subclass of Plant for types priced and stocked per plant"""

    __mapper_args__ = {"polymorphic_abstract": True}

    def sale_unit(self) -> str:
        """
        Return the unit this plant is sold and stocked in

        :return (str): The unit this plant is sold and stocked in
        """
        return "plant"


class TreeAndShrub(IndividualPlant):
    """
    Represents a subclass of plant called TreeAndShrub, priced and stocked per
    plant
    """

    # Kept in one place so the stored type and plant_type() cannot drift apart.
    TYPE_NAME = "trees and shrubs"

    __mapper_args__ = {"polymorphic_identity": TYPE_NAME}

    def plant_type(self) -> str:
        """
        Return the type of plant

        :return (str): The type of plant
        """
        return self.TYPE_NAME


class Perennial(IndividualPlant):
    """
    Represents a subclass of plant called Perennial, priced and stocked per
    plant
    """

    TYPE_NAME = "perennials"

    __mapper_args__ = {"polymorphic_identity": TYPE_NAME}

    def plant_type(self) -> str:
        """
        Return the type of plant

        :return (str): The type of plant
        """
        return self.TYPE_NAME


class PotPlant(Plant):
    """
    Represents a subclass of plant called PotPlant, priced and stocked by pot
    size
    """

    TYPE_NAME = "pot plants"

    __mapper_args__ = {"polymorphic_identity": TYPE_NAME}

    def __init__(
        self,
        plant_name: str,
        plant_price: float,
        plant_stock: int,
        image_filename: str,
        pot_size: PotSize,
    ) -> None:
        """
        Initialise a new PotPlant object

        :param plant_name (str): Name of the plant
        :param plant_price (float): Price for this pot size, must be greater
            than 0
        :param plant_stock (int): Number of pots on hand, must be greater than
            0
        :param image_filename (str): File name of the plant photo
        :param pot_size (PotSize): Pot size, must be small, medium, or large
        :raises ValueError: If pot size is invalid, price is not greater than
            0, stock is not greater than 0, or the photo file name is missing
        """
        if pot_size not in get_args(PotSize):
            raise ValueError(f"Pot size must be one of {get_args(PotSize)}")

        super().__init__(
            plant_name, plant_price, plant_stock, image_filename
        )
        self._pot_size = pot_size

    @property
    def pot_size(self) -> PotSize:
        """
        Get the pot size

        :return (PotSize): The pot size
        """
        return self._pot_size  # type: ignore[return-value]

    def plant_type(self) -> str:
        """
        Return the type of plant

        :return (str): The type of plant
        """
        return self.TYPE_NAME

    def sale_unit(self) -> str:
        """
        Return the unit this plant is sold and stocked in

        :return (str): The unit this plant is sold and stocked in
        """
        return "pot"

    def __str__(self) -> str:
        """
        Returns a readable string of the pot plant details

        :return (str): A readable string of the pot plant details
        """
        return "{}, Pot Size: {}".format(super().__str__(), self.pot_size)


class VegetableSeedling(Plant):
    """
    Represents a subclass of plant called VegetableSeedling, priced and stocked
    per punnet
    """

    TYPE_NAME = "vegetable seedlings"

    __mapper_args__ = {"polymorphic_identity": TYPE_NAME}

    def __init__(
        self,
        plant_name: str,
        plant_price: float,
        plant_stock: int,
        image_filename: str,
        seedlings_per_punnet: int = 6,
    ) -> None:
        """
        Initialise a new VegetableSeedling object

        :param plant_name (str): Name of the plant
        :param plant_price (float): Price per punnet, must be greater than 0
        :param plant_stock (int): Number of punnets on hand, must be greater
            than 0
        :param image_filename (str): File name of the plant photo
        :param seedlings_per_punnet (int): Seedlings in each punnet, defaults
            to 6, must be greater than 0
        :raises ValueError: If seedlings per punnet is not greater than 0,
            price is not greater than 0, stock is not greater than 0, or the
            photo file name is missing
        """
        if seedlings_per_punnet <= 0:
            raise ValueError("Seedlings per punnet must be greater than 0")

        super().__init__(
            plant_name, plant_price, plant_stock, image_filename
        )
        self._seedlings_per_punnet = seedlings_per_punnet

    @property
    def seedlings_per_punnet(self) -> int:
        """
        Get the number of seedlings in each punnet

        :return (int): The number of seedlings in each punnet
        """
        return int(self._seedlings_per_punnet)

    def plant_type(self) -> str:
        """
        Return the type of plant

        :return (str): The type of plant
        """
        return self.TYPE_NAME

    def sale_unit(self) -> str:
        """
        Return the unit this plant is sold and stocked in

        :return (str): The unit this plant is sold and stocked in
        """
        return "punnet"

    def __str__(self) -> str:
        """
        Returns a readable string of the vegetable seedling details

        :return (str): A readable string of the vegetable seedling details
        """
        return "{}, Seedlings Per Punnet: {}".format(
            super().__str__(), self.seedlings_per_punnet
        )
