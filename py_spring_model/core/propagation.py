from enum import Enum


class Propagation(Enum):
    REQUIRED = "REQUIRED"
    REQUIRES_NEW = "REQUIRES_NEW"
    SUPPORTS = "SUPPORTS"
    MANDATORY = "MANDATORY"
    NOT_SUPPORTED = "NOT_SUPPORTED"
    NEVER = "NEVER"
    NESTED = "NESTED"


class TransactionRequiredError(Exception):
    """Raised by MANDATORY when no active transaction exists."""


class ExistingTransactionError(Exception):
    """Raised by NEVER when an active transaction exists."""
