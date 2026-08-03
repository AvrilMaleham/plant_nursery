from customer import Customer

class CustomerList:
    """A list of the customers of the nursery"""
    
    def __init__(self) -> None:
        """Initialise a new CustomerList object"""
        
        self.__customer_list = []
        
    # ---------- Getters and Setters ----------
        
    @property
    def customer_list(self) -> list[Customer]:
        """Get the list of customer"""
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
            if existing_customer.cust_id == customer.cust_id:
                raise ValueError(f"Customer with ID {customer.cust_id} is already in the list")
            
        self.__customer_list.append(customer)
    
    # Included this even though we have the customer_list getter just to be explicit that there is a method to print each customer in the list so we dont need the print statement in the driver for this    
    def display_all_customers(self) -> None:
        """Print a readable list of every customer in the list"""
        if not self.__customer_list:
            print("No customers in the catalog")
            return
        
        for customer in self.__customer_list:
            print(customer)
        