import logging

from django.contrib import admin, messages
from django.contrib.admin import ModelAdmin
from django.contrib.admin.utils import unquote
from django.contrib.admin.views.main import ChangeList
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.forms import ModelForm
from django.http import HttpResponseRedirect
from django.urls import reverse

from .admin_actions import DynamoDBActionMixin
from .admin_autocomplete import DynamoDBAutocompleteMixin
from .admin_filters import (
    DynamoDBFilterMixin,
)
from .admin_permissions import SecureDynamoDBAdmin
from .gsi_optimizer import GSIMonitoringMixin
from .pagination import DynamoDBPaginationMixin

logger = logging.getLogger(__name__)


class DynamoDBDateHierarchyMixin:
    """Mixin to add date_hierarchy support for DynamoDB models."""

    def get_date_hierarchy_queryset(self, queryset, date_hierarchy, request):
        """Apply date hierarchy filtering to the queryset.

        DynamoDB doesn't have native date component filtering, so we use
        range queries on the date field.
        """
        from calendar import monthrange
        from datetime import datetime, timedelta

        if not date_hierarchy:
            return queryset

        # Get date parameters from request
        year = request.GET.get("year")
        month = request.GET.get("month")
        day = request.GET.get("day")

        if not year:
            return queryset

        try:
            year = int(year)

            if day and month:
                # Filter for specific day
                month = int(month)
                day = int(day)
                start_date = datetime(year, month, day)
                end_date = start_date + timedelta(days=1)

            elif month:
                # Filter for specific month
                month = int(month)
                start_date = datetime(year, month, 1)
                _, last_day = monthrange(year, month)
                end_date = datetime(year, month, last_day, 23, 59, 59)

            else:
                # Filter for specific year
                start_date = datetime(year, 1, 1)
                end_date = datetime(year, 12, 31, 23, 59, 59)

            # Apply range filter
            queryset = queryset.filter(
                **{
                    f"{date_hierarchy}__gte": start_date,
                    f"{date_hierarchy}__lte": end_date,
                }
            )

            logger.info(
                f"Applied date_hierarchy filter: {date_hierarchy} from {start_date} to {end_date}"
            )

        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid date_hierarchy parameters: {e}")

        return queryset

    def get_date_hierarchy_drilldown(self, queryset, date_hierarchy):
        """Get available date values for the hierarchy drilldown.

        Returns dict with years, months, days that have data.
        """
        from collections import defaultdict
        from datetime import datetime

        if not date_hierarchy:
            return None

        dates = defaultdict(lambda: defaultdict(set))

        try:
            for obj in queryset:
                date_val = getattr(obj, date_hierarchy, None)
                if date_val:
                    if isinstance(date_val, str):
                        date_val = datetime.fromisoformat(
                            date_val.replace("Z", "+00:00")
                        )
                    if hasattr(date_val, "year"):
                        year = date_val.year
                        month = date_val.month
                        day = date_val.day
                        dates[year][month].add(day)
        except Exception as e:
            logger.error(f"Error getting date_hierarchy drilldown: {e}")

        return dict(dates)


class DynamoDBChangeList(ChangeList):
    """Custom ChangeList for DynamoDB models to handle pagination efficiently."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Store pagination info for DynamoDB
        self._last_evaluated_key = None
        self._total_count = None
        self._date_hierarchy_field = self.date_hierarchy

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
        return len(self.object_list)

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


class DynamoDBAdminLoggingMixin:
    """Mixin to add comprehensive admin action logging."""

    def log_admin_action(self, request, obj, action, message=""):
        """Log an admin action for auditing.

        Args:
            request: The HTTP request
            obj: The object being acted upon (can be None for bulk actions)
            action: Action type ('add', 'change', 'delete', 'view', 'bulk_delete', etc.)
            message: Additional message to log
        """
        from django.contrib.admin.models import ADDITION, CHANGE, DELETION, LogEntry
        from django.contrib.contenttypes.models import ContentType

        action_flags = {
            "add": ADDITION,
            "change": CHANGE,
            "delete": DELETION,
            "view": CHANGE,  # No VIEW flag, use CHANGE
            "bulk_delete": DELETION,
            "export": CHANGE,
        }

        action_flag = action_flags.get(action, CHANGE)

        try:
            if obj:
                LogEntry.objects.log_action(
                    user_id=request.user.pk,
                    content_type_id=ContentType.objects.get_for_model(obj).pk,
                    object_id=str(obj.pk),
                    object_repr=str(obj)[:200],
                    action_flag=action_flag,
                    change_message=message or f"DynamoDB {action} action",
                )

            # Also log to application logger
            logger.info(
                f"Admin action: user={request.user.username}, "
                f"action={action}, model={self.model.__name__}, "
                f"object={obj.pk if obj else 'bulk'}, message={message}"
            )

        except Exception as e:
            logger.error(f"Error logging admin action: {e}")

    def log_addition(self, request, obj, message):
        """Log object addition."""
        super().log_addition(request, obj, message)
        self.log_admin_action(request, obj, "add", str(message))

    def log_change(self, request, obj, message):
        """Log object change."""
        super().log_change(request, obj, message)
        self.log_admin_action(request, obj, "change", str(message))

    def log_deletion(self, request, obj, object_repr):
        """Log object deletion."""
        super().log_deletion(request, obj, object_repr)
        self.log_admin_action(request, obj, "delete", f"Deleted: {object_repr}")


# ---------------------------------------------------------------------------
# Consolidated mixin groups – keeps MRO shallow and easier to maintain
# when Django's ModelAdmin evolves.
# ---------------------------------------------------------------------------


class DynamoDBCoreMixin(
    DynamoDBPaginationMixin,
    DynamoDBDateHierarchyMixin,
    DynamoDBFilterMixin,
    GSIMonitoringMixin,
):
    """Core DynamoDB query, pagination, filtering and GSI behaviour."""


class DynamoDBActionsMixin(
    DynamoDBActionMixin,
    DynamoDBAutocompleteMixin,
):
    """Admin actions and autocomplete."""


class DynamoDBSecurityMixin(
    SecureDynamoDBAdmin,
    DynamoDBAdminLoggingMixin,
):
    """Permissions, audit, and rate-limiting."""


class DynamoDBAdmin(
    DynamoDBCoreMixin,
    DynamoDBActionsMixin,
    DynamoDBSecurityMixin,
    ModelAdmin,
):
    """Enhanced admin class for DynamoDB models with full Django Admin compatibility."""

    # Use custom components
    form = DynamoDBAdminForm

    # Default configuration optimized for DynamoDB
    list_per_page = 25  # Reasonable for DynamoDB scan operations
    list_max_show_all = 100
    preserve_filters = True

    # date_hierarchy support - set to a DateTimeField name to enable
    date_hierarchy = None

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

        # Apply date_hierarchy filtering
        if self.date_hierarchy:
            queryset = self.get_date_hierarchy_queryset(
                queryset, self.date_hierarchy, request
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


class DynamoDBAdminSite(admin.AdminSite):
    """Custom admin site for DynamoDB with enhanced features."""

    site_header = "DynamoDB Django Admin"
    site_title = "DynamoDB Admin"
    index_title = "DynamoDB Administration"

    def index(self, request, extra_context=None):
        """Enhanced admin index with DynamoDB-specific information."""
        extra_context = extra_context or {}

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


# Pre-built admin site instance for convenience
dynamodb_admin_site = DynamoDBAdminSite(name="dynamodb_admin")

