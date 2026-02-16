# Demo Status and Health Check Command

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

# Import all demo models
from interactive_demo.apps.blog.models import (
    BlogAuthor,
    BlogCategory,
    BlogComment,
    BlogPost,
    BlogTag,
)
from interactive_demo.apps.ecommerce.models import (
    Customer,
    Order,
    OrderItem,
    Product,
    ProductCategory,
)


class Command(BaseCommand):
    help = "Check demo environment status and data counts"

    def add_arguments(self, parser):
        parser.add_argument(
            "--detailed",
            action="store_true",
            help="Show detailed breakdown of data",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("🔍 Django DynamoDB Admin Demo Status"))
        self.stdout.write("=" * 50)

        # Check admin user
        try:
            User.objects.get(username="admin")
            self.stdout.write("👤 Admin User: ✅ Available (admin/admin123)")
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR("👤 Admin User: ❌ Missing"))

        # Check data counts
        counts = {}
        models = [
            ("Blog Categories", BlogCategory),
            ("Blog Authors", BlogAuthor),
            ("Blog Tags", BlogTag),
            ("Blog Posts", BlogPost),
            ("Blog Comments", BlogComment),
            ("Product Categories", ProductCategory),
            ("Products", Product),
            ("Customers", Customer),
            ("Orders", Order),
            ("Order Items", OrderItem),
        ]

        total_items = 0
        self.stdout.write("\n📊 Data Summary:")

        for name, model in models:
            try:
                count = model.objects.count()
                counts[name] = count
                total_items += count

                status = "✅" if count > 0 else "⚠️"
                self.stdout.write(f"  {status} {name}: {count:,}")

                if options["detailed"] and count > 0:
                    self.show_detailed_info(model, count)

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ❌ {name}: Error - {e}"))

        self.stdout.write(f"\nTotal Records: {total_items:,}")

        # Show access information
        self.stdout.write("\n🔗 Access Information:")
        self.stdout.write("  Django Admin: http://localhost:8001/admin/")
        self.stdout.write("  DynamoDB UI: http://localhost:8002/")
        self.stdout.write("  Performance: http://localhost:8003/")

        # Performance quick check
        self.stdout.write("\n⚡ Quick Performance Check:")
        self.run_performance_check()

        # Recommendations
        if total_items == 0:
            self.stdout.write("\n💡 Recommendations:")
            self.stdout.write("  Run: python manage.py setup_demo_data")
        elif total_items < 100:
            self.stdout.write("\n💡 Recommendations:")
            self.stdout.write("  For better demo experience, run:")
            self.stdout.write("  python manage.py setup_demo_data --size medium")

    def show_detailed_info(self, model, count):
        """Show detailed information for models with data"""
        try:
            if model == BlogPost:
                published = model.objects.filter(is_published=True).count()
                featured = model.objects.filter(is_featured=True).count()
                self.stdout.write(f"    Published: {published}, Featured: {featured}")

            elif model == Product:
                available = model.objects.filter(is_available=True).count()
                featured = model.objects.filter(is_featured=True).count()
                self.stdout.write(f"    Available: {available}, Featured: {featured}")

            elif model == Order:
                statuses = {}
                for status_code, status_name in [
                    ("pending", "Pending"),
                    ("paid", "Paid"),
                    ("shipped", "Shipped"),
                    ("delivered", "Delivered"),
                ]:
                    count = model.objects.filter(status=status_code).count()
                    if count > 0:
                        statuses[status_name] = count

                if statuses:
                    status_str = ", ".join([f"{k}: {v}" for k, v in statuses.items()])
                    self.stdout.write(f"    {status_str}")

            elif model == Customer:
                active = model.objects.filter(is_active=True).count()
                vip = model.objects.filter(
                    customer_tier__in=["platinum", "vip"]
                ).count()
                self.stdout.write(f"    Active: {active}, VIP: {vip}")

        except Exception:
            # Silently skip detailed info on error
            pass

    def run_performance_check(self):
        """Run basic performance checks"""
        import time

        try:
            # Test simple query
            start = time.time()
            list(BlogPost.objects.all()[:10])
            duration = (time.time() - start) * 1000

            if duration < 100:
                status = "🟢 Excellent"
            elif duration < 500:
                status = "🟡 Good"
            else:
                status = "🔴 Slow"

            self.stdout.write(f"  Query Performance: {status} ({duration:.1f}ms)")

            # Test filtered query
            start = time.time()
            list(BlogPost.objects.filter(is_published=True)[:10])
            duration = (time.time() - start) * 1000

            self.stdout.write(f"  Filtered Query: {duration:.1f}ms")

        except Exception as e:
            self.stdout.write(f"  Performance Check: ❌ Error - {e}")

        # Check connection status
        try:
            from django_dynamodb_backend.performance import get_connection_pool

            get_connection_pool()
            self.stdout.write("  Connection Pool: ✅ Available")
        except Exception:
            self.stdout.write("  Connection Pool: ⚠️  Not available")
