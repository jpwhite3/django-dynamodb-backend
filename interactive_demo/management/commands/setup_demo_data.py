# Demo Data Setup Command - Generates Rich Sample Data

import random
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from faker import Faker

# Import all demo models
from interactive_demo.apps.blog.models import (BlogAuthor, BlogCategory,
                                               BlogComment, BlogPost, BlogTag)
from interactive_demo.apps.ecommerce.models import (Customer, Order, OrderItem,
                                                    Product, ProductCategory)


class Command(BaseCommand):
    help = "Generate comprehensive sample data for interactive demo"

    def __init__(self):
        super().__init__()
        self.fake = Faker()
        self.fake.seed_instance(42)  # Reproducible data
        random.seed(42)

        # Data counters
        self.created_counts = {
            "users": 0,
            "blog_categories": 0,
            "blog_authors": 0,
            "blog_tags": 0,
            "blog_posts": 0,
            "blog_comments": 0,
            "product_categories": 0,
            "products": 0,
            "customers": 0,
            "orders": 0,
            "order_items": 0,
        }

    def add_arguments(self, parser):
        parser.add_argument(
            "--quick",
            action="store_true",
            help="Generate minimal data for quick testing",
        )
        parser.add_argument(
            "--size",
            type=str,
            default="medium",
            choices=["small", "medium", "large"],
            help="Size of dataset to generate",
        )
        parser.add_argument(
            "--skip-users",
            action="store_true",
            help="Skip creating Django users (useful for repeated runs)",
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS("🚀 Setting up Django DynamoDB Admin Demo Data...")
        )

        # Configure data sizes
        sizes = {
            "small": {
                "blog_posts": 20,
                "users": 10,
                "products": 50,
                "orders": 30,
                "customers": 20,
            },
            "medium": {
                "blog_posts": 100,
                "users": 50,
                "products": 200,
                "orders": 300,
                "customers": 150,
            },
            "large": {
                "blog_posts": 500,
                "users": 200,
                "products": 1000,
                "orders": 1500,
                "customers": 800,
            },
        }

        if options["quick"]:
            data_size = sizes["small"]
            self.stdout.write("📊 Quick mode: Generating minimal dataset")
        else:
            data_size = sizes[options["size"]]
            self.stdout.write(f'📊 Generating {options["size"]} dataset')

        try:
            # Create Django admin user
            if not options["skip_users"]:
                self.create_admin_user()

            # Generate demo data in dependency order
            self.stdout.write("\n🏗️  Building demo data...")

            # Blog data
            self.create_blog_categories()
            self.create_blog_authors(data_size["users"])
            self.create_blog_tags()
            self.create_blog_posts(data_size["blog_posts"])
            self.create_blog_comments(data_size["blog_posts"] * 10)

            # E-commerce data
            self.create_product_categories()
            self.create_products(data_size["products"])
            self.create_customers(data_size["customers"])
            self.create_orders(data_size["orders"])

            # Final report
            self.print_summary()

        except Exception as e:
            raise CommandError(f"Error generating demo data: {e}")

    def create_admin_user(self):
        """Create Django admin user"""
        try:
            admin_user = User.objects.get(username="admin")
            self.stdout.write("👤 Admin user already exists")
        except User.DoesNotExist:
            admin_user = User.objects.create_superuser(
                username="admin", email="admin@example.com", password="admin123"
            )
            self.stdout.write(
                self.style.SUCCESS("👤 Created admin user (admin/admin123)")
            )
        self.created_counts["users"] += 1

    def create_blog_categories(self):
        """Create blog categories with hierarchy"""
        categories_data = [
            {"name": "Technology", "description": "Latest tech trends and tutorials"},
            {"name": "Lifestyle", "description": "Life tips and personal development"},
            {
                "name": "Business",
                "description": "Entrepreneurship and business insights",
            },
            {"name": "Travel", "description": "Travel guides and experiences"},
            {
                "name": "Food & Cooking",
                "description": "Recipes and culinary adventures",
            },
            {"name": "Health & Fitness", "description": "Wellness and fitness tips"},
        ]

        for cat_data in categories_data:
            category = BlogCategory(
                category_id=str(uuid.uuid4()),
                name=cat_data["name"],
                slug=cat_data["name"].lower().replace(" ", "-").replace("&", "and"),
                description=cat_data["description"],
                post_count=0,
                subscriber_count=random.randint(100, 5000),
                color_code=self.fake.color(),
                meta_title=f"{cat_data['name']} Articles",
                meta_description=cat_data["description"],
            )
            category.save()
            self.created_counts["blog_categories"] += 1

        self.stdout.write(f"📚 Created {len(categories_data)} blog categories")

    def create_blog_authors(self, count):
        """Create blog authors"""
        for i in range(count):
            author = BlogAuthor(
                author_id=str(uuid.uuid4()),
                username=self.fake.user_name() + str(i),  # Ensure uniqueness
                first_name=self.fake.first_name(),
                last_name=self.fake.last_name(),
                email=self.fake.email(),
                bio=self.fake.text(max_nb_chars=500),
                profile_image_url=self.fake.image_url(),
                website_url=self.fake.url(),
                twitter_handle=self.fake.user_name(),
                linkedin_url=f"https://linkedin.com/in/{self.fake.user_name()}",
                github_username=self.fake.user_name(),
                post_count=0,
                total_views=random.randint(1000, 50000),
                follower_count=random.randint(50, 10000),
                is_active=True,
                email_notifications=random.choice([True, False]),
                joined_date=self.fake.date_time_between(
                    start_date="-2y", end_date="now", tzinfo=timezone.utc
                ),
            )
            author.save()
            self.created_counts["blog_authors"] += 1

        self.stdout.write(f"✍️  Created {count} blog authors")

    def create_blog_tags(self):
        """Create blog tags"""
        tags_data = [
            "python",
            "django",
            "javascript",
            "react",
            "aws",
            "database",
            "productivity",
            "career",
            "remote-work",
            "startups",
            "innovation",
            "mindfulness",
            "fitness",
            "nutrition",
            "travel-tips",
            "photography",
            "cooking",
            "recipes",
            "healthy-eating",
            "wellness",
            "technology",
        ]

        for tag_name in tags_data:
            tag = BlogTag(
                tag_id=str(uuid.uuid4()),
                name=tag_name.replace("-", " ").title(),
                slug=tag_name,
                description=f"Posts related to {tag_name.replace('-', ' ')}",
                usage_count=random.randint(5, 100),
                color=self.fake.color(),
            )
            tag.save()
            self.created_counts["blog_tags"] += 1

        self.stdout.write(f"🏷️  Created {len(tags_data)} blog tags")

    def create_blog_posts(self, count):
        """Create blog posts with realistic content"""
        categories = list(BlogCategory.objects.all())
        authors = list(BlogAuthor.objects.all())

        if not categories or not authors:
            self.stdout.write(
                self.style.WARNING(
                    "⚠️  Skipping blog posts - missing categories or authors"
                )
            )
            return

        for i in range(count):
            author = random.choice(authors)
            category = random.choice(categories)

            # Generate realistic post
            title = self.fake.sentence(nb_words=6).rstrip(".")
            is_published = random.choice([True, True, True, False])  # 75% published

            post = BlogPost(
                user_id=f"user_{author.author_id}",
                post_id=str(uuid.uuid4()),
                title=title,
                slug=title.lower().replace(" ", "-").replace(",", "").replace(".", ""),
                content=self.fake.text(max_nb_chars=2000),
                excerpt=self.fake.text(max_nb_chars=200),
                author=f"{author.first_name} {author.last_name}",
                category=category.name.lower(),
                is_published=is_published,
                published_date=(
                    self.fake.date_time_between(
                        start_date="-1y", end_date="now", tzinfo=timezone.utc
                    )
                    if is_published
                    else None
                ),
                created_date=self.fake.date_time_between(
                    start_date="-1y", end_date="now", tzinfo=timezone.utc
                ),
                view_count=random.randint(100, 5000) if is_published else 0,
                like_count=random.randint(10, 500) if is_published else 0,
                comment_count=random.randint(0, 50) if is_published else 0,
                tags=set(
                    random.sample(
                        [
                            "python",
                            "django",
                            "javascript",
                            "react",
                            "aws",
                            "database",
                            "productivity",
                            "career",
                            "remote-work",
                            "startups",
                        ],
                        k=random.randint(1, 3),
                    )
                ),
                is_featured=random.choice([True, False, False, False]),  # 25% featured
                featured_image_url=(
                    self.fake.image_url() if random.random() > 0.5 else ""
                ),
            )
            post.save()
            self.created_counts["blog_posts"] += 1

        self.stdout.write(f"📝 Created {count} blog posts")

    def create_blog_comments(self, count):
        """Create blog comments"""
        posts = list(BlogPost.objects.filter(is_published=True))

        if not posts:
            self.stdout.write(
                self.style.WARNING("⚠️  Skipping comments - no published posts")
            )
            return

        for i in range(count):
            post = random.choice(posts)

            comment = BlogComment(
                comment_id=str(uuid.uuid4()),
                post_id=post.post_id,
                parent_comment_id=None,  # For simplicity, no nested comments
                author_name=self.fake.name(),
                author_email=self.fake.email(),
                content=self.fake.text(max_nb_chars=300),
                is_approved=random.choice([True, True, True, False]),  # 75% approved
                is_spam=random.choice([False, False, False, True]),  # 25% spam
                like_count=random.randint(0, 20),
                reply_count=random.randint(0, 5),
                created_date=self.fake.date_time_between(
                    start_date=post.published_date or post.created_date,
                    end_date="now",
                    tzinfo=timezone.utc,
                ),
            )
            comment.save()
            self.created_counts["blog_comments"] += 1

        self.stdout.write(f"💬 Created {count} blog comments")

    def create_product_categories(self):
        """Create product categories"""
        categories_data = [
            {"name": "Electronics", "description": "Gadgets and electronic devices"},
            {"name": "Clothing", "description": "Fashion and apparel"},
            {"name": "Home & Garden", "description": "Home improvement and gardening"},
            {
                "name": "Sports & Outdoors",
                "description": "Sports equipment and outdoor gear",
            },
            {"name": "Books", "description": "Physical and digital books"},
            {"name": "Toys & Games", "description": "Toys, games, and hobbies"},
        ]

        for cat_data in categories_data:
            category = ProductCategory(
                category_id=str(uuid.uuid4()),
                name=cat_data["name"],
                slug=cat_data["name"].lower().replace(" ", "-").replace("&", "and"),
                description=cat_data["description"],
                parent_category_id=None,
                level=0,
                image_url=self.fake.image_url(),
                sort_order=len(self.created_counts) * 10,
                product_count=0,
                is_active=True,
                meta_title=f"Shop {cat_data['name']}",
                meta_description=cat_data["description"],
            )
            category.save()
            self.created_counts["product_categories"] += 1

        self.stdout.write(f"🛍️  Created {len(categories_data)} product categories")

    def create_products(self, count):
        """Create products with detailed attributes"""
        categories = list(ProductCategory.objects.all())
        brands = [
            "Apple",
            "Samsung",
            "Nike",
            "Adidas",
            "Sony",
            "Amazon",
            "Microsoft",
            "Google",
        ]

        if not categories:
            self.stdout.write(
                self.style.WARNING("⚠️  Skipping products - no categories")
            )
            return

        for i in range(count):
            category = random.choice(categories)
            brand = random.choice(brands)

            name = f"{brand} {self.fake.word().title()} {random.randint(100, 9999)}"
            price = Decimal(str(random.uniform(10.99, 999.99))).quantize(
                Decimal("0.01")
            )

            product = Product(
                product_id=str(uuid.uuid4()),
                sku=f"SKU{random.randint(100000, 999999)}",
                name=name,
                slug=name.lower().replace(" ", "-"),
                description=self.fake.text(max_nb_chars=1000),
                short_description=self.fake.text(max_nb_chars=200),
                category_id=category.category_id,
                brand=brand,
                manufacturer=brand,
                price=price,
                sale_price=(
                    price * Decimal("0.85") if random.random() < 0.3 else None
                ),  # 30% on sale
                cost_price=price * Decimal("0.6"),  # 40% margin
                stock_quantity=random.randint(0, 500),
                low_stock_threshold=random.randint(5, 20),
                is_available=random.choice([True, True, True, False]),  # 75% available
                is_digital=random.choice([False, False, False, True]),  # 25% digital
                attributes={
                    "color": random.choice(["Black", "White", "Red", "Blue", "Silver"]),
                    "size": (
                        random.choice(["S", "M", "L", "XL"])
                        if category.name == "Clothing"
                        else None
                    ),
                    "weight": f"{random.uniform(0.5, 50.0):.1f} lbs",
                },
                specifications={
                    "warranty": f"{random.randint(1, 3)} years",
                    "model": f"Model-{random.randint(1000, 9999)}",
                },
                image_url=self.fake.image_url(),
                gallery_images=[
                    self.fake.image_url() for _ in range(random.randint(1, 4))
                ],
                meta_title=f"Buy {name} - Best Price",
                meta_description=f"Shop {name} with free shipping and warranty.",
                tags=set(
                    random.sample(
                        ["premium", "bestseller", "new", "featured", "eco-friendly"],
                        k=random.randint(1, 3),
                    )
                ),
                rating=Decimal(str(random.uniform(3.0, 5.0))).quantize(Decimal("0.1")),
                review_count=random.randint(0, 500),
                view_count=random.randint(100, 10000),
                purchase_count=random.randint(0, 200),
                wishlist_count=random.randint(0, 100),
                is_featured=random.choice([True, False, False, False]),  # 25% featured
                is_new_arrival=random.choice([True, False, False, False]),  # 25% new
                is_bestseller=random.choice(
                    [True, False, False, False]
                ),  # 25% bestseller
                created_date=self.fake.date_time_between(
                    start_date="-2y", end_date="now", tzinfo=timezone.utc
                ),
            )
            product.save()
            self.created_counts["products"] += 1

        self.stdout.write(f"📦 Created {count} products")

    def create_customers(self, count):
        """Create customer profiles"""
        tiers = ["bronze", "silver", "gold", "platinum", "vip"]

        for i in range(count):
            customer = Customer(
                customer_id=str(uuid.uuid4()),
                email=self.fake.email(),
                first_name=self.fake.first_name(),
                last_name=self.fake.last_name(),
                phone=self.fake.phone_number(),
                birth_date=self.fake.date_of_birth(minimum_age=18, maximum_age=80),
                default_shipping_address={
                    "street": self.fake.street_address(),
                    "city": self.fake.city(),
                    "state": self.fake.state(),
                    "zip": self.fake.zipcode(),
                    "country": "US",
                },
                default_billing_address={
                    "street": self.fake.street_address(),
                    "city": self.fake.city(),
                    "state": self.fake.state(),
                    "zip": self.fake.zipcode(),
                    "country": "US",
                },
                total_orders=random.randint(0, 50),
                total_spent=Decimal(str(random.uniform(0, 5000))).quantize(
                    Decimal("0.01")
                ),
                average_order_value=Decimal(str(random.uniform(50, 300))).quantize(
                    Decimal("0.01")
                ),
                customer_tier=random.choice(tiers),
                loyalty_points=random.randint(0, 5000),
                email_marketing=random.choice([True, False]),
                sms_marketing=random.choice([True, False]),
                preferred_language="en",
                is_active=random.choice([True, True, True, False]),  # 75% active
                account_created=self.fake.date_time_between(
                    start_date="-3y", end_date="-1d", tzinfo=timezone.utc
                ),
                last_order_date=(
                    self.fake.date_time_between(
                        start_date="-6m", end_date="now", tzinfo=timezone.utc
                    )
                    if random.random() > 0.3
                    else None
                ),
                last_login_date=(
                    self.fake.date_time_between(
                        start_date="-1m", end_date="now", tzinfo=timezone.utc
                    )
                    if random.random() > 0.2
                    else None
                ),
            )
            customer.save()
            self.created_counts["customers"] += 1

        self.stdout.write(f"👥 Created {count} customers")

    def create_orders(self, count):
        """Create orders with order items"""
        customers = list(Customer.objects.all())
        products = list(Product.objects.all())
        statuses = [
            "pending",
            "paid",
            "processing",
            "shipped",
            "delivered",
            "cancelled",
        ]

        if not customers or not products:
            self.stdout.write(
                self.style.WARNING(
                    "⚠️  Skipping orders - missing customers or products"
                )
            )
            return

        for i in range(count):
            customer = random.choice(customers)
            order_date = self.fake.date_time_between(
                start_date="-1y", end_date="now", tzinfo=timezone.utc
            )

            # Create order
            order = Order(
                order_id=f"ORD{random.randint(100000, 999999)}",
                order_date=order_date,
                customer_email=customer.email,
                customer_name=customer.full_name,
                customer_phone=customer.phone,
                status=random.choice(statuses),
                subtotal=Decimal("0.00"),
                tax_amount=Decimal("0.00"),
                shipping_cost=Decimal("9.99"),
                discount_amount=Decimal("0.00"),
                total_amount=Decimal("0.00"),
                item_count=0,
                weight_total=Decimal("0.00"),
                shipping_address=customer.default_shipping_address,
                billing_address=customer.default_billing_address,
                shipping_method=random.choice(["Standard", "Express", "Overnight"]),
                tracking_number=(
                    f"TRK{random.randint(100000000, 999999999)}"
                    if random.random() > 0.5
                    else ""
                ),
                payment_method=random.choice(
                    ["Credit Card", "PayPal", "Apple Pay", "Google Pay"]
                ),
                payment_status=random.choice(["pending", "captured", "failed"]),
                transaction_id=f"TXN{random.randint(100000000, 999999999)}",
                customer_notes=(
                    self.fake.text(max_nb_chars=100) if random.random() > 0.7 else ""
                ),
                admin_notes=(
                    self.fake.text(max_nb_chars=100) if random.random() > 0.8 else ""
                ),
            )

            # Add order items
            num_items = random.randint(1, 5)
            subtotal = Decimal("0.00")

            for item_seq in range(num_items):
                product = random.choice(products)
                quantity = random.randint(1, 3)
                unit_price = product.effective_price
                total_price = unit_price * quantity
                subtotal += total_price

                order_item = OrderItem(
                    item_id=str(uuid.uuid4()),
                    order_id=order.order_id,
                    product_id=product.product_id,
                    item_sequence=item_seq + 1,
                    product_name=product.name,
                    product_sku=product.sku,
                    unit_price=unit_price,
                    quantity=quantity,
                    total_price=total_price,
                    product_attributes=product.attributes,
                    created_date=order_date,
                )
                order_item.save()
                self.created_counts["order_items"] += 1

            # Update order totals
            order.subtotal = subtotal
            order.tax_amount = subtotal * Decimal("0.08")  # 8% tax
            order.total_amount = order.subtotal + order.tax_amount + order.shipping_cost
            order.item_count = num_items

            # Set shipping dates based on status
            if order.status in ["shipped", "delivered"]:
                order.shipped_date = order_date + timedelta(days=random.randint(1, 3))
            if order.status == "delivered":
                order.delivered_date = order.shipped_date + timedelta(
                    days=random.randint(1, 7)
                )

            order.save()
            self.created_counts["orders"] += 1

        self.stdout.write(f"🛒 Created {count} orders with order items")

    def print_summary(self):
        """Print creation summary"""
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write(self.style.SUCCESS("🎉 Demo Data Generation Complete!"))
        self.stdout.write("=" * 50)

        total_items = sum(self.created_counts.values())

        for item_type, count in self.created_counts.items():
            if count > 0:
                self.stdout.write(f'  {item_type.replace("_", " ").title()}: {count}')

        self.stdout.write(f"\nTotal items created: {total_items}")

        self.stdout.write("\n📋 Access Information:")
        self.stdout.write("  Django Admin: http://localhost:8001/admin/")
        self.stdout.write("  Username: admin")
        self.stdout.write("  Password: admin123")
        self.stdout.write("  DynamoDB Admin UI: http://localhost:8002/")

        self.stdout.write("\n🚀 Start the demo with:")
        self.stdout.write("  docker-compose -f docker-compose.dev.yml up")
        self.stdout.write("")
