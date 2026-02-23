"""
Django version compatibility shim.

Centralizes all version-sensitive Django imports so that when a Django release
moves or renames an internal symbol, only this file needs updating.
"""

import django

DJANGO_VERSION = django.VERSION

# ---------------------------------------------------------------------------
# Admin internals
# ---------------------------------------------------------------------------

try:
    from django.contrib.admin.options import IS_POPUP_VAR
except ImportError:
    IS_POPUP_VAR = "_popup"

try:
    from django.contrib.admin.views.main import ChangeList
except ImportError:  # pragma: no cover
    ChangeList = None

try:
    from django.contrib.admin import helpers as admin_helpers
except ImportError:  # pragma: no cover
    admin_helpers = None

# ---------------------------------------------------------------------------
# Auth admin internals
# ---------------------------------------------------------------------------

try:
    from django.contrib.auth.admin import sensitive_post_parameters_m
except ImportError:
    from functools import wraps

    def sensitive_post_parameters_m(func):
        """Fallback no-op decorator when Django removes the symbol."""

        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        return wrapper


# ---------------------------------------------------------------------------
# Auth forms – base classes for thin-adapter subclassing
# ---------------------------------------------------------------------------

try:
    from django.contrib.auth.forms import (
        AdminPasswordChangeForm as DjangoAdminPasswordChangeForm,
    )
    from django.contrib.auth.forms import AuthenticationForm as DjangoAuthenticationForm
    from django.contrib.auth.forms import (
        UserChangeForm as DjangoUserChangeForm,
    )
    from django.contrib.auth.forms import (
        UserCreationForm as DjangoUserCreationForm,
    )
except ImportError:  # pragma: no cover
    DjangoUserCreationForm = None
    DjangoUserChangeForm = None
    DjangoAdminPasswordChangeForm = None
    DjangoAuthenticationForm = None

# ---------------------------------------------------------------------------
# Auth admin – UserAdmin base
# ---------------------------------------------------------------------------

try:
    from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
except ImportError:  # pragma: no cover
    DjangoUserAdmin = None

# ---------------------------------------------------------------------------
# Auth backends – BaseBackend
# ---------------------------------------------------------------------------

try:
    from django.contrib.auth.backends import BaseBackend as DjangoBaseBackend
except ImportError:  # pragma: no cover
    DjangoBaseBackend = object

# ---------------------------------------------------------------------------
# Auth models – AbstractBaseUser, PermissionsMixin, AnonymousUser
# ---------------------------------------------------------------------------

try:
    from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
    from django.contrib.auth.models import AnonymousUser as DjangoAnonymousUser
except ImportError:  # pragma: no cover
    AbstractBaseUser = None
    PermissionsMixin = None
    DjangoAnonymousUser = None
