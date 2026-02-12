"""
DynamoDB-optimized Django Admin Inlines.

This module provides inline admin classes that work efficiently with DynamoDB's
data patterns and relationship structures.
"""

import logging
from decimal import Decimal

from django.contrib import admin
from django.contrib.admin.options import InlineModelAdmin
from django.contrib.contenttypes.admin import GenericInlineModelAdmin
from django.core.exceptions import ValidationError
from django.db import transaction
from django.forms import BaseInlineFormSet, modelformset_factory
from django.forms.models import inlineformset_factory
from django.utils.functional import cached_property

from .admin_forms import DynamoDBModelForm
from .models import DynamoDBModel

logger = logging.getLogger(__name__)


class DynamoDBInlineFormSet(BaseInlineFormSet):
    """
    Custom formset for DynamoDB inline forms with optimized batch operations.
    """

    def __init__(self, *args, **kwargs):
        self.parent_obj = kwargs.pop("instance", None)
        super().__init__(*args, **kwargs)
        self._batch_operations = []

    def save(self, commit=True):
        """Save all forms in the formset with DynamoDB batch optimization."""
        if not commit:
            return super().save(commit=False)

        # Collect all operations for batch processing
        saved_instances = []
        instances_to_create = []
        instances_to_update = []
        instances_to_delete = []

        # Process each form
        for form in self.forms:
            if not hasattr(form, "cleaned_data"):
                continue

            # Check if form should be deleted
            if self._should_delete_form(form):
                if form.instance.pk:
                    instances_to_delete.append(form.instance)
                continue

            # Skip empty forms
            if not form.has_changed():
                continue

            # Validate form
            if not form.is_valid():
                continue

            instance = form.save(commit=False)

            # Set parent relationship
            self._set_parent_relationship(instance)

            # Categorize by operation type
            if instance.pk:
                instances_to_update.append(instance)
            else:
                instances_to_create.append(instance)

            saved_instances.append(instance)

        # Execute batch operations
        try:
            self._execute_batch_operations(
                instances_to_create, instances_to_update, instances_to_delete
            )
            logger.info(
                f"Batch inline operation: {len(instances_to_create)} creates, "
                f"{len(instances_to_update)} updates, {len(instances_to_delete)} deletes"
            )
        except Exception as e:
            logger.error(f"Error in batch inline operations: {e}")
            raise ValidationError(f"Failed to save inline objects: {e}")

        return saved_instances

    def _should_delete_form(self, form):
        """Check if form should be deleted."""
        return form.cleaned_data.get("DELETE", False) or (
            hasattr(form, "empty_permitted")
            and form.empty_permitted
            and not form.has_changed()
        )

    def _set_parent_relationship(self, instance):
        """Set the parent relationship on the instance."""
        if self.parent_obj and hasattr(instance, self.fk.name):
            setattr(instance, self.fk.name, self.parent_obj)

    def _execute_batch_operations(self, creates, updates, deletes):
        """Execute batch operations optimized for DynamoDB."""
        # DynamoDB batch operations are limited to 25 items per batch
        batch_size = 25

        # Batch creates
        for i in range(0, len(creates), batch_size):
            batch = creates[i : i + batch_size]
            self._batch_create(batch)

        # Batch updates (DynamoDB doesn't have batch update, so process individually)
        for instance in updates:
            instance.save()

        # Batch deletes
        for i in range(0, len(deletes), batch_size):
            batch = deletes[i : i + batch_size]
            self._batch_delete(batch)

    def _batch_create(self, instances):
        """Perform batch create operation."""
        if not instances:
            return

        # For DynamoDB, we'll save each instance individually
        # but we can optimize by using the same connection
        for instance in instances:
            instance.save()

    def _batch_delete(self, instances):
        """Perform batch delete operation."""
        if not instances:
            return

        # Collect primary keys for batch deletion
        for instance in instances:
            instance.delete()


