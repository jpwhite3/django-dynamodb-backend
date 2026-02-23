"""
Django compatibility smoke tests.

These tests verify that the refactored classes satisfy the contracts Django
expects, so that Django version upgrades surface breakage here rather than in
production.  They intentionally avoid hitting DynamoDB (no moto/localstack).
"""

import inspect
from unittest.mock import MagicMock, patch

import django
import pytest
from django.contrib.admin import ModelAdmin
from django.contrib.admin.views.main import ChangeList
from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.models import AbstractBaseUser


# ── ChangeList *args/**kwargs forwarding ──────────────────────────────────


class TestChangeListInit:
    """DynamoDBChangeList must accept whatever args Django's ChangeList does."""

    def test_init_signature_is_open(self):
        """__init__ uses *args/**kwargs so new Django params don't break it."""
        from django_dynamodb_backend.admin import DynamoDBChangeList

        sig = inspect.signature(DynamoDBChangeList.__init__)
        param_kinds = {p.kind for p in sig.parameters.values() if p.name != "self"}
        assert inspect.Parameter.VAR_POSITIONAL in param_kinds, (
            "DynamoDBChangeList.__init__ must accept *args"
        )
        assert inspect.Parameter.VAR_KEYWORD in param_kinds, (
            "DynamoDBChangeList.__init__ must accept **kwargs"
        )

    def test_subclasses_changelist(self):
        from django_dynamodb_backend.admin import DynamoDBChangeList

        assert issubclass(DynamoDBChangeList, ChangeList)


# ── DynamoUser auth contract ─────────────────────────────────────────────


class TestDynamoUserAuthContract:
    """DynamoUser must satisfy Django's authentication contract."""

    @pytest.fixture(autouse=True)
    def _user(self):
        from django_dynamodb_backend.contrib.auth_dynamo.models import DynamoUser

        self.User = DynamoUser

    def test_inherits_abstract_base_user(self):
        assert issubclass(self.User, AbstractBaseUser)

    def test_username_field_set(self):
        assert hasattr(self.User, "USERNAME_FIELD")
        assert self.User.USERNAME_FIELD == "username"

    def test_required_fields(self):
        assert hasattr(self.User, "REQUIRED_FIELDS")
        assert isinstance(self.User.REQUIRED_FIELDS, (list, tuple))

    @pytest.mark.parametrize(
        "method",
        [
            "set_password",
            "check_password",
            "has_usable_password",
            "get_session_auth_hash",
            "get_username",
            "natural_key",
            "get_full_name",
            "get_short_name",
            # DynamoDB-specific permission methods
            "has_perm",
            "has_perms",
            "has_module_perms",
            "get_all_permissions",
        ],
    )
    def test_has_required_method(self, method):
        assert hasattr(self.User, method), f"DynamoUser missing method: {method}"

    @pytest.mark.parametrize("prop", ["is_anonymous", "is_authenticated"])
    def test_has_auth_properties(self, prop):
        assert hasattr(self.User, prop)

    @pytest.mark.parametrize(
        "field", ["password", "last_login", "username", "email", "is_active", "is_staff"]
    )
    def test_has_expected_field(self, field):
        field_names = [f.name for f in self.User._meta.get_fields()]
        assert field in field_names, f"DynamoUser missing field: {field}"

    def test_set_password_syncs_field_values(self):
        """set_password must sync to _field_values for DynamoDB persistence."""
        user = self.User(username="test")
        user.set_password("secret123")
        assert user._field_values.get("password") == user.password

    def test_set_unusable_password_syncs_field_values(self):
        user = self.User(username="test")
        user.set_unusable_password()
        assert user._field_values.get("password") == user.password
        assert not user.has_usable_password()


# ── Auth backends ────────────────────────────────────────────────────────


