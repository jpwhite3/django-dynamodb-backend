"""
SQL compiler for DynamoDB backend.

This module handles the translation of Django ORM queries to DynamoDB operations.
"""

import logging

from django.db.models.sql import compiler
from django.db.models.sql.constants import SINGLE

logger = logging.getLogger(__name__)


class SQLCompiler(compiler.SQLCompiler):
    """
    SQL compiler that translates Django ORM queries to DynamoDB operations.
    """

    def __init__(self, query, connection, using, elide_empty=True):
        super().__init__(query, connection, using, elide_empty)
        self.dynamodb_operation = None
        self.table_name = None
        self.filter_expression = []
        self.projection_expression = None

    def as_sql(self, with_limits=True, with_col_aliases=False):
        """
        Convert the query to DynamoDB operations instead of SQL.
        """
        try:
            # Analyze the query and determine the DynamoDB operation needed
            self._analyze_query()

            # For now, return a placeholder that can be processed by the cursor
            return self._build_dynamodb_query(), []

        except Exception as e:
            logger.error(f"Error compiling query: {e}")
            raise

    def _analyze_query(self):
        """
        Analyze the Django query and determine the appropriate DynamoDB operation.
        """
        # Get table name from the main model
        if self.query.model:
            self.table_name = self.query.model._meta.db_table

        # Determine operation type
        if self.query.where:
            # This is a filtered query - use Query or Scan
            self._analyze_filters()

        # Handle SELECT operations
        if self.query.select:
            self._analyze_select()

        # Handle ordering
        if self.query.order_by:
            self._analyze_ordering()

    def _analyze_filters(self):
        """
        Analyze WHERE clause filters and convert to DynamoDB filter expressions.
        """
        # This is a simplified implementation
        # In a full implementation, you'd recursively parse the where tree
        filters = []

        if hasattr(self.query.where, "children"):
            for child in self.query.where.children:
                if hasattr(child, "lhs") and hasattr(child, "rhs"):
                    field_name = child.lhs.target.column
                    lookup_type = child.lookup_name
                    value = child.rhs

                    # Convert Django lookup to DynamoDB format
                    filter_dict = self._convert_lookup(field_name, lookup_type, value)
                    if filter_dict:
                        filters.append(filter_dict)

        self.filter_expression = filters

    def _convert_lookup(self, field_name, lookup_type, value):
        """
        Convert Django field lookup to DynamoDB filter format.
        """
        lookup_map = {
            "exact": {"op": "=", "value": value},
            "gt": {"op": ">", "value": value},
            "gte": {"op": ">=", "value": value},
            "lt": {"op": "<", "value": value},
            "lte": {"op": "<=", "value": value},
            "contains": {"op": "contains", "value": value},
            "startswith": {"op": "begins_with", "value": value},
        }

        if lookup_type in lookup_map:
            return {
                "field": field_name,
                "operation": lookup_map[lookup_type]["op"],
                "value": lookup_map[lookup_type]["value"],
            }

        logger.warning(f"Unsupported lookup type: {lookup_type}")
        return None

    def _analyze_select(self):
        """
        Analyze SELECT clause and build projection expression.
        """
        if self.query.select:
            # Build projection expression for DynamoDB
            fields = []
            for col in self.query.select:
                if hasattr(col, "target"):
                    fields.append(col.target.column)

            self.projection_expression = fields

    def _analyze_ordering(self):
        """
        Analyze ORDER BY clause (limited support in DynamoDB).
        """
        # DynamoDB has limited ordering capabilities
        # Only sort keys can be ordered, and only in ascending or descending order
        if self.query.order_by:
            logger.warning(
                "DynamoDB has limited ordering support. "
                "Consider using Global Secondary Indexes for complex ordering."
            )

    def _build_dynamodb_query(self):
        """
        Build the DynamoDB operation dictionary.
        """
        operation = {
            "operation_type": "scan",  # Default to scan
            "table_name": self.table_name,
            "filters": self.filter_expression or [],
            "projection": self.projection_expression,
        }

        # Determine if we should use Query instead of Scan
        # This would require analyzing if we're filtering on the partition key
        if self._can_use_query():
            operation["operation_type"] = "query"

        return operation

    def _can_use_query(self):
        """
        Determine if we can use DynamoDB Query operation instead of Scan.
        """
        # For now, always use Scan
        # In a full implementation, you'd check if the partition key is being filtered
        return False

    def results_iter(self, results=None):
        """
        Return an iterator over the results from executing this query.
        """
        try:
            # Get the model and create a QuerySet
            if self.query.model:
                from django_dynamodb_backend.managers import DynamoDBQuerySet

                # Create a QuerySet for this model
                queryset = DynamoDBQuerySet(model=self.query.model, using=self.using)

                # Apply filters from the compiled query
                queryset = self._apply_query_filters(queryset)

                # Apply ordering
                if self.query.order_by:
                    order_fields = []
                    for order_col in self.query.order_by:
                        if hasattr(order_col, "col"):
                            field_name = order_col.col.target.name
                            if order_col.descending:
                                field_name = f"-{field_name}"
                            order_fields.append(field_name)
                    if order_fields:
                        queryset = queryset.order_by(*order_fields)

                # Apply limits
                if self.query.low_mark or self.query.high_mark:
                    start = self.query.low_mark or 0
                    stop = self.query.high_mark
                    if stop is not None:
                        queryset = queryset[start:stop]
                    else:
                        queryset = queryset[start:]

                # Return results
                for result in queryset:
                    yield self._convert_result_to_row(result)
            else:
                return iter([])

        except Exception as e:
            logger.error(f"Error in results_iter: {e}")
            return iter([])

    def _apply_query_filters(self, queryset):
        """
        Apply WHERE clause filters to the QuerySet.
        """
        if not self.query.where:
            return queryset

        try:
            filter_kwargs = self._extract_filter_kwargs(self.query.where)
            if filter_kwargs:
                queryset = queryset.filter(**filter_kwargs)
            return queryset
        except Exception as e:
            logger.error(f"Error applying query filters: {e}")
            return queryset

    def _extract_filter_kwargs(self, where_node):
        """
        Extract filter kwargs from Django's WHERE node.
        """
        kwargs = {}

        try:
            if hasattr(where_node, "children"):
                for child in where_node.children:
                    if hasattr(child, "lhs") and hasattr(child, "rhs"):
                        # Extract field name and lookup
                        if hasattr(child.lhs, "target"):
                            field_name = child.lhs.target.name
                            lookup_type = getattr(child, "lookup_name", "exact")

                            # Get the value
                            if hasattr(child.rhs, "value"):
                                value = child.rhs.value
                            else:
                                value = child.rhs

                            # Build the lookup key
                            if lookup_type != "exact":
                                lookup_key = f"{field_name}__{lookup_type}"
                            else:
                                lookup_key = field_name

                            kwargs[lookup_key] = value

            return kwargs

        except Exception as e:
            logger.error(f"Error extracting filter kwargs: {e}")
            return {}

    def _convert_result_to_row(self, django_instance):
        """
        Convert a Django model instance to a result row.
        """
        try:
            # If we have specific select fields, only return those
            if self.query.select:
                row = []
                for col in self.query.select:
                    if hasattr(col, "target"):
                        field_name = col.target.name
                        value = getattr(django_instance, field_name, None)
                        row.append(value)
                return row
            else:
                # Return all field values
                row = []
                for field in self.query.model._meta.fields:
                    value = getattr(django_instance, field.name, None)
                    row.append(value)
                return row

        except Exception as e:
            logger.error(f"Error converting result to row: {e}")
            return []

    def execute_sql(self, result_type=None, chunked_fetch=False, chunk_size=0):
        """
        Execute the SQL query and return results.
        """
        try:
            if result_type == SINGLE:
                # Return single result
                results = list(self.results_iter())
                return results[0] if results else None
            else:
                # Return all results
                return list(self.results_iter())

        except Exception as e:
            logger.error(f"Error executing SQL: {e}")
            if result_type == SINGLE:
                return None
            else:
                return []


