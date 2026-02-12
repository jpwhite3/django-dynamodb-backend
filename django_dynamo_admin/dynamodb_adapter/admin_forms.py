"""
Enhanced form handling for DynamoDB admin with validation and widgets.
"""

import json
import logging
import uuid
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation

from django import forms
from django.contrib.admin.widgets import (AdminDateWidget, AdminSplitDateTime,
                                          AdminTimeWidget)
from django.core.exceptions import ValidationError
from django.forms.widgets import CheckboxInput, Select, Textarea, TextInput
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)


class DynamoDBFormMixin:
    """Mixin for DynamoDB-specific form enhancements."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._enhance_form_fields()

    def _enhance_form_fields(self):
        """Add DynamoDB-specific enhancements to form fields."""
        for field_name, field in self.fields.items():
            # Add common CSS classes
            if hasattr(field.widget, "attrs"):
                current_class = field.widget.attrs.get("class", "")
                field.widget.attrs["class"] = f"{current_class} form-control".strip()

            # Add field-specific enhancements
            self._enhance_field(field_name, field)

    def _enhance_field(self, field_name, field):
        """Enhance individual fields based on type."""
        # Add placeholder text
        if isinstance(field, forms.CharField):
            if hasattr(field.widget, "attrs"):
                field.widget.attrs.setdefault(
                    "placeholder", f'Enter {field_name.replace("_", " ").title()}'
                )

        # Add validation hints for numeric fields
        elif isinstance(
            field, (forms.IntegerField, forms.DecimalField, forms.FloatField)
        ):
            if hasattr(field.widget, "attrs"):
                field.widget.attrs.setdefault("placeholder", "Enter numeric value")
                field.widget.attrs["type"] = "number"

        # Add validation for email fields
        elif isinstance(field, forms.EmailField):
            if hasattr(field.widget, "attrs"):
                field.widget.attrs.setdefault("placeholder", "email@example.com")
                field.widget.attrs["type"] = "email"

        # Add validation for URL fields
        elif isinstance(field, forms.URLField):
            if hasattr(field.widget, "attrs"):
                field.widget.attrs.setdefault("placeholder", "https://example.com")
                field.widget.attrs["type"] = "url"


class DynamoDBModelForm(DynamoDBFormMixin, forms.ModelForm):
    """Enhanced ModelForm for DynamoDB models."""

    def clean(self):
        """Enhanced validation for DynamoDB constraints."""
        cleaned_data = super().clean()

        # Validate DynamoDB-specific constraints
        self._validate_primary_key(cleaned_data)
        self._validate_dynamodb_types(cleaned_data)
        self._validate_size_limits(cleaned_data)

        return cleaned_data

    def _validate_primary_key(self, cleaned_data):
        """Validate primary key constraints."""
        model_fields = self._meta.model._meta.fields

        for field in model_fields:
            if hasattr(field, "primary_key") and field.primary_key:
                field_value = cleaned_data.get(field.name)

                if not field_value and not self.instance.pk:
                    raise ValidationError(
                        {field.name: _("Primary key is required for new items.")}
                    )

                # Validate primary key format
                if field_value:
                    self._validate_key_format(field.name, field_value)

    def _validate_key_format(self, field_name, value):
        """Validate DynamoDB key format."""
        # DynamoDB keys must be non-empty strings or numbers
        if isinstance(value, str) and not value.strip():
            raise ValidationError(
                {field_name: _("Primary key cannot be empty or whitespace.")}
            )

        # Check for invalid characters in string keys
        if isinstance(value, str):
            invalid_chars = ["\x00", "\x01", "\x02", "\x03"]  # Some control characters
            for char in invalid_chars:
                if char in value:
                    raise ValidationError(
                        {field_name: _("Primary key contains invalid characters.")}
                    )

    def _validate_dynamodb_types(self, cleaned_data):
        """Validate DynamoDB data type constraints."""
        for field_name, value in cleaned_data.items():
            if value is None:
                continue

            try:
                # Validate based on field type
                model_field = self._meta.model._meta.get_field(field_name)

                if hasattr(model_field, "max_length") and model_field.max_length:
                    if len(str(value)) > model_field.max_length:
                        raise ValidationError(
                            {
                                field_name: _(
                                    f"Value exceeds maximum length of {model_field.max_length} characters."
                                )
                            }
                        )

                # Validate JSON fields
                if hasattr(model_field, "default") and hasattr(model_field, "encoder"):
                    # This is likely a JSONField
                    try:
                        json.dumps(value)
                    except (TypeError, ValueError):
                        raise ValidationError(
                            {field_name: _("Value must be valid JSON.")}
                        )

            except Exception as e:
                logger.warning(f"Error validating field {field_name}: {e}")

    def _validate_size_limits(self, cleaned_data):
        """Validate DynamoDB item size limits."""
        # DynamoDB has a 400KB limit per item
        # This is an approximation
        estimated_size = 0

        for field_name, value in cleaned_data.items():
            if value is not None:
                # Rough size estimation
                if isinstance(value, str):
                    estimated_size += len(value.encode("utf-8"))
                elif isinstance(value, (int, float, Decimal)):
                    estimated_size += 8  # Approximate size for numbers
                elif isinstance(value, bool):
                    estimated_size += 1
                elif isinstance(value, (dict, list)):
                    estimated_size += len(json.dumps(value).encode("utf-8"))
                else:
                    estimated_size += len(str(value).encode("utf-8"))

        # 400KB limit (with some buffer)
        if estimated_size > 350 * 1024:  # 350KB
            raise ValidationError(
                _("Item size is too large. DynamoDB items must be under 400KB.")
            )

    def save(self, commit=True):
        """Enhanced save with DynamoDB optimizations."""
        instance = super().save(commit=False)

        # Add any DynamoDB-specific processing here
        self._process_dynamodb_fields(instance)

        if commit:
            try:
                instance.save()
            except Exception as e:
                logger.error(f"Error saving DynamoDB model: {e}")
                raise ValidationError(_("Error saving to DynamoDB. Please try again."))

        return instance

    def _process_dynamodb_fields(self, instance):
        """Process fields for DynamoDB storage."""
        # Convert Python types to DynamoDB-compatible formats
        for field in instance._meta.fields:
            value = getattr(instance, field.name)

            if value is not None:
                # Convert Decimal for numeric fields
                if isinstance(field, (forms.IntegerField, forms.DecimalField)):
                    if not isinstance(value, Decimal):
                        try:
                            setattr(instance, field.name, Decimal(str(value)))
                        except (InvalidOperation, ValueError):
                            pass

                # Ensure datetime fields are timezone-aware
                elif isinstance(field, forms.DateTimeField):
                    if isinstance(value, datetime) and value.tzinfo is None:
                        from django.utils import timezone

                        setattr(instance, field.name, timezone.make_aware(value))


class DynamoDBInlineFormSet(forms.BaseInlineFormSet):
    """Enhanced inline formset for DynamoDB models."""

    def clean(self):
        """Enhanced validation for inline formsets."""
        if any(self.errors):
            return

        # Add DynamoDB-specific validation for related objects
        self._validate_related_constraints()

    def _validate_related_constraints(self):
        """Validate constraints for related DynamoDB objects."""
        # Check for duplicate keys in related objects
        keys_seen = set()

        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get("DELETE", False):
                # Get the foreign key value
                fk_field = None
                for field in form._meta.model._meta.fields:
                    if (
                        hasattr(field, "related_model")
                        and field.related_model == self.fk.related_model
                    ):
                        fk_field = field
                        break

                if fk_field:
                    key_value = form.cleaned_data.get(fk_field.name)
                    if key_value in keys_seen:
                        raise ValidationError(
                            _("Duplicate related objects are not allowed.")
                        )
                    keys_seen.add(key_value)


class DynamoDBWidget:
    """Base widget class with DynamoDB-specific enhancements."""

    def __init__(self, attrs=None):
        default_attrs = {"class": "form-control"}
        if attrs:
            default_attrs.update(attrs)
        super().__init__(attrs=default_attrs)


class DynamoDBTextInput(DynamoDBWidget, TextInput):
    """Enhanced text input for DynamoDB string fields."""

    pass


class DynamoDBTextarea(DynamoDBWidget, Textarea):
    """Enhanced textarea for DynamoDB text fields."""

    def __init__(self, attrs=None):
        default_attrs = {"rows": 4, "cols": 40}
        if attrs:
            default_attrs.update(attrs)
        super().__init__(attrs=default_attrs)


class DynamoDBNumberInput(DynamoDBWidget, TextInput):
    """Enhanced number input for DynamoDB numeric fields."""

    def __init__(self, attrs=None):
        default_attrs = {"type": "number", "step": "any"}
        if attrs:
            default_attrs.update(attrs)
        super().__init__(attrs=default_attrs)


class DynamoDBSelect(DynamoDBWidget, Select):
    """Enhanced select widget for DynamoDB choice fields."""

    pass


class DynamoDBCheckbox(CheckboxInput):
    """Enhanced checkbox for DynamoDB boolean fields."""

    def __init__(self, attrs=None):
        default_attrs = {"class": "form-check-input"}
        if attrs:
            default_attrs.update(attrs)
        super().__init__(attrs=default_attrs)


class JSONEditorWidget(DynamoDBWidget, Textarea):
    """Widget for editing JSON data with validation."""

    def __init__(self, attrs=None):
        default_attrs = {
            "rows": 10,
            "cols": 80,
            "class": "form-control json-editor",
            "data-json": "true",
        }
        if attrs:
            default_attrs.update(attrs)
        super().__init__(attrs=default_attrs)

    def format_value(self, value):
        """Format value for display in widget."""
        if value is None:
            return ""

        if isinstance(value, str):
            try:
                # Try to parse and reformat JSON
                parsed = json.loads(value)
                return json.dumps(parsed, indent=2, sort_keys=True)
            except (json.JSONDecodeError, TypeError):
                return value

        return json.dumps(value, indent=2, sort_keys=True)


class UUIDWidget(DynamoDBWidget, TextInput):
    """Widget for UUID fields with generation button."""

    def __init__(self, attrs=None):
        default_attrs = {
            "class": "form-control uuid-field",
            "placeholder": "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx",
        }
        if attrs:
            default_attrs.update(attrs)
        super().__init__(attrs=default_attrs)

    def render(self, name, value, attrs=None, renderer=None):
        """Render widget with UUID generation button."""
        html = super().render(name, value, attrs, renderer)

        # Add UUID generation button
        button_html = f"""
        <button type="button" class="btn btn-outline-secondary btn-sm ml-1" 
                onclick="document.getElementById('id_{name}').value = generateUUID()">
            Generate UUID
        </button>
        <script>
        function generateUUID() {{
            return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {{
                var r = Math.random() * 16 | 0,
                    v = c == 'x' ? r : (r & 0x3 | 0x8);
                return v.toString(16);
            }});
        }}
        </script>
        """

        return html + button_html


# Widget mapping for DynamoDB fields
DYNAMODB_WIDGET_MAPPING = {
    "CharField": DynamoDBTextInput,
    "TextField": DynamoDBTextarea,
    "IntegerField": DynamoDBNumberInput,
    "DecimalField": DynamoDBNumberInput,
    "FloatField": DynamoDBNumberInput,
    "BooleanField": DynamoDBCheckbox,
    "JSONField": JSONEditorWidget,
    "UUIDField": UUIDWidget,
    "EmailField": DynamoDBTextInput,
    "URLField": DynamoDBTextInput,
    "DateTimeField": AdminSplitDateTime,
    "DateField": AdminDateWidget,
    "TimeField": AdminTimeWidget,
}


def get_dynamodb_widget_for_field(field):
    """Get the appropriate widget for a DynamoDB field."""
    field_type = field.__class__.__name__
    widget_class = DYNAMODB_WIDGET_MAPPING.get(field_type, DynamoDBTextInput)

    attrs = {}

    # Add field-specific attributes
    if hasattr(field, "max_length") and field.max_length:
        attrs["maxlength"] = field.max_length

    if hasattr(field, "help_text") and field.help_text:
        attrs["title"] = field.help_text

    return widget_class(attrs=attrs)
