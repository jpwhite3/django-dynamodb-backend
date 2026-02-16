"""
Custom managers and QuerySets for DynamoDB models.
"""

import logging
import uuid
from datetime import date, datetime, time
from decimal import Decimal

from boto3.dynamodb.conditions import And, Attr, Key, Not, Or
from django.core.exceptions import MultipleObjectsReturned, ObjectDoesNotExist
from django.db import models
from django.db.models import Q
from django.db.models.query import QuerySet
from pynamodb.exceptions import DoesNotExist, QueryError

logger = logging.getLogger(__name__)


class DynamoDBQuerySet(QuerySet):
    """
    QuerySet that translates Django ORM operations to DynamoDB operations.
    """

    def __init__(self, model=None, query=None, using=None, hints=None):
        super().__init__(model, query, using, hints)
        self._dynamodb_filters = []
        self._dynamodb_scan_filters = []
        self._dynamodb_query_filters = []  # For Query operations with key conditions
        self._limit_count = None
        self._offset_count = 0
        self._order_by_fields = []
        self._scan_index_forward = True
        self._last_evaluated_key = None
        self._use_query_operation = False  # Flag to determine Query vs Scan

    def _clone(self):
        """Create a copy of this QuerySet."""
        clone = super()._clone()
        clone._dynamodb_filters = self._dynamodb_filters[:]
        clone._dynamodb_scan_filters = self._dynamodb_scan_filters[:]
        clone._dynamodb_query_filters = self._dynamodb_query_filters[:]
        clone._limit_count = self._limit_count
        clone._offset_count = self._offset_count
        clone._order_by_fields = self._order_by_fields[:]
        clone._scan_index_forward = self._scan_index_forward
        clone._last_evaluated_key = self._last_evaluated_key
        clone._use_query_operation = self._use_query_operation
        return clone

    def filter(self, *args, **kwargs):
        """Add filters to the queryset.

        Accepts both Q objects as positional arguments and keyword arguments.
        """
        clone = self._clone()

        # Handle Q objects passed as positional arguments
        for arg in args:
            if isinstance(arg, Q):
                # Extract filters from Q object and process them
                clone = clone._process_q_object(arg)

        # Handle keyword argument filters
        for lookup, value in kwargs.items():
            field_name, *lookup_parts = lookup.split("__")
            lookup_type = lookup_parts[0] if lookup_parts else "exact"

            # Convert Django lookup to DynamoDB filter
            dynamodb_filter = self._convert_lookup(field_name, lookup_type, value)
            if dynamodb_filter:
                # Determine if this filter can be used for Query operation
                if clone._can_use_query_filter(field_name, lookup_type):
                    clone._dynamodb_query_filters.append(
                        (field_name, lookup_type, value)
                    )
                    clone._use_query_operation = True
                else:
                    clone._dynamodb_scan_filters.append(dynamodb_filter)

        return clone

    def _process_q_object(self, q_obj):
        """Process a Q object and add its filters to the queryset."""
        clone = self._clone()

        # Q objects have children which are tuples of (key, value) or nested Q objects
        for child in q_obj.children:
            if isinstance(child, Q):
                # Recursively process nested Q objects
                clone = clone._process_q_object(child)
            elif isinstance(child, tuple) and len(child) == 2:
                # It's a (lookup, value) tuple
                lookup, value = child
                field_name, *lookup_parts = lookup.split("__")
                lookup_type = lookup_parts[0] if lookup_parts else "exact"

                dynamodb_filter = self._convert_lookup(field_name, lookup_type, value)
                if dynamodb_filter:
                    if clone._can_use_query_filter(field_name, lookup_type):
                        clone._dynamodb_query_filters.append(
                            (field_name, lookup_type, value)
                        )
                        clone._use_query_operation = True
                    else:
                        clone._dynamodb_scan_filters.append(dynamodb_filter)

        return clone

    def exclude(self, **kwargs):
        """Exclude objects matching the given filters."""
        clone = self._clone()

        for lookup, value in kwargs.items():
            field_name, *lookup_parts = lookup.split("__")
            lookup_type = lookup_parts[0] if lookup_parts else "exact"

            # Convert to exclusion filter
            dynamodb_filter = self._convert_lookup(
                field_name, lookup_type, value, exclude=True
            )
            if dynamodb_filter:
                clone._dynamodb_scan_filters.append(dynamodb_filter)

        return clone

    def get(self, **kwargs):
        """Get a single object matching the criteria."""
        clone = self.filter(**kwargs)
        results = list(clone[:2])  # Get at most 2 to check for multiple

        if not results:
            raise ObjectDoesNotExist(
                f"{self.model.__name__} matching query does not exist."
            )
        if len(results) > 1:
            raise MultipleObjectsReturned(
                f"get() returned more than one {self.model.__name__}"
            )

        return results[0]

    def first(self):
        """Return the first object from the queryset."""
        results = list(self[:1])
        return results[0] if results else None

    def last(self):
        """Return the last object from the queryset."""
        # DynamoDB doesn't have a direct "last" operation
        # We'd need to implement ordering for this to work properly
        results = list(self)
        return results[-1] if results else None

    def count(self):
        """Return the count of objects in the queryset."""
        # For DynamoDB, we need to perform a count operation
        try:
            pynamodb_model = self.model._get_pynamodb_model()

            # If no filters, use table item count
            if not self._dynamodb_scan_filters and not self._dynamodb_query_filters:
                table = pynamodb_model.describe_table()
                return table["ItemCount"]

            # Otherwise, perform appropriate count operation
            count = 0
            if self._use_query_operation and self._dynamodb_query_filters:
                for _ in self._execute_query(count_only=True):
                    count += 1
            else:
                for _ in self._execute_scan(count_only=True):
                    count += 1
            return count

        except Exception as e:
            logger.error(f"Error counting DynamoDB objects: {e}")
            return 0

    def exists(self):
        """Return True if the queryset contains any results."""
        return self.first() is not None

    def order_by(self, *field_names):
        """Order the queryset (limited support in DynamoDB)."""
        clone = self._clone()

        if not field_names:
            # Clear ordering
            clone._order_by_fields = []
            clone._scan_index_forward = True
            return clone

        clone._order_by_fields = list(field_names)

        # Handle ordering direction
        for field_name in field_names:
            if field_name.startswith("-"):
                clone._scan_index_forward = False
                field_name = field_name[1:]
            else:
                clone._scan_index_forward = True

            # Check if ordering is possible with current query
            if not clone._can_order_by_field(field_name):
                logger.warning(
                    f"DynamoDB cannot order by {field_name} without a GSI. Consider adding a Global Secondary Index or using scan."
                )

        return clone

    def distinct(self, *field_names):
        """Return distinct values (limited support in DynamoDB)."""
        logger.warning("DynamoDB doesn't support SQL-like DISTINCT operations.")
        return self._clone()

    def only(self, *fields):
        """Defer all fields except the specified ones."""
        return self.values(*fields)

    def defer(self, *fields):
        """Defer loading of specific fields."""
        clone = self._clone()
        clone._deferred_fields = set(fields)
        return clone

    def select_related(self, *fields):
        """DynamoDB doesn't support joins, log warning."""
        logger.warning(
            "DynamoDB doesn't support SQL joins. select_related has no effect."
        )
        return self._clone()

    def prefetch_related(self, *lookups):
        """DynamoDB doesn't support joins, log warning."""
        logger.warning(
            "DynamoDB doesn't support SQL joins. prefetch_related has no effect."
        )
        return self._clone()

    def aggregate(self, **kwargs):
        """Limited aggregation support in DynamoDB."""
        logger.warning(
            "DynamoDB has limited aggregation support. Use scan operations for complex aggregations."
        )
        result = {}

        # Only support Count for now
        for alias, aggregation in kwargs.items():
            if hasattr(aggregation, "source_expressions"):
                # Django 2.0+ aggregation
                agg_func = aggregation.__class__.__name__
                if agg_func == "Count":
                    result[alias] = self.count()
                else:
                    logger.warning(f"Aggregation {agg_func} not supported in DynamoDB")
                    result[alias] = None
            else:
                logger.warning(f"Unknown aggregation format: {aggregation}")
                result[alias] = None

        return result

    def annotate(self, **kwargs):
        """Limited annotation support in DynamoDB."""
        logger.warning("DynamoDB has limited annotation support.")
        return self._clone()

    def extra(
        self,
        select=None,
        where=None,
        params=None,
        tables=None,
        order_by=None,
        select_params=None,
    ):
        """Extra is not supported in DynamoDB."""
        logger.error(
            "DynamoDB doesn't support raw SQL. Use native DynamoDB operations."
        )
        raise NotImplementedError("extra() is not supported with DynamoDB backend")

    def raw(self, raw_query, params=None):
        """Raw queries not supported in DynamoDB."""
        logger.error("DynamoDB doesn't support raw SQL queries.")
        raise NotImplementedError("raw() is not supported with DynamoDB backend")

    def update(self, **kwargs):
        """Update all objects in the queryset."""
        # This is a complex operation in DynamoDB as it requires individual updates
        count = 0
        try:
            for obj in self:
                for field, value in kwargs.items():
                    setattr(obj, field, value)
                obj.save()
                count += 1
            return count
        except Exception as e:
            logger.error(f"Error in bulk update: {e}")
            return count

    def delete(self):
        """Delete all objects in the queryset."""
        count = 0
        try:
            pynamodb_model = self.model._get_pynamodb_model()

            # For efficient deletion, collect keys first
            items_to_delete = []
            for obj in self:
                # Get the primary key value(s)
                pk_value = getattr(obj, self.model._meta.pk.name)
                items_to_delete.append(pk_value)
                count += 1

                # Process in batches
                if len(items_to_delete) >= 25:  # DynamoDB batch limit
                    self._batch_delete_items(pynamodb_model, items_to_delete)
                    items_to_delete = []

            # Process remaining items
            if items_to_delete:
                self._batch_delete_items(pynamodb_model, items_to_delete)

            return count, {self.model._meta.label: count}

        except Exception as e:
            logger.error(f"Error in bulk delete: {e}")
            return count, {self.model._meta.label: count}

    def _batch_delete_items(self, pynamodb_model, pk_values):
        """Helper method to delete items in batch."""
        try:
            with pynamodb_model.batch_write() as batch:
                for pk_value in pk_values:
                    # Create a dummy instance with just the key for deletion
                    item = pynamodb_model()
                    setattr(item, self.model._meta.pk.name, pk_value)
                    batch.delete(item)
        except Exception as e:
            logger.error(f"Error in batch delete: {e}")
            # Fallback to individual deletes
            for pk_value in pk_values:
                try:
                    item = pynamodb_model.get(pk_value)
                    item.delete()
                except Exception as delete_error:
                    logger.error(f"Error deleting item {pk_value}: {delete_error}")

    def values(self, *fields):
        """Return dictionaries instead of model instances."""
        clone = self._clone()
        clone._fields = fields
        return clone

    def values_list(self, *fields, flat=False):
        """Return tuples of values instead of model instances."""
        clone = self._clone()
        clone._fields = fields
        clone._flat = flat
        return clone

    def iterator(self):
        """Return an iterator over the results."""
        if self._use_query_operation and self._dynamodb_query_filters:
            return iter(self._execute_query())
        else:
            return iter(self._execute_scan())

    def __iter__(self):
        """Iterate over the queryset results."""
        return self.iterator()

    def __getitem__(self, k):
        """Support slicing and indexing."""
        if not isinstance(k, (int, slice)):
            raise TypeError("QuerySet indices must be integers or slices.")

        if isinstance(k, slice):
            clone = self._clone()
            if k.start:
                clone._offset_count = k.start
            if k.stop:
                clone._limit_count = k.stop - (k.start or 0)
            return clone
        else:
            # Single index access
            if k < 0:
                # Negative indexing requires getting all results
                results = list(self)
                return results[k]
            else:
                # Positive indexing
                results = list(self[k : k + 1])
                if not results:
                    raise IndexError("list index out of range")
                return results[0]

    def _convert_lookup(self, field_name, lookup_type, value, exclude=False):
        """Convert Django lookup to DynamoDB filter expression."""
        # Preprocess value based on field type if we have model info
        processed_value = self._preprocess_value(field_name, value)

        # Map Django lookups to DynamoDB conditions
        try:
            if lookup_type == "exact":
                condition = Attr(field_name).eq(processed_value)
            elif lookup_type == "iexact":
                # Case-insensitive exact match (limited support in DynamoDB)
                if isinstance(processed_value, str):
                    condition = Attr(field_name).eq(processed_value.lower())
                    logger.warning(
                        f"Case-insensitive lookup on {field_name} may not work as expected"
                    )
                else:
                    condition = Attr(field_name).eq(processed_value)
            elif lookup_type == "gt":
                condition = Attr(field_name).gt(processed_value)
            elif lookup_type == "gte":
                condition = Attr(field_name).gte(processed_value)
            elif lookup_type == "lt":
                condition = Attr(field_name).lt(processed_value)
            elif lookup_type == "lte":
                condition = Attr(field_name).lte(processed_value)
            elif lookup_type == "contains":
                condition = Attr(field_name).contains(str(processed_value))
            elif lookup_type == "icontains":
                # Case-insensitive contains (limited support)
                condition = Attr(field_name).contains(str(processed_value).lower())
                logger.warning(
                    f"Case-insensitive contains on {field_name} may not work as expected"
                )
            elif lookup_type == "startswith":
                condition = Attr(field_name).begins_with(str(processed_value))
            elif lookup_type == "istartswith":
                condition = Attr(field_name).begins_with(str(processed_value).lower())
                logger.warning(
                    f"Case-insensitive startswith on {field_name} may not work as expected"
                )
            elif lookup_type == "endswith":
                # DynamoDB doesn't have native endswith, need custom implementation
                logger.warning(
                    f"endswith lookup on {field_name} requires full table scan"
                )
                condition = Attr(field_name).contains(str(processed_value))
            elif lookup_type == "iendswith":
                logger.warning(
                    f"Case-insensitive endswith on {field_name} requires full table scan"
                )
                condition = Attr(field_name).contains(str(processed_value).lower())
            elif lookup_type == "in":
                if isinstance(processed_value, (list, tuple, set)):
                    condition = Attr(field_name).is_in(list(processed_value))
                else:
                    condition = Attr(field_name).eq(processed_value)
            elif lookup_type == "range":
                if (
                    isinstance(processed_value, (list, tuple))
                    and len(processed_value) == 2
                ):
                    condition = Attr(field_name).between(
                        processed_value[0], processed_value[1]
                    )
                else:
                    logger.error(f"Range lookup requires a list/tuple of 2 values")
                    return None
            elif lookup_type == "isnull":
                if processed_value:
                    condition = Attr(field_name).not_exists()
                else:
                    condition = Attr(field_name).exists()
            elif lookup_type == "regex":
                logger.warning(
                    f"Regex lookup not supported by DynamoDB for {field_name}"
                )
                return None
            elif lookup_type == "iregex":
                logger.warning(
                    f"Case-insensitive regex lookup not supported by DynamoDB for {field_name}"
                )
                return None
            elif lookup_type in ["year", "month", "day", "hour", "minute", "second"]:
                # Date/time component lookups require special handling
                condition = self._handle_datetime_component_lookup(
                    field_name, lookup_type, processed_value
                )
                if condition is None:
                    return None
            else:
                logger.warning(f"Unsupported lookup type: {lookup_type}")
                return None

            # Handle exclusion
            if exclude:
                condition = Not(condition)

            return condition

        except Exception as e:
            logger.error(f"Error converting lookup {field_name}__{lookup_type}: {e}")
            return None

    def _execute_scan(self, count_only=False):
        """Execute the scan operation on DynamoDB."""
        try:
            pynamodb_model = self.model._get_pynamodb_model()

            # Build scan parameters
            scan_kwargs = {}

            # Add filters
            if self._dynamodb_scan_filters:
                filter_condition = self._dynamodb_scan_filters[0]
                for additional_filter in self._dynamodb_scan_filters[1:]:
                    filter_condition = filter_condition & additional_filter
                scan_kwargs["filter_condition"] = filter_condition

            # Add pagination
            if self._last_evaluated_key:
                scan_kwargs["last_evaluated_key"] = self._last_evaluated_key

            # Add limit (adjust for offset if needed)
            actual_limit = self._limit_count
            if self._offset_count and self._limit_count:
                actual_limit = self._limit_count + self._offset_count
            elif actual_limit:
                scan_kwargs["limit"] = actual_limit

            # Perform scan
            if count_only:
                scan_kwargs["select"] = "COUNT"

            results = []
            last_evaluated_key = None
            items_processed = 0
            total_scanned = 0

            while True:
                if last_evaluated_key:
                    scan_kwargs["last_evaluated_key"] = last_evaluated_key

                response = pynamodb_model.scan(**scan_kwargs)

                # Store pagination info
                self._query_last_evaluated_key = getattr(
                    response, "last_evaluated_key", None
                )
                self._query_scanned_count = getattr(response, "scanned_count", 0)
                self._query_consumed_capacity = getattr(
                    response, "consumed_capacity", None
                )

                total_scanned += self._query_scanned_count

                if count_only:
                    for item in response:
                        yield item
                else:
                    for item in response:
                        if items_processed < self._offset_count:
                            items_processed += 1
                            continue

                        # Convert PynamoDB model to Django model instance
                        django_instance = self._convert_pynamodb_to_django(item)
                        results.append(django_instance)
                        yield django_instance
                        items_processed += 1

                        if self._limit_count and len(results) >= self._limit_count:
                            self._query_has_more_pages = bool(
                                self._query_last_evaluated_key
                            )
                            return

                # Check if there are more results
                last_evaluated_key = getattr(response, "last_evaluated_key", None)
                if not last_evaluated_key:
                    break

            self._query_has_more_pages = False

        except Exception as e:
            logger.error(f"Error executing DynamoDB scan: {e}")
            return []

    def _execute_query(self, count_only=False):
        """Execute optimized Query operation on DynamoDB."""
        try:
            pynamodb_model = self.model._get_pynamodb_model()

            if not self._dynamodb_query_filters:
                logger.warning(
                    "Query operation requested but no query filters available"
                )
                return self._execute_scan(count_only)

            # Build query parameters
            query_kwargs = {}
            key_condition = None

            # Build key condition from query filters
            for field_name, lookup_type, value in self._dynamodb_query_filters:
                if lookup_type == "exact":
                    condition = Key(field_name).eq(
                        self._preprocess_value(field_name, value)
                    )
                    if key_condition is None:
                        key_condition = condition
                    else:
                        key_condition = key_condition & condition
                elif lookup_type in ["gt", "gte", "lt", "lte", "between"]:
                    # These can only be used for sort key
                    if lookup_type == "gt":
                        condition = Key(field_name).gt(
                            self._preprocess_value(field_name, value)
                        )
                    elif lookup_type == "gte":
                        condition = Key(field_name).gte(
                            self._preprocess_value(field_name, value)
                        )
                    elif lookup_type == "lt":
                        condition = Key(field_name).lt(
                            self._preprocess_value(field_name, value)
                        )
                    elif lookup_type == "lte":
                        condition = Key(field_name).lte(
                            self._preprocess_value(field_name, value)
                        )
                    elif lookup_type == "between":
                        if isinstance(value, (list, tuple)) and len(value) == 2:
                            condition = Key(field_name).between(
                                self._preprocess_value(field_name, value[0]),
                                self._preprocess_value(field_name, value[1]),
                            )
                        else:
                            continue

                    if key_condition is None:
                        key_condition = condition
                    else:
                        key_condition = key_condition & condition

            if key_condition is None:
                logger.warning("No valid key condition for Query operation")
                return self._execute_scan(count_only)

            query_kwargs["key_condition"] = key_condition

            # Add scan filters as filter expression
            if self._dynamodb_scan_filters:
                filter_condition = self._dynamodb_scan_filters[0]
                for additional_filter in self._dynamodb_scan_filters[1:]:
                    filter_condition = filter_condition & additional_filter
                query_kwargs["filter_condition"] = filter_condition

            # Add ordering
            if self._order_by_fields:
                query_kwargs["scan_index_forward"] = self._scan_index_forward

            # Add pagination
            if self._last_evaluated_key:
                query_kwargs["last_evaluated_key"] = self._last_evaluated_key

            # Add limit
            if self._limit_count:
                query_kwargs["limit"] = self._limit_count + (self._offset_count or 0)

            # Perform query
            if count_only:
                query_kwargs["select"] = "COUNT"

            results = []
            items_processed = 0

            response = pynamodb_model.query(**query_kwargs)

            # Store pagination info
            self._query_last_evaluated_key = getattr(
                response, "last_evaluated_key", None
            )
            self._query_scanned_count = getattr(response, "scanned_count", 0)
            self._query_consumed_capacity = getattr(response, "consumed_capacity", None)
            self._query_has_more_pages = bool(self._query_last_evaluated_key)

            if count_only:
                for item in response:
                    yield item
            else:
                for item in response:
                    if items_processed < self._offset_count:
                        items_processed += 1
                        continue

                    # Convert PynamoDB model to Django model instance
                    django_instance = self._convert_pynamodb_to_django(item)
                    results.append(django_instance)
                    yield django_instance
                    items_processed += 1

                    if self._limit_count and len(results) >= self._limit_count:
                        return

        except Exception as e:
            logger.error(f"Error executing DynamoDB query: {e}")
            # Fallback to scan
            return self._execute_scan(count_only)

    def _convert_pynamodb_to_django(self, pynamodb_instance):
        """Convert a PynamoDB model instance to Django model instance."""
        django_data = {}

        try:
            # Extract field values from PynamoDB instance
            for field in self.model._meta.get_fields():
                if hasattr(pynamodb_instance, field.name):
                    raw_value = getattr(pynamodb_instance, field.name)
                    # Convert DynamoDB value to Django-compatible value
                    converted_value = self._convert_pynamodb_value_to_django(
                        field, raw_value
                    )
                    django_data[field.name] = converted_value
                elif hasattr(pynamodb_instance, field.column):
                    raw_value = getattr(pynamodb_instance, field.column)
                    converted_value = self._convert_pynamodb_value_to_django(
                        field, raw_value
                    )
                    django_data[field.name] = converted_value

            # Create Django model instance
            django_instance = self.model(**django_data)

            # Mark as not from database initially
            django_instance._state.adding = False
            django_instance._state.db = self._db

            return django_instance

        except Exception as e:
            logger.error(f"Error converting PynamoDB instance to Django: {e}")
            # Return a basic instance with available data
            return self.model(**{k: v for k, v in django_data.items() if v is not None})

    def _convert_pynamodb_value_to_django(self, field, value):
        """Convert a PynamoDB field value to Django-compatible format."""
        import uuid
        from datetime import date, datetime, time
        from decimal import Decimal

        from django.db import models

        if value is None:
            return None

        try:
            # Handle different Django field types
            if isinstance(
                field,
                (
                    models.IntegerField,
                    models.BigIntegerField,
                    models.PositiveIntegerField,
                    models.SmallIntegerField,
                ),
            ):
                if isinstance(value, Decimal):
                    return int(value)
                return int(value)

            elif isinstance(field, (models.FloatField)):
                if isinstance(value, Decimal):
                    return float(value)
                return float(value)

            elif isinstance(field, models.DecimalField):
                if isinstance(value, (int, float, str)):
                    return Decimal(str(value))
                return value

            elif isinstance(field, models.BooleanField):
                return bool(value)

            elif isinstance(field, models.DateTimeField):
                if isinstance(value, str):
                    try:
                        return datetime.fromisoformat(value.replace("Z", "+00:00"))
                    except ValueError:
                        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
                return value

            elif isinstance(field, models.DateField):
                if isinstance(value, str):
                    try:
                        return date.fromisoformat(value)
                    except ValueError:
                        return datetime.strptime(value, "%Y-%m-%d").date()
                return value

            elif isinstance(field, models.TimeField):
                if isinstance(value, str):
                    try:
                        return time.fromisoformat(value)
                    except ValueError:
                        return datetime.strptime(value, "%H:%M:%S").time()
                return value

            elif isinstance(field, models.UUIDField):
                if isinstance(value, str):
                    return uuid.UUID(value)
                return value

            elif isinstance(field, models.JSONField):
                return value  # DynamoDB handles JSON natively

            elif isinstance(
                field,
                (
                    models.CharField,
                    models.TextField,
                    models.EmailField,
                    models.URLField,
                    models.SlugField,
                ),
            ):
                return str(value) if value is not None else None

            else:
                # Default conversion to string for unknown field types
                return str(value) if value is not None else None

        except (ValueError, TypeError) as e:
            logger.warning(f"Error converting field {field.name} value {value}: {e}")
            return value  # Return original value if conversion fails

    def _preprocess_value(self, field_name, value):
        """Preprocess values for DynamoDB compatibility."""
        if value is None:
            return value

        # Convert Python types to DynamoDB-compatible types
        if isinstance(value, (int, float)):
            return Decimal(str(value))
        elif isinstance(value, bool):
            return value
        elif isinstance(value, (datetime, date, time)):
            return value.isoformat()
        elif isinstance(value, uuid.UUID):
            return str(value)
        elif isinstance(value, (list, tuple, set)):
            return [self._preprocess_value(field_name, item) for item in value]
        elif isinstance(value, dict):
            return {k: self._preprocess_value(field_name, v) for k, v in value.items()}
        else:
            return str(value)

    def _handle_datetime_component_lookup(self, field_name, component, value):
        """Handle datetime component lookups (year, month, day, etc.)."""
        try:
            # For DynamoDB, we need to convert this to a range query
            # This is an approximation and may not be 100% accurate
            if component == "year":
                start_date = datetime(int(value), 1, 1)
                end_date = datetime(int(value), 12, 31, 23, 59, 59)
            elif component == "month":
                # Need to know the year for this to work properly
                logger.warning(f"Month lookup on {field_name} requires year context")
                return None
            elif component == "day":
                logger.warning(
                    f"Day lookup on {field_name} requires month/year context"
                )
                return None
            else:
                logger.warning(f"Time component lookup {component} not fully supported")
                return None

            return Attr(field_name).between(
                start_date.isoformat(), end_date.isoformat()
            )

        except (ValueError, TypeError) as e:
            logger.error(f"Error handling datetime component lookup: {e}")
            return None

    def _can_use_query_filter(self, field_name, lookup_type):
        """Determine if a filter can be used in a DynamoDB Query operation."""
        try:
            # Get model metadata
            if not hasattr(self.model, "_meta"):
                return False

            # Check if field is a primary key or GSI key
            pk_field = self.model._meta.pk
            if pk_field and field_name == pk_field.name:
                # Only exact lookups work for partition key in Query
                return lookup_type in ["exact"]

            # For sort keys, range lookups are allowed
            # This would need model introspection to determine sort keys
            # For now, be conservative and only allow exact matches
            return False

        except Exception as e:
            logger.error(f"Error determining query filter capability: {e}")
            return False

    def _can_order_by_field(self, field_name):
        """Determine if ordering by a field is supported."""
        try:
            # DynamoDB can only order by sort key in Query operations
            # or requires client-side sorting for Scan operations
            if self._use_query_operation:
                # Check if field is the sort key (this would need model introspection)
                # For now, assume ordering is limited
                return False
            else:
                # Scan operations require client-side sorting (limited performance)
                logger.info(
                    f"Ordering by {field_name} will require client-side sorting"
                )
                return True

        except Exception as e:
            logger.error(f"Error determining ordering capability: {e}")
            return False

    def using_pagination(self, last_evaluated_key=None):
        """Enable pagination with DynamoDB's LastEvaluatedKey."""
        clone = self._clone()
        clone._last_evaluated_key = last_evaluated_key
        return clone

    def get_pagination_info(self):
        """Get pagination information from the last query."""
        return {
            "last_evaluated_key": getattr(self, "_query_last_evaluated_key", None),
            "has_more_pages": getattr(self, "_query_has_more_pages", False),
            "scanned_count": getattr(self, "_query_scanned_count", 0),
            "consumed_capacity": getattr(self, "_query_consumed_capacity", None),
        }


