"""Django DynamoDB Backend - A database backend for Amazon DynamoDB."""

__all__ = [
    "DynamoDBModel",
    "DynamoDBManager",
    "DynamoDBQuerySet",
    "DynamoDBF",
    "is_f_expression",
    "convert_f_expression",
]

__version__ = "1.0.0rc1"


def __getattr__(name):
    """Lazy imports to avoid Django AppRegistryNotReady errors."""
    if name == "DynamoDBModel":
        from .models import DynamoDBModel

        return DynamoDBModel
    elif name == "DynamoDBManager":
        from .managers import DynamoDBManager

        return DynamoDBManager
    elif name == "DynamoDBQuerySet":
        from .managers import DynamoDBQuerySet

        return DynamoDBQuerySet
    elif name == "DynamoDBF":
        from .expressions import DynamoDBF

        return DynamoDBF
    elif name == "is_f_expression":
        from .expressions import is_f_expression

        return is_f_expression
    elif name == "convert_f_expression":
        from .expressions import convert_f_expression

        return convert_f_expression
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
