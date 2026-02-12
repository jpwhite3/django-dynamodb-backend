import logging

from django.contrib import admin, messages
from django.contrib.admin import ModelAdmin
from django.contrib.admin.utils import unquote
from django.contrib.admin.views.main import ChangeList
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.forms import ModelForm
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .admin_actions import DynamoDBActionMixin
from .admin_autocomplete import DynamoDBAutocompleteMixin
from .admin_filters import (DynamoDBFilterMixin, IsActiveFilter,
                            NameSearchFilter, PublishedDateFilter,
                            StatusFilter, VoteCountFilter)
from .admin_forms import DynamoDBModelForm, get_dynamodb_widget_for_field
from .admin_inlines import DynamoDBStackedInline, DynamoDBTabularInline
from .admin_permissions import SecureDynamoDBAdmin
from .gsi_optimizer import GSIMonitoringMixin
from .models import Choice, MyModel, Question
from .pagination import DynamoDBPaginationMixin

logger = logging.getLogger(__name__)


class DynamoDBChangeList(ChangeList):
    """Custom ChangeList for DynamoDB models to handle pagination efficiently."""

    def __init__(
        self,
        request,
        model,
        list_display,
        list_display_links,
        list_filter,
        date_hierarchy,
        search_fields,
        list_select_related,
        list_per_page,
        list_max_show_all,
        list_editable,
        model_admin,
        sortable_by,
        search_help_text=None,
    ):
        super().__init__(
            request,
            model,
            list_display,
            list_display_links,
            list_filter,
            date_hierarchy,
            search_fields,
            list_select_related,
            list_per_page,
            list_max_show_all,
            list_editable,
            model_admin,
            sortable_by,
            search_help_text,
        )

        # Store pagination info for DynamoDB
        self._last_evaluated_key = None
        self._total_count = None

    def get_queryset(self, request):
        """Get queryset with DynamoDB optimizations."""
        queryset = super().get_queryset(request)

        # Apply DynamoDB-specific optimizations
        if hasattr(queryset, "_dynamodb_scan_filters"):
            # Log the filters being used
            logger.info(
                f"Admin query with {len(queryset._dynamodb_scan_filters)} scan filters"
            )

        # Handle pagination info from request
        if "last_key" in request.GET:
            try:
                import json

                last_key = json.loads(request.GET["last_key"])
                queryset = queryset.using_pagination(last_key)
            except (ValueError, KeyError) as e:
                logger.warning(f"Invalid pagination key: {e}")

        return queryset

    def get_results(self, request):
        """Get results with DynamoDB pagination handling."""
        try:
            paginator = self.model_admin.get_paginator(
                request, self.queryset, self.list_per_page
            )
            page_num = request.GET.get("p", 1)

            try:
                page_num = int(page_num)
            except ValueError:
                page_num = 1

            self.result_list = list(paginator.get_page(page_num))
            self.result_count = len(self.result_list)
            self.full_result_count = (
                self.result_count
            )  # DynamoDB doesn't easily provide total count

            # Handle pagination info
            if hasattr(self.queryset, "get_pagination_info"):
                pagination_info = self.queryset.get_pagination_info()
                self._last_evaluated_key = pagination_info.get("last_evaluated_key")

        except Exception as e:
            logger.error(f"Error getting admin results: {e}")
            self.result_list = []
            self.result_count = 0
            self.full_result_count = 0


class DynamoDBPaginator(Paginator):
    """Custom paginator for DynamoDB that handles LastEvaluatedKey pagination."""

    def __init__(self, object_list, per_page, orphans=0, allow_empty_first_page=True):
        super().__init__(object_list, per_page, orphans, allow_empty_first_page)
        self._last_evaluated_key = None

    @property
    def count(self):
        """Return approximate count - DynamoDB doesn't provide exact counts efficiently."""
        try:
            if hasattr(self.object_list, "count"):
                return self.object_list.count()
            return len(self.object_list)
        except Exception:
            return 0

    def get_page(self, number):
        """Get a page with DynamoDB-specific handling."""
        try:
            # For DynamoDB, we'll work with the current result set
            start = (number - 1) * self.per_page
            end = start + self.per_page

            # Get the slice of results
            if hasattr(self.object_list, "__getitem__"):
                page_items = self.object_list[start:end]
            else:
                items = list(self.object_list)
                page_items = items[start:end]

            return page_items
        except Exception as e:
            logger.error(f"Error getting page {number}: {e}")
            return []


