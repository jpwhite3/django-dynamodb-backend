"""
DynamoDB Authentication Backend for Django.

Provides authentication against DynamoUser stored in DynamoDB.
"""

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class DynamoAuthBackend:
    """
    Authentication backend for DynamoDB users.

    Authenticates against DynamoUser model and provides permission checking.

    Usage:
        AUTHENTICATION_BACKENDS = [
            'django_dynamodb_backend.contrib.auth_dynamo.backends.DynamoAuthBackend',
        ]
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        """
        Authenticate a user by username and password.

        Args:
            request: The current HTTP request
            username: The username to authenticate
            password: The password to check

        Returns:
            DynamoUser instance if authentication succeeds, None otherwise
        """
        from .models import DynamoUser

        if username is None or password is None:
            return None

        try:
            # Get manager from model
            from .managers import DynamoUserManager

            manager = DynamoUserManager()
            manager.model = DynamoUser

            # Look up user by username
            user = manager.get(username=username)

            # Check password
            if user.check_password(password):
                # Update last_login
                user.last_login = datetime.now(timezone.utc).isoformat()
                user._field_values["last_login"] = user.last_login
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

        Args:
            user_id: The user's ID (UUID string)

        Returns:
            DynamoUser instance or None
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

    def has_perm(self, user_obj, perm, obj=None):
        """
        Check if user has a specific permission.

        Delegates to user's has_perm method.
        """
        if not user_obj.is_active:
            return False
        return user_obj.has_perm(perm, obj)

    def has_module_perms(self, user_obj, app_label):
        """
        Check if user has any permission in the app.

        Delegates to user's has_module_perms method.
        """
        if not user_obj.is_active:
            return False
        return user_obj.has_module_perms(app_label)

    def get_all_permissions(self, user_obj, obj=None):
        """
        Get all permissions for user.

        Delegates to user's get_all_permissions method.
        """
        if not user_obj.is_active:
            return set()
        return user_obj.get_all_permissions(obj)

    def get_group_permissions(self, user_obj, obj=None):
        """
        Get permissions from user's groups.

        Currently returns empty set - group permissions not fully implemented.
        """
        # TODO: Implement group permissions if needed
        return set()

    def user_can_authenticate(self, user):
        """
        Check if user is allowed to authenticate.

        Rejects inactive users.
        """
        return getattr(user, "is_active", False)


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

        Args:
            request: The current HTTP request
            email: The email to authenticate
            password: The password to check

        Returns:
            DynamoUser instance if authentication succeeds, None otherwise
        """
        from .models import DynamoUser

        if email is None or password is None:
            return None

        try:
            from .managers import DynamoUserManager

            manager = DynamoUserManager()
            manager.model = DynamoUser

            # Look up user by email
            user = manager.get(email=email.lower().strip())

            # Check password
            if user.check_password(password):
                # Update last_login
                user.last_login = datetime.now(timezone.utc).isoformat()
                user._field_values["last_login"] = user.last_login
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
