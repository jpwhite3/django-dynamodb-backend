"""
Global Secondary Index (GSI) optimization and monitoring for DynamoDB Django Admin.

This module provides intelligent GSI selection, performance monitoring, and
optimization recommendations for DynamoDB queries.
"""

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.utils import timezone

logger = logging.getLogger(__name__)


@dataclass
class GSIInfo:
    """Information about a Global Secondary Index."""

    name: str
    hash_key: str
    range_key: Optional[str]
    projection: str  # 'ALL', 'KEYS_ONLY', or 'INCLUDE'
    projected_attributes: List[str]
    read_capacity: int
    write_capacity: int
    status: str  # 'ACTIVE', 'CREATING', 'UPDATING', etc.
    item_count: Optional[int] = None
    size_bytes: Optional[int] = None


@dataclass
class QueryPattern:
    """Represents a query pattern for optimization analysis."""

    filters: Dict[str, Any]
    ordering: List[str]
    frequency: int
    avg_response_time: float
    last_used: datetime
    operation_type: str  # 'query' or 'scan'


@dataclass
class OptimizationRecommendation:
    """Recommendation for query optimization."""

    type: str  # 'use_gsi', 'create_gsi', 'modify_query'
    description: str
    potential_improvement: str
    estimated_cost_savings: float
    complexity: str  # 'low', 'medium', 'high'
    gsi_name: Optional[str] = None


