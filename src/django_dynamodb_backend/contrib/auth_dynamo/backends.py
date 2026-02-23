"""
DynamoDB Authentication Backend for Django.

Provides authentication against DynamoUser stored in DynamoDB.

Inherits from ``django.contrib.auth.backends.BaseBackend`` so that
``has_perm``, ``get_all_permissions``, ``get_group_permissions``,
and similar plumbing is maintained by Django.
Only ``authenticate()`` and ``get_user()`` contain DynamoDB-specific logic.
"""

import logging
from datetime import datetime, timezone

from ...compat import DjangoBaseBackend

logger = logging.getLogger(__name__)


class DynamoAuthBackend(DjangoBaseBackend):
    """
    Authentication backend for DynamoDB users.

    Inherits from ``BaseBackend`` which provides default implementations for:
    - ``has_perm()``, ``has_module_perms()``
    - ``get_all_permissions()``, ``get_group_permissions()``, ``get_user_permissions()``

    Usage:
        AUTHENTICATION_BACKENDS = [
            'django_dynamodb_backend.contrib.auth_dynamo.backends.DynamoAuthBackend',
        ]
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        """
        Authenticate a user by username and password.

        Returns:
            DynamoUser instance if authentication succeeds, None otherwise.
        """
        from .models import DynamoUser

        if username is None or password is None:
            return None

        try:
            from .managers import DynamoUserManager

            manager = DynamoUserManager()
            manager.model = DynamoUser

            user = manager.get(username=username)

            if user.check_password(password) and getattr(user, "is_active", True):
                # Update last_login
                now = datetime.now(timezone.utc)
                user.last_login = now
                user._field_values["last_login"] = now
                try:
                    user.save()
                except Exception as e:
                    logger.warning(f"Failed to update last_login: {e}")

                return user

        except DynamoUser.DoesNotExist:
            # Run the default password hasher to reduce timing attacks
            from django.contrib.auth.hashers import make_password

            make_password(password)
            return None
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return None

        return None

    def get_user(self, user_id):
        """
        Get a user by their primary key.

        Returns:
            DynamoUser instance or None.
        """
        from .models import DynamoUser

        try:
            from .managers import DynamoUserManager

            manager = DynamoUserManager()
            manager.model = DynamoUser
            return manager.get(pk=user_id)
        except DynamoUser.DoesNotExist:
            return None
        except Exception as e:
            logger.error(f"Error getting user: {e}")
            return None

    # has_perm, has_module_perms, get_all_permissions, get_group_permissions
    # are all inherited from BaseBackend.


class EmailAuthBackend(DynamoAuthBackend):
    """
    Authentication backend that uses email instead of username.

    Usage:
        AUTHENTICATION_BACKENDS = [
            'django_dynamodb_backend.contrib.auth_dynamo.backends.EmailAuthBackend',
        ]
    """

    def authenticate(self, request, email=None, password=None, **kwargs):
        """
        Authenticate a user by email and password.

        Returns:
            DynamoUser instance if authentication succeeds, None otherwise.
        """
        from .models import DynamoUser

        if email is None or password is None:
            return None

        try:
            from .managers import DynamoUserManager

            manager = DynamoUserManager()
            manager.model = DynamoUser

            user = manager.get(email=email.lower().strip())

            if user.check_password(password) and getattr(user, "is_active", True):
                # Update last_login
                now = datetime.now(timezone.utc)
                user.last_login = now
                user._field_values["last_login"] = now
                try:
                    user.save()
                except Exception as e:
                    logger.warning(f"Failed to update last_login: {e}")

                return user

        except DynamoUser.DoesNotExist:
            from django.contrib.auth.hashers import make_password

            make_password(password)
            return None
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return None

        return None
