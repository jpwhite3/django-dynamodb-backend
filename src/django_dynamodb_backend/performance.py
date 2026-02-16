"""
Performance optimization utilities for DynamoDB Django Admin.

This module provides connection pooling, query caching, and other performance
enhancements for the DynamoDB Django Admin system.
"""

import hashlib
import json
import logging
import threading
from queue import Empty, Queue

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


class ConnectionPool:
    """Simple connection pool for DynamoDB resources."""

    def __init__(self, max_connections=10):
        self.max_connections = max_connections
        self.pool = Queue(maxsize=max_connections)
        self.active_connections = 0
        self.lock = threading.Lock()
        self.created_connections = 0

    def get_connection(self, connection_factory):
        """Get a connection from pool or create new one."""
        try:
            # Try to get existing connection from pool
            connection = self.pool.get_nowait()
            logger.debug("Retrieved connection from pool")
            return connection
        except Empty:
            # No available connection, create new one if under limit
            with self.lock:
                if self.active_connections < self.max_connections:
                    connection = connection_factory()
                    self.active_connections += 1
                    self.created_connections += 1
                    logger.debug(
                        f"Created new connection #{self.created_connections}, "
                        f"active: {self.active_connections}"
                    )
                    return connection
                else:
                    # Pool is full, wait for available connection
                    logger.debug("Pool full, waiting for available connection")
                    return self.pool.get(timeout=30)

    def return_connection(self, connection):
        """Return connection to pool."""
        try:
            self.pool.put_nowait(connection)
            logger.debug("Returned connection to pool")
        except Exception:
            # Pool full, close the connection
            with self.lock:
                self.active_connections -= 1
            logger.debug(
                f"Pool full, closed connection, active: {self.active_connections}"
            )

    def get_stats(self):
        """Get connection pool statistics."""
        return {
            "max_connections": self.max_connections,
            "active_connections": self.active_connections,
            "created_connections": self.created_connections,
            "pool_size": self.pool.qsize(),
        }


class QueryCache:
    """Advanced caching for DynamoDB queries."""

    def __init__(self):
        self.default_timeout = getattr(
            settings, "DYNAMODB_CACHE_TIMEOUT", 300
        )  # 5 minutes
        self.cache_enabled = getattr(settings, "DYNAMODB_ENABLE_CACHE", True)
        self.cache_stats = {"hits": 0, "misses": 0, "sets": 0, "invalidations": 0}

    def _generate_cache_key(self, operation, table_name, params):
        """Generate cache key for query."""
        key_data = {
            "operation": operation,
            "table": table_name,
            "params": self._normalize_params(params),
        }
        key_json = json.dumps(key_data, sort_keys=True, default=str)
        key_hash = hashlib.md5(key_json.encode()).hexdigest()
        return f"dynamodb:{operation}:{table_name}:{key_hash}"

    def _normalize_params(self, params):
        """Normalize parameters for consistent caching."""
        if isinstance(params, dict):
            return {k: str(v) for k, v in sorted(params.items())}
        return str(params)

    def get(self, operation, table_name, params):
        """Get cached query result."""
        if not self.cache_enabled:
            return None

        cache_key = self._generate_cache_key(operation, table_name, params)
        result = cache.get(cache_key)

        if result is not None:
            self.cache_stats["hits"] += 1
            logger.debug(f"Cache hit for {operation} on {table_name}")
            return result
        else:
            self.cache_stats["misses"] += 1
            logger.debug(f"Cache miss for {operation} on {table_name}")
            return None

    def set(self, operation, table_name, params, result, timeout=None):
        """Cache query result."""
        if not self.cache_enabled:
            return

        if result is None or isinstance(result, Exception):
            return  # Don't cache empty results or errors

        cache_key = self._generate_cache_key(operation, table_name, params)
        timeout = timeout or self.default_timeout

        cache.set(cache_key, result, timeout)
        self.cache_stats["sets"] += 1
        logger.debug(f"Cached result for {operation} on {table_name}")

    def invalidate_table(self, table_name):
        """Invalidate all cached results for a table."""
        # Note: This is a simplified approach
        # In production, you might want to use cache tags or Redis SCAN
        self.cache_stats["invalidations"] += 1
        logger.info(f"Cache invalidation requested for table: {table_name}")

        # If using Redis, you could do something like:
        # cache_keys = cache.keys(f"dynamodb:*:{table_name}:*")
        # cache.delete_many(cache_keys)

    def get_stats(self):
        """Get cache statistics."""
        total_requests = self.cache_stats["hits"] + self.cache_stats["misses"]
        hit_rate = (
            (self.cache_stats["hits"] / total_requests) * 100
            if total_requests > 0
            else 0
        )

        return {
            **self.cache_stats,
            "hit_rate_percent": round(hit_rate, 2),
            "enabled": self.cache_enabled,
        }

    def clear_stats(self):
        """Clear cache statistics."""
        self.cache_stats = {"hits": 0, "misses": 0, "sets": 0, "invalidations": 0}


