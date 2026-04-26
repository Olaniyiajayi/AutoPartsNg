"""
Exceptions
"""


class DatabaseError(Exception):
    """
    Database Error - when there is an error using the database
    """

    def __init__(self, message):
        self.message = message


class EventBridgeError(Exception):
    """
    EventBridge Error - when there is an error using the EventBridge
    """

    def __init__(self, message):
        self.message = message


class ValidationError(Exception):
    """
    Validation Error - when there is an error validating the payload
    """

    def __init__(self, message):
        self.message = message