class GSIOptimizer:
    """Optimizes DynamoDB queries using Global Secondary Indexes."""

    def __init__(self, model_class):
        self.model_class = model_class
        self.table_name = model_class._meta.db_table
        self._gsi_cache_key = f"dynamodb_gsi_info_{self.table_name}"
        self._query_patterns_key = f"dynamodb_query_patterns_{self.table_name}"
        self._gsi_info = None

    def get_gsi_info(self) -> List[GSIInfo]:
        """Get information about all GSIs for the table."""
        if self._gsi_info is None:
            self._gsi_info = self._load_gsi_info()
        return self._gsi_info

    def _load_gsi_info(self) -> List[GSIInfo]:
        """Load GSI information from DynamoDB."""
        # Check cache first
        cached_info = cache.get(self._gsi_cache_key)
        if cached_info:
            return cached_info

        gsi_list = []

        try:
            # Get DynamoDB client from connection
            dynamodb_client = connection.connection.client

            # Describe the table to get GSI information
            response = dynamodb_client.describe_table(TableName=self.table_name)
            table_info = response["Table"]

            # Process Global Secondary Indexes
            for gsi in table_info.get("GlobalSecondaryIndexes", []):
                gsi_info = GSIInfo(
                    name=gsi["IndexName"],
                    hash_key=gsi["KeySchema"][0]["AttributeName"],
                    range_key=(
                        gsi["KeySchema"][1]["AttributeName"]
                        if len(gsi["KeySchema"]) > 1
                        else None
                    ),
                    projection=gsi["Projection"]["ProjectionType"],
                    projected_attributes=gsi["Projection"].get("NonKeyAttributes", []),
                    read_capacity=gsi.get("ProvisionedThroughput", {}).get(
                        "ReadCapacityUnits", 0
                    ),
                    write_capacity=gsi.get("ProvisionedThroughput", {}).get(
                        "WriteCapacityUnits", 0
                    ),
                    status=gsi["IndexStatus"],
                    item_count=gsi.get("ItemCount"),
                    size_bytes=gsi.get("IndexSizeBytes"),
                )
                gsi_list.append(gsi_info)

            # Cache for 5 minutes
            cache.set(self._gsi_cache_key, gsi_list, 300)

        except Exception as e:
            logger.error(f"Error loading GSI info for {self.table_name}: {e}")

        return gsi_list

    def analyze_query_for_gsi(
        self, filters: Dict[str, Any], ordering: List[str] = None
    ) -> Tuple[Optional[str], str]:
        """
        Analyze a query to determine the best GSI to use.
        Returns (gsi_name, operation_type).
        """
        gsi_options = []
        gsi_info_list = self.get_gsi_info()

        if not filters:
            return None, "scan"

        # Analyze each GSI for compatibility
        for gsi in gsi_info_list:
            score = self._score_gsi_for_query(gsi, filters, ordering or [])
            if score > 0:
                gsi_options.append((gsi.name, score, "query"))

        # Sort by score and return the best option
        if gsi_options:
            gsi_options.sort(key=lambda x: x[1], reverse=True)
            best_gsi, best_score, operation = gsi_options[0]

            # Log the decision
            logger.info(f"Selected GSI {best_gsi} for query (score: {best_score})")
            return best_gsi, operation

        # No suitable GSI found, use scan
        logger.debug(f"No suitable GSI found for query, using scan")
        return None, "scan"

    def _score_gsi_for_query(
        self, gsi: GSIInfo, filters: Dict[str, Any], ordering: List[str]
    ) -> float:
        """Score how well a GSI matches a query."""
        score = 0.0

        # Check if hash key is in filters
        hash_key_filter = None
        for filter_key in filters.keys():
            field_name = filter_key.split("__")[0]  # Remove lookup type
            if field_name == gsi.hash_key:
                hash_key_filter = filter_key
                score += 10.0  # High score for hash key match
                break

        if not hash_key_filter:
            return 0.0  # Cannot use GSI without hash key filter

        # Check hash key filter type
        lookup_type = (
            hash_key_filter.split("__")[-1] if "__" in hash_key_filter else "exact"
        )
        if lookup_type != "exact":
            score -= 5.0  # Penalty for non-exact hash key lookups

        # Check if range key is used effectively
        if gsi.range_key:
            range_key_used = False
            for filter_key in filters.keys():
                field_name = filter_key.split("__")[0]
                if field_name == gsi.range_key:
                    range_key_used = True
                    lookup_type = (
                        filter_key.split("__")[-1] if "__" in filter_key else "exact"
                    )

                    # Score based on lookup type
                    if lookup_type in ["exact", "lt", "lte", "gt", "gte", "between"]:
                        score += 5.0  # Good range key usage
                    elif lookup_type in ["startswith", "begins_with"]:
                        score += 3.0  # Decent range key usage
                    else:
                        score += 1.0  # Basic range key usage
                    break

            if not range_key_used:
                score -= 2.0  # Small penalty for not using range key

        # Check ordering compatibility
        if ordering:
            first_order_field = ordering[0].lstrip("-")
            if first_order_field == gsi.range_key:
                score += 2.0  # Good ordering match
                # Check if ordering direction matches GSI sort order
                is_descending = ordering[0].startswith("-")
                # In DynamoDB, you can specify ScanIndexForward=False for descending
                score += 0.5
            elif first_order_field == gsi.hash_key:
                score += 1.0  # Partial ordering match

        # Consider projection efficiency
        if gsi.projection == "ALL":
            score += 1.0  # No additional reads needed
        elif gsi.projection == "KEYS_ONLY":
            score -= 1.0  # May need additional reads

        # Consider GSI status
        if gsi.status != "ACTIVE":
            score = 0.0  # Cannot use inactive GSI

        return max(0.0, score)

    def record_query_pattern(
        self,
        filters: Dict[str, Any],
        ordering: List[str],
        response_time: float,
        operation_type: str,
    ):
        """Record a query pattern for analysis."""
        pattern_key = self._generate_pattern_key(filters, ordering)

        # Get existing patterns
        patterns = cache.get(self._query_patterns_key, {})

        if pattern_key in patterns:
            # Update existing pattern
            pattern = patterns[pattern_key]
            pattern.frequency += 1
            pattern.avg_response_time = (pattern.avg_response_time + response_time) / 2
            pattern.last_used = timezone.now()
        else:
            # Create new pattern
            patterns[pattern_key] = QueryPattern(
                filters=filters,
                ordering=ordering,
                frequency=1,
                avg_response_time=response_time,
                last_used=timezone.now(),
                operation_type=operation_type,
            )

        # Cache patterns for 1 hour
        cache.set(self._query_patterns_key, patterns, 3600)

    def _generate_pattern_key(
        self, filters: Dict[str, Any], ordering: List[str]
    ) -> str:
        """Generate a key for the query pattern."""
        import hashlib

        pattern_str = f"{sorted(filters.keys())}_{sorted(ordering)}"
        return hashlib.md5(pattern_str.encode()).hexdigest()

    def get_optimization_recommendations(self) -> List[OptimizationRecommendation]:
        """Get recommendations for optimizing queries."""
        recommendations = []
        patterns = cache.get(self._query_patterns_key, {})
        gsi_info = self.get_gsi_info()

        # Analyze query patterns
        for pattern_key, pattern in patterns.items():
            if pattern.operation_type == "scan" and pattern.frequency > 5:
                # Frequent scan operations are candidates for GSI optimization
                rec = self._analyze_scan_pattern(pattern, gsi_info)
                if rec:
                    recommendations.append(rec)

            elif pattern.avg_response_time > 1.0:  # Slow queries
                rec = self._analyze_slow_query(pattern, gsi_info)
                if rec:
                    recommendations.append(rec)

        # Look for missing GSIs based on common patterns
        recommendations.extend(self._suggest_new_gsis(patterns))

        return recommendations

    def _analyze_scan_pattern(
        self, pattern: QueryPattern, gsi_info: List[GSIInfo]
    ) -> Optional[OptimizationRecommendation]:
        """Analyze a scan pattern for optimization opportunities."""
        # Check if any existing GSI could handle this pattern
        for gsi in gsi_info:
            if gsi.status == "ACTIVE":
                score = self._score_gsi_for_query(
                    gsi, pattern.filters, pattern.ordering
                )
                if score > 5.0:  # Good match
                    return OptimizationRecommendation(
                        type="use_gsi",
                        description=f"Use GSI '{gsi.name}' instead of table scan",
                        potential_improvement=f"Could reduce response time by ~{min(90, int(score * 10))}%",
                        estimated_cost_savings=pattern.frequency
                        * 0.1,  # Rough estimate
                        complexity="low",
                        gsi_name=gsi.name,
                    )

        # Suggest creating a new GSI
        if pattern.frequency > 10:  # High frequency scan
            return OptimizationRecommendation(
                type="create_gsi",
                description=f"Create GSI for frequent scan pattern",
                potential_improvement=f"Could eliminate {pattern.frequency} scan operations per period",
                estimated_cost_savings=pattern.frequency * 0.2,
                complexity="high",
            )

        return None

    def _analyze_slow_query(
        self, pattern: QueryPattern, gsi_info: List[GSIInfo]
    ) -> Optional[OptimizationRecommendation]:
        """Analyze a slow query pattern."""
        if pattern.operation_type == "query":
            # Query is slow - might need better GSI or query modification
            return OptimizationRecommendation(
                type="modify_query",
                description=f"Optimize slow query (avg: {pattern.avg_response_time:.2f}s)",
                potential_improvement="Reduce response time by optimizing filters",
                estimated_cost_savings=0.0,
                complexity="medium",
            )

        return None

    def _suggest_new_gsis(
        self, patterns: Dict[str, QueryPattern]
    ) -> List[OptimizationRecommendation]:
        """Suggest new GSIs based on query patterns."""
        recommendations = []

        # Analyze common filter combinations
        filter_combinations = defaultdict(int)

        for pattern in patterns.values():
            for filter_key in pattern.filters.keys():
                field_name = filter_key.split("__")[0]
                filter_combinations[field_name] += pattern.frequency

        # Suggest GSIs for frequently filtered fields
        existing_gsi_keys = set()
        for gsi in self.get_gsi_info():
            existing_gsi_keys.add(gsi.hash_key)
            if gsi.range_key:
                existing_gsi_keys.add(gsi.range_key)

        for field_name, frequency in filter_combinations.items():
            if field_name not in existing_gsi_keys and frequency > 20:
                recommendations.append(
                    OptimizationRecommendation(
                        type="create_gsi",
                        description=f"Create GSI with hash key '{field_name}' for frequent filtering",
                        potential_improvement=f"Optimize {frequency} queries per period",
                        estimated_cost_savings=frequency * 0.15,
                        complexity="high",
                    )
                )

        return recommendations

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics for the table and GSIs."""
        patterns = cache.get(self._query_patterns_key, {})
        gsi_info = self.get_gsi_info()

        # Calculate metrics
        total_queries = sum(p.frequency for p in patterns.values())
        scan_queries = sum(
            p.frequency for p in patterns.values() if p.operation_type == "scan"
        )
        avg_response_time = (
            sum(p.avg_response_time * p.frequency for p in patterns.values())
            / total_queries
            if total_queries > 0
            else 0
        )

        # GSI utilization
        gsi_utilization = {}
        for gsi in gsi_info:
            # This would need actual CloudWatch metrics in production
            gsi_utilization[gsi.name] = {
                "status": gsi.status,
                "item_count": gsi.item_count or 0,
                "size_mb": (gsi.size_bytes or 0) / (1024 * 1024),
                "read_capacity": gsi.read_capacity,
                "write_capacity": gsi.write_capacity,
            }

        return {
            "table_name": self.table_name,
            "total_queries": total_queries,
            "scan_percentage": (
                (scan_queries / total_queries * 100) if total_queries > 0 else 0
            ),
            "avg_response_time_ms": avg_response_time * 1000,
            "gsi_count": len(gsi_info),
            "gsi_utilization": gsi_utilization,
            "query_patterns": len(patterns),
            "recommendations_count": len(self.get_optimization_recommendations()),
        }


class GSIMonitoringMixin:
    """Mixin for Django Admin to add GSI monitoring capabilities."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.gsi_optimizer = GSIOptimizer(self.model)

    def changelist_view(self, request, extra_context=None):
        """Add GSI performance data to changelist view."""
        extra_context = extra_context or {}

        # Get performance metrics
        metrics = self.gsi_optimizer.get_performance_metrics()
        recommendations = self.gsi_optimizer.get_optimization_recommendations()

        # Add GSI info to context
        extra_context.update(
            {
                "gsi_metrics": metrics,
                "gsi_recommendations": recommendations[:3],  # Top 3 recommendations
                "show_gsi_panel": True,
            }
        )

        return super().changelist_view(request, extra_context)

    def get_queryset(self, request):
        """Get queryset with GSI optimization."""
        queryset = super().get_queryset(request)

        # Record query pattern for analysis
        if hasattr(queryset, "_dynamodb_scan_filters"):
            # Extract filters for pattern analysis
            filters = {}
            for filter_condition in getattr(queryset, "_dynamodb_scan_filters", []):
                # This is a simplified extraction - would need more sophisticated parsing
                filters["analyzed"] = True

            # Record the pattern (response time would be measured elsewhere)
            self.gsi_optimizer.record_query_pattern(
                filters,
                getattr(queryset, "_order_by_fields", []),
                0.0,  # Response time would be measured during execution
                "scan",  # Would determine based on actual operation
            )

        return queryset


def optimize_queryset_with_gsi(queryset, model_class):
    """Optimize a queryset using GSI analysis."""
    optimizer = GSIOptimizer(model_class)

    # Extract query information
    filters = {}
    ordering = []

    # This would need more sophisticated query introspection
    # For now, return the queryset as-is
    return queryset
