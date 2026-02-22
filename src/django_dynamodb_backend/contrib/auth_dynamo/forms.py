"""
Forms for DynamoUser admin interface.

Provides forms for user creation, editing, and password management.
"""

from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import ReadOnlyPasswordHashField
from django.utils.translation import gettext_lazy as _

from .models import DynamoUser


class DynamoUserCreationForm(forms.ModelForm):
    """
    Form for creating new users in admin.

    Includes password confirmation and validation.
    """

    password1 = forms.CharField(
        label=_("Password"),
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text=password_validation.password_validators_help_text_html(),
    )
    password2 = forms.CharField(
        label=_("Password confirmation"),
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text=_("Enter the same password as before, for verification."),
    )

    class Meta:
        model = DynamoUser
        fields = ("username", "email")

    def clean_username(self):
        """Validate username is unique."""
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

    def clean_password2(self):
        """Validate passwords match."""
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError(_("The two password fields didn't match."))
        return password2

    def _post_clean(self):
        """Run password validation after clean."""
        super()._post_clean()
        password = self.cleaned_data.get("password2")
        if password:
            try:
                password_validation.validate_password(password, self.instance)
            except forms.ValidationError as error:
                self.add_error("password2", error)

    def save(self, commit=True):
        """Save user with hashed password."""
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class DynamoUserChangeForm(forms.ModelForm):
    """
    Form for editing existing users in admin.

    Shows password as a read-only hash with link to change.
    """

    password = ReadOnlyPasswordHashField(
        label=_("Password"),
        help_text=_(
            "Raw passwords are not stored, so there is no way to see this "
            "user's password, but you can change the password using "
            '<a href="{}">this form</a>.'
        ),
    )

    class Meta:
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
        password = self.fields.get("password")
        if password:
            password.help_text = password.help_text.format("../password/")

        # Make user_permissions and groups display as textareas
        if "user_permissions" in self.fields:
            self.fields["user_permissions"].widget = forms.Textarea(
                attrs={"rows": 3, "cols": 60}
            )
            self.fields["user_permissions"].help_text = _(
                "Comma-separated list of permissions (e.g., polls:question:add,polls:question:change)"
            )

        if "groups" in self.fields:
            self.fields["groups"].widget = forms.Textarea(attrs={"rows": 2, "cols": 60})
            self.fields["groups"].help_text = _("Comma-separated list of group names")


class AdminPasswordChangeForm(forms.Form):
    """
    Form for changing a user's password in admin.
    """

    error_messages = {
        "password_mismatch": _("The two password fields didn't match."),
    }

    password1 = forms.CharField(
        label=_("New password"),
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text=password_validation.password_validators_help_text_html(),
    )
    password2 = forms.CharField(
        label=_("Confirm password"),
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text=_("Enter the same password as before, for verification."),
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_password2(self):
        """Validate passwords match."""
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError(
                self.error_messages["password_mismatch"],
                code="password_mismatch",
            )
        password_validation.validate_password(password2, self.user)
        return password2

    def save(self, commit=True):
        """Save user with new password."""
        password = self.cleaned_data["password1"]
        self.user.set_password(password)
        if commit:
            self.user.save()
        return self.user


class AuthenticationForm(forms.Form):
    """
    Form for user login.

    Can be used with Django's login view.
    """

    username = forms.CharField(
        label=_("Username"),
        max_length=150,
        widget=forms.TextInput(attrs={"autofocus": True}),
    )
    password = forms.CharField(
        label=_("Password"),
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )

    error_messages = {
        "invalid_login": _(
            "Please enter a correct username and password. Note that both "
            "fields may be case-sensitive."
        ),
        "inactive": _("This account is inactive."),
    }

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user_cache = None
        super().__init__(*args, **kwargs)

    def clean(self):
        """Validate username and password."""
        username = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")

        if username is not None and password:
            from .backends import DynamoAuthBackend

            backend = DynamoAuthBackend()
            self.user_cache = backend.authenticate(
                self.request, username=username, password=password
            )
            if self.user_cache is None:
                raise forms.ValidationError(
                    self.error_messages["invalid_login"],
                    code="invalid_login",
                )
            elif not self.user_cache.is_active:
                raise forms.ValidationError(
                    self.error_messages["inactive"],
                    code="inactive",
                )
        return self.cleaned_data

    def get_user(self):
        """Return the authenticated user."""
        return self.user_cache
