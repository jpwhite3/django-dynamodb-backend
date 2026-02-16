# E-commerce Demo Models - Advanced DynamoDB Patterns

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from django_dynamodb_backend.fields import (
    BooleanField,
    CharField,
    DateTimeField,
    DecimalField,
    DictField,
    IntegerField,
    ListField,
    SetField,
    TextField,
)
from django_dynamodb_backend.models import DynamoDBModel


class Product(DynamoDBModel):
    """
    Product catalog demonstrating:
    - Complex pricing and inventory management
    - Category hierarchies with GSI
    - Search optimization patterns
    - Variant management (size, color, etc.)
    """

    class Meta:
        table_name = "demo_products"
        global_secondary_indexes = [
            {
                "index_name": "category-price-index",
                "partition_key": "category_id",
                "sort_key": "price",
                "projection_type": "ALL",
            },
            {
                "index_name": "brand-name-index",
                "partition_key": "brand",
                "sort_key": "name",
                "projection_type": "INCLUDE",
                "non_key_attributes": ["price", "rating", "image_url"],
            },
            {
                "index_name": "availability-index",
                "partition_key": "is_available",
                "sort_key": "created_date",
                "projection_type": "KEYS_ONLY",
            },
        ]

    # Primary key
    product_id = CharField(max_length=50, primary_key=True)
    sku = CharField(max_length=50, sort_key=True, unique=True)

    # Basic information
    name = CharField(max_length=200)
    slug = CharField(max_length=200, unique=True)
    description = TextField()
    short_description = TextField(max_length=300, blank=True)

    # Categorization
    category_id = CharField(max_length=50)
    brand = CharField(max_length=100)
    manufacturer = CharField(max_length=100, blank=True)

    # Pricing
    price = DecimalField(max_digits=10, decimal_places=2)
    sale_price = DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    cost_price = DecimalField(
        max_digits=10, decimal_places=2
    )  # For profit calculations

    # Inventory
    stock_quantity = IntegerField(default=0)
    low_stock_threshold = IntegerField(default=10)
    is_available = BooleanField(default=True)
    is_digital = BooleanField(default=False)

    # Product attributes (flexible JSON storage)
    attributes = DictField(default=dict)  # color, size, weight, dimensions, etc.
    specifications = DictField(default=dict)  # technical specs

    # Images and media
    image_url = CharField(max_length=500, blank=True)
    gallery_images = ListField(base_field=CharField(max_length=500), default=list)

    # SEO and marketing
    meta_title = CharField(max_length=200, blank=True)
    meta_description = TextField(max_length=300, blank=True)
    tags = SetField(base_field=CharField(max_length=30), default=set)

    # Reviews and ratings
    rating = DecimalField(max_digits=3, decimal_places=2, default=Decimal("0.00"))
    review_count = IntegerField(default=0)

    # Sales metrics
    view_count = IntegerField(default=0)
    purchase_count = IntegerField(default=0)
    wishlist_count = IntegerField(default=0)

    # Status
    is_featured = BooleanField(default=False)
    is_new_arrival = BooleanField(default=False)
    is_bestseller = BooleanField(default=False)

    # Timestamps
    created_date = DateTimeField(auto_now_add=True)
    updated_date = DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.sku})"

    @property
    def effective_price(self):
        """Return sale price if available, otherwise regular price"""
        return self.sale_price if self.sale_price else self.price

    @property
    def discount_percentage(self):
        """Calculate discount percentage"""
        if self.sale_price and self.price > self.sale_price:
            return round(((self.price - self.sale_price) / self.price) * 100, 1)
        return 0

    @property
    def is_low_stock(self):
        """Check if product is low in stock"""
        return self.stock_quantity <= self.low_stock_threshold


class ProductCategory(DynamoDBModel):
    """Product categories with hierarchical structure"""

    class Meta:
        table_name = "demo_product_categories"
        global_secondary_indexes = [
            {
                "index_name": "parent-name-index",
                "partition_key": "parent_category_id",
                "sort_key": "name",
                "projection_type": "ALL",
            }
        ]

    category_id = CharField(max_length=50, primary_key=True)

    name = CharField(max_length=100)
    slug = CharField(max_length=100, unique=True)
    description = TextField(blank=True)

    # Hierarchy
    parent_category_id = CharField(max_length=50, null=True, blank=True)
    level = IntegerField(default=0)  # 0=root, 1=subcategory, etc.

    # Display
    image_url = CharField(max_length=500, blank=True)
    icon_class = CharField(max_length=50, blank=True)
    sort_order = IntegerField(default=0)

    # Statistics
    product_count = IntegerField(default=0)

    # SEO
    meta_title = CharField(max_length=200, blank=True)
    meta_description = TextField(max_length=300, blank=True)

    # Status
    is_active = BooleanField(default=True)

    def __str__(self):
        return self.name


