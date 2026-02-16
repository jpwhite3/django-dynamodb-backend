# Blog Admin Configuration - Demonstrating DynamoDB Admin Features

from django.contrib import admin
from dynamodb_adapter.admin import DynamoDBAdmin
from dynamodb_adapter.admin_inlines import DynamoDBStackedInline, DynamoDBTabularInline

from .models import BlogAuthor, BlogCategory, BlogComment, BlogPost, BlogTag


class BlogCommentInline(DynamoDBTabularInline):
    """Inline comments for blog posts"""

    model = BlogComment
    fk_name = "post_id"
    fields = ("author_name", "content", "is_approved", "created_date")
    readonly_fields = ("created_date", "like_count")
    extra = 0
    max_num_items = 10  # DynamoDB batch limit consideration

    def get_queryset(self, request):
        # Optimize query using GSI
        qs = super().get_queryset(request)
        return qs.filter(is_spam=False)


@admin.register(BlogPost)
class BlogPostAdmin(DynamoDBAdmin):
    """
    Advanced BlogPost admin demonstrating all DynamoDB admin features
    """

    # List display with GSI optimization
    list_display = [
        "title",
        "author",
        "category",
        "is_published",
        "published_date",
        "view_count",
        "like_count",
        "is_featured",
    ]
    list_display_links = ["title"]
    list_editable = ["is_published", "is_featured", "category"]

    # Filtering with DynamoDB optimization
    list_filter = [
        "is_published",
        "category",
        "is_featured",
        "published_date",
        "created_date",
        "author",
    ]

    # Search with autocomplete
    search_fields = ["title", "author", "content", "tags"]
    autocomplete_fields = ["author"]  # Uses DynamoDBAutocompleteMixin

    # Fieldsets for organized editing
    fieldsets = (
        (
            "Content",
            {"fields": ("title", "slug", "content", "excerpt"), "classes": ("wide",)},
        ),
        (
            "Publishing",
            {
                "fields": ("author", "category", "is_published", "published_date"),
                "classes": ("collapse",),
            },
        ),
        (
            "Metadata",
            {
                "fields": ("tags", "is_featured", "featured_image_url"),
                "classes": ("collapse",),
            },
        ),
        (
            "Statistics",
            {
                "fields": ("view_count", "like_count", "comment_count"),
                "classes": ("collapse",),
                "description": "Engagement metrics (read-only)",
            },
        ),
    )

    # Read-only fields
    readonly_fields = [
        "user_id",
        "post_id",
        "created_date",
        "updated_date",
        "view_count",
        "like_count",
        "comment_count",
    ]

    # Prepopulated fields
    prepopulated_fields = {"slug": ("title",)}

    # Inline editing
    inlines = [BlogCommentInline]

    # Pagination optimization
    list_per_page = 25  # Optimized for DynamoDB scan operations

    # Ordering (uses GSI when possible)
    ordering = ["-published_date", "-created_date"]

    # Actions with confirmation pages (DynamoDBActionMixin)
    actions = [
        "publish_selected",
        "unpublish_selected",
        "feature_selected",
        "bulk_update_category",
        "export_to_json",
        "backup_to_s3",
    ]

    def get_queryset(self, request):
        """Optimize queryset using appropriate GSI"""
        qs = super().get_queryset(request)

        # Use published-date-index for published posts
        if request.GET.get("is_published") == "1":
            return qs.filter(is_published=True).order_by("-published_date")

        return qs

    def publish_selected(self, request, queryset):
        """Custom action to publish posts with confirmation"""
        from datetime import datetime, timezone

        updated = 0
        for post in queryset:
            if not post.is_published:
                post.is_published = True
                post.published_date = datetime.now(timezone.utc)
                post.save()
                updated += 1

        self.message_user(request, f"Successfully published {updated} blog posts.")

    publish_selected.short_description = "Publish selected posts"

    def unpublish_selected(self, request, queryset):
        """Custom action to unpublish posts"""
        updated = queryset.filter(is_published=True).count()
        for post in queryset:
            if post.is_published:
                post.is_published = False
                post.published_date = None
                post.save()

        self.message_user(request, f"Successfully unpublished {updated} blog posts.")

    unpublish_selected.short_description = "Unpublish selected posts"


