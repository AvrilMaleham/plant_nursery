import uuid

class Customer:
    """Represents a customer with an ID, name, and email or phone number"""
    
    def __init__(self, cust_name: str, cust_email: str = "", cust_phone: str = "") -> None:
        """
        Initialise a new Customer object

        :param cust_name: Name of the customer (does not need to be unique, differnt customers can have the same name)
        :param cust_email: Contact email address of the customer
        :param cust_phone: Contact phone number of the customer
        :raises ValueError: If there is not at least one of cust_email or cust_phone
        """
        
        # At least one contact method is required so the nursery can still reach the customer.
        if not cust_email and not cust_phone:
            raise ValueError("Please provide at least an email or a phone number")
        
        # UUID is used so two customers with the same name still have distinct IDs.
        self.__cust_id = uuid.uuid4()
        self.__cust_name = cust_name
        # Empty strings are stored as None so a missing email or phone is consistent.
        self.__cust_email = cust_email if cust_email else None
        self.__cust_phone = cust_phone if cust_phone else None
        
    # ---------- Getters and Setters ----------
    # ID is generated once and has no setter, so it cannot be changed later.
    # Name, email, and phone can be updated if details change. Clearing email or phone
    # is only allowed if the other contact method is still set, matching the create rule.
        
    @property
    def cust_id(self) -> uuid.UUID:
        """Get the unique customer ID"""
        return self.__cust_id

    @property
    def cust_name(self) -> str:
        """Get the customer name"""
        return self.__cust_name

    @cust_name.setter
    def cust_name(self, value: str) -> None:
        """
        Update the customer name

        :param value: New customer name
        """
        self.__cust_name = value

    @property
    def cust_email(self) -> str:
        """Get the customer email"""
        return self.__cust_email

    @cust_email.setter
    def cust_email(self, value: str) -> None:
        """
        Update the customer email. At least one contact method must remain.

        :param value: New email address, or empty/None to clear it
        :raises ValueError: If clearing the email would leave the customer with no contact details
        """
        new_email = value if value else None
        # Reject clearing email if there is no phone, otherwise the customer would have
        # no way to be contacted.
        if not new_email and not self.__cust_phone:
            raise ValueError("Please provide at least an email or a phone number")
        self.__cust_email = new_email

    @property
    def cust_phone(self) -> str:
        """Get the customer phone number"""
        return self.__cust_phone

    @cust_phone.setter
    def cust_phone(self, value: str) -> None:
        """
        Update the customer phone number. At least one contact method must remain.

        :param value: New phone number, or empty/None to clear it
        :raises ValueError: If clearing the phone would leave the customer with no contact details
        """
        new_phone = value if value else None
        # Same rule as the email setter: one of email or phone must remain.
        if not self.__cust_email and not new_phone:
            raise ValueError("Please provide at least an email or a phone number")
        self.__cust_phone = new_phone
        
    # ---------- Methods ----------
        
    def __str__(self) -> str:
        """Returns a readable string of the customer details"""
        return (
            "Customer ID: {}, Customer Name: {}, Customer Email: {},"
            " Customer Phone Number: {}"
            .format(
                self.__cust_id, self.__cust_name,
                self.__cust_email, self.__cust_phone,
            )
        )