class TestAuthBackends:
    """Auth backends must inherit from Django's BaseBackend."""

    def test_dynamo_backend_inherits_base(self):
        from django_dynamodb_backend.contrib.auth_dynamo.backends import (
            DynamoAuthBackend,
        )

        assert issubclass(DynamoAuthBackend, BaseBackend)

    def test_email_backend_inherits_base(self):
        from django_dynamodb_backend.contrib.auth_dynamo.backends import (
            EmailAuthBackend,
        )

        assert issubclass(EmailAuthBackend, BaseBackend)

    @pytest.mark.parametrize("method", ["authenticate", "get_user"])
    def test_backend_has_required_methods(self, method):
        from django_dynamodb_backend.contrib.auth_dynamo.backends import (
            DynamoAuthBackend,
        )

        assert hasattr(DynamoAuthBackend, method)


# ── Auth forms ───────────────────────────────────────────────────────────


class TestAuthForms:
    """Auth forms must subclass Django's built-in auth forms."""

    def test_creation_form_subclasses_django(self):
        from django.contrib.auth.forms import UserCreationForm

        from django_dynamodb_backend.contrib.auth_dynamo.forms import (
            DynamoUserCreationForm,
        )

        assert issubclass(DynamoUserCreationForm, UserCreationForm)

    def test_change_form_subclasses_django(self):
        from django.contrib.auth.forms import UserChangeForm

        from django_dynamodb_backend.contrib.auth_dynamo.forms import (
            DynamoUserChangeForm,
        )

        assert issubclass(DynamoUserChangeForm, UserChangeForm)

    def test_password_change_form_subclasses_django(self):
        from django.contrib.auth.forms import AdminPasswordChangeForm

        from django_dynamodb_backend.contrib.auth_dynamo.forms import (
            AdminPasswordChangeForm as DynamoAdminPWForm,
        )

        assert issubclass(DynamoAdminPWForm, AdminPasswordChangeForm)

    def test_auth_form_subclasses_django(self):
        from django.contrib.auth.forms import AuthenticationForm

        from django_dynamodb_backend.contrib.auth_dynamo.forms import (
            AuthenticationForm as DynamoAuthForm,
        )

        assert issubclass(DynamoAuthForm, AuthenticationForm)


# ── DynamoUserAdmin ──────────────────────────────────────────────────────


class TestDynamoUserAdmin:
    """DynamoUserAdmin must subclass Django's UserAdmin."""

    def test_subclasses_user_admin(self):
        from django.contrib.auth.admin import UserAdmin

        from django_dynamodb_backend.contrib.auth_dynamo.admin import DynamoUserAdmin

        assert issubclass(DynamoUserAdmin, UserAdmin)

    def test_specifies_custom_forms(self):
        from django_dynamodb_backend.contrib.auth_dynamo.admin import DynamoUserAdmin
        from django_dynamodb_backend.contrib.auth_dynamo.forms import (
            AdminPasswordChangeForm,
            DynamoUserChangeForm,
            DynamoUserCreationForm,
        )

        assert DynamoUserAdmin.form is DynamoUserChangeForm
        assert DynamoUserAdmin.add_form is DynamoUserCreationForm
        assert DynamoUserAdmin.change_password_form is AdminPasswordChangeForm


# ── DynamoDBAdmin mixin MRO ──────────────────────────────────────────────


class TestDynamoDBAdminMRO:
    """DynamoDBAdmin's consolidated mixin chain must resolve cleanly."""

    def test_inherits_model_admin(self):
        from django_dynamodb_backend.admin import DynamoDBAdmin

        assert issubclass(DynamoDBAdmin, ModelAdmin)

    def test_mro_resolves(self):
        """MRO must compute without TypeError."""
        from django_dynamodb_backend.admin import DynamoDBAdmin

        mro = DynamoDBAdmin.__mro__
        assert ModelAdmin in mro


# ── compat.py shim ───────────────────────────────────────────────────────


class TestCompatShim:
    """compat.py must expose usable symbols for the current Django version."""

    @pytest.mark.parametrize(
        "name",
        [
            "IS_POPUP_VAR",
            "DjangoUserCreationForm",
            "DjangoUserChangeForm",
            "DjangoAdminPasswordChangeForm",
            "DjangoAuthenticationForm",
            "DjangoUserAdmin",
            "DjangoBaseBackend",
        ],
    )
    def test_compat_exports_non_none(self, name):
        import django_dynamodb_backend.compat as compat

        val = getattr(compat, name, None)
        assert val is not None, f"compat.{name} is None — missing fallback?"
