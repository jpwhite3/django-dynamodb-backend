"""
DynamoDB-specific expression support for atomic operations.

Provides F() expression-like functionality that leverages DynamoDB's
native atomic increment/decrement capabilities.
"""

import logging
from decimal import Decimal

from django.db.models import F
from django.db.models.expressions import CombinedExpression, Value

logger = logging.getLogger(__name__)


class DynamoDBF(F):
    """
    DynamoDB-compatible F() expression that supports atomic operations.

    While Django's F() expressions are typically used for database-level operations,
    DynamoDB has native support for atomic increment/decrement through UpdateExpression.

    Usage:
        # Atomic increment
        obj.update(votes=DynamoDBF('votes') + 1)

        # Atomic decrement
        obj.update(count=DynamoDBF('count') - 5)

        # QuerySet update with atomic increment
        queryset.update(votes=DynamoDBF('votes') + 1)
    """

    def __init__(self, name):
        """Initialize with the field name to reference."""
        super().__init__(name)
        self._field_name = name
        self._operation = None
        self._operand = None

    def __add__(self, other):
        """Support F('field') + value for atomic increment."""
        result = DynamoDBF(self._field_name)
        result._operation = "ADD"
        result._operand = self._convert_operand(other)
        return result

    def __radd__(self, other):
        """Support value + F('field') for atomic increment."""
        return self.__add__(other)

    def __sub__(self, other):
        """Support F('field') - value for atomic decrement."""
        result = DynamoDBF(self._field_name)
        result._operation = "ADD"  # DynamoDB uses ADD with negative value for decrement
        result._operand = -self._convert_operand(other)
        return result

    def __rsub__(self, other):
        """Support value - F('field')."""
        # This is unusual but supported
        result = DynamoDBF(self._field_name)
        result._operation = "SUBTRACT_FROM"
        result._operand = self._convert_operand(other)
        return result

    def __mul__(self, other):
        """Multiplication - not natively atomic in DynamoDB."""
        logger.warning(
            "Multiplication is not atomic in DynamoDB; will use read-modify-write"
        )
        result = DynamoDBF(self._field_name)
        result._operation = "MULTIPLY"
        result._operand = self._convert_operand(other)
        return result

    def __truediv__(self, other):
        """Division - not natively atomic in DynamoDB."""
        logger.warning("Division is not atomic in DynamoDB; will use read-modify-write")
        result = DynamoDBF(self._field_name)
        result._operation = "DIVIDE"
        result._operand = self._convert_operand(other)
        return result

    def _convert_operand(self, value):
        """Convert operand to DynamoDB-compatible format."""
        if isinstance(value, (int, float)):
            return Decimal(str(value))
        elif isinstance(value, Decimal):
            return value
        elif isinstance(value, Value):
            return self._convert_operand(value.value)
        elif isinstance(value, DynamoDBF):
            # Reference to another field - not supported for atomic ops
            logger.warning("Cross-field references not supported for atomic operations")
            return None
        return value

    @property
    def field_name(self):
        """Return the field name being referenced."""
        return self._field_name

    @property
    def is_atomic(self):
        """Check if this expression can be executed atomically."""
        return self._operation in ("ADD", None)

    def get_update_expression(self, attribute_name=None):
        """
        Get the DynamoDB UpdateExpression components for this F expression.

        Returns:
            tuple: (update_expression, expression_attribute_names, expression_attribute_values)
        """
        attr_name = attribute_name or self._field_name

        if self._operation == "ADD":
            # Atomic increment/decrement using SET with ADD function
            update_expr = f"SET #{attr_name} = #{attr_name} + :delta"
            attr_names = {f"#{attr_name}": attr_name}
            attr_values = {":delta": self._operand}
            return update_expr, attr_names, attr_values

        elif self._operation is None:
            # Just a field reference, no operation
            return None, {}, {}

        else:
            # Non-atomic operations require read-modify-write
            return None, {}, {}

    def apply_to_instance(self, instance):
        """
        Apply this F expression to a model instance.

        For non-atomic operations, this reads the current value and computes the new value.
        For atomic operations, this should be handled at the DynamoDB level.

        Args:
            instance: The model instance to apply the expression to

        Returns:
            The computed new value
        """
        current_value = getattr(instance, self._field_name, 0)

        # Convert to Decimal for numeric operations
        if isinstance(current_value, (int, float)):
            current_value = Decimal(str(current_value))

        if self._operation == "ADD":
            return current_value + self._operand
        elif self._operation == "SUBTRACT_FROM":
            return self._operand - current_value
        elif self._operation == "MULTIPLY":
            return current_value * self._operand
        elif self._operation == "DIVIDE":
            if self._operand == 0:
                raise ValueError("Division by zero")
            return current_value / self._operand
        else:
            return current_value

    def __repr__(self):
        if self._operation:
            return f"DynamoDBF({self._field_name!r}) {self._operation} {self._operand}"
        return f"DynamoDBF({self._field_name!r})"


def is_f_expression(value):
    """Check if a value is an F() expression (Django or DynamoDB)."""
    return isinstance(value, (F, DynamoDBF, CombinedExpression))


def convert_f_expression(value):
    """
    Convert a Django F() expression to DynamoDBF if possible.

    Args:
        value: The value to check/convert

    Returns:
        DynamoDBF instance if convertible, original value otherwise
    """
    if isinstance(value, DynamoDBF):
        return value
    elif isinstance(value, CombinedExpression):
        # Handle Django's combined expressions (F('field') + 1)
        lhs = value.lhs
        rhs = value.rhs
        connector = value.connector

        if isinstance(lhs, F) and isinstance(rhs, Value):
            result = DynamoDBF(lhs.name)
            if connector == "+":
                return result + rhs.value
            elif connector == "-":
                return result - rhs.value
            elif connector == "*":
                return result * rhs.value
            elif connector == "/":
                return result / rhs.value
    elif isinstance(value, F):
        return DynamoDBF(value.name)

    return value
