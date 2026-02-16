"""
DynamoDB-optimized admin filters.

These filters are designed to work efficiently with DynamoDB's query patterns
and limitations.
"""

import logging
from datetime import timedelta
from decimal import Decimal

from django.contrib.admin import SimpleListFilter
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)


class DynamoDBListFilter(SimpleListFilter):
    """Base filter class optimized for DynamoDB operations."""

    def queryset(self, request, queryset):
        """Apply filter with DynamoDB optimization logging."""
        if self.value():
            logger.info(
                f"Applying DynamoDB filter {self.parameter_name}={self.value()}"
            )
        return super().queryset(request, queryset)


class DynamoDBBooleanFilter(DynamoDBListFilter):
    """Boolean filter optimized for DynamoDB."""

    def lookups(self, request, model_admin):
        """Return filter options."""
        return (
            ("1", _("Yes")),
            ("0", _("No")),
        )

    def queryset(self, request, queryset):
        """Apply boolean filter."""
        if self.value() == "1":
            return queryset.filter(**{self.parameter_name: True})
        elif self.value() == "0":
            return queryset.filter(**{self.parameter_name: False})
        return queryset


class DynamoDBDateRangeFilter(DynamoDBListFilter):
    """Date range filter optimized for DynamoDB."""

    def lookups(self, request, model_admin):
        """Return date range options."""
        return (
            ("today", _("Today")),
            ("yesterday", _("Yesterday")),
            ("this_week", _("This week")),
            ("this_month", _("This month")),
            ("last_30_days", _("Last 30 days")),
            ("this_year", _("This year")),
        )

    def queryset(self, request, queryset):
        """Apply date range filter."""
        if not self.value():
            return queryset

        now = timezone.now()

        if self.value() == "today":
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            return queryset.filter(**{f"{self.parameter_name}__gte": start_date})

        elif self.value() == "yesterday":
            yesterday = now - timedelta(days=1)
            start_date = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = yesterday.replace(
                hour=23, minute=59, second=59, microsecond=999999
            )
            return queryset.filter(
                **{
                    f"{self.parameter_name}__gte": start_date,
                    f"{self.parameter_name}__lte": end_date,
                }
            )

        elif self.value() == "this_week":
            start_of_week = now - timedelta(days=now.weekday())
            start_date = start_of_week.replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            return queryset.filter(**{f"{self.parameter_name}__gte": start_date})

        elif self.value() == "this_month":
            start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            return queryset.filter(**{f"{self.parameter_name}__gte": start_date})

        elif self.value() == "last_30_days":
            start_date = now - timedelta(days=30)
            return queryset.filter(**{f"{self.parameter_name}__gte": start_date})

        elif self.value() == "this_year":
            start_date = now.replace(
                month=1, day=1, hour=0, minute=0, second=0, microsecond=0
            )
            return queryset.filter(**{f"{self.parameter_name}__gte": start_date})

        return queryset


class DynamoDBNumericRangeFilter(DynamoDBListFilter):
    """Numeric range filter optimized for DynamoDB."""

    def __init__(self, request, params, model, model_admin):
        self.ranges = getattr(model_admin, f"{self.parameter_name}_ranges", [])
        super().__init__(request, params, model, model_admin)

    def lookups(self, request, model_admin):
        """Return numeric range options."""
        if not self.ranges:
            # Default ranges - can be overridden in admin class
            return (
                ("0-10", _("0-10")),
                ("11-50", _("11-50")),
                ("51-100", _("51-100")),
                ("100+", _("100+")),
            )

        return [
            (f'{r["min"]}-{r["max"]}', f'{r["min"]}-{r["max"]}') for r in self.ranges
        ]

    def queryset(self, request, queryset):
        """Apply numeric range filter."""
        if not self.value():
            return queryset

        try:
            if self.value() == "100+":
                return queryset.filter(**{f"{self.parameter_name}__gte": 100})

            # Parse range like "0-10"
            min_val, max_val = self.value().split("-")
            min_val = Decimal(min_val)
            max_val = Decimal(max_val)

            return queryset.filter(
                **{
                    f"{self.parameter_name}__gte": min_val,
                    f"{self.parameter_name}__lte": max_val,
                }
            )

        except (ValueError, TypeError) as e:
            logger.error(f"Error parsing numeric range {self.value()}: {e}")
            return queryset


