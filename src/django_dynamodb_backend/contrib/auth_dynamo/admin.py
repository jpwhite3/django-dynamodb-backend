"""
Django Admin configuration for DynamoUser.

Provides admin interface for managing DynamoDB users.
"""

from django.contrib import admin, messages
from django.contrib.admin.options import IS_POPUP_VAR
from django.contrib.auth.admin import sensitive_post_parameters_m
from django.http import Http404, HttpResponseRedirect
from django.urls import path, reverse
from django.utils.html import escape
from django.utils.translation import gettext_lazy as _

from .forms import (
    AdminPasswordChangeForm,
    DynamoUserChangeForm,
    DynamoUserCreationForm,
)
from .models import DynamoUser


@admin.register(DynamoUser)
class DynamoUserAdmin(admin.ModelAdmin):
    """
    Admin interface for DynamoUser model.

    Provides user management including password changes.
    """

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

    def get_fieldsets(self, request, obj=None):
        """Return fieldsets for add vs change views."""
        if not obj:
            return self.add_fieldsets
        return super().get_fieldsets(request, obj)

    def get_form(self, request, obj=None, **kwargs):
        """Return the form class for add vs change."""
        defaults = {}
        if obj is None:
            defaults["form"] = self.add_form
        defaults.update(kwargs)
        return super().get_form(request, obj, **defaults)

    def get_urls(self):
        """Add password change URL."""
        return [
            path(
                "<id>/password/",
                self.admin_site.admin_view(self.user_change_password),
                name="auth_dynamo_dynamouser_password_change",
            ),
        ] + super().get_urls()

    def lookup_allowed(self, lookup, value):
        """Allow lookups for change password link."""
        return not lookup.startswith("password") and super().lookup_allowed(
            lookup, value
        )

    @sensitive_post_parameters_m
    def user_change_password(self, request, id, form_url=""):
        """Handle password change for a user."""
        from .managers import DynamoUserManager

        manager = DynamoUserManager()
        manager.model = DynamoUser

        try:
            user = manager.get(pk=id)
        except DynamoUser.DoesNotExist:
            raise Http404(
                _("%(name)s object with primary key %(key)r does not exist.")
                % {
                    "name": DynamoUser._meta.verbose_name,
                    "key": escape(id),
                }
            )

        if request.method == "POST":
            form = self.change_password_form(user, request.POST)
            if form.is_valid():
                form.save()
                change_message = self.construct_change_message(request, form, None)
                self.log_change(request, user, change_message)
                msg = _("Password changed successfully.")
                messages.success(request, msg)
                return HttpResponseRedirect(
                    reverse(
                        f"{self.admin_site.name}:auth_dynamo_dynamouser_change",
                        args=(user.pk,),
                    )
                )
        else:
            form = self.change_password_form(user)

        fieldsets = [(None, {"fields": list(form.base_fields)})]
        admin_form = admin.helpers.AdminForm(form, fieldsets, {})

        context = {
            "title": _("Change password: %s") % escape(user.get_username()),
            "adminForm": admin_form,
            "form_url": form_url,
            "form": form,
            "is_popup": (IS_POPUP_VAR in request.POST or IS_POPUP_VAR in request.GET),
            "is_popup_var": IS_POPUP_VAR,
            "add": True,
            "change": False,
            "has_delete_permission": False,
            "has_change_permission": True,
            "has_absolute_url": False,
            "opts": self.model._meta,
            "original": user,
            "save_as": False,
            "show_save": True,
            **self.admin_site.each_context(request),
        }

        request.current_app = self.admin_site.name

        return self.render_change_form(
            request,
            context,
            add=False,
            change=True,
            obj=user,
            form_url=form_url,
        )

    def save_model(self, request, obj, form, change):
        """Save user model, handling password for new users."""
        if not change:
            # New user - password handled by form
            obj.set_password(form.cleaned_data["password1"])
        obj.save()

    def response_add(self, request, obj, post_url_continue=None):
        """Handle response after adding a user."""
        # Redirect to password change if requested
        if "_addanother" not in request.POST and IS_POPUP_VAR not in request.POST:
            request.POST = request.POST.copy()
            request.POST["_continue"] = True
        return super().response_add(request, obj, post_url_continue)
