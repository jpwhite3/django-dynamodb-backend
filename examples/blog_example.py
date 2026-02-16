"""
Complete Blog Example using DynamoDB Django Admin

This example demonstrates a full blog application using DynamoDB as the backend,
including models, admin configuration, and management commands.
"""

from datetime import datetime, timedelta

from django.contrib import admin
from django.db import models

from django_dynamodb_backend.admin import DynamoDBAdmin
from django_dynamodb_backend.admin_filters import (
    DynamoDBBooleanFilter,
    DynamoDBDateRangeFilter,
)
from django_dynamodb_backend.models import DynamoDBModel

# =====================================
# Models
# =====================================


class BlogPost(DynamoDBModel):
    """Blog post model using DynamoDB backend."""

    # Primary key - must be unique across all posts
    slug = models.CharField(
        primary_key=True, max_length=200, help_text="URL-friendly title"
    )

    # Post content
    title = models.CharField(max_length=200)
    content = models.TextField()
    excerpt = models.CharField(
        max_length=300, blank=True, help_text="Short description for previews"
    )

    # Metadata
    author = models.CharField(max_length=100)
    category = models.CharField(
        max_length=50,
        choices=[
            ("tech", "Technology"),
            ("lifestyle", "Lifestyle"),
            ("business", "Business"),
            ("travel", "Travel"),
            ("food", "Food & Drink"),
        ],
        default="tech",
    )

    # Status and timestamps
    status = models.CharField(
        max_length=20,
        choices=[
            ("draft", "Draft"),
            ("published", "Published"),
            ("archived", "Archived"),
        ],
        default="draft",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)

    # Engagement metrics
    view_count = models.IntegerField(default=0)
    like_count = models.IntegerField(default=0)

    # SEO fields
    meta_description = models.CharField(max_length=160, blank=True)
    meta_keywords = models.CharField(max_length=200, blank=True)

    # Featured content
    is_featured = models.BooleanField(default=False)
    featured_image_url = models.URLField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return f"/blog/{self.slug}/"

    @property
    def is_published(self):
        return self.status == "published" and self.published_at is not None

    def publish(self):
        """Mark post as published."""
        self.status = "published"
        if not self.published_at:
            self.published_at = datetime.now()
        self.save()

    def get_reading_time(self):
        """Estimate reading time based on word count."""
        word_count = len(self.content.split())
        return max(1, word_count // 200)  # Average 200 words per minute


class Comment(DynamoDBModel):
    """Comment model with reference to blog posts."""

    id = models.AutoField(primary_key=True)
    post_slug = models.CharField(max_length=200, db_index=True)  # Reference to BlogPost

    # Comment content
    author_name = models.CharField(max_length=100)
    author_email = models.EmailField()
    content = models.TextField()

    # Moderation
    is_approved = models.BooleanField(default=False)
    is_spam = models.BooleanField(default=False)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Threading (simple parent-child relationship)
    parent_comment_id = models.IntegerField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Comment by {self.author_name} on {self.post_slug}"

    @property
    def post(self):
        """Get the related BlogPost."""
        try:
            return BlogPost.objects.get(slug=self.post_slug)
        except BlogPost.DoesNotExist:
            return None


class Category(DynamoDBModel):
    """Blog category model."""

    name = models.CharField(primary_key=True, max_length=50)
    description = models.TextField(blank=True)
    color = models.CharField(
        max_length=7, default="#007cba", help_text="Hex color code"
    )

    # SEO
    meta_description = models.CharField(max_length=160, blank=True)

    # Stats (denormalized for performance)
    post_count = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Tag(DynamoDBModel):
    """Tag model for blog posts."""

    name = models.CharField(primary_key=True, max_length=50)
    description = models.TextField(blank=True)

    # Stats (denormalized)
    usage_count = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class PostTag(DynamoDBModel):
    """Many-to-many relationship between posts and tags."""

    id = models.AutoField(primary_key=True)
    post_slug = models.CharField(max_length=200)
    tag_name = models.CharField(max_length=50)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["post_slug", "tag_name"]

    def __str__(self):
        return f"{self.post_slug} - {self.tag_name}"


# =====================================
# Custom Admin Filters
# =====================================


class PostStatusFilter(DynamoDBBooleanFilter):
    title = "publication status"
    parameter_name = "status"

    def lookups(self, request, model_admin):
        return [
            ("published", "Published"),
            ("draft", "Draft"),
            ("archived", "Archived"),
        ]


class CreatedDateFilter(DynamoDBDateRangeFilter):
    title = "created date"
    parameter_name = "created_at"


class FeaturedFilter(DynamoDBBooleanFilter):
    title = "featured status"
    parameter_name = "is_featured"


class CategoryFilter(admin.SimpleListFilter):
    title = "category"
    parameter_name = "category"

    def lookups(self, request, model_admin):
        return [
            ("tech", "Technology"),
            ("lifestyle", "Lifestyle"),
            ("business", "Business"),
            ("travel", "Travel"),
            ("food", "Food & Drink"),
        ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(category=self.value())
        return queryset


# =====================================
# Admin Configuration
# =====================================


@admin.register(BlogPost)
class BlogPostAdmin(DynamoDBAdmin):
    """Enhanced admin for blog posts."""

    # List display
    list_display = [
        "title",
        "author",
        "category",
        "status",
        "is_featured",
        "view_count",
        "created_at",
        "published_at",
    ]
    list_display_links = ["title"]
    list_editable = ["status", "is_featured", "category"]

    # Filtering
    list_filter = [
        PostStatusFilter,
        CategoryFilter,
        FeaturedFilter,
        CreatedDateFilter,
        "author",
    ]

    # Search
    search_fields = ["title", "content", "author", "meta_keywords"]

    # Pagination
    list_per_page = 20

    # Form organization
    fieldsets = [
        (None, {"fields": ["slug", "title", "content", "excerpt"]}),
        ("Publishing", {"fields": ["author", "category", "status", "published_at"]}),
        (
            "Featured",
            {"fields": ["is_featured", "featured_image_url"], "classes": ["collapse"]},
        ),
        (
            "SEO",
            {"fields": ["meta_description", "meta_keywords"], "classes": ["collapse"]},
        ),
        (
            "Statistics",
            {"fields": ["view_count", "like_count"], "classes": ["collapse"]},
        ),
    ]

    # Read-only fields
    readonly_fields = ["created_at", "updated_at"]

    # Custom actions
    actions = [
        "mark_as_published",
        "mark_as_draft",
        "mark_as_featured",
        "export_to_csv",
        "update_view_counts",
    ]

    def mark_as_published(self, request, queryset):
        """Mark selected posts as published."""
        count = 0
        for post in queryset:
            if post.status != "published":
                post.publish()
                count += 1

        self.message_user(request, f"Successfully published {count} post(s).")

    mark_as_published.short_description = "Publish selected posts"

    def mark_as_draft(self, request, queryset):
        """Mark selected posts as draft."""
        count = queryset.update(status="draft")
        self.message_user(request, f"Successfully marked {count} post(s) as draft.")

    mark_as_draft.short_description = "Mark as draft"

    def mark_as_featured(self, request, queryset):
        """Mark selected posts as featured."""
        count = queryset.update(is_featured=True)
        self.message_user(request, f"Successfully featured {count} post(s).")

    mark_as_featured.short_description = "Mark as featured"

    def update_view_counts(self, request, queryset):
        """Batch update view counts (example of complex operations)."""
        # This would typically integrate with analytics
        import random

        count = 0
        for post in queryset:
            # Simulate analytics data
            additional_views = random.randint(0, 100)
            post.view_count += additional_views
            post.save()
            count += 1

        self.message_user(request, f"Updated view counts for {count} post(s).")

    update_view_counts.short_description = "Update view counts"


@admin.register(Comment)
class CommentAdmin(DynamoDBAdmin):
    """Admin for comment moderation."""

    list_display = [
        "author_name",
        "post_slug",
        "content_preview",
        "is_approved",
        "is_spam",
        "created_at",
    ]
    list_display_links = ["author_name"]
    list_editable = ["is_approved", "is_spam"]

    list_filter = [
        "is_approved",
        "is_spam",
        CreatedDateFilter,
        "post_slug",
    ]

    search_fields = ["author_name", "author_email", "content", "post_slug"]

    list_per_page = 25

    actions = ["approve_comments", "mark_as_spam", "delete_spam"]

    def content_preview(self, obj):
        """Show truncated content."""
        return (obj.content[:50] + "...") if len(obj.content) > 50 else obj.content

    content_preview.short_description = "Content Preview"

    def approve_comments(self, request, queryset):
        """Approve selected comments."""
        count = queryset.update(is_approved=True, is_spam=False)
        self.message_user(request, f"Approved {count} comment(s).")

    approve_comments.short_description = "Approve comments"

    def mark_as_spam(self, request, queryset):
        """Mark comments as spam."""
        count = queryset.update(is_spam=True, is_approved=False)
        self.message_user(request, f"Marked {count} comment(s) as spam.")

    mark_as_spam.short_description = "Mark as spam"

    def delete_spam(self, request, queryset):
        """Delete spam comments."""
        spam_comments = queryset.filter(is_spam=True)
        count = spam_comments.count()
        spam_comments.delete()
        self.message_user(request, f"Deleted {count} spam comment(s).")

    delete_spam.short_description = "Delete spam comments"


@admin.register(Category)
class CategoryAdmin(DynamoDBAdmin):
    """Admin for blog categories."""

    list_display = ["name", "description", "post_count", "created_at"]
    list_display_links = ["name"]
    list_editable = ["description"]

    search_fields = ["name", "description"]

    readonly_fields = ["post_count", "created_at"]

    actions = ["update_post_counts"]

    def update_post_counts(self, request, queryset):
        """Update post counts for categories."""
        count = 0
        for category in queryset:
            # Count posts in this category
            post_count = BlogPost.objects.filter(category=category.name).count()
            category.post_count = post_count
            category.save()
            count += 1

        self.message_user(
            request,
            f"Updated post counts for {count} categor{'y' if count == 1 else 'ies'}.",
        )

    update_post_counts.short_description = "Update post counts"


@admin.register(Tag)
class TagAdmin(DynamoDBAdmin):
    """Admin for blog tags."""

    list_display = ["name", "description", "usage_count", "created_at"]
    list_display_links = ["name"]

    search_fields = ["name", "description"]

    readonly_fields = ["usage_count", "created_at"]

    actions = ["update_usage_counts"]

    def update_usage_counts(self, request, queryset):
        """Update usage counts for tags."""
        count = 0
        for tag in queryset:
            # Count how many posts use this tag
            usage_count = PostTag.objects.filter(tag_name=tag.name).count()
            tag.usage_count = usage_count
            tag.save()
            count += 1

        self.message_user(request, f"Updated usage counts for {count} tag(s).")

    update_usage_counts.short_description = "Update usage counts"


@admin.register(PostTag)
class PostTagAdmin(DynamoDBAdmin):
    """Admin for post-tag relationships."""

    list_display = ["post_slug", "tag_name", "created_at"]
    list_display_links = ["post_slug"]

    list_filter = ["tag_name", "post_slug"]
    search_fields = ["post_slug", "tag_name"]

    list_per_page = 50


# =====================================
# Usage Examples and Utilities
# =====================================


def create_sample_data():
    """Create sample blog data for testing."""

    # Create categories
    categories = [
        Category(name="tech", description="Technology and programming articles"),
        Category(name="lifestyle", description="Lifestyle and wellness content"),
        Category(name="business", description="Business and entrepreneurship"),
    ]

    for category in categories:
        try:
            category.save()
        except:
            pass  # May already exist

    # Create tags
    tags = [
        "python",
        "django",
        "web-development",
        "aws",
        "dynamodb",
        "productivity",
        "startup",
        "career",
        "tutorial",
    ]

    for tag_name in tags:
        tag = Tag(name=tag_name)
        try:
            tag.save()
        except:
            pass  # May already exist

    # Create sample blog posts
    posts_data = [
        {
            "slug": "getting-started-with-dynamodb-django",
            "title": "Getting Started with DynamoDB and Django",
            "content": "This comprehensive guide will walk you through setting up Django with DynamoDB...",
            "excerpt": "Learn how to integrate Django with Amazon DynamoDB for scalable web applications.",
            "author": "John Doe",
            "category": "tech",
            "status": "published",
            "is_featured": True,
            "meta_description": "Complete guide to using DynamoDB with Django framework",
            "meta_keywords": "django,dynamodb,aws,web development",
        },
        {
            "slug": "building-scalable-web-apps",
            "title": "Building Scalable Web Applications",
            "content": "Scalability is crucial for modern web applications. In this post, we explore...",
            "excerpt": "Explore strategies and patterns for building web applications that scale.",
            "author": "Jane Smith",
            "category": "business",
            "status": "published",
            "is_featured": False,
        },
        {
            "slug": "productivity-tips-for-developers",
            "title": "Productivity Tips for Developers",
            "content": "As a developer, staying productive is essential. Here are some tips...",
            "excerpt": "Practical tips to boost your productivity as a software developer.",
            "author": "Bob Wilson",
            "category": "lifestyle",
            "status": "draft",
        },
    ]

    for post_data in posts_data:
        post = BlogPost(**post_data)
        if post.status == "published":
            post.published_at = datetime.now()
        try:
            post.save()
            print(f"Created post: {post.title}")
        except Exception as e:
            print(f"Failed to create post {post.title}: {e}")

    # Create sample comments
    comments_data = [
        {
            "post_slug": "getting-started-with-dynamodb-django",
            "author_name": "Alice Cooper",
            "author_email": "alice@example.com",
            "content": "Great tutorial! This really helped me understand the integration.",
            "is_approved": True,
        },
        {
            "post_slug": "building-scalable-web-apps",
            "author_name": "Charlie Brown",
            "author_email": "charlie@example.com",
            "content": "Could you provide more examples of scaling patterns?",
            "is_approved": True,
        },
        {
            "post_slug": "getting-started-with-dynamodb-django",
            "author_name": "Spam Bot",
            "author_email": "spam@spam.com",
            "content": "Buy cheap products now! Click here!!!",
            "is_approved": False,
            "is_spam": True,
        },
    ]

    for comment_data in comments_data:
        comment = Comment(**comment_data)
        try:
            comment.save()
            print(f"Created comment from: {comment.author_name}")
        except Exception as e:
            print(f"Failed to create comment: {e}")

    print("Sample data creation completed!")


def demonstrate_queries():
    """Demonstrate various query patterns."""

    print("=== DynamoDB Django Query Examples ===\n")

    # Basic queries
    print("1. All published posts:")
    published_posts = BlogPost.objects.filter(status="published")
    for post in published_posts[:3]:
        print(f"   - {post.title} by {post.author}")

    print(f"\n2. Total published posts: {published_posts.count()}")

    # Date filtering
    print("\n3. Recent posts (last 30 days):")
    recent_date = datetime.now() - timedelta(days=30)
    recent_posts = BlogPost.objects.filter(created_at__gte=recent_date)
    for post in recent_posts[:3]:
        print(f"   - {post.title} ({post.created_at.strftime('%Y-%m-%d')})")

    # Complex filtering
    print("\n4. Featured tech posts:")
    featured_tech = BlogPost.objects.filter(
        category="tech", is_featured=True, status="published"
    )
    for post in featured_tech[:3]:
        print(f"   - {post.title}")

    # Search functionality
    print("\n5. Posts containing 'Django':")
    django_posts = BlogPost.objects.filter(title__icontains="django")
    for post in django_posts[:3]:
        print(f"   - {post.title}")

    # Author-based queries
    print("\n6. Posts by author:")
    authors = BlogPost.objects.values_list("author", flat=True).distinct()
    for author in list(authors)[:3]:
        author_posts = BlogPost.objects.filter(author=author)
        print(f"   - {author}: {author_posts.count()} posts")

    # Comment queries
    print("\n7. Recent approved comments:")
    approved_comments = Comment.objects.filter(is_approved=True).order_by("-created_at")
    for comment in approved_comments[:3]:
        print(
            f"   - {comment.author_name} on '{comment.post_slug}': {comment.content[:50]}..."
        )

    print("\n=== Query Examples Complete ===")


if __name__ == "__main__":
    # This would typically be run from Django management commands
    print("Blog Example - DynamoDB Django Admin")
    print("=====================================")
    print("This example demonstrates:")
    print("- Complex DynamoDB model relationships")
    print("- Advanced admin configuration")
    print("- Custom filters and actions")
    print("- Efficient query patterns")
    print("- Data management utilities")
    print("\nTo use this example:")
    print("1. Apply the migrations: python manage.py dynamodb_migrate")
    print(
        "2. Create sample data: python manage.py shell -c 'from examples.blog_example import create_sample_data; create_sample_data()'"
    )
    print("3. Access the admin at: http://localhost:8000/admin/")