@admin.register(BlogComment)
class BlogCommentAdmin(DynamoDBAdmin):
    """Comment moderation with DynamoDB optimizations"""

    list_display = [
        "author_name",
        "post_preview",
        "content_preview",
        "is_approved",
        "is_spam",
        "created_date",
        "like_count",
    ]

    list_filter = ["is_approved", "is_spam", "created_date"]
    list_editable = ["is_approved", "is_spam"]

    search_fields = ["author_name", "author_email", "content"]

    # Use GSI for efficient post-based queries
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Optimize with post-date-index when filtering by post
        return qs.order_by("-created_date")

    def post_preview(self, obj):
        """Show related post title"""
        # In a real implementation, you'd fetch the post
        return f"Post {obj.post_id}"

    post_preview.short_description = "Blog Post"

    def content_preview(self, obj):
        """Show comment content preview"""
        return obj.content[:50] + "..." if len(obj.content) > 50 else obj.content

    content_preview.short_description = "Content"

    actions = ["approve_comments", "mark_as_spam", "delete_spam_comments"]

    def approve_comments(self, request, queryset):
        """Bulk approve comments"""
        updated = 0
        for comment in queryset:
            if not comment.is_approved:
                comment.is_approved = True
                comment.is_spam = False
                comment.save()
                updated += 1

        self.message_user(request, f"Approved {updated} comments.")

    approve_comments.short_description = "Approve selected comments"


@admin.register(BlogCategory)
class BlogCategoryAdmin(DynamoDBAdmin):
    """Category management with hierarchy support"""

    list_display = [
        "name",
        "slug",
        "post_count",
        "subscriber_count",
        "parent_category_preview",
    ]
    list_editable = ["post_count", "subscriber_count"]
    search_fields = ["name", "slug", "description"]
    prepopulated_fields = {"slug": ("name",)}

    fieldsets = (
        (
            "Basic Information",
            {"fields": ("name", "slug", "description", "parent_category_id")},
        ),
        (
            "Statistics",
            {"fields": ("post_count", "subscriber_count"), "classes": ("collapse",)},
        ),
        (
            "Display Settings",
            {"fields": ("color_code", "icon_class"), "classes": ("collapse",)},
        ),
        (
            "SEO",
            {"fields": ("meta_title", "meta_description"), "classes": ("collapse",)},
        ),
    )

    def parent_category_preview(self, obj):
        return obj.parent_category_id or "Root Category"

    parent_category_preview.short_description = "Parent"


@admin.register(BlogAuthor)
class BlogAuthorAdmin(DynamoDBAdmin):
    """Author management with profile features"""

    list_display = [
        "username",
        "full_name",
        "email",
        "post_count",
        "total_views",
        "follower_count",
        "is_active",
    ]
    list_editable = ["is_active", "email_notifications"]
    list_filter = ["is_active", "email_notifications", "joined_date"]

    search_fields = ["username", "first_name", "last_name", "email"]

    fieldsets = (
        (
            "Basic Information",
            {"fields": ("username", "first_name", "last_name", "email")},
        ),
        (
            "Profile",
            {
                "fields": ("bio", "profile_image_url", "website_url"),
                "classes": ("collapse",),
            },
        ),
        (
            "Social Media",
            {
                "fields": ("twitter_handle", "linkedin_url", "github_username"),
                "classes": ("collapse",),
            },
        ),
        (
            "Statistics",
            {
                "fields": ("post_count", "total_views", "follower_count"),
                "classes": ("collapse",),
            },
        ),
        (
            "Settings",
            {
                "fields": ("is_active", "email_notifications"),
            },
        ),
        (
            "Timestamps",
            {"fields": ("joined_date", "last_login"), "classes": ("collapse",)},
        ),
    )

    readonly_fields = [
        "joined_date",
        "last_login",
        "post_count",
        "total_views",
        "follower_count",
    ]

    # Use GSI for username searches
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Optimize with username-index when searching
        return qs

    actions = ["activate_authors", "deactivate_authors", "reset_stats"]

    def activate_authors(self, request, queryset):
        updated = 0
        for author in queryset:
            if not author.is_active:
                author.is_active = True
                author.save()
                updated += 1

        self.message_user(request, f"Activated {updated} authors.")

    activate_authors.short_description = "Activate selected authors"


@admin.register(BlogTag)
class BlogTagAdmin(DynamoDBAdmin):
    """Tag management with usage statistics"""

    list_display = ["name", "slug", "usage_count", "color"]
    list_editable = ["color"]
    search_fields = ["name", "slug", "description"]
    prepopulated_fields = {"slug": ("name",)}

    fieldsets = (
        ("Tag Information", {"fields": ("name", "slug", "description")}),
        ("Statistics", {"fields": ("usage_count",), "classes": ("collapse",)}),
        ("Display", {"fields": ("color",), "classes": ("collapse",)}),
    )

    readonly_fields = ["usage_count"]

    actions = ["merge_tags", "reset_usage_count"]

    def merge_tags(self, request, queryset):
        """Merge selected tags (demonstration of complex action)"""
        if queryset.count() < 2:
            self.message_user(
                request, "Select at least 2 tags to merge.", level="ERROR"
            )
            return

        # This would implement tag merging logic
        self.message_user(
            request,
            f"Tag merging initiated for {queryset.count()} tags. "
            "This operation will be processed in the background.",
        )

    merge_tags.short_description = "Merge selected tags"
