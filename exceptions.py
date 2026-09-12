class InsufficientStockError(Exception):
    """An error when an order requests more stock than is available"""

    def __init__(self, message: str = "Insufficient stock available") -> None:
        """
        Initialise a new InsufficientStockError object

        :param message: The message to show for this error
        """
        self.message = message
        super().__init__(self.message)

    def __str__(self) -> str:
        """Returns a readable string of the error message"""
        return self.message


class OrderNotAllowedError(Exception):
    """An error when a customer is not allowed to place a new order"""

    def __init__(self, message: str = "Customer is not allowed to place a new order") -> None:
        """
        Initialise a new OrderNotAllowedError object

        :param message: The message to show for this error
        """
        self.message = message
        super().__init__(self.message)

    def __str__(self) -> str:
        """Returns a readable string of the error message"""
        return self.message


class OrderCannotBeCollectedError(Exception):
    """An error when an order cannot be collected"""

    def __init__(self, message: str = "Order cannot be collected") -> None:
        """
        Initialise a new OrderCannotBeCollectedError object

        :param message: The message to show for this error
        """
        self.message = message
        super().__init__(self.message)

    def __str__(self) -> str:
        """Returns a readable string of the error message"""
        return self.message


class OrderCannotBeCancelledError(Exception):
    """An error when an order cannot be cancelled"""

    def __init__(self, message: str = "Order cannot be cancelled") -> None:
        """
        Initialise a new OrderCannotBeCancelledError object

        :param message: The message to show for this error
        """
        self.message = message
        super().__init__(self.message)

    def __str__(self) -> str:
        """Returns a readable string of the error message"""
        return self.message
