# E-commerce Admin Configuration - Advanced DynamoDB Features

from django.contrib import admin
from django.utils.html import format_html
from dynamodb_adapter.admin import DynamoDBAdmin
from dynamodb_adapter.admin_inlines import DynamoDBTabularInline

from .models import Customer, Order, OrderItem, Product, ProductCategory


class OrderItemInline(DynamoDBTabularInline):
    """Inline order items with batch optimization"""

    model = OrderItem
    fk_name = "order_id"
    fields = ("product_name", "product_sku", "quantity", "unit_price", "total_price")
    readonly_fields = ("total_price",)
    extra = 0
    max_num_items = 15

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.order_by("item_sequence")


@admin.register(Product)
class ProductAdmin(DynamoDBAdmin):
    """
    Advanced product management with inventory and pricing
    """

    list_display = [
        "name",
        "sku",
        "brand",
        "category_preview",
        "price_display",
        "stock_status",
        "rating_display",
        "is_featured",
        "is_available",
    ]
    list_display_links = ["name", "sku"]
    list_editable = ["is_featured", "is_available"]

    list_filter = [
        "is_available",
        "is_featured",
        "is_new_arrival",
        "is_bestseller",
        "brand",
        "category_id",
        "created_date",
    ]

    search_fields = ["name", "sku", "brand", "description", "tags"]

    fieldsets = (
        (
            "Product Information",
            {
                "fields": ("name", "slug", "sku", "description", "short_description"),
                "classes": ("wide",),
            },
        ),
        (
            "Categorization",
            {
                "fields": ("category_id", "brand", "manufacturer", "tags"),
                "classes": ("collapse",),
            },
        ),
        (
            "Pricing",
            {"fields": ("price", "sale_price", "cost_price"), "classes": ("collapse",)},
        ),
        (
            "Inventory",
            {
                "fields": (
                    "stock_quantity",
                    "low_stock_threshold",
                    "is_available",
                    "is_digital",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Attributes",
            {
                "fields": ("attributes", "specifications"),
                "classes": ("collapse",),
                "description": "Flexible product attributes and specifications (JSON format)",
            },
        ),
        (
            "Media",
            {"fields": ("image_url", "gallery_images"), "classes": ("collapse",)},
        ),
        (
            "Marketing",
            {
                "fields": ("is_featured", "is_new_arrival", "is_bestseller"),
                "classes": ("collapse",),
            },
        ),
        (
            "SEO",
            {"fields": ("meta_title", "meta_description"), "classes": ("collapse",)},
        ),
        (
            "Statistics",
            {
                "fields": (
                    "rating",
                    "review_count",
                    "view_count",
                    "purchase_count",
                    "wishlist_count",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    readonly_fields = [
        "created_date",
        "updated_date",
        "view_count",
        "purchase_count",
        "review_count",
        "wishlist_count",
        "rating",
    ]
    prepopulated_fields = {"slug": ("name",)}

    # Advanced filtering using GSI
    def get_queryset(self, request):
        qs = super().get_queryset(request)

        # Use category-price-index for category-based browsing
        if request.GET.get("category_id"):
            return qs.filter(category_id=request.GET["category_id"]).order_by("price")

        # Use brand-name-index for brand searches
        if request.GET.get("brand"):
            return qs.filter(brand=request.GET["brand"]).order_by("name")

        return qs

    def category_preview(self, obj):
        return f"Category {obj.category_id}"

    category_preview.short_description = "Category"

    def price_display(self, obj):
        if obj.sale_price and obj.sale_price < obj.price:
            return format_html(
                '<span style="text-decoration: line-through;">${}</span> '
                '<strong style="color: red;">${}</strong> ({}% off)',
                obj.price,
                obj.sale_price,
                obj.discount_percentage,
            )
        return f"${obj.price}"

    price_display.short_description = "Price"

    def stock_status(self, obj):
        if obj.stock_quantity <= 0:
            return format_html('<span style="color: red;">Out of Stock</span>')
        elif obj.is_low_stock:
            return format_html(
                '<span style="color: orange;">Low Stock ({})</span>', obj.stock_quantity
            )
        else:
            return format_html(
                '<span style="color: green;">In Stock ({})</span>', obj.stock_quantity
            )

    stock_status.short_description = "Stock"

    def rating_display(self, obj):
        stars = "★" * int(obj.rating) + "☆" * (5 - int(obj.rating))
        return format_html("{} ({} reviews)", stars, obj.review_count)

    rating_display.short_description = "Rating"

    actions = [
        "mark_featured",
        "mark_bestseller",
        "apply_discount",
        "update_stock",
        "export_catalog",
        "check_inventory",
    ]

    def mark_featured(self, request, queryset):
        updated = 0
        for product in queryset:
            if not product.is_featured:
                product.is_featured = True
                product.save()
                updated += 1
        self.message_user(request, f"Marked {updated} products as featured.")

    mark_featured.short_description = "Mark as featured"

    def apply_discount(self, request, queryset):
        """Custom action with confirmation - applies 20% discount"""
        for product in queryset:
            if not product.sale_price or product.sale_price >= product.price:
                product.sale_price = product.price * Decimal("0.8")  # 20% off
                product.save()

        self.message_user(
            request, f"Applied 20% discount to {queryset.count()} products."
        )

    apply_discount.short_description = "Apply 20% discount"


@admin.register(ProductCategory)
class ProductCategoryAdmin(DynamoDBAdmin):
    """Category management with hierarchy"""

    list_display = [
        "name",
        "slug",
        "level",
        "parent_preview",
        "product_count",
        "is_active",
    ]
    list_editable = ["is_active", "sort_order"]
    list_filter = ["is_active", "level"]
    search_fields = ["name", "slug", "description"]

    fieldsets = (
        (
            "Category Information",
            {"fields": ("name", "slug", "description", "parent_category_id", "level")},
        ),
        (
            "Display",
            {
                "fields": ("image_url", "icon_class", "sort_order", "is_active"),
                "classes": ("collapse",),
            },
        ),
        (
            "SEO",
            {"fields": ("meta_title", "meta_description"), "classes": ("collapse",)},
        ),
        ("Statistics", {"fields": ("product_count",), "classes": ("collapse",)}),
    )

    readonly_fields = ["product_count"]
    prepopulated_fields = {"slug": ("name",)}

    def parent_preview(self, obj):
        return obj.parent_category_id or "Root"

    parent_preview.short_description = "Parent"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Use parent-name-index for hierarchical browsing
        return qs.order_by("level", "name")


@admin.register(Order)
class OrderAdmin(DynamoDBAdmin):
    """
    Comprehensive order management with workflow support
    """

    list_display = [
        "order_id",
        "customer_name",
        "status_display",
        "total_amount",
        "item_count",
        "payment_status",
        "order_date",
        "shipped_date",
    ]
    list_display_links = ["order_id"]
    list_editable = ["status"]

    list_filter = [
        "status",
        "payment_status",
        "order_date",
        "shipped_date",
        "shipping_method",
        "payment_method",
    ]

    search_fields = ["order_id", "customer_email", "customer_name", "tracking_number"]

    fieldsets = (
        (
            "Order Information",
            {"fields": ("order_id", "order_date", "status", "customer_notes")},
        ),
        (
            "Customer",
            {
                "fields": ("customer_email", "customer_name", "customer_phone"),
                "classes": ("collapse",),
            },
        ),
        (
            "Financial",
            {
                "fields": (
                    "subtotal",
                    "tax_amount",
                    "shipping_cost",
                    "discount_amount",
                    "total_amount",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Payment",
            {
                "fields": ("payment_method", "payment_status", "transaction_id"),
                "classes": ("collapse",),
            },
        ),
        (
            "Shipping",
            {
                "fields": (
                    "shipping_address",
                    "billing_address",
                    "shipping_method",
                    "tracking_number",
                    "shipped_date",
                    "delivered_date",
                    "estimated_delivery",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Order Details",
            {"fields": ("item_count", "weight_total"), "classes": ("collapse",)},
        ),
        ("Admin", {"fields": ("admin_notes",), "classes": ("collapse",)}),
    )

    readonly_fields = ["order_date", "updated_date", "item_count"]
    inlines = [OrderItemInline]

    # GSI optimization for order queries
    def get_queryset(self, request):
        qs = super().get_queryset(request)

        # Use customer-date-index for customer order history
        if request.GET.get("customer_email"):
            return qs.filter(customer_email=request.GET["customer_email"]).order_by(
                "-order_date"
            )

        # Use status-date-index for status-based filtering
        if request.GET.get("status"):
            return qs.filter(status=request.GET["status"]).order_by("-order_date")

        return qs.order_by("-order_date")

    def status_display(self, obj):
        colors = {
            "pending": "orange",
            "paid": "blue",
            "processing": "purple",
            "shipped": "green",
            "delivered": "darkgreen",
            "cancelled": "red",
            "refunded": "gray",
        }
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            colors.get(obj.status, "black"),
            obj.get_status_display(),
        )

    status_display.short_description = "Status"

    actions = [
        "mark_as_processing",
        "mark_as_shipped",
        "send_tracking_email",
        "export_orders",
        "generate_shipping_labels",
    ]

    def mark_as_processing(self, request, queryset):
        updated = 0
        for order in queryset:
            if order.status in ["pending", "paid"]:
                order.status = "processing"
                order.save()
                updated += 1

        self.message_user(request, f"Marked {updated} orders as processing.")

    mark_as_processing.short_description = "Mark as processing"

    def mark_as_shipped(self, request, queryset):
        from datetime import datetime, timezone

        updated = 0
        for order in queryset:
            if order.status == "processing":
                order.status = "shipped"
                order.shipped_date = datetime.now(timezone.utc)
                # In real implementation, would generate tracking number
                order.tracking_number = f"TRK{order.order_id}"
                order.save()
                updated += 1

        self.message_user(
            request, f"Marked {updated} orders as shipped with tracking numbers."
        )

    mark_as_shipped.short_description = "Mark as shipped"


@admin.register(Customer)
class CustomerAdmin(DynamoDBAdmin):
    """Customer relationship management"""

    list_display = [
        "email",
        "full_name",
        "customer_tier",
        "total_orders",
        "total_spent",
        "loyalty_points",
        "last_order_date",
        "is_active",
    ]
    list_display_links = ["email", "full_name"]
    list_editable = ["customer_tier", "is_active"]

    list_filter = [
        "customer_tier",
        "is_active",
        "email_marketing",
        "sms_marketing",
        "account_created",
        "last_order_date",
    ]

    search_fields = ["email", "first_name", "last_name", "phone"]

    fieldsets = (
        (
            "Personal Information",
            {"fields": ("email", "first_name", "last_name", "phone", "birth_date")},
        ),
        (
            "Customer Status",
            {
                "fields": ("customer_tier", "loyalty_points", "is_active"),
                "classes": ("collapse",),
            },
        ),
        (
            "Purchase History",
            {
                "fields": ("total_orders", "total_spent", "average_order_value"),
                "classes": ("collapse",),
            },
        ),
        (
            "Preferences",
            {
                "fields": ("email_marketing", "sms_marketing", "preferred_language"),
                "classes": ("collapse",),
            },
        ),
        (
            "Addresses",
            {
                "fields": ("default_shipping_address", "default_billing_address"),
                "classes": ("collapse",),
            },
        ),
        (
            "Account Info",
            {
                "fields": ("account_created", "last_order_date", "last_login_date"),
                "classes": ("collapse",),
            },
        ),
    )

    readonly_fields = [
        "account_created",
        "last_order_date",
        "last_login_date",
        "total_orders",
        "total_spent",
        "average_order_value",
    ]

    def get_queryset(self, request):
        qs = super().get_queryset(request)

        # Use tier-spent-index for VIP customer analysis
        if request.GET.get("customer_tier"):
            return qs.filter(customer_tier=request.GET["customer_tier"]).order_by(
                "-total_spent"
            )

        return qs.order_by("-total_spent")

    actions = [
        "upgrade_to_silver",
        "upgrade_to_gold",
        "send_loyalty_bonus",
        "export_customer_data",
        "send_marketing_email",
    ]

    def upgrade_to_silver(self, request, queryset):
        updated = 0
        for customer in queryset:
            if customer.customer_tier == "bronze" and customer.total_spent >= Decimal(
                "500"
            ):
                customer.customer_tier = "silver"
                customer.loyalty_points += 100  # Bonus for upgrade
                customer.save()
                updated += 1

        self.message_user(request, f"Upgraded {updated} customers to Silver tier.")

    upgrade_to_silver.short_description = "Upgrade eligible customers to Silver"