class BatchOperationOptimizer:
    """Optimize batch operations for DynamoDB."""

    @staticmethod
    def optimize_batch_write(items, batch_size=25):
        """Optimize batch write operations."""
        # DynamoDB batch write limit is 25 items
        batches = []
        current_batch = []
        current_size = 0

        for item in items:
            # Estimate item size (simplified)
            item_size = len(str(item))

            # Check if adding this item would exceed batch size or item limit
            if (
                len(current_batch) >= batch_size
                or current_size + item_size > 400 * 1024
            ):  # 400KB limit

                if current_batch:
                    batches.append(current_batch)
                    current_batch = [item]
                    current_size = item_size
                else:
                    # Single item too large
                    logger.warning(f"Item too large for DynamoDB: {item_size} bytes")
                    continue
            else:
                current_batch.append(item)
                current_size += item_size

        if current_batch:
            batches.append(current_batch)

        return batches

    @staticmethod
    def optimize_scan_parameters(table_size_estimate=None):
        """Optimize scan parameters based on table size."""
        if table_size_estimate and table_size_estimate > 100000:
            # Large table - use parallel scanning
            return {
                "parallel_scan": True,
                "total_segments": min(10, table_size_estimate // 10000),
                "page_size": 1000,
            }
        else:
            # Small to medium table - standard scanning
            return {"parallel_scan": False, "page_size": 100}


# Global instances for easy access
default_connection_pool = None
default_query_cache = None


def get_connection_pool():
    """Get the default connection pool."""
    global default_connection_pool
    if default_connection_pool is None:
        max_connections = getattr(settings, "DYNAMODB_MAX_CONNECTIONS", 10)
        default_connection_pool = ConnectionPool(max_connections)
    return default_connection_pool


def get_query_cache():
    """Get the default query cache."""
    global default_query_cache
    if default_query_cache is None:
        default_query_cache = QueryCache()
    return default_query_cache


# Performance monitoring utilities
class PerformanceMonitor:
    """Monitor performance metrics for DynamoDB operations."""

    def __init__(self):
        self.metrics = {
            "query_count": 0,
            "scan_count": 0,
            "total_query_time": 0.0,
            "total_scan_time": 0.0,
            "cache_hit_rate": 0.0,
        }
        self.lock = threading.Lock()

    def record_query(self, duration):
        """Record query execution time."""
        with self.lock:
            self.metrics["query_count"] += 1
            self.metrics["total_query_time"] += duration

    def record_scan(self, duration):
        """Record scan execution time."""
        with self.lock:
            self.metrics["scan_count"] += 1
            self.metrics["total_scan_time"] += duration

    def get_metrics(self):
        """Get performance metrics."""
        with self.lock:
            avg_query_time = (
                self.metrics["total_query_time"] / self.metrics["query_count"]
                if self.metrics["query_count"] > 0
                else 0
            )
            avg_scan_time = (
                self.metrics["total_scan_time"] / self.metrics["scan_count"]
                if self.metrics["scan_count"] > 0
                else 0
            )

            return {
                **self.metrics,
                "avg_query_time_ms": round(avg_query_time * 1000, 2),
                "avg_scan_time_ms": round(avg_scan_time * 1000, 2),
            }

    def reset_metrics(self):
        """Reset all performance metrics."""
        with self.lock:
            self.metrics = {
                "query_count": 0,
                "scan_count": 0,
                "total_query_time": 0.0,
                "total_scan_time": 0.0,
                "cache_hit_rate": 0.0,
            }


# Global performance monitor
performance_monitor = PerformanceMonitor()
