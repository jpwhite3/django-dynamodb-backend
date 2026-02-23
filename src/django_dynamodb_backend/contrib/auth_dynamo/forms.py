"""
Forms for DynamoUser admin interface.

Inherits from Django's built-in auth forms so that password validation,
help-text rendering, and other UX details are maintained upstream.
Only DynamoDB-specific overrides (e.g. the username-uniqueness check that
hits DynamoDB instead of SQL) are kept here.
"""

from django import forms
from django.utils.translation import gettext_lazy as _

from ...compat import (
    DjangoAdminPasswordChangeForm,
    DjangoAuthenticationForm,
    DjangoUserChangeForm,
    DjangoUserCreationForm,
)
from .models import DynamoUser

# ---------------------------------------------------------------------------
# User creation
# ---------------------------------------------------------------------------


class DynamoUserCreationForm(DjangoUserCreationForm):
    """
    Form for creating new users in admin.

    Inherits password fields, matching/validation, and ``save()`` from
    Django's ``UserCreationForm``.  Only the DynamoDB username-uniqueness
    check is overridden.
    """

    class Meta(DjangoUserCreationForm.Meta):
        model = DynamoUser
        fields = ("username", "email")

    def clean_username(self):
        """Validate username is unique via DynamoDB lookup."""
        username = self.cleaned_data.get("username")
        if username:
            from .managers import DynamoUserManager

            manager = DynamoUserManager()
            manager.model = DynamoUser
            if manager.exists(username=username):
                raise forms.ValidationError(
                    _("A user with that username already exists.")
                )
        return username


# ---------------------------------------------------------------------------
# User change
# ---------------------------------------------------------------------------


class DynamoUserChangeForm(DjangoUserChangeForm):
    """
    Form for editing existing users in admin.

    Inherits the read-only password hash widget and help-text from Django's
    ``UserChangeForm``.  We just point it at ``DynamoUser`` and add
    DynamoDB-friendly widgets for the text-field permissions / groups.
    """

    class Meta(DjangoUserChangeForm.Meta):
        model = DynamoUser
        fields = (
            "username",
            "email",
            "password",
            "first_name",
            "last_name",
            "is_active",
            "is_staff",
            "is_superuser",
            "user_permissions",
            "groups",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Make user_permissions and groups display as textareas
        # (they are plain TextFields, not M2M, in DynamoDB)
        if "user_permissions" in self.fields:
            self.fields["user_permissions"].widget = forms.Textarea(
                attrs={"rows": 3, "cols": 60}
            )
            self.fields["user_permissions"].help_text = _(
                "Comma-separated list of permissions "
                "(e.g., polls:question:add,polls:question:change)"
            )

        if "groups" in self.fields:
            self.fields["groups"].widget = forms.Textarea(attrs={"rows": 2, "cols": 60})
            self.fields["groups"].help_text = _("Comma-separated list of group names")


# ---------------------------------------------------------------------------
# Admin password change
# ---------------------------------------------------------------------------


class AdminPasswordChangeForm(DjangoAdminPasswordChangeForm):
    """
    Form for changing a user's password in admin.

    Inherits all logic from Django's ``AdminPasswordChangeForm``.
    No DynamoDB-specific overrides needed — ``set_password()`` and ``save()``
    are handled by the ``DynamoUser`` model.
    """

    pass


# ---------------------------------------------------------------------------
# Login form
# ---------------------------------------------------------------------------


class AuthenticationForm(DjangoAuthenticationForm):
    """
    Form for user login.

    Inherits all login logic from Django's ``AuthenticationForm``.
    Authentication is routed through ``AUTHENTICATION_BACKENDS`` which
    includes our ``DynamoAuthBackend``, so no override is needed here.
    """

    pass
