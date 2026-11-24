"""Exceptions raised by services and handled by controllers."""


class ValidationError(Exception):
    """One or more input fields are invalid. `errors` maps field name -> message."""

    def __init__(self, errors):
        super().__init__("Invalid input")
        self.errors = dict(errors)


class AuthenticationError(Exception):
    """Sign-in refused. `message` is safe to show to the user."""

    def __init__(self, message):
        super().__init__(message)
        self.message = message