class DynamoDBInlineModelAdmin(InlineModelAdmin):
    """
    Base class for DynamoDB inline model admin.
    """

    formset = DynamoDBInlineFormSet
    form = DynamoDBModelForm

    # DynamoDB-specific settings
    max_num_items = 25  # DynamoDB batch limit
    extra_items = 3
    can_delete = True
    show_change_link = False

    def __init__(self, parent_model, admin_site):
        super().__init__(parent_model, admin_site)
        self._validate_dynamodb_relationship()

    def _validate_dynamodb_relationship(self):
        """Validate that the relationship is compatible with DynamoDB."""
        if not issubclass(self.model, DynamoDBModel):
            logger.warning(f"Inline model {self.model} is not a DynamoDBModel")

    def get_formset(self, request, obj=None, **kwargs):
        """Get the formset with DynamoDB optimizations."""
        if "fields" in kwargs:
            fields = kwargs.pop("fields")
        else:
            fields = None

        # Set default values
        kwargs.setdefault("formset", self.formset)
        kwargs.setdefault("form", self.form)
        kwargs.setdefault("extra", self.get_extra(request, obj))
        kwargs.setdefault("max_num", self.get_max_num(request, obj))
        kwargs.setdefault("can_delete", self.can_delete)

        # Create formset with DynamoDB optimizations
        FormSet = inlineformset_factory(self.parent_model, self.model, **kwargs)

        # Add DynamoDB-specific validation
        FormSet.validate_unique = self._validate_unique_dynamodb

        return FormSet

    def _validate_unique_dynamodb(self, forms):
        """Custom unique validation for DynamoDB."""
        # DynamoDB uniqueness is enforced at the primary key level
        seen_keys = set()
        for form in forms:
            if not form.cleaned_data or form.cleaned_data.get("DELETE"):
                continue

            # Check primary key uniqueness
            pk_field = self.model._meta.pk
            if pk_field:
                pk_value = form.cleaned_data.get(pk_field.name)
                if pk_value and pk_value in seen_keys:
                    form.add_error(pk_field.name, "Duplicate primary key value")
                seen_keys.add(pk_value)

    def get_extra(self, request, obj=None, **kwargs):
        """Get number of extra forms to display."""
        return self.extra_items

    def get_max_num(self, request, obj=None, **kwargs):
        """Get maximum number of forms."""
        return self.max_num_items

    def has_add_permission(self, request, obj=None):
        """Check if user can add inline objects."""
        return super().has_add_permission(request) and self._check_dynamodb_capacity(
            request, "add"
        )

    def has_change_permission(self, request, obj=None):
        """Check if user can change inline objects."""
        return super().has_change_permission(
            request, obj
        ) and self._check_dynamodb_capacity(request, "change")

    def has_delete_permission(self, request, obj=None):
        """Check if user can delete inline objects."""
        return super().has_delete_permission(
            request, obj
        ) and self._check_dynamodb_capacity(request, "delete")

    def _check_dynamodb_capacity(self, request, operation):
        """Check if DynamoDB has sufficient capacity for the operation."""
        # This could be enhanced to check actual DynamoDB capacity
        # For now, just return True
        return True

    def get_queryset(self, request):
        """Get queryset optimized for DynamoDB."""
        queryset = super().get_queryset(request)

        # Apply DynamoDB-specific optimizations
        if hasattr(queryset, "_dynamodb_scan_filters"):
            # Add logging for inline queries
            logger.debug(f"Inline admin query for {self.model.__name__}")

        return queryset


class DynamoDBTabularInline(DynamoDBInlineModelAdmin):
    """
    DynamoDB-optimized tabular inline admin.
    """

    template = "admin/edit_inline/dynamodb_tabular.html"

    def __init__(self, parent_model, admin_site):
        super().__init__(parent_model, admin_site)
        # Optimize for tabular display
        self.extra_items = 2
        self.max_num_items = 15  # Smaller for tabular view


