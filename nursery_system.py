import uuid
from plant import Plant
from customer import Customer
from order import Order
from plant_catalog import PlantCatalog
from customer_directory import CustomerDirectory
from order_history import OrderHistory


class NurserySystem:
    """
    A central system class that manages the collections of plants, customers,
    and orders, and is responsible for adding, searching, updating, and
    reporting across them.
    """

    def __init__(self) -> None:
        """Initialise a new NurserySystem with empty catalog, directory, and order history"""
        # The three collections live here so the driver only talks to one object.
        # Orders can then only be created for plants and customers that are already registered.
        self.__catalog = PlantCatalog()
        self.__directory = CustomerDirectory()
        self.__history = OrderHistory()

    # ---------- Getters and Setters ----------

    @property
    def catalog(self) -> PlantCatalog:
        """Get the plant catalog"""
        return self.__catalog

    @property
    def directory(self) -> CustomerDirectory:
        """Get the customer directory"""
        return self.__directory

    @property
    def history(self) -> OrderHistory:
        """Get the order history"""
        return self.__history

    # ---------- Plant Methods ----------

    def add_plant(self, plant: Plant) -> None:
        """
        Add a new plant to the catalog

        :param plant: Plant to add
        :raises TypeError: If plant is not a Plant object
        :raises ValueError: If a plant with the same ID already exists
        """
        self.__catalog.catalog_plant(plant)

    def find_plant(self, plant_id: uuid.UUID) -> Plant:
        """
        Search for a plant by its ID

        :param plant_id: The UUID of the plant to find
        :return: The matching Plant object
        :raises ValueError: If no plant with that ID is found
        """
        for plant in self.__catalog.plant_list:
            # Search is by ID because plant names are not unique (two batches can share a name).
            if plant.plant_id == plant_id:
                return plant
        raise ValueError(f"No plant found with ID {plant_id}")

    def display_all_plants(self) -> None:
        """Print a readable list of every plant in the catalog"""
        self.__catalog.display_all_plants()

    def get_available_plants(self) -> list[Plant]:
        """
        Return plants that currently have stock available to sell

        :return: A list of Plant objects with current stock greater than 0
        """
        return self.__catalog.get_available_plants()

    def display_available_plants(self) -> None:
        """Print a readable list of plants with non-zero current stock"""
        self.__catalog.display_available_plants()

    # ---------- Customer Methods ----------

    def add_customer(self, customer: Customer) -> None:
        """
        Add a new customer to the directory

        :param customer: Customer to add
        :raises TypeError: If customer is not a Customer object
        :raises ValueError: If a customer with the same ID already exists
        """
        self.__directory.add_customer(customer)

    def find_customer(self, customer_id: uuid.UUID) -> Customer:
        """
        Search for a customer by their ID

        :param customer_id: The UUID of the customer to find
        :return: The matching Customer object
        :raises ValueError: If no customer with that ID is found
        """
        for customer in self.__directory.customer_list:
            # Search is by ID because customer names are not unique.
            if customer.cust_id == customer_id:
                return customer
        raise ValueError(f"No customer found with ID {customer_id}")

    def display_all_customers(self) -> None:
        """Print a readable list of every customer in the directory"""
        self.__directory.display_all_customers()

    def display_staff_customers(self) -> None:
        """Print a readable list of staff customers"""
        self.__directory.display_staff_customers()

    def display_student_customers(self) -> None:
        """Print a readable list of student customers"""
        self.__directory.display_student_customers()

    def display_community_customers(self) -> None:
        """Print a readable list of community customers"""
        self.__directory.display_community_customers()

    # ---------- Order Methods ----------

    def place_order(
        self,
        customer: Customer,
        items: list[tuple[Plant, int]],
        order_date: str = None,
    ) -> Order:
        """
        Place a new order after validating the customer and plants are registered by ID.
        The customer's place-order rules are checked before the order is created.
        Stock is reduced immediately when the order is created.

        :param customer: The Customer placing the order
        :param items: A list of (plant, quantity) pairs to include on the order
        :param order_date: Optional order date in DD-MM-YYYY format, defaults to today
        :return: The newly created Order object
        :raises ValueError: If customer or a plant is not registered, the customer is not
            allowed to place an order, there is insufficient stock, or the order date is invalid
        """
        # Registration is checked by ID rather than `customer in list` / `plant in list`.
        # That way a Customer or Plant with the same ID is accepted even if it is not
        # the exact same Python object that was originally added.
        customer_found = False
        for existing_customer in self.__directory.customer_list:
            if existing_customer.cust_id == customer.cust_id:
                customer_found = True
                break
        if not customer_found:
            raise ValueError("Customer is not registered in the system")

        for plant, _quantity in items:
            plant_found = False
            for existing_plant in self.__catalog.plant_list:
                if existing_plant.plant_id == plant.plant_id:
                    plant_found = True
                    break
            if not plant_found:
                raise ValueError("Plant is not registered in the system")

        # Ask the customer whether they may order. Staff/student use balance,
        # community uses how many pending orders they already have.
        pending_count = self.__history.get_pending_order_count(customer)
        if not customer.can_place_order(pending_count):
            raise ValueError("Customer is not allowed to place a new order")

        # Creating the Order reduces stock and adds the total to the customer balance.
        order = Order(customer, items, order_date)
        self.__history.add_order(order)
        return order

    def find_order(self, order_id: uuid.UUID) -> Order:
        """
        Search for an order by its ID

        :param order_id: The UUID of the order to find
        :return: The matching Order object
        :raises ValueError: If no order with that ID is found
        """
        for order in self.__history.order_list:
            if order.order_id == order_id:
                return order
        raise ValueError(f"No order found with ID {order_id}")

    def collect_order(self, order: Order) -> None:
        """
        Mark an order as collected

        :param order: The Order to collect
        :raises ValueError: If the order is not in the system, or cannot be collected
        """
        if order not in self.__history.order_list:
            raise ValueError("Order is not in the system")
        # collect_order() on Order enforces the legal status change, this only confirms
        # the order belongs to this nursery first.
        order.collect_order()

    def cancel_order(self, order: Order) -> None:
        """
        Cancel a pending unpaid order, restore the stock, and take the total off the customer balance

        :param order: The Order to cancel
        :raises ValueError: If the order is not in the system, or cannot be cancelled
        """
        if order not in self.__history.order_list:
            raise ValueError("Order is not in the system")
        # cancel_order() on Order restores stock if the order is still pending.
        order.cancel_order()

    def get_customer_order_history(self, customer: Customer) -> list[Order]:
        """
        Retrieve all orders for a specific customer

        :param customer: The Customer to look up
        :return: A list of Order objects belonging to that customer
        :raises ValueError: If customer is not registered in the system
        """
        # Same ID check as place_order, so history can be requested without needing
        # the original Customer object that was added to the directory.
        customer_found = False
        for existing_customer in self.__directory.customer_list:
            if existing_customer.cust_id == customer.cust_id:
                customer_found = True
                break
        if not customer_found:
            raise ValueError("Customer is not registered in the system")
        return self.__history.get_customer_order_history(customer)

    def display_all_orders(self) -> None:
        """Print a readable list of every order on record"""
        self.__history.display_all_orders()

    # ---------- String Method ----------

    def __str__(self) -> str:
        """Returns a summary of the nursery system"""
        return (
            "Nursery System: {} plants, {} customers, {} orders"
            .format(
                len(self.__catalog.plant_list),
                len(self.__directory.customer_list),
                len(self.__history.order_list),
            )
        )
