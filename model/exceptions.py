class InsufficientStockError(Exception):
    """An error when an order requests more stock than is available"""

    def __init__(self, message: str = "Insufficient stock available") -> None:
        """
        Initialise a new InsufficientStockError object

        :param message (str): The message to show for this error
        """
        self.__message = message
        super().__init__(self.__message)

    def __str__(self) -> str:
        """
        Returns a readable string of the error message

        :return (str): A readable string of the error message
        """
        return self.__message


class OrderNotAllowedError(Exception):
    """An error when a customer is not allowed to place a new order"""

    def __init__(
        self,
        message: str = "Customer is not allowed to place a new order",
    ) -> None:
        """
        Initialise a new OrderNotAllowedError object

        :param message (str): The message to show for this error
        """
        self.__message = message
        super().__init__(self.__message)

    def __str__(self) -> str:
        """
        Returns a readable string of the error message

        :return (str): A readable string of the error message
        """
        return self.__message


class OrderCannotBeCollectedError(Exception):
    """An error when an order cannot be collected"""

    def __init__(self, message: str = "Order cannot be collected") -> None:
        """
        Initialise a new OrderCannotBeCollectedError object

        :param message (str): The message to show for this error
        """
        self.__message = message
        super().__init__(self.__message)

    def __str__(self) -> str:
        """
        Returns a readable string of the error message

        :return (str): A readable string of the error message
        """
        return self.__message


class LoginFailedError(Exception):
    """An error when a username and password do not match an account"""

    def __init__(
        self,
        message: str = "Username or password is incorrect",
    ) -> None:
        """
        Initialise a new LoginFailedError object

        :param message (str): The message to show for this error
        """
        self.__message = message
        super().__init__(self.__message)

    def __str__(self) -> str:
        """
        Returns a readable string of the error message

        :return (str): A readable string of the error message
        """
        return self.__message


class NotAuthorisedError(Exception):
    """An error when the logged-in person is not allowed to do this"""

    def __init__(
        self,
        message: str = "You are not allowed to do that",
    ) -> None:
        """
        Initialise a new NotAuthorisedError object

        :param message (str): The message to show for this error
        """
        self.__message = message
        super().__init__(self.__message)

    def __str__(self) -> str:
        """
        Returns a readable string of the error message

        :return (str): A readable string of the error message
        """
        return self.__message


class OrderCannotBeCancelledError(Exception):
    """An error when an order cannot be cancelled"""

    def __init__(self, message: str = "Order cannot be cancelled") -> None:
        """
        Initialise a new OrderCannotBeCancelledError object

        :param message (str): The message to show for this error
        """
        self.__message = message
        super().__init__(self.__message)

    def __str__(self) -> str:
        """
        Returns a readable string of the error message

        :return (str): A readable string of the error message
        """
        return self.__message


class PlantInUseError(Exception):
    """An error when a plant cannot be removed because it is on an order"""

    def __init__(
        self,
        message: str = "Cannot remove a plant that has been ordered",
    ) -> None:
        """
        Initialise a new PlantInUseError object

        :param message (str): The message to show for this error
        """
        self.__message = message
        super().__init__(self.__message)

    def __str__(self) -> str:
        """
        Returns a readable string of the error message

        :return (str): A readable string of the error message
        """
        return self.__message


class CustomerInUseError(Exception):
    """An error when a customer cannot be removed because they have ordered"""

    def __init__(
        self,
        message: str = "Cannot remove a customer who has placed an order",
    ) -> None:
        """
        Initialise a new CustomerInUseError object

        :param message (str): The message to show for this error
        """
        self.__message = message
        super().__init__(self.__message)

    def __str__(self) -> str:
        """
        Returns a readable string of the error message

        :return (str): A readable string of the error message
        """
        return self.__message


class OverpaymentError(Exception):
    """An error when a payment is more than what is still owed on an order"""

    def __init__(
        self,
        message: str = (
            "Payment cannot be more than what is still owed on this order"
        ),
    ) -> None:
        """
        Initialise a new OverpaymentError object

        :param message (str): The message to show for this error
        """
        self.__message = message
        super().__init__(self.__message)

    def __str__(self) -> str:
        """
        Returns a readable string of the error message

        :return (str): A readable string of the error message
        """
        return self.__message


class OrderNotPayableError(Exception):
    """An error when an order cannot take a payment, such as a cancelled or
    fully paid order"""

    def __init__(
        self,
        message: str = "Nothing can be paid toward this order",
    ) -> None:
        """
        Initialise a new OrderNotPayableError object

        :param message (str): The message to show for this error
        """
        self.__message = message
        super().__init__(self.__message)

    def __str__(self) -> str:
        """
        Returns a readable string of the error message

        :return (str): A readable string of the error message
        """
        return self.__message
