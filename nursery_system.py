import pickle
import uuid
from plant import Plant
from customer import Customer
from order import Order
from payment import Payment
from plant_catalog import PlantCatalog
from customer_directory import CustomerDirectory
from order_history import OrderHistory
from payment_history import PaymentHistory
from exceptions import OrderNotAllowedError


class NurserySystem:
    """
    A central system class that manages the collections of plants, customers,
    orders, and payments, and is responsible for adding, searching, updating,
    and reporting across them.
    """

    # The whole nursery is written to one pickle file.
    DATA_FILE = "nursery_system.pkl"

    def __init__(self) -> None:
        """
        Initialise a new NurserySystem. If a save file exists from a previous
        run, plants, customers, orders, and payments are loaded from it.
        Otherwise the catalog, directory, and histories start empty.
        """
        # The collections live here so the driver only talks to one object.
        # Orders can then only be created for plants and customers that are already registered.
        self.__catalog = PlantCatalog()
        self.__directory = CustomerDirectory()
        self.__history = OrderHistory()
        self.__payment_history = PaymentHistory()
        self.__loaded_from_file = self.load_from_file()

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

    @property
    def payment_history(self) -> PaymentHistory:
        """Get the payment history"""
        return self.__payment_history

    @property
    def loaded_from_file(self) -> bool:
        """True if plants, customers, orders, and payments were restored from the save file"""
        return self.__loaded_from_file

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

    def place_order(self, customer: Customer, items: list[tuple[Plant, int]], order_date: str = None) -> Order:
        """
        Place a new order after validating the customer and plants are registered by ID.
        The customer's place-order rules are checked before the order is created.
        Stock is reduced immediately when the order is created.

        :param customer: The Customer placing the order
        :param items: A list of (plant, quantity) pairs to include on the order
        :param order_date: Optional order date in DD-MM-YYYY format, defaults to today
        :return: The newly created Order object
        :raises ValueError: If customer or a plant is not registered, or the order date is invalid
        :raises OrderNotAllowedError: If the customer is not allowed to place an order
        :raises InsufficientStockError: If there is not enough stock for an item
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
            if customer.customer_type() == "community":
                raise OrderNotAllowedError(
                    "Community customers may only have one pending order at a time"
                )
            raise OrderNotAllowedError(
                "Staff and students cannot place a new order while owing more than $100"
            )

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
        :raises ValueError: If the order is not in the system
        :raises OrderCannotBeCollectedError: If the order cannot be collected
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
        :raises ValueError: If the order is not in the system
        :raises OrderCannotBeCancelledError: If the order cannot be cancelled
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

    # ---------- Payment Methods ----------

    def record_payment(self, payment: Payment) -> None:
        """
        Record a payment toward an order. The amount is applied to the order and
        taken off the customer balance. A payment is accepted whenever the order
        still has a remaining balance.

        :param payment: The Payment to record
        :raises ValueError: If the customer or order is not in the system, the customer
            does not own the order, or the amount is more than what is still owed
        """
        customer_found = False
        for existing_customer in self.__directory.customer_list:
            if existing_customer.cust_id == payment.customer.cust_id:
                customer_found = True
                break
        if not customer_found:
            raise ValueError("Customer is not registered in the system")

        if payment.order not in self.__history.order_list:
            raise ValueError("Order is not in the system")

        if payment.customer.cust_id != payment.order.customer.cust_id:
            raise ValueError("Payment customer must be the customer on the order")

        # record_payment() on Order enforces amount > 0 and not more than remaining.
        payment.order.record_payment(payment.amount)
        self.__payment_history.add_payment(payment)

    def find_payment(self, payment_id: uuid.UUID) -> Payment:
        """
        Search for a payment by its ID

        :param payment_id: The UUID of the payment to find
        :return: The matching Payment object
        :raises ValueError: If no payment with that ID is found
        """
        for payment in self.__payment_history.payment_list:
            if payment.payment_id == payment_id:
                return payment
        raise ValueError(f"No payment found with ID {payment_id}")

    def get_customer_payments(self, customer: Customer) -> list[Payment]:
        """
        Retrieve all payments made by a specific customer

        :param customer: The Customer to look up
        :return: A list of Payment objects belonging to that customer
        :raises ValueError: If customer is not registered in the system
        """
        customer_found = False
        for existing_customer in self.__directory.customer_list:
            if existing_customer.cust_id == customer.cust_id:
                customer_found = True
                break
        if not customer_found:
            raise ValueError("Customer is not registered in the system")
        return self.__payment_history.get_customer_payments(customer)

    def get_order_payments(self, order: Order) -> list[Payment]:
        """
        Retrieve all payments made toward a specific order

        :param order: The Order to look up
        :return: A list of Payment objects for that order
        :raises ValueError: If the order is not in the system
        """
        if order not in self.__history.order_list:
            raise ValueError("Order is not in the system")
        return self.__payment_history.get_order_payments(order)

    def display_all_payments(self) -> None:
        """Print a readable list of every payment on record"""
        self.__payment_history.display_all_payments()

    def display_customer_payments(self, customer: Customer) -> None:
        """Print a readable list of payments made by a specific customer"""
        self.__payment_history.display_customer_payments(customer)

    def display_order_payments(self, order: Order) -> None:
        """Print a readable list of payments made toward a specific order"""
        self.__payment_history.display_order_payments(order)

    # ---------- Save and Load ----------

    def save_to_file(self) -> None:
        """
        Write the whole nursery system to a pickle file, including plants,
        customers, orders, and payments
        """
        with open(self.DATA_FILE, "wb") as file:
            pickle.dump(self, file)
        print("Nursery system saved successfully")

    def load_from_file(self) -> bool:
        """
        Load a previously saved nursery system and replace this object's
        plants, customers, orders, and payments with the loaded data.

        :return: True if a save file was found and loaded, False if there is no file yet
        """
        try:
            with open(self.DATA_FILE, "rb") as file:
                loaded = pickle.load(file)
        except FileNotFoundError:
            # First run has nothing to restore, so the empty collections stay in place.
            return False

        self.__catalog = loaded.__catalog
        self.__directory = loaded.__directory
        self.__history = loaded.__history
        self.__payment_history = loaded.__payment_history
        print("Nursery system loaded successfully")
        return True

    # ---------- String Method ----------

    def __str__(self) -> str:
        """Returns a summary of the nursery system"""
        return (
            "Nursery System: {} plants, {} customers, {} orders, {} payments"
            .format(
                len(self.__catalog.plant_list),
                len(self.__directory.customer_list),
                len(self.__history.order_list),
                len(self.__payment_history.payment_list),
            )
        )
