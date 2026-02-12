"""
Django management command for monitoring DynamoDB performance.
"""

import json

from django.core.management.base import BaseCommand
from dynamodb_adapter.performance import (get_connection_pool, get_query_cache,
                                          performance_monitor)


class Command(BaseCommand):
    help = "Monitor DynamoDB performance metrics"

    def add_arguments(self, parser):
        parser.add_argument(
            "--format",
            choices=["table", "json"],
            default="table",
            help="Output format (table or json)",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Reset performance metrics after displaying",
        )
        parser.add_argument(
            "--watch",
            type=int,
            metavar="SECONDS",
            help="Watch mode - refresh every N seconds",
        )

    def handle(self, *args, **options):
        """Handle the command execution."""
        if options["watch"]:
            self.watch_metrics(options["watch"], options)
        else:
            self.display_metrics(options)

        if options["reset"]:
            self.reset_metrics()

    def display_metrics(self, options):
        """Display current performance metrics."""
        # Get metrics from all components
        connection_stats = get_connection_pool().get_stats()
        cache_stats = get_query_cache().get_stats()
        perf_metrics = performance_monitor.get_metrics()

        if options["format"] == "json":
            self.output_json(
                {
                    "connection_pool": connection_stats,
                    "query_cache": cache_stats,
                    "performance": perf_metrics,
                }
            )
        else:
            self.output_table(connection_stats, cache_stats, perf_metrics)

    def output_table(self, connection_stats, cache_stats, perf_metrics):
        """Output metrics in table format."""
        self.stdout.write(self.style.SUCCESS("\nDynamoDB Performance Metrics"))
        self.stdout.write("=" * 60)

        # Connection Pool Stats
        self.stdout.write(self.style.WARNING("\nConnection Pool:"))
        self.stdout.write(
            f"  Active Connections: {connection_stats['active_connections']}"
        )
        self.stdout.write(f"  Max Connections: {connection_stats['max_connections']}")
        self.stdout.write(f"  Total Created: {connection_stats['created_connections']}")
        self.stdout.write(f"  Pool Size: {connection_stats['pool_size']}")

        # Query Cache Stats
        self.stdout.write(self.style.WARNING("\nQuery Cache:"))
        self.stdout.write(f"  Cache Enabled: {cache_stats['enabled']}")
        self.stdout.write(f"  Cache Hits: {cache_stats['hits']}")
        self.stdout.write(f"  Cache Misses: {cache_stats['misses']}")
        self.stdout.write(f"  Hit Rate: {cache_stats['hit_rate_percent']:.1f}%")
        self.stdout.write(f"  Cache Sets: {cache_stats['sets']}")
        self.stdout.write(f"  Invalidations: {cache_stats['invalidations']}")

        # Performance Metrics
        self.stdout.write(self.style.WARNING("\nQuery Performance:"))
        self.stdout.write(f"  Total Queries: {perf_metrics['query_count']}")
        self.stdout.write(f"  Total Scans: {perf_metrics['scan_count']}")
        self.stdout.write(
            f"  Avg Query Time: {perf_metrics['avg_query_time_ms']:.2f}ms"
        )
        self.stdout.write(f"  Avg Scan Time: {perf_metrics['avg_scan_time_ms']:.2f}ms")

        self.stdout.write("=" * 60)

    def output_json(self, data):
        """Output metrics in JSON format."""
        self.stdout.write(json.dumps(data, indent=2))

    def watch_metrics(self, interval, options):
        """Watch metrics with periodic refresh."""
        import os
        import time

        self.stdout.write(f"Watching DynamoDB metrics (refresh every {interval}s)")
        self.stdout.write("Press Ctrl+C to stop\n")

        try:
            while True:
                # Clear screen (works on most terminals)
                os.system("clear" if os.name == "posix" else "cls")

                self.stdout.write(
                    f"DynamoDB Performance Monitor - {time.strftime('%Y-%m-%d %H:%M:%S')}"
                )
                self.display_metrics(options)

                time.sleep(interval)
        except KeyboardInterrupt:
            self.stdout.write("\nMonitoring stopped.")

    def reset_metrics(self):
        """Reset all performance metrics."""
        get_query_cache().clear_stats()
        performance_monitor.reset_metrics()
        self.stdout.write(self.style.SUCCESS("Performance metrics reset."))
