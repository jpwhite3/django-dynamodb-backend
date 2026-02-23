"""
Django Admin configuration for DynamoUser.

Inherits from Django's ``UserAdmin`` so that password-change views,
fieldset switching (add vs. change), URL routing, and response handling
are all maintained upstream.  Only DynamoDB-specific behaviour is overridden.
"""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from ...compat import DjangoUserAdmin
from .forms import (
    AdminPasswordChangeForm,
    DynamoUserChangeForm,
    DynamoUserCreationForm,
)
from .models import DynamoUser


@admin.register(DynamoUser)
class DynamoUserAdmin(DjangoUserAdmin):
    """
    Admin interface for DynamoUser model.

    Inherits from ``django.contrib.auth.admin.UserAdmin`` which provides:
    - ``get_fieldsets()`` switching between add and change views
    - ``get_form()`` switching between add_form and change form
    - ``get_urls()`` with password-change URL
    - ``user_change_password()`` view
    - ``add_view()`` / ``response_add()`` redirect behaviour
    - ``lookup_allowed()`` filtering

    We only override the form classes (to point at DynamoUser),
    the fieldsets (adapted for DynamoDB text-field permissions),
    and ``save_model()`` for DynamoDB persistence.
    """

    # Point at our DynamoDB-aware forms
    form = DynamoUserChangeForm
    add_form = DynamoUserCreationForm
    change_password_form = AdminPasswordChangeForm

    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "is_staff",
        "is_active",
    )
    list_filter = ("is_staff", "is_superuser", "is_active")
    search_fields = ("username", "email", "first_name", "last_name")
    ordering = ("username",)

    # DynamoDB uses text fields for permissions/groups instead of M2M,
    # so we customise the fieldsets.
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        (_("Personal info"), {"fields": ("first_name", "last_name", "email")}),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "user_permissions",
                ),
            },
        ),
        (_("Groups"), {"fields": ("groups",)}),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("username", "email", "password1", "password2"),
            },
        ),
    )

    readonly_fields = ("last_login", "date_joined")

    # get_fieldsets, get_form, get_urls, user_change_password,
    # lookup_allowed, response_add are all inherited from UserAdmin.

    def save_model(self, request, obj, form, change):
        """Save user model, handling password for new users."""
        if not change:
            obj.set_password(form.cleaned_data["password1"])
        obj.save()