class SQLInsertCompiler(compiler.SQLInsertCompiler):
    """
    Compiler for INSERT operations in DynamoDB.
    """

    def __init__(self, query, connection, using, return_id=False):
        super().__init__(query, connection, using, return_id)

    def as_sql(self):
        """
        Convert INSERT operation to DynamoDB PutItem.
        """
        # Extract the values to be inserted
        fields = self.query.fields
        values = []

        # Handle different structures for fields and objs
        if fields and self.query.objs:
            for obj_values in self.query.objs:
                item = {}
                if isinstance(obj_values, (list, tuple)):
                    # Multiple values per object
                    for field, value in zip(fields, obj_values):
                        if hasattr(field, "column"):
                            column_name = field.column
                        else:
                            column_name = field.name
                        item[column_name] = value
                else:
                    # Single value - use first field
                    if fields:
                        field = (
                            fields[0] if isinstance(fields, (list, tuple)) else fields
                        )
                        if hasattr(field, "column"):
                            column_name = field.column
                        else:
                            column_name = field.name
                        item[column_name] = obj_values
                values.append(item)

        operation = {
            "operation_type": "put_item",
            "table_name": self.query.model._meta.db_table,
            "items": values,
        }

        return operation, []


class SQLUpdateCompiler(compiler.SQLUpdateCompiler):
    """
    Compiler for UPDATE operations in DynamoDB.
    """

    def __init__(self, query, connection, using):
        super().__init__(query, connection, using)

    def as_sql(self):
        """
        Convert UPDATE operation to DynamoDB UpdateItem.
        """
        # Extract the fields and values to update
        update_fields = {}
        for field, model, val in self.query.values:
            if hasattr(field, "column"):
                column_name = field.column
            else:
                column_name = field.name
            update_fields[column_name] = val

        operation = {
            "operation_type": "update_item",
            "table_name": self.query.model._meta.db_table,
            "updates": update_fields,
            "filters": self.query.where,  # This would need to be processed
        }

        return operation, []


class SQLDeleteCompiler(compiler.SQLDeleteCompiler):
    """
    Compiler for DELETE operations in DynamoDB.
    """

    def __init__(self, query, connection, using):
        super().__init__(query, connection, using)

    def as_sql(self):
        """
        Convert DELETE operation to DynamoDB DeleteItem.
        """
        operation = {
            "operation_type": "delete_item",
            "table_name": self.query.model._meta.db_table,
            "filters": self.query.where,  # This would need to be processed
        }

        return operation, []


class SQLAggregateCompiler(compiler.SQLAggregateCompiler):
    """
    Compiler for aggregate operations in DynamoDB.
    """

    def __init__(self, query, connection, using, elide_empty=True):
        super().__init__(query, connection, using, elide_empty)

    def as_sql(self):
        """
        Convert aggregate operations to DynamoDB operations.
        """
        # DynamoDB doesn't support traditional aggregates
        # This would need custom implementation using Scan/Query with client-side aggregation
        logger.warning("Aggregate operations have limited support in DynamoDB")
        return None, []