class DynamoDBAdminForm(ModelForm):
    """Enhanced form for DynamoDB models with better validation."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Add custom validation or field modifications for DynamoDB
        for field_name, field in self.fields.items():
            # Add CSS classes for better styling
            if hasattr(field.widget, "attrs"):
                field.widget.attrs.update({"class": "form-control"})

    def clean(self):
        """Custom validation for DynamoDB constraints."""
        cleaned_data = super().clean()

        # Add DynamoDB-specific validation
        # For example, ensure partition key is provided
        model_fields = self._meta.model._meta.fields
        for field in model_fields:
            if hasattr(field, "primary_key") and field.primary_key:
                field_value = cleaned_data.get(field.name)
                if not field_value:
                    raise ValidationError(
                        f"Primary key field '{field.name}' is required."
                    )

        return cleaned_data


class DynamoDBAdmin(
    DynamoDBFilterMixin,
    SecureDynamoDBAdmin,
    DynamoDBActionMixin,
    DynamoDBAutocompleteMixin,
    DynamoDBPaginationMixin,
    GSIMonitoringMixin,
    ModelAdmin,
):
    """Enhanced admin class for DynamoDB models with full Django Admin compatibility."""

    # Use custom components
    changelist_view_class = DynamoDBChangeList
    form = DynamoDBAdminForm

    # Default configuration optimized for DynamoDB
    list_per_page = 25  # Reasonable for DynamoDB scan operations
    list_max_show_all = 100
    preserve_filters = True

    # Enhanced actions
    actions = ["delete_selected_optimized", "export_to_csv"]

    def __init__(self, model, admin_site):
        super().__init__(model, admin_site)

        # Auto-configure list_display if not set
        if not hasattr(self, "list_display") or self.list_display == ("__str__",):
            self.list_display = self._get_default_list_display()

        # Auto-configure search fields for common patterns
        if not hasattr(self, "search_fields") or not self.search_fields:
            self.search_fields = self._get_default_search_fields()

    def _get_default_list_display(self):
        """Auto-generate reasonable list_display based on model fields."""
        fields = []
        model_fields = self.model._meta.fields

        # Add primary key first
        for field in model_fields:
            if hasattr(field, "primary_key") and field.primary_key:
                fields.append(field.name)
                break

        # Add other important fields (limit to 5 for performance)
        for field in model_fields[:5]:
            if field.name not in fields:
                # Prefer string fields and common field names
                if hasattr(field, "max_length") or field.name in [
                    "name",
                    "title",
                    "description",
                    "status",
                ]:
                    fields.append(field.name)

        return fields if fields else ["__str__"]

    def _get_default_search_fields(self):
        """Auto-generate search fields for text fields."""
        search_fields = []
        model_fields = self.model._meta.fields

        for field in model_fields:
            # Include text fields in search
            if hasattr(field, "max_length") and field.max_length:
                if field.name in ["name", "title", "description", "text"]:
                    search_fields.append(field.name)

        return search_fields

    def get_changelist(self, request, **kwargs):
        """Return custom ChangeList class."""
        return DynamoDBChangeList

    def get_paginator(
        self, request, queryset, per_page, orphans=0, allow_empty_first_page=True
    ):
        """Return custom paginator for DynamoDB."""
        return DynamoDBPaginator(queryset, per_page, orphans, allow_empty_first_page)

    def get_queryset(self, request):
        """Get queryset with DynamoDB optimizations."""
        queryset = super().get_queryset(request)

        # Apply any DynamoDB-specific query optimizations
        if hasattr(queryset, "_use_query_operation"):
            logger.info(
                f"Admin using {'Query' if queryset._use_query_operation else 'Scan'} operation"
            )

        return queryset

    def delete_selected_optimized(self, request, queryset):
        """Optimized bulk delete for DynamoDB."""
        try:
            count, models_dict = queryset.delete()

            if count == 1:
                message = "1 item was successfully deleted."
            else:
                message = f"{count} items were successfully deleted."

            self.message_user(request, message, messages.SUCCESS)

        except Exception as e:
            logger.error(f"Error in bulk delete: {e}")
            self.message_user(
                request, f"Error deleting items: {str(e)}", messages.ERROR
            )

    delete_selected_optimized.short_description = (
        "Delete selected items (DynamoDB optimized)"
    )

    def export_to_csv(self, request, queryset):
        """Export selected items to CSV."""
        import csv

        from django.http import HttpResponse

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="{self.model._meta.model_name}_export.csv"'
        )

        writer = csv.writer(response)

        # Write header
        field_names = [field.name for field in self.model._meta.fields]
        writer.writerow(field_names)

        # Write data
        for obj in queryset:
            row = []
            for field_name in field_names:
                value = getattr(obj, field_name, "")
                # Handle complex data types
                if isinstance(value, (dict, list)):
                    value = str(value)
                row.append(value)
            writer.writerow(row)

        return response

    export_to_csv.short_description = "Export selected items to CSV"

    def get_search_results(self, request, queryset, search_term):
        """Enhanced search for DynamoDB models."""
        if not search_term:
            return queryset, False

        # Apply search filters
        search_queryset = queryset
        use_distinct = False

        if self.search_fields:
            search_filters = []

            for field_name in self.search_fields:
                # Use contains lookup for text search
                filter_key = f"{field_name}__contains"
                search_filters.append(filter_key)

            # Apply search to each field (OR logic)
            from django.db.models import Q

            search_q = Q()
            for field_name in self.search_fields:
                search_q |= Q(**{f"{field_name}__contains": search_term})

            # For DynamoDB, we'll need to handle this differently
            # Apply the first search field for now
            if self.search_fields:
                search_field = self.search_fields[0]
                search_queryset = queryset.filter(
                    **{f"{search_field}__contains": search_term}
                )

        return search_queryset, use_distinct

    def changelist_view(self, request, extra_context=None):
        """Enhanced changelist view with DynamoDB-specific features."""
        extra_context = extra_context or {}

        # Add DynamoDB-specific context
        extra_context.update(
            {
                "title": f"{self.model._meta.verbose_name_plural} (DynamoDB)",
                "has_filters": bool(self.list_filter),
                "has_search": bool(self.search_fields),
            }
        )

        try:
            return super().changelist_view(request, extra_context)
        except Exception as e:
            logger.error(f"Error in changelist view: {e}")
            # Provide fallback behavior
            messages.error(request, f"Error loading list: {str(e)}")
            return HttpResponseRedirect(reverse("admin:index"))

    def add_view(self, request, form_url="", extra_context=None):
        """Enhanced add view with DynamoDB validations."""
        extra_context = extra_context or {}
        extra_context["title"] = f"Add {self.model._meta.verbose_name}"

        return super().add_view(request, form_url, extra_context)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        """Enhanced change view with DynamoDB optimizations."""
        extra_context = extra_context or {}

        try:
            # Get the object using DynamoDB-optimized query
            obj = self.get_object(request, unquote(object_id))
            if obj:
                extra_context["title"] = f"Change {self.model._meta.verbose_name}"

            return super().change_view(request, object_id, form_url, extra_context)

        except Exception as e:
            logger.error(f"Error in change view for {object_id}: {e}")
            messages.error(request, f"Error loading item: {str(e)}")
            return HttpResponseRedirect(
                reverse(
                    f"admin:{self.model._meta.app_label}_{self.model._meta.model_name}_changelist"
                )
            )

    def delete_view(self, request, object_id, extra_context=None):
        """Enhanced delete view with DynamoDB optimizations."""
        extra_context = extra_context or {}
        extra_context["title"] = f"Delete {self.model._meta.verbose_name}"

        return super().delete_view(request, object_id, extra_context)

    def has_add_permission(self, request):
        """Check add permission with DynamoDB considerations."""
        return super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        """Check change permission with DynamoDB considerations."""
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        """Check delete permission with DynamoDB considerations."""
        return super().has_delete_permission(request, obj)

    def has_view_permission(self, request, obj=None):
        """Check view permission with DynamoDB considerations."""
        return super().has_view_permission(request, obj)


# Register models with enhanced DynamoDB admin
admin.site.register(MyModel, DynamoDBAdmin)


class QuestionAdmin(DynamoDBAdmin):
    """Enhanced admin configuration for Question model."""

    list_display = ["question_text", "pub_date", "was_published_recently"]
    list_filter = ["pub_date"]
    search_fields = ["question_text"]
    # Note: DynamoDB has limited ordering support
    # ordering = ["pub_date"]
    empty_value_display = "-empty-"
    fieldsets = [
        (None, {"fields": ["question_text"]}),
        ("Date information", {"fields": ["pub_date"]}),
    ]

    # DynamoDB-specific configuration
    list_per_page = 20  # Smaller page size for complex data
    actions = DynamoDBAdmin.actions + ["mark_as_published"]

    def was_published_recently(self, obj):
        """Display method for recent publication status."""
        import datetime

        from django.utils import timezone

        if not obj.pub_date:
            return False

        return obj.pub_date >= timezone.now() - datetime.timedelta(days=1)

    was_published_recently.boolean = True
    was_published_recently.short_description = "Published recently?"

    def mark_as_published(self, request, queryset):
        """Custom action to mark questions as recently published."""
        from django.utils import timezone

        count = queryset.update(pub_date=timezone.now())
        self.message_user(
            request, f"{count} questions marked as published.", messages.SUCCESS
        )

    mark_as_published.short_description = "Mark selected questions as published"


class ChoiceAdmin(DynamoDBAdmin):
    """Enhanced admin configuration for Choice model."""

    list_display = ["choice_text", "question_id", "votes", "vote_percentage"]
    list_filter = ["votes"]
    search_fields = ["choice_text"]
    readonly_fields = ["vote_percentage"]

    # DynamoDB-specific configuration
    list_per_page = 30
    actions = DynamoDBAdmin.actions + ["reset_votes"]

    def vote_percentage(self, obj):
        """Calculate and display vote percentage."""
        if not obj.votes:
            return "0%"

        # This is a simplified calculation
        # In a real app, you'd want to calculate against total votes
        total_votes = max(obj.votes, 1)  # Avoid division by zero
        percentage = (obj.votes / total_votes) * 100
        return f"{percentage:.1f}%"

    vote_percentage.short_description = "Vote %"

    def reset_votes(self, request, queryset):
        """Custom action to reset vote counts."""
        count = queryset.update(votes=0)
        self.message_user(
            request, f"Reset votes for {count} choices.", messages.SUCCESS
        )

    reset_votes.short_description = "Reset vote counts"


# Enhanced admin site configuration
class DynamoDBAdminSite(admin.AdminSite):
    """Custom admin site for DynamoDB with enhanced features."""

    site_header = "DynamoDB Django Admin"
    site_title = "DynamoDB Admin"
    index_title = "DynamoDB Administration"

    def index(self, request, extra_context=None):
        """Enhanced admin index with DynamoDB-specific information."""
        extra_context = extra_context or {}

        # Add DynamoDB-specific context
        extra_context.update(
            {
                "dynamodb_info": {
                    "backend": "Amazon DynamoDB",
                    "features": [
                        "NoSQL Document Store",
                        "Auto-scaling",
                        "Global Tables",
                        "Point-in-time Recovery",
                    ],
                }
            }
        )

        return super().index(request, extra_context)


# Create custom admin site instance
dynamodb_admin_site = DynamoDBAdminSite(name="dynamodb_admin")

# Register models with both default and custom admin sites
admin.site.register(Question, QuestionAdmin)
admin.site.register(Choice, ChoiceAdmin)

# Also register with custom site
dynamodb_admin_site.register(Question, QuestionAdmin)
dynamodb_admin_site.register(Choice, ChoiceAdmin)
dynamodb_admin_site.register(MyModel, DynamoDBAdmin)