class DynamoDBManager(models.Manager):
    """
    Manager for DynamoDB models.
    """

    def get_queryset(self):
        """Return a DynamoDBQuerySet."""
        return DynamoDBQuerySet(self.model, using=self._db)

    def create(self, **kwargs):
        """Create and save a new model instance."""
        obj = self.model(**kwargs)
        obj.save(using=self._db)
        return obj

    def get_or_create(self, defaults=None, **kwargs):
        """Get an existing object or create a new one."""
        try:
            obj = self.get(**kwargs)
            return obj, False
        except ObjectDoesNotExist:
            if defaults:
                kwargs.update(defaults)
            obj = self.create(**kwargs)
            return obj, True

    def update_or_create(self, defaults=None, **kwargs):
        """Update an existing object or create a new one."""
        try:
            obj = self.get(**kwargs)
            if defaults:
                for key, value in defaults.items():
                    setattr(obj, key, value)
                obj.save(using=self._db)
            return obj, False
        except ObjectDoesNotExist:
            if defaults:
                kwargs.update(defaults)
            obj = self.create(**kwargs)
            return obj, True

    def bulk_create(self, objs, batch_size=None, ignore_conflicts=False):
        """Create multiple objects in batch using DynamoDB batch_write."""
        # DynamoDB supports batch writes up to 25 items
        max_batch_size = 25
        if batch_size is None:
            batch_size = max_batch_size
        else:
            batch_size = min(batch_size, max_batch_size)

        created_objects = []
        for i in range(0, len(objs), batch_size):
            batch = objs[i : i + batch_size]

            try:
                # Get the PynamoDB model
                pynamodb_model = self.model._get_pynamodb_model()

                # Convert Django instances to PynamoDB instances
                pynamodb_instances = []
                for obj in batch:
                    # Convert Django model to PynamoDB model data
                    pynamodb_data = self._convert_django_to_pynamodb_data(obj)
                    pynamodb_instance = pynamodb_model(**pynamodb_data)
                    pynamodb_instances.append(pynamodb_instance)

                # Use batch write
                with pynamodb_model.batch_write() as batch_writer:
                    for instance in pynamodb_instances:
                        batch_writer.save(instance)

                created_objects.extend(batch)

            except Exception as e:
                logger.error(f"Error in batch_create: {e}")
                if not ignore_conflicts:
                    raise
                # Fall back to individual saves
                for obj in batch:
                    try:
                        obj.save(using=self._db)
                        created_objects.append(obj)
                    except Exception as save_error:
                        if not ignore_conflicts:
                            raise save_error
                        logger.warning(f"Skipped object due to conflict: {save_error}")

        return created_objects

    def bulk_update(self, objs, fields, batch_size=None):
        """Update multiple objects in batch."""
        max_batch_size = 25
        if batch_size is None:
            batch_size = max_batch_size
        else:
            batch_size = min(batch_size, max_batch_size)

        updated_count = 0
        for i in range(0, len(objs), batch_size):
            batch = objs[i : i + batch_size]

            try:
                # For DynamoDB, we need to update each item individually
                # as batch_update has limitations
                for obj in batch:
                    # Only update specified fields
                    update_data = {field: getattr(obj, field) for field in fields}
                    obj.save(using=self._db, update_fields=fields)
                    updated_count += 1

            except Exception as e:
                logger.error(f"Error in bulk_update: {e}")
                raise

        return updated_count

    def _convert_django_to_pynamodb_data(self, django_instance):
        """Convert Django model instance to PynamoDB-compatible data."""
        pynamodb_data = {}

        # Get model fields
        for field in self.model._meta.fields:
            value = getattr(django_instance, field.name, None)
            if value is not None:
                # Convert value to DynamoDB-compatible format
                pynamodb_data[field.column] = self._preprocess_field_value(field, value)

        return pynamodb_data

    def _preprocess_field_value(self, field, value):
        """Preprocess field value for DynamoDB storage."""
        from django.db import models

        if value is None:
            return None

        # Handle different Django field types
        if isinstance(
            field,
            (
                models.IntegerField,
                models.BigIntegerField,
                models.PositiveIntegerField,
                models.SmallIntegerField,
            ),
        ):
            return Decimal(str(value))
        elif isinstance(field, (models.FloatField, models.DecimalField)):
            return Decimal(str(value))
        elif isinstance(
            field, (models.DateTimeField, models.DateField, models.TimeField)
        ):
            if hasattr(value, "isoformat"):
                return value.isoformat()
            return str(value)
        elif isinstance(field, models.BooleanField):
            return bool(value)
        elif isinstance(field, models.UUIDField):
            return str(value)
        elif isinstance(field, models.JSONField):
            return value  # DynamoDB handles JSON natively
        else:
            return str(value)
