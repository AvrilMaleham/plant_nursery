from customer import Customer

class CustomerDirectory:
    """A directory of the customers of the nursery"""
    
    def __init__(self) -> None:
        """Initialise a new CustomerDirectory object"""
        
        self.__customer_list = []
        
    # ---------- Getters and Setters ----------
        
    @property
    def customer_list(self) -> list[Customer]:
        """Get the list of customer"""
        # A copy is returned so callers cannot change the internal list directly.
        # New customers still have to go through add_customer(), which checks for duplicate IDs.
        return self.__customer_list.copy()
        
     # ---------- Methods ----------

    def add_customer(self, customer: Customer) -> None:
        """
        Adds a new customer to the list

        :param customer: Customer to add to the list
        :raises TypeError: If customer is not a Customer object
        :raises ValueError: If a customer with the same ID is already in the list
        """
        if not isinstance(customer, Customer):
            raise TypeError("Only Customer objects may be added to the list")
        
        for existing_customer in self.__customer_list:
            # Duplicate check is by customer ID because two people can share a name.
            if existing_customer.cust_id == customer.cust_id:
                raise ValueError(f"Customer with ID {customer.cust_id} is already in the list")
            
        self.__customer_list.append(customer)
    
    def get_customers_by_type(self, customer_type: str) -> list[Customer]:
        """
        Return customers of one type

        :param customer_type: The customer_type() value to match, such as staff, student, or community
        :return: A list of matching Customer objects
        """
        matching_customers = []
        # customer_type() is abstract, so each subclass supplies its own label
        # without the directory needing to know StaffCustomer from CommunityCustomer.
        for customer in self.__customer_list:
            if customer.customer_type() == customer_type:
                matching_customers.append(customer)
        return matching_customers

    # display_all_customers exists alongside the customer_list getter so printing stays
    # inside the directory. The driver can call one method instead of looping itself.
    def display_all_customers(self) -> None:
        """Print a readable list of every customer in the list"""
        if not self.__customer_list:
            print("No customers in the catalog")
            return

        for customer in self.__customer_list:
            print(customer)

    def display_staff_customers(self) -> None:
        """Print a readable list of staff customers"""
        self.__display_customers_of_type("staff", "No staff customers in the directory")

    def display_student_customers(self) -> None:
        """Print a readable list of student customers"""
        self.__display_customers_of_type("student", "No student customers in the directory")

    def display_community_customers(self) -> None:
        """Print a readable list of community customers"""
        self.__display_customers_of_type("community", "No community customers in the directory")

    def __display_customers_of_type(self, customer_type: str, empty_message: str) -> None:
        """
        Print customers of one type

        :param customer_type: The customer_type() value to match
        :param empty_message: Message to print when none are found
        """
        matching_customers = self.get_customers_by_type(customer_type)
        if not matching_customers:
            print(empty_message)
            return

        for customer in matching_customers:
            print(customer)