class DynamoDBStackedInline(DynamoDBInlineModelAdmin):
    """
    DynamoDB-optimized stacked inline admin.
    """

    template = "admin/edit_inline/dynamodb_stacked.html"

    def __init__(self, parent_model, admin_site):
        super().__init__(parent_model, admin_site)
        # Optimize for stacked display
        self.extra_items = 1
        self.max_num_items = 10  # Smaller for stacked view


class DynamoDBGenericInlineModelAdmin(
    GenericInlineModelAdmin, DynamoDBInlineModelAdmin
):
    """
    DynamoDB-optimized generic inline admin.
    """

    def __init__(self, parent_model, admin_site):
        # Call both parent constructors
        GenericInlineModelAdmin.__init__(self, parent_model, admin_site)
        DynamoDBInlineModelAdmin.__init__(self, parent_model, admin_site)

    def get_formset(self, request, obj=None, **kwargs):
        """Get generic formset with DynamoDB optimizations."""
        # Use Django's generic inline formset creation
        return GenericInlineModelAdmin.get_formset(self, request, obj, **kwargs)


class DynamoDBGenericTabularInline(DynamoDBGenericInlineModelAdmin):
    """
    DynamoDB-optimized generic tabular inline.
    """

    template = "admin/edit_inline/dynamodb_generic_tabular.html"


class DynamoDBGenericStackedInline(DynamoDBGenericInlineModelAdmin):
    """
    DynamoDB-optimized generic stacked inline.
    """

    template = "admin/edit_inline/dynamodb_generic_stacked.html"


# Convenience functions for creating inline classes
def create_dynamodb_tabular_inline(model, parent_model, **options):
    """
    Create a DynamoDB tabular inline class dynamically.
    """

    class Meta:
        model = model

    attrs = {"model": model, "Meta": Meta}
    attrs.update(options)

    return type(f"{model.__name__}TabularInline", (DynamoDBTabularInline,), attrs)


def create_dynamodb_stacked_inline(model, parent_model, **options):
    """
    Create a DynamoDB stacked inline class dynamically.
    """

    class Meta:
        model = model

    attrs = {"model": model, "Meta": Meta}
    attrs.update(options)

    return type(f"{model.__name__}StackedInline", (DynamoDBStackedInline,), attrs)


# Enhanced inline with DynamoDB relationship handling
class DynamoDBForeignKeyInline(DynamoDBTabularInline):
    """
    Inline for DynamoDB models that use reference fields instead of true foreign keys.
    """

    def __init__(self, parent_model, admin_site):
        super().__init__(parent_model, admin_site)
        self.reference_field = self._find_reference_field()

    def _find_reference_field(self):
        """Find the field that references the parent model."""
        parent_model_name = self.parent_model.__name__.lower()

        # Look for fields that might be references
        for field in self.model._meta.fields:
            if (
                field.name.endswith("_id")
                or field.name.endswith("_ref")
                or field.name == parent_model_name
                or field.name == f"{parent_model_name}_id"
            ):
                return field.name

        return None

    def get_formset(self, request, obj=None, **kwargs):
        """Get formset with reference field handling."""
        if self.reference_field:
            # Ensure the reference field is included in the form
            if "fields" not in kwargs:
                kwargs["fields"] = None

        return super().get_formset(request, obj, **kwargs)

    def get_queryset(self, request):
        """Filter queryset by parent reference."""
        queryset = super().get_queryset(request)

        # If we have a reference field and parent object, filter by it
        parent_obj = getattr(request, "_current_object", None)
        if parent_obj and self.reference_field:
            parent_id = getattr(parent_obj, parent_obj._meta.pk.name, None)
            if parent_id:
                filter_kwargs = {self.reference_field: parent_id}
                queryset = queryset.filter(**filter_kwargs)
                logger.debug(
                    f"Filtered inline queryset by {self.reference_field}={parent_id}"
                )

        return queryset
