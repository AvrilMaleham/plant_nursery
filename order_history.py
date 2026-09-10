from order import Order
from customer import Customer

class OrderHistory:
    """Record of all orders placed at the nursery"""
    
    def __init__(self) -> None:
        """Initialise a new OrderHistory object"""
        
        self.__order_list = []
        
    # ---------- Getters and Setters ----------
        
    @property
    def order_list(self) -> list[Order]:
        """Get the list of orders"""
        # A copy is returned so callers cannot change the internal list directly.
        # New orders still have to go through add_order(), which checks for duplicate IDs.
        return self.__order_list.copy()
        
     # ---------- Methods ----------

    def add_order(self, order: Order) -> None:
        """
        Adds a new order to the list

        :param order: Order to add to the list
        :raises TypeError: If order is not an Order object
        :raises ValueError: If an order with the same ID is already in the list
        """
        if not isinstance(order, Order):
            raise TypeError("Only orders may be added to the list")
        
        for existing_order in self.__order_list:
            if existing_order.order_id == order.order_id:
                raise ValueError(f"Order with ID {order.order_id} is already in the list")
            
        self.__order_list.append(order)
    
    def get_customer_order_history(self, customer: Customer) -> list[Order]:
        """
        Retrieve all orders placed by a specific customer

        :param customer: The customer to look up
        :return: A list of Order objects belonging to that customer
        """
        matching_orders = []
        # Match on customer ID rather than the Customer object itself, so history still
        # works if the caller holds a different Python object with the same ID.
        for order in self.__order_list:
            if order.customer.cust_id == customer.cust_id:
                matching_orders.append(order)
        return matching_orders
    
    # display_all_orders exists alongside the order_list getter so printing stays
    # inside the history. The driver can call one method instead of looping itself. 
    def display_all_orders(self) -> None:
        """Print a readable list of every order in the list"""
        if not self.__order_list:
            print("No orders yet")
            return
        
        for order in self.__order_list:
            print(order)
        