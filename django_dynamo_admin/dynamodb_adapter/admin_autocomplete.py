"""
DynamoDB-optimized admin autocomplete functionality.

This module provides autocomplete widgets and views that work efficiently
with DynamoDB's query patterns and data structures.
"""

import logging
from typing import Any, Dict, List, Optional, Union

from django.contrib import admin
from django.contrib.admin.widgets import (AutocompleteSelect,
                                          AutocompleteSelectMultiple)
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.forms import Select, SelectMultiple
from django.http import HttpRequest, JsonResponse
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.views.generic import View

from .models import DynamoDBModel

logger = logging.getLogger(__name__)


class DynamoDBAutocompleteView(View):
    """
    Autocomplete view optimized for DynamoDB models.
    """

    def __init__(self, model_admin, **kwargs):
        super().__init__(**kwargs)
        self.model_admin = model_admin
        self.model = model_admin.model

    def get(self, request: HttpRequest) -> JsonResponse:
        """Handle autocomplete GET requests."""
        if not self.has_view_permission(request):
            raise PermissionDenied("You don't have permission to view these items")

        # Get search parameters
        term = request.GET.get("term", "")
        page = request.GET.get("page", 1)
        app_label = request.GET.get("app_label", "")
        model_name = request.GET.get("model_name", "")
        field_name = request.GET.get("field_name", "")

        # Validate parameters
        if not term or len(term) < 2:
            return JsonResponse({"results": [], "pagination": {"more": False}})

        try:
            page = int(page)
        except (ValueError, TypeError):
            page = 1

        # Perform search
        results, has_more = self.get_search_results(request, term, page)

        # Format results for Select2
        formatted_results = []
        for obj in results:
            formatted_results.append(
                {
                    "id": str(getattr(obj, obj._meta.pk.name)),
                    "text": str(obj),
                    "title": str(obj),  # Tooltip text
                }
            )

        return JsonResponse(
            {"results": formatted_results, "pagination": {"more": has_more}}
        )

    def get_search_results(
        self, request: HttpRequest, term: str, page: int = 1
    ) -> tuple:
        """
        Get search results optimized for DynamoDB.
        Returns (results, has_more) tuple.
        """
        # Get base queryset
        queryset = self.get_queryset(request)

        # Apply search
        search_results = self.apply_search(queryset, term)

        # Apply pagination
        page_size = self.get_page_size()
        paginator = Paginator(search_results, page_size)

        try:
            page_obj = paginator.get_page(page)
            results = list(page_obj)
            has_more = page_obj.has_next()
        except Exception as e:
            logger.error(f"Pagination error in autocomplete: {e}")
            results = list(search_results[:page_size])
            has_more = False

        return results, has_more

    def get_queryset(self, request: HttpRequest):
        """Get the base queryset for autocomplete."""
        queryset = self.model.objects.all()

        # Apply any model admin filters
        if hasattr(self.model_admin, "get_search_queryset"):
            queryset = self.model_admin.get_search_queryset(request, queryset)

        return queryset

    def apply_search(self, queryset, term: str):
        """Apply search filters to the queryset."""
        search_fields = self.get_search_fields()

        if not search_fields:
            # If no search fields defined, search in string representation field
            return queryset

        # Build search filters for DynamoDB
        search_queries = []

        for field_name in search_fields:
            # Handle different search patterns
            if field_name.startswith("^"):
                # Starts with search
                field_name = field_name[1:]
                search_queries.append({f"{field_name}__startswith": term})
            elif field_name.startswith("="):
                # Exact match
                field_name = field_name[1:]
                search_queries.append({f"{field_name}__exact": term})
            elif field_name.startswith("@"):
                # Full-text search (limited in DynamoDB)
                field_name = field_name[1:]
                search_queries.append({f"{field_name}__contains": term})
            else:
                # Default: contains search
                search_queries.append({f"{field_name}__contains": term})

        # Apply OR logic for multiple search fields
        if len(search_queries) == 1:
            filtered_queryset = queryset.filter(**search_queries[0])
        else:
            # For DynamoDB, we need to apply filters sequentially
            # This is not as efficient as SQL OR, but it's what we have
            combined_results = []
            for query in search_queries[:3]:  # Limit to first 3 fields for performance
                try:
                    field_results = list(queryset.filter(**query)[:50])
                    combined_results.extend(field_results)
                except Exception as e:
                    logger.warning(f"Search query failed: {query}, error: {e}")

            # Remove duplicates while preserving order
            seen = set()
            unique_results = []
            for obj in combined_results:
                obj_id = getattr(obj, obj._meta.pk.name)
                if obj_id not in seen:
                    seen.add(obj_id)
                    unique_results.append(obj)

            # Create a mock queryset-like object
            filtered_queryset = unique_results

        return filtered_queryset

    def get_search_fields(self) -> List[str]:
        """Get search fields from model admin."""
        if hasattr(self.model_admin, "autocomplete_fields_search"):
            return self.model_admin.autocomplete_fields_search
        elif hasattr(self.model_admin, "search_fields"):
            return self.model_admin.search_fields
        else:
            # Default: search in fields that are likely to be text
            text_fields = []
            for field in self.model._meta.fields:
                if field.get_internal_type() in ["CharField", "TextField"]:
                    text_fields.append(field.name)
            return text_fields[:3]  # Limit to first 3 text fields

    def get_page_size(self) -> int:
        """Get page size for autocomplete results."""
        return getattr(self.model_admin, "autocomplete_page_size", 20)

    def has_view_permission(self, request: HttpRequest) -> bool:
        """Check if user has permission to view autocomplete results."""
        return self.model_admin.has_view_permission(request)


class DynamoDBAutocompleteWidget(AutocompleteSelect):
    """
    Autocomplete widget optimized for DynamoDB models.
    """

    def __init__(self, remote_field, admin_site, attrs=None, choices=(), using=None):
        super().__init__(remote_field, admin_site, attrs, choices, using)
        self.model = remote_field.model

    def get_url(self):
        """Get the autocomplete URL."""
        model = self.remote_field.model
        app_label = model._meta.app_label
        model_name = model._meta.model_name
        return reverse(
            "admin:autocomplete",
            kwargs={
                "app_label": app_label,
                "model_name": model_name,
            },
        )

    def format_value(self, value):
        """Format the selected value."""
        if value:
            try:
                obj = self.model.objects.get(pk=value)
                return {
                    "id": str(value),
                    "text": str(obj),
                }
            except self.model.DoesNotExist:
                pass
        return value

    def optgroups(self, name, value, attr=None):
        """Return selected options formatted for display."""
        # Custom implementation for DynamoDB
        if not value:
            return []

        # Handle multiple values
        if not isinstance(value, (list, tuple)):
            value = [value]

        selected_options = []
        for val in value:
            if val:
                try:
                    obj = self.model.objects.get(pk=val)
                    selected_options.append(
                        {
                            "value": str(val),
                            "label": str(obj),
                            "selected": True,
                        }
                    )
                except self.model.DoesNotExist:
                    logger.warning(f"Object with pk {val} not found for autocomplete")

        if selected_options:
            return [(None, selected_options, 0)]
        return []


class DynamoDBAutocompleteMultipleWidget(AutocompleteSelectMultiple):
    """
    Multiple selection autocomplete widget for DynamoDB models.
    """

    def __init__(self, remote_field, admin_site, attrs=None, choices=(), using=None):
        super().__init__(remote_field, admin_site, attrs, choices, using)
        self.model = remote_field.model

    def get_url(self):
        """Get the autocomplete URL."""
        model = self.remote_field.model
        app_label = model._meta.app_label
        model_name = model._meta.model_name
        return reverse(
            "admin:autocomplete",
            kwargs={
                "app_label": app_label,
                "model_name": model_name,
            },
        )

    def format_value(self, value):
        """Format multiple selected values."""
        if not value:
            return []

        formatted_values = []
        if isinstance(value, (list, tuple)):
            for val in value:
                if val:
                    try:
                        obj = self.model.objects.get(pk=val)
                        formatted_values.append(
                            {
                                "id": str(val),
                                "text": str(obj),
                            }
                        )
                    except self.model.DoesNotExist:
                        pass

        return formatted_values


class DynamoDBAutocompleteMixin:
    """
    Mixin to add DynamoDB-optimized autocomplete functionality to ModelAdmin.
    """

    # Fields that should use autocomplete
    autocomplete_fields = []

    # Custom search fields for autocomplete (overrides search_fields)
    autocomplete_fields_search = []

    # Page size for autocomplete results
    autocomplete_page_size = 20

    # Minimum characters required to trigger search
    autocomplete_min_chars = 2

    def _get_autocomplete_view_class(self):
        """Create a view class with this model_admin baked in."""
        model_admin = self

        class ConfiguredAutocompleteView(DynamoDBAutocompleteView):
            def __init__(self, **kwargs):
                # Call View's __init__ directly, skipping DynamoDBAutocompleteView's
                View.__init__(self, **kwargs)
                self.model_admin = model_admin
                self.model = model_admin.model

        return ConfiguredAutocompleteView

    def get_urls(self):
        """Add autocomplete URLs to admin URLs."""
        urls = super().get_urls()

        # Create a view class with this model_admin configured
        autocomplete_view_class = self._get_autocomplete_view_class()

        # Add autocomplete URL
        autocomplete_url = path(
            "autocomplete/",
            self.admin_site.admin_view(autocomplete_view_class.as_view()),
            name=f"{self.model._meta.app_label}_{self.model._meta.model_name}_autocomplete",
        )

        return [autocomplete_url] + urls

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Override to use DynamoDB autocomplete widget for foreign keys."""
        if db_field.name in self.autocomplete_fields:
            kwargs["widget"] = DynamoDBAutocompleteWidget(
                db_field.remote_field, self.admin_site
            )
            # Don't pass choices to avoid loading all objects
            kwargs.pop("choices", None)

        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        """Override to use DynamoDB autocomplete widget for many-to-many fields."""
        if db_field.name in self.autocomplete_fields:
            kwargs["widget"] = DynamoDBAutocompleteMultipleWidget(
                db_field.remote_field, self.admin_site
            )
            # Don't pass choices to avoid loading all objects
            kwargs.pop("choices", None)

        return super().formfield_for_manytomany(db_field, request, **kwargs)

    def get_search_queryset(self, request, queryset):
        """
        Customize the queryset used for autocomplete searches.
        Can be overridden by subclasses for more specific filtering.
        """
        return queryset

    def get_autocomplete_search_fields(self):
        """Get search fields for autocomplete."""
        if self.autocomplete_fields_search:
            return self.autocomplete_fields_search
        return getattr(self, "search_fields", [])


class DynamoDBReferenceFieldWidget(Select):
    """
    Widget for DynamoDB reference fields (pseudo-foreign keys).
    """

    def __init__(self, reference_model, admin_site, attrs=None, choices=()):
        super().__init__(attrs, choices)
        self.reference_model = reference_model
        self.admin_site = admin_site

    def format_value(self, value):
        """Format the reference value."""
        if value:
            try:
                # Try to load the referenced object for display
                obj = self.reference_model.objects.get(pk=value)
                return str(value)  # Return the ID value for the select
            except self.reference_model.DoesNotExist:
                return value
        return ""

    def choices(self):
        """Generate choices for the select widget."""
        # Limit the number of choices to avoid performance issues
        try:
            queryset = self.reference_model.objects.all()[:100]
            choices = [("", "---------")]  # Empty choice

            for obj in queryset:
                pk_value = getattr(obj, obj._meta.pk.name)
                choices.append((str(pk_value), str(obj)))

            return choices
        except Exception as e:
            logger.error(f"Error loading choices for reference field: {e}")
            return [("", "---------")]


# Utility functions for setting up autocomplete
def setup_autocomplete_admin(admin_class, autocomplete_fields: List[str]):
    """
    Utility function to add autocomplete functionality to an admin class.
    """
    # Add the mixin if not already present
    if not issubclass(admin_class, DynamoDBAutocompleteMixin):
        # Create new class with mixin
        class EnhancedAdmin(DynamoDBAutocompleteMixin, admin_class):
            pass

        # Copy attributes from original class
        for attr_name in dir(admin_class):
            if not attr_name.startswith("_") and attr_name != "autocomplete_fields":
                setattr(EnhancedAdmin, attr_name, getattr(admin_class, attr_name))

        # Set autocomplete fields
        EnhancedAdmin.autocomplete_fields = autocomplete_fields

        return EnhancedAdmin
    else:
        # Just update autocomplete fields
        admin_class.autocomplete_fields = autocomplete_fields
        return admin_class


def register_autocomplete_admin(
    admin_site, model, admin_class, autocomplete_fields: List[str]
):
    """
    Register an admin class with autocomplete functionality.
    """
    enhanced_admin = setup_autocomplete_admin(admin_class, autocomplete_fields)
    admin_site.register(model, enhanced_admin)


# Template tags helpers (can be used in custom templates)
def render_autocomplete_field(field, admin_url_name: str = None) -> str:
    """
    Render an autocomplete field with proper JavaScript initialization.
    """
    if not admin_url_name:
        admin_url_name = "admin:autocomplete"

    return format_html(
        """
        <script>
        (function($) {{
            $(document).ready(function() {{
                $('#id_{field_name}').select2({{
                    ajax: {{
                        url: '{autocomplete_url}',
                        dataType: 'json',
                        delay: 250,
                        data: function (params) {{
                            return {{
                                term: params.term,
                                page: params.page
                            }};
                        }},
                        processResults: function (data, params) {{
                            params.page = params.page || 1;
                            return {{
                                results: data.results,
                                pagination: {{
                                    more: data.pagination.more
                                }}
                            }};
                        }},
                        cache: true
                    }},
                    minimumInputLength: {min_chars},
                    placeholder: 'Start typing to search...',
                    allowClear: true
                }});
            }});
        }})(django.jQuery);
        </script>
        """,
        field_name=field.name,
        autocomplete_url=reverse(admin_url_name),
        min_chars=2,
    )