class DynamoDBTextSearchFilter(DynamoDBListFilter):
    """Text search filter with DynamoDB contains operation."""

    def lookups(self, request, model_admin):
        """Return text search options based on common patterns."""
        # These could be dynamically generated based on actual data
        return (
            ("starts_a", _("Starts with A-G")),
            ("starts_h", _("Starts with H-N")),
            ("starts_o", _("Starts with O-Z")),
            ("contains_test", _('Contains "test"')),
            ("contains_prod", _('Contains "prod"')),
        )

    def queryset(self, request, queryset):
        """Apply text search filter."""
        if not self.value():
            return queryset

        if self.value() == "starts_a":
            # DynamoDB efficient range query
            return queryset.filter(
                **{
                    f"{self.parameter_name}__gte": "A",
                    f"{self.parameter_name}__lt": "H",
                }
            )
        elif self.value() == "starts_h":
            return queryset.filter(
                **{
                    f"{self.parameter_name}__gte": "H",
                    f"{self.parameter_name}__lt": "O",
                }
            )
        elif self.value() == "starts_o":
            return queryset.filter(**{f"{self.parameter_name}__gte": "O"})
        elif self.value() == "contains_test":
            return queryset.filter(**{f"{self.parameter_name}__contains": "test"})
        elif self.value() == "contains_prod":
            return queryset.filter(**{f"{self.parameter_name}__contains": "prod"})

        return queryset


class DynamoDBStatusFilter(DynamoDBListFilter):
    """Status filter for common status patterns."""

    def lookups(self, request, model_admin):
        """Return status options."""
        return (
            ("active", _("Active")),
            ("inactive", _("Inactive")),
            ("pending", _("Pending")),
            ("archived", _("Archived")),
        )

    def queryset(self, request, queryset):
        """Apply status filter."""
        if self.value():
            return queryset.filter(**{self.parameter_name: self.value()})
        return queryset


class DynamoDBChoiceFilter(DynamoDBListFilter):
    """Generic choice filter for fields with predefined choices."""

    def __init__(self, request, params, model, model_admin):
        self.field_choices = []

        # Get choices from model field
        for field in model._meta.fields:
            if field.name == self.parameter_name and hasattr(field, "choices"):
                self.field_choices = field.choices
                break

        super().__init__(request, params, model, model_admin)

    def lookups(self, request, model_admin):
        """Return field choices."""
        return self.field_choices

    def queryset(self, request, queryset):
        """Apply choice filter."""
        if self.value():
            return queryset.filter(**{self.parameter_name: self.value()})
        return queryset


# Specific filter implementations
class IsActiveFilter(DynamoDBBooleanFilter):
    title = _("active status")
    parameter_name = "is_active"


class CreatedDateFilter(DynamoDBDateRangeFilter):
    title = _("created date")
    parameter_name = "created_at"


class UpdatedDateFilter(DynamoDBDateRangeFilter):
    title = _("updated date")
    parameter_name = "updated_at"


class PublishedDateFilter(DynamoDBDateRangeFilter):
    title = _("published date")
    parameter_name = "pub_date"


class VoteCountFilter(DynamoDBNumericRangeFilter):
    title = _("vote count")
    parameter_name = "votes"


class NameSearchFilter(DynamoDBTextSearchFilter):
    title = _("name search")
    parameter_name = "name"


class TitleSearchFilter(DynamoDBTextSearchFilter):
    title = _("title search")
    parameter_name = "title"


class StatusFilter(DynamoDBStatusFilter):
    title = _("status")
    parameter_name = "status"


# Filter mixins for common patterns
class DynamoDBFilterMixin:
    """Mixin to add DynamoDB-optimized filters to admin classes."""

    def get_list_filter(self, request):
        """Return list filters optimized for DynamoDB."""
        filters = list(self.list_filter) if self.list_filter else []

        # Auto-add filters for common fields
        model_fields = [f.name for f in self.model._meta.fields]

        if "is_active" in model_fields and "is_active" not in [
            getattr(f, "parameter_name", None) for f in filters
        ]:
            filters.append(IsActiveFilter)

        if "created_at" in model_fields and "created_at" not in [
            getattr(f, "parameter_name", None) for f in filters
        ]:
            filters.append(CreatedDateFilter)

        if "status" in model_fields and "status" not in [
            getattr(f, "parameter_name", None) for f in filters
        ]:
            filters.append(StatusFilter)

        return filters

    def get_queryset(self, request):
        """Get queryset with filter optimization logging."""
        queryset = super().get_queryset(request)

        # Log filter usage for optimization
        applied_filters = []
        for key, value in request.GET.items():
            if key not in ["p", "q", "o"]:  # Exclude pagination, search, and ordering
                applied_filters.append(f"{key}={value}")

        if applied_filters:
            logger.info(f"DynamoDB admin filters applied: {', '.join(applied_filters)}")

        return queryset


class DynamoDBAutoFilterAdmin(DynamoDBFilterMixin):
    """Admin class that automatically adds DynamoDB-optimized filters."""