class Order(DynamoDBModel):
    """
    Order management demonstrating:
    - Complex order states and workflows
    - Customer relationship patterns
    - Payment and shipping integration
    - Order item management
    """

    class Meta:
        table_name = "demo_orders"
        global_secondary_indexes = [
            {
                "index_name": "customer-date-index",
                "partition_key": "customer_email",
                "sort_key": "order_date",
                "projection_type": "ALL",
            },
            {
                "index_name": "status-date-index",
                "partition_key": "status",
                "sort_key": "order_date",
                "projection_type": "INCLUDE",
                "non_key_attributes": ["total_amount", "customer_email", "item_count"],
            },
        ]

    # Primary key
    order_id = CharField(max_length=50, primary_key=True)
    order_date = DateTimeField(sort_key=True, auto_now_add=True)

    # Customer information
    customer_email = CharField(max_length=200)
    customer_name = CharField(max_length=200)
    customer_phone = CharField(max_length=20, blank=True)

    # Order status
    status = CharField(
        max_length=20,
        choices=[
            ("pending", "Pending Payment"),
            ("paid", "Paid"),
            ("processing", "Processing"),
            ("shipped", "Shipped"),
            ("delivered", "Delivered"),
            ("cancelled", "Cancelled"),
            ("refunded", "Refunded"),
        ],
        default="pending",
    )

    # Financial information
    subtotal = DecimalField(max_digits=10, decimal_places=2)
    tax_amount = DecimalField(max_digits=10, decimal_places=2)
    shipping_cost = DecimalField(max_digits=10, decimal_places=2)
    discount_amount = DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    total_amount = DecimalField(max_digits=10, decimal_places=2)

    # Order details
    item_count = IntegerField(default=0)
    weight_total = DecimalField(max_digits=8, decimal_places=2, default=Decimal("0.00"))

    # Shipping information
    shipping_address = DictField(default=dict)  # street, city, state, zip, country
    billing_address = DictField(default=dict)  # Same structure
    shipping_method = CharField(max_length=50, blank=True)
    tracking_number = CharField(max_length=100, blank=True)

    # Payment information
    payment_method = CharField(max_length=50, blank=True)
    payment_status = CharField(
        max_length=20,
        choices=[
            ("pending", "Pending"),
            ("authorized", "Authorized"),
            ("captured", "Captured"),
            ("failed", "Failed"),
            ("refunded", "Refunded"),
        ],
        default="pending",
    )
    transaction_id = CharField(max_length=100, blank=True)

    # Fulfillment
    shipped_date = DateTimeField(null=True, blank=True)
    delivered_date = DateTimeField(null=True, blank=True)
    estimated_delivery = DateTimeField(null=True, blank=True)

    # Notes and communication
    customer_notes = TextField(blank=True)
    admin_notes = TextField(blank=True)

    # Timestamps
    updated_date = DateTimeField(auto_now=True)

    def __str__(self):
        return f"Order #{self.order_id} - {self.customer_email}"

    @property
    def can_cancel(self):
        """Check if order can be cancelled"""
        return self.status in ["pending", "paid"]

    @property
    def is_completed(self):
        """Check if order is completed"""
        return self.status == "delivered"


class OrderItem(DynamoDBModel):
    """Individual items within an order"""

    class Meta:
        table_name = "demo_order_items"
        global_secondary_indexes = [
            {
                "index_name": "order-index",
                "partition_key": "order_id",
                "sort_key": "item_sequence",
                "projection_type": "ALL",
            },
            {
                "index_name": "product-date-index",
                "partition_key": "product_id",
                "sort_key": "created_date",
                "projection_type": "KEYS_ONLY",
            },
        ]

    # Primary key
    item_id = CharField(max_length=50, primary_key=True)
    created_date = DateTimeField(sort_key=True, auto_now_add=True)

    # Relationships
    order_id = CharField(max_length=50)
    product_id = CharField(max_length=50)

    # Item details
    item_sequence = IntegerField()  # Order within the order
    product_name = CharField(max_length=200)  # Snapshot at time of order
    product_sku = CharField(max_length=50)

    # Pricing (snapshot)
    unit_price = DecimalField(max_digits=10, decimal_places=2)
    quantity = IntegerField()
    total_price = DecimalField(max_digits=10, decimal_places=2)

    # Product attributes at time of purchase
    product_attributes = DictField(default=dict)  # color, size, etc.

    def __str__(self):
        return f"{self.product_name} x{self.quantity} in Order #{self.order_id}"


class Customer(DynamoDBModel):
    """Customer profiles and purchase history"""

    class Meta:
        table_name = "demo_customers"
        global_secondary_indexes = [
            {
                "index_name": "email-index",
                "partition_key": "email",
                "projection_type": "ALL",
            },
            {
                "index_name": "tier-spent-index",
                "partition_key": "customer_tier",
                "sort_key": "total_spent",
                "projection_type": "INCLUDE",
                "non_key_attributes": ["first_name", "last_name", "email"],
            },
        ]

    # Primary key
    customer_id = CharField(max_length=50, primary_key=True)

    # Basic information
    email = CharField(max_length=200, unique=True)
    first_name = CharField(max_length=100)
    last_name = CharField(max_length=100)
    phone = CharField(max_length=20, blank=True)
    birth_date = DateTimeField(null=True, blank=True)

    # Addresses
    default_shipping_address = DictField(default=dict)
    default_billing_address = DictField(default=dict)

    # Customer metrics
    total_orders = IntegerField(default=0)
    total_spent = DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    average_order_value = DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )

    # Customer tier/loyalty
    customer_tier = CharField(
        max_length=20,
        choices=[
            ("bronze", "Bronze"),
            ("silver", "Silver"),
            ("gold", "Gold"),
            ("platinum", "Platinum"),
            ("vip", "VIP"),
        ],
        default="bronze",
    )
    loyalty_points = IntegerField(default=0)

    # Preferences
    email_marketing = BooleanField(default=True)
    sms_marketing = BooleanField(default=False)
    preferred_language = CharField(max_length=10, default="en")

    # Account status
    is_active = BooleanField(default=True)
    account_created = DateTimeField(auto_now_add=True)
    last_order_date = DateTimeField(null=True, blank=True)
    last_login_date = DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def is_vip(self):
        """Check if customer is VIP tier"""
        return self.customer_tier in ["platinum", "vip"]
