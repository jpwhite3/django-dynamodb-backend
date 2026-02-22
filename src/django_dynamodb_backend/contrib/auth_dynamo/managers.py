"""
DynamoDB User Manager for Django Authentication.

Provides user creation and lookup functionality using DynamoDB GSIs.
"""

import logging
from datetime import datetime, timezone

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist

from ...managers import DynamoDBManager

logger = logging.getLogger(__name__)

# Table configuration
DYNAMODB_USER_TABLE_NAME = getattr(settings, "DYNAMODB_USER_TABLE_NAME", "django_users")


class DynamoUserManager(DynamoDBManager):
    """
    Manager for DynamoUser model with authentication-specific methods.

    Provides methods for creating users and looking up by username/email
    using DynamoDB Global Secondary Indexes.
    """

    def _get_table(self):
        """Get the DynamoDB table resource."""
        from ...sessions import get_dynamodb_resource

        dynamodb = get_dynamodb_resource()
        return dynamodb.Table(DYNAMODB_USER_TABLE_NAME)

    def _normalize_email(self, email):
        """Normalize email address to lowercase."""
        if email:
            return email.lower().strip()
        return ""

    def _normalize_username(self, username):
        """Normalize username (case-insensitive by default)."""
        if username:
            return username.strip()
        return ""

    def get_by_natural_key(self, username):
        """Look up user by username (natural key)."""
        return self.get(username=username)

    def get(self, **kwargs):
        """
        Get a single user by primary key or unique field.

        Supports lookups by:
        - id (pk): Direct hash key lookup
        - username: GSI lookup
        - email: GSI lookup
        """
        from .models import DynamoUser

        table = self._get_table()

        # Primary key lookup
        if "pk" in kwargs or "id" in kwargs:
            pk = kwargs.get("pk") or kwargs.get("id")
            response = table.get_item(
                Key={"id": str(pk)},
                ConsistentRead=True,
            )
            item = response.get("Item")
            if not item:
                raise DynamoUser.DoesNotExist(
                    "DynamoUser matching query does not exist."
                )
            return self._item_to_user(item)

        # Username lookup via GSI
        if "username" in kwargs:
            username = self._normalize_username(kwargs["username"])
            response = table.query(
                IndexName="username-index",
                KeyConditionExpression="username = :username",
                ExpressionAttributeValues={":username": username},
                Limit=1,
            )
            items = response.get("Items", [])
            if not items:
                raise DynamoUser.DoesNotExist(
                    "DynamoUser matching query does not exist."
                )
            return self._item_to_user(items[0])

        # Email lookup via GSI
        if "email" in kwargs:
            email = self._normalize_email(kwargs["email"])
            response = table.query(
                IndexName="email-index",
                KeyConditionExpression="email = :email",
                ExpressionAttributeValues={":email": email},
                Limit=1,
            )
            items = response.get("Items", [])
            if not items:
                raise DynamoUser.DoesNotExist(
                    "DynamoUser matching query does not exist."
                )
            return self._item_to_user(items[0])

        raise ValueError("Must provide pk, id, username, or email for lookup")

    def _item_to_user(self, item):
        """Convert a DynamoDB item to a DynamoUser instance."""
        from .models import DynamoUser

        # Convert DynamoDB types to Python types
        user_data = {}
        for key, value in item.items():
            # Handle Decimal conversion for booleans stored as numbers
            if isinstance(value, (int, float)) and key in (
                "is_active",
                "is_staff",
                "is_superuser",
            ):
                user_data[key] = bool(value)
            else:
                user_data[key] = value

        user = DynamoUser(**user_data)
        # Sync field values
        user._field_values = dict(item)
        return user

    def filter(self, **kwargs):
        """
        Filter users by criteria.

        Note: DynamoDB doesn't support arbitrary filtering efficiently.
        This performs a scan for complex queries.
        """
        table = self._get_table()

        # Build filter expression
        filter_parts = []
        expr_values = {}
        expr_names = {}

        for i, (key, value) in enumerate(kwargs.items()):
            placeholder = f":val{i}"
            name_placeholder = f"#name{i}"

            # Handle reserved words and special characters
            expr_names[name_placeholder] = key
            expr_values[placeholder] = value
            filter_parts.append(f"{name_placeholder} = {placeholder}")

        scan_kwargs = {}
        if filter_parts:
            scan_kwargs["FilterExpression"] = " AND ".join(filter_parts)
            scan_kwargs["ExpressionAttributeValues"] = expr_values
            scan_kwargs["ExpressionAttributeNames"] = expr_names

        # Perform scan
        response = table.scan(**scan_kwargs)

        return DynamoUserQuerySet(
            [self._item_to_user(item) for item in response.get("Items", [])]
        )

    def all(self):
        """Return all users."""
        return self.filter()

    def exists(self, **kwargs):
        """Check if a user exists with the given criteria."""
        try:
            self.get(**kwargs)
            return True
        except ObjectDoesNotExist:
            return False

    def create(self, **kwargs):
        """Create and save a new user."""
        from .models import DynamoUser

        user = DynamoUser(**kwargs)
        user.save()
        return user

    def create_user(self, username, email=None, password=None, **extra_fields):
        """
        Create a regular user.

        Args:
            username: The username for the new user
            email: Optional email address
            password: The password (will be hashed)
            **extra_fields: Additional fields (first_name, last_name, etc.)

        Returns:
            The created DynamoUser instance
        """
        if not username:
            raise ValueError("Users must have a username")

        # Check for existing username
        if self.exists(username=username):
            raise ValueError(f"User with username '{username}' already exists")

        # Check for existing email if provided
        if email and self.exists(email=email):
            raise ValueError(f"User with email '{email}' already exists")

        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        extra_fields.setdefault("is_active", True)

        from .models import DynamoUser

        user = DynamoUser(
            username=self._normalize_username(username),
            email=self._normalize_email(email) if email else "",
            **extra_fields,
        )

        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()

        user._field_values["date_joined"] = datetime.now(timezone.utc).isoformat()
        user.save()
        return user

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        """
        Create a superuser.

        Args:
            username: The username for the new superuser
            email: Optional email address
            password: The password (will be hashed)
            **extra_fields: Additional fields

        Returns:
            The created DynamoUser instance with superuser privileges
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(username, email, password, **extra_fields)


class DynamoUserQuerySet(list):
    """
    A list-like object that mimics Django QuerySet behavior.

    Provides chainable filtering methods for DynamoUser queries.
    """

    def __init__(self, users=None):
        super().__init__(users or [])

    def filter(self, **kwargs):
        """Filter the current set of users."""
        result = []
        for user in self:
            match = True
            for key, value in kwargs.items():
                user_value = getattr(user, key, None)
                if user_value != value:
                    match = False
                    break
            if match:
                result.append(user)
        return DynamoUserQuerySet(result)

    def exclude(self, **kwargs):
        """Exclude users matching criteria."""
        result = []
        for user in self:
            match = False
            for key, value in kwargs.items():
                user_value = getattr(user, key, None)
                if user_value == value:
                    match = True
                    break
            if not match:
                result.append(user)
        return DynamoUserQuerySet(result)

    def first(self):
        """Return the first user or None."""
        return self[0] if self else None

    def last(self):
        """Return the last user or None."""
        return self[-1] if self else None

    def exists(self):
        """Check if any users match."""
        return len(self) > 0

    def count(self):
        """Return the count of users."""
        return len(self)

    def order_by(self, *fields):
        """Sort users by fields (prefix with '-' for descending)."""
        for field in reversed(fields):
            reverse = field.startswith("-")
            field_name = field[1:] if reverse else field
            self.sort(key=lambda u: getattr(u, field_name, ""), reverse=reverse)
        return self

    def values(self, *fields):
        """Return dictionaries with specified fields."""
        result = []
        for user in self:
            if fields:
                result.append({f: getattr(user, f, None) for f in fields})
            else:
                result.append(user._field_values.copy())
        return result

    def values_list(self, *fields, flat=False):
        """Return tuples (or flat list) of field values."""
        result = []
        for user in self:
            if flat and len(fields) == 1:
                result.append(getattr(user, fields[0], None))
            else:
                result.append(tuple(getattr(user, f, None) for f in fields))
        return result

    def get(self, **kwargs):
        """Get a single user matching criteria."""
        from .models import DynamoUser

        filtered = self.filter(**kwargs)
        if len(filtered) == 0:
            raise DynamoUser.DoesNotExist("DynamoUser matching query does not exist.")
        if len(filtered) > 1:
            raise Exception("Multiple users match the query")
        return filtered[0]

    def __getitem__(self, key):
        """Support slicing."""
        result = super().__getitem__(key)
        if isinstance(key, slice):
            return DynamoUserQuerySet(result)
        return result
