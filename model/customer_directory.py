from sqlalchemy import select
from sqlalchemy.orm import Session

from .customer import Customer


class CustomerDirectory:
    """A directory of the customers of the nursery"""

    def __init__(self, session: Session) -> None:
        """
        Initialise a new CustomerDirectory object

        :param session (Session): The database session that stores the
            customers
        """
        self.__session = session

    # ---------- Getters and Setters ----------

    @property
    def customer_list(self) -> list[Customer]:
        """
        Get the list of customers

        :return (list[Customer]): The list of customers
        """
        # A new list is returned so callers cannot change the directory by
        # editing it. New customers still have to go through add_customer(),
        # which checks for duplicate IDs.
        customers = self.__session.scalars(select(Customer)).all()
        return list(customers)

    # ---------- Methods ----------

    def add_customer(self, customer: Customer) -> None:
        """
        Adds a new customer to the list

        :param customer (Customer): Customer to add to the list
        :raises TypeError: If customer is not a Customer object
        :raises ValueError: If a customer with the same ID is already in the
            list
        """
        if not isinstance(customer, Customer):
            raise TypeError("Only Customer objects may be added to the list")

        existing_customer = self.__session.get(Customer, customer.cust_id)
        # Duplicate check is by customer ID because two people can share a
        # name.
        if existing_customer is not None:
            raise ValueError(
                f"Customer with ID {customer.cust_id} is already in the list"
            )

        self.__session.add(customer)

    def get_customers_by_type(self, customer_type: str) -> list[Customer]:
        """
        Return customers of one type

        :param customer_type (str): The customer_type() value to match, such as
            staff, student, or community
        :return (list[Customer]): A list of matching Customer objects
        """
        matching_customers = []
        # customer_type() is supplied by each subclass, so the directory does
        # not need to know StaffCustomer from CommunityCustomer.
        for customer in self.customer_list:
            if customer.customer_type() == customer_type:
                matching_customers.append(customer)
        return matching_customers

    # display_all_customers exists alongside the customer_list getter so
    # printing stays inside the directory. A caller can use one method
    # instead of looping itself.
    def display_all_customers(self) -> None:
        """Print a readable list of every customer in the list"""
        customers = self.customer_list
        if not customers:
            print("No customers in the catalog")
            return

        for customer in customers:
            print(customer)

    def display_staff_customers(self) -> None:
        """Print a readable list of staff customers"""
        self.__display_customers_of_type(
            "staff", "No staff customers in the directory")

    def display_student_customers(self) -> None:
        """Print a readable list of student customers"""
        self.__display_customers_of_type(
            "student", "No student customers in the directory")

    def display_community_customers(self) -> None:
        """Print a readable list of community customers"""
        self.__display_customers_of_type(
            "community", "No community customers in the directory")

    def __display_customers_of_type(
        self,
        customer_type: str,
        empty_message: str,
    ) -> None:
        """
        Print customers of one type

        :param customer_type (str): The customer_type() value to match
        :param empty_message (str): Message to print when none are found
        """
        matching_customers = self.get_customers_by_type(customer_type)
        if not matching_customers:
            print(empty_message)
            return

        for customer in matching_customers:
            print(customer)
