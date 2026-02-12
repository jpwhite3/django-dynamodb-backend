# Blog Demo Models - Showcasing Django DynamoDB Admin Features

from datetime import datetime, timezone

from django.contrib.auth.models import User
from dynamodb_adapter.fields import (BooleanField, CharField, DateTimeField,
                                     IntegerField, ListField, SetField,
                                     TextField)
from dynamodb_adapter.models import DynamoDBModel


class BlogPost(DynamoDBModel):
    """
    Blog post model demonstrating:
    - Primary key design (user_id as partition key, post_id as sort key)
    - Rich text content with metadata
    - GSI for published posts by date
    - Tags for filtering demonstrations
    """

    class Meta:
        table_name = "demo_blog_posts"

        # GSI for querying published posts by date
        global_secondary_indexes = [
            {
                "index_name": "published-date-index",
                "partition_key": "is_published",
                "sort_key": "published_date",
                "projection_type": "ALL",
            },
            {
                "index_name": "category-date-index",
                "partition_key": "category",
                "sort_key": "published_date",
                "projection_type": "INCLUDE",
                "non_key_attributes": ["title", "author", "view_count"],
            },
        ]

    # Primary key design
    user_id = CharField(max_length=50, primary_key=True)  # Partition key
    post_id = CharField(max_length=50, sort_key=True)  # Sort key

    # Post content
    title = CharField(max_length=200)
    slug = CharField(max_length=200, unique=True)
    content = TextField()
    excerpt = TextField(max_length=500, blank=True)

    # Metadata
    author = CharField(max_length=100)
    category = CharField(
        max_length=50,
        choices=[
            ("tech", "Technology"),
            ("lifestyle", "Lifestyle"),
            ("business", "Business"),
            ("travel", "Travel"),
            ("food", "Food & Cooking"),
            ("health", "Health & Fitness"),
        ],
    )

    # Publishing information
    is_published = BooleanField(default=False)
    published_date = DateTimeField(null=True, blank=True)
    created_date = DateTimeField(auto_now_add=True)
    updated_date = DateTimeField(auto_now=True)

    # Engagement metrics
    view_count = IntegerField(default=0)
    like_count = IntegerField(default=0)
    comment_count = IntegerField(default=0)

    # Tags for filtering
    tags = SetField(base_field=CharField(max_length=30), default=set)

    # Featured content
    is_featured = BooleanField(default=False)
    featured_image_url = CharField(max_length=500, blank=True)

    def __str__(self):
        return f"{self.title} by {self.author}"

    @property
    def is_recent(self):
        """Check if post was published in last 7 days"""
        if not self.published_date:
            return False
        from datetime import timedelta

        recent_threshold = datetime.now(timezone.utc) - timedelta(days=7)
        return self.published_date >= recent_threshold

    def get_absolute_url(self):
        return f"/blog/{self.slug}/"


class BlogComment(DynamoDBModel):
    """
    Blog comments model demonstrating:
    - One-to-many relationships with blog posts
    - Hierarchical comments (replies to comments)
    - User interaction tracking
    """

    class Meta:
        table_name = "demo_blog_comments"
        global_secondary_indexes = [
            {
                "index_name": "post-date-index",
                "partition_key": "post_id",
                "sort_key": "created_date",
                "projection_type": "ALL",
            }
        ]

    # Primary key
    comment_id = CharField(max_length=50, primary_key=True)
    created_date = DateTimeField(sort_key=True, auto_now_add=True)

    # Relationships
    post_id = CharField(max_length=100)  # Reference to BlogPost
    parent_comment_id = CharField(max_length=50, null=True, blank=True)  # For replies

    # Comment content
    author_name = CharField(max_length=100)
    author_email = CharField(max_length=200)
    content = TextField()

    # Moderation
    is_approved = BooleanField(default=True)
    is_spam = BooleanField(default=False)

    # Engagement
    like_count = IntegerField(default=0)
    reply_count = IntegerField(default=0)

    def __str__(self):
        return f"Comment by {self.author_name} on {self.created_date}"


class BlogCategory(DynamoDBModel):
    """
    Blog categories with hierarchical structure
    """

    class Meta:
        table_name = "demo_blog_categories"

    category_id = CharField(max_length=50, primary_key=True)

    name = CharField(max_length=100)
    slug = CharField(max_length=100, unique=True)
    description = TextField(blank=True)
    parent_category_id = CharField(max_length=50, null=True, blank=True)

    # Statistics
    post_count = IntegerField(default=0)
    subscriber_count = IntegerField(default=0)

    # Display
    color_code = CharField(max_length=7, default="#007cba")  # Hex color
    icon_class = CharField(max_length=50, blank=True)

    # SEO
    meta_title = CharField(max_length=200, blank=True)
    meta_description = TextField(max_length=300, blank=True)

    def __str__(self):
        return self.name


class BlogAuthor(DynamoDBModel):
    """
    Blog author profiles with detailed information
    """

    class Meta:
        table_name = "demo_blog_authors"
        global_secondary_indexes = [
            {
                "index_name": "username-index",
                "partition_key": "username",
                "projection_type": "ALL",
            }
        ]

    author_id = CharField(max_length=50, primary_key=True)

    # Basic info
    username = CharField(max_length=50, unique=True)
    first_name = CharField(max_length=50)
    last_name = CharField(max_length=50)
    email = CharField(max_length=200)

    # Profile
    bio = TextField(max_length=1000, blank=True)
    profile_image_url = CharField(max_length=500, blank=True)
    website_url = CharField(max_length=500, blank=True)

    # Social media
    twitter_handle = CharField(max_length=50, blank=True)
    linkedin_url = CharField(max_length=500, blank=True)
    github_username = CharField(max_length=50, blank=True)

    # Stats
    post_count = IntegerField(default=0)
    total_views = IntegerField(default=0)
    follower_count = IntegerField(default=0)

    # Settings
    is_active = BooleanField(default=True)
    email_notifications = BooleanField(default=True)

    # Timestamps
    joined_date = DateTimeField(auto_now_add=True)
    last_login = DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} (@{self.username})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class BlogTag(DynamoDBModel):
    """
    Blog tags for categorization and filtering
    """

    class Meta:
        table_name = "demo_blog_tags"

    tag_id = CharField(max_length=50, primary_key=True)

    name = CharField(max_length=50, unique=True)
    slug = CharField(max_length=50, unique=True)
    description = TextField(max_length=200, blank=True)

    # Usage statistics
    usage_count = IntegerField(default=0)

    # Display
    color = CharField(max_length=7, default="#6c757d")  # Bootstrap secondary color

    def __str__(self):
        return self.name
