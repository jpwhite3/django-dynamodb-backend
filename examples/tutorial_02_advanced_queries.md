# Tutorial 2: Advanced Queries and Relationships

This tutorial covers advanced DynamoDB querying patterns, simulated relationships, and performance optimization techniques.

## Building on Tutorial 1

This tutorial assumes you've completed Tutorial 1 and have the Book model set up. We'll extend it with more complex examples.

## Setting Up Advanced Models

Let's create a more complex library system with authors, publishers, and reviews.

### myapp/models.py (Extended)

```python
from django.db import models
from django_dynamodb_backend.models import DynamoDBModel
from datetime import datetime, timedelta
import uuid

class Author(DynamoDBModel):
    """Author model with biographical information."""
    
    id = models.CharField(max_length=36, primary_key=True, default=lambda: str(uuid.uuid4()))
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    birth_date = models.DateField(null=True, blank=True)
    nationality = models.CharField(max_length=50, blank=True)
    biography = models.TextField(blank=True)
    
    # Social media
    website = models.URLField(blank=True)
    twitter_handle = models.CharField(max_length=50, blank=True)
    
    # Stats (denormalized for performance)
    book_count = models.IntegerField(default=0)
    total_pages_written = models.IntegerField(default=0)
    
    # Meta
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.first_name} {self.last_name}"
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    @property
    def age(self):
        if self.birth_date:
            today = datetime.now().date()
            return today.year - self.birth_date.year - (
                (today.month, today.day) < (self.birth_date.month, self.birth_date.day)
            )
        return None


class Publisher(DynamoDBModel):
    """Publisher model with company information."""
    
    name = models.CharField(primary_key=True, max_length=100)
    founded_year = models.IntegerField(null=True, blank=True)
    headquarters = models.CharField(max_length=100, blank=True)
    website = models.URLField(blank=True)
    description = models.TextField(blank=True)
    
    # Business info
    is_active = models.BooleanField(default=True)
    company_type = models.CharField(max_length=20, choices=[
        ('indie', 'Independent'),
        ('major', 'Major Publisher'),
        ('academic', 'Academic Press'),
        ('self', 'Self Publishing'),
    ], default='indie')
    
    # Stats
    book_count = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name


class Book(DynamoDBModel):
    """Enhanced Book model with relationships."""
    
    isbn = models.CharField(primary_key=True, max_length=13)
    title = models.CharField(max_length=200)
    
    # Relationship fields (denormalized)
    author_id = models.CharField(max_length=36)  # Reference to Author
    author_name = models.CharField(max_length=100)  # Denormalized for performance
    
    publisher_name = models.CharField(max_length=100)  # Reference to Publisher
    
    # Book details
    publication_date = models.DateField()
    pages = models.IntegerField()
    price = models.DecimalField(max_digits=8, decimal_places=2)
    genre = models.CharField(max_length=50, choices=[
        ('fiction', 'Fiction'),
        ('non-fiction', 'Non-Fiction'),
        ('mystery', 'Mystery'),
        ('romance', 'Romance'),
        ('sci-fi', 'Science Fiction'),
        ('fantasy', 'Fantasy'),
        ('biography', 'Biography'),
        ('history', 'History'),
        ('science', 'Science'),
        ('technology', 'Technology'),
    ])
    
    # Additional categorization
    age_rating = models.CharField(max_length=10, choices=[
        ('children', 'Children (0-12)'),
        ('ya', 'Young Adult (13-17)'),
        ('adult', 'Adult (18+)'),
    ], default='adult')
    
    language = models.CharField(max_length=10, choices=[
        ('en', 'English'),
        ('es', 'Spanish'),
        ('fr', 'French'),
        ('de', 'German'),
        ('it', 'Italian'),
        ('pt', 'Portuguese'),
    ], default='en')
    
    # Status and flags
    is_available = models.BooleanField(default=True)
    is_bestseller = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)
    is_digital_available = models.BooleanField(default=False)
    
    # Stats (updated periodically)
    rating_average = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    rating_count = models.IntegerField(default=0)
    sales_count = models.IntegerField(default=0)
    
    # Content
    description = models.TextField(blank=True)
    table_of_contents = models.TextField(blank=True)  # JSON string
    cover_image_url = models.URLField(blank=True)
    
    # SEO and marketing
    keywords = models.CharField(max_length=200, blank=True)  # Comma-separated
    marketing_tags = models.CharField(max_length=200, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.title} by {self.author_name}"
    
    @property
    def author(self):
        """Get the related Author object."""
        try:
            return Author.objects.get(id=self.author_id)
        except Author.DoesNotExist:
            return None
    
    @property
    def publisher(self):
        """Get the related Publisher object."""
        try:
            return Publisher.objects.get(name=self.publisher_name)
        except Publisher.DoesNotExist:
            return None
    
    @property
    def is_recent(self):
        from datetime import date, timedelta
        return self.publication_date >= (date.today() - timedelta(days=730))
    
    @property
    def keyword_list(self):
        """Return keywords as a list."""
        return [k.strip() for k in self.keywords.split(',') if k.strip()]


class BookReview(DynamoDBModel):
    """Book review model."""
    
    id = models.CharField(max_length=36, primary_key=True, default=lambda: str(uuid.uuid4()))
    book_isbn = models.CharField(max_length=13, db_index=True)
    
    # Reviewer info
    reviewer_name = models.CharField(max_length=100)
    reviewer_email = models.EmailField()
    
    # Review content
    title = models.CharField(max_length=200)
    content = models.TextField()
    rating = models.IntegerField(choices=[(i, i) for i in range(1, 6)])  # 1-5 stars
    
    # Moderation
    is_approved = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)
    
    # Helpfulness
    helpful_votes = models.IntegerField(default=0)
    total_votes = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Review of {self.book_isbn} by {self.reviewer_name}"
    
    @property
    def book(self):
        """Get the related Book object."""
        try:
            return Book.objects.get(isbn=self.book_isbn)
        except Book.DoesNotExist:
            return None
    
    @property
    def helpfulness_ratio(self):
        """Calculate helpfulness percentage."""
        if self.total_votes > 0:
            return (self.helpful_votes / self.total_votes) * 100
        return 0


class ReadingList(DynamoDBModel):
    """User reading lists/collections."""
    
    id = models.CharField(max_length=36, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    # Owner (simplified - in real app would reference User)
    owner_name = models.CharField(max_length=100)
    owner_email = models.EmailField()
    
    # Settings
    is_public = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)
    
    # Stats
    book_count = models.IntegerField(default=0)
    follower_count = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} by {self.owner_name}"


class ReadingListItem(DynamoDBModel):
    """Items in a reading list."""
    
    id = models.CharField(max_length=36, primary_key=True, default=lambda: str(uuid.uuid4()))
    reading_list_id = models.CharField(max_length=36)
    book_isbn = models.CharField(max_length=13)
    
    # Item-specific data
    added_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)
    
    # Reading status
    status = models.CharField(max_length=20, choices=[
        ('want_to_read', 'Want to Read'),
        ('currently_reading', 'Currently Reading'),
        ('finished', 'Finished'),
        ('did_not_finish', 'Did Not Finish'),
    ], default='want_to_read')
    
    # Personal rating (different from public reviews)
    personal_rating = models.IntegerField(
        choices=[(i, i) for i in range(1, 6)], 
        null=True, 
        blank=True
    )
    
    class Meta:
        # Note: unique_together is not enforced by DynamoDB.
        # Uniqueness must be handled in application code or by
        # using a composite partition key.
        unique_together = ['reading_list_id', 'book_isbn']
    
    def __str__(self):
        return f"{self.book_isbn} in list {self.reading_list_id}"
    
    @property
    def book(self):
        try:
            return Book.objects.get(isbn=self.book_isbn)
        except Book.DoesNotExist:
            return None
    
    @property
    def reading_list(self):
        try:
            return ReadingList.objects.get(id=self.reading_list_id)
        except ReadingList.DoesNotExist:
            return None
```

## Advanced Query Patterns

### Complex Filtering

```python
# myapp/queries.py

from django.db.models import Q
from datetime import datetime, timedelta, date
from decimal import Decimal
from .models import Book, Author, BookReview, Publisher

class BookQueryService:
    """Service class for complex book queries."""
    
    @staticmethod
    def recent_bestsellers(days=30):
        """Get recent bestsellers."""
        cutoff_date = date.today() - timedelta(days=days)
        return Book.objects.filter(
            is_bestseller=True,
            publication_date__gte=cutoff_date,
            is_available=True
        ).order_by('-publication_date')
    
    @staticmethod
    def books_by_price_range(min_price, max_price):
        """Get books within a price range."""
        return Book.objects.filter(
            price__gte=Decimal(str(min_price)),
            price__lte=Decimal(str(max_price)),
            is_available=True
        )
    
    @staticmethod
    def highly_rated_books(min_rating=4.0, min_review_count=10):
        """Get highly rated books with sufficient reviews."""
        return Book.objects.filter(
            rating_average__gte=Decimal(str(min_rating)),
            rating_count__gte=min_review_count,
            is_available=True
        ).order_by('-rating_average')
    
    @staticmethod
    def books_by_genre_and_age(genre, age_rating):
        """Get books by genre and age rating."""
        return Book.objects.filter(
            genre=genre,
            age_rating=age_rating,
            is_available=True
        )
    
    @staticmethod
    def search_books(query, genres=None, languages=None):
        """Full-text search across books."""
        books = Book.objects.all()
        
        if query:
            # Search in title, description, and keywords
            books = books.filter(
                Q(title__icontains=query) |
                Q(description__icontains=query) |
                Q(keywords__icontains=query) |
                Q(author_name__icontains=query)
            )
        
        if genres:
            books = books.filter(genre__in=genres)
        
        if languages:
            books = books.filter(language__in=languages)
        
        return books.filter(is_available=True)
    
    @staticmethod
    def books_by_author_id(author_id):
        """Get all books by a specific author."""
        return Book.objects.filter(author_id=author_id).order_by('-publication_date')
    
    @staticmethod
    def books_by_publisher(publisher_name):
        """Get all books by a specific publisher."""
        return Book.objects.filter(
            publisher_name=publisher_name,
            is_available=True
        ).order_by('-publication_date')
    
    @staticmethod
    def featured_books_by_category():
        """Get featured books grouped by category."""
        return {
            'fiction': Book.objects.filter(genre='fiction', is_featured=True)[:5],
            'non_fiction': Book.objects.filter(genre='non-fiction', is_featured=True)[:5],
            'sci_fi': Book.objects.filter(genre='sci-fi', is_featured=True)[:5],
            'mystery': Book.objects.filter(genre='mystery', is_featured=True)[:5],
        }
    
    @staticmethod
    def books_with_stats():
        """Get books with computed statistics."""
        books = []
        for book in Book.objects.all():
            # Calculate additional stats
            reviews = BookReview.objects.filter(book_isbn=book.isbn, is_approved=True)
            
            stats = {
                'book': book,
                'review_count': reviews.count(),
                'avg_rating': reviews.aggregate(avg=models.Avg('rating'))['avg'] or 0,
                'recent_reviews': reviews.filter(
                    created_at__gte=datetime.now() - timedelta(days=30)
                ).count(),
            }
            books.append(stats)
        
        return sorted(books, key=lambda x: x['avg_rating'], reverse=True)


class AuthorQueryService:
    """Service class for author-related queries."""
    
    @staticmethod
    def prolific_authors(min_books=5):
        """Get authors with many books."""
        return Author.objects.filter(book_count__gte=min_books).order_by('-book_count')
    
    @staticmethod
    def authors_by_nationality(nationality):
        """Get authors by nationality."""
        return Author.objects.filter(nationality=nationality)
    
    @staticmethod
    def young_authors(max_age=40):
        """Get young authors (approximation - would need birth_date filtering)."""
        # This is a simplified version - in practice you'd filter by birth_date
        return Author.objects.filter(birth_date__isnull=False)
    
    @staticmethod
    def author_with_book_stats(author_id):
        """Get author with detailed book statistics."""
        try:
            author = Author.objects.get(id=author_id)
            books = Book.objects.filter(author_id=author_id)
            
            return {
                'author': author,
                'total_books': books.count(),
                'published_books': books.filter(is_available=True).count(),
                'bestsellers': books.filter(is_bestseller=True).count(),
                'genres': list(books.values_list('genre', flat=True).distinct()),
                'avg_price': books.aggregate(avg=models.Avg('price'))['avg'] or 0,
                'total_pages': books.aggregate(sum=models.Sum('pages'))['sum'] or 0,
            }
        except Author.DoesNotExist:
            return None


class ReviewQueryService:
    """Service class for review-related queries."""
    
    @staticmethod
    def top_reviewed_books(limit=10):
        """Get books with the most reviews."""
        # This would typically be done with aggregation, but DynamoDB has limitations
        # So we'll do it in Python
        book_review_counts = {}
        
        for review in BookReview.objects.filter(is_approved=True):
            if review.book_isbn not in book_review_counts:
                book_review_counts[review.book_isbn] = 0
            book_review_counts[review.book_isbn] += 1
        
        # Sort by review count
        top_books = sorted(book_review_counts.items(), 
                          key=lambda x: x[1], reverse=True)[:limit]
        
        # Get the actual book objects
        result = []
        for isbn, count in top_books:
            try:
                book = Book.objects.get(isbn=isbn)
                result.append({
                    'book': book,
                    'review_count': count
                })
            except Book.DoesNotExist:
                continue
        
        return result
    
    @staticmethod
    def recent_reviews(days=7):
        """Get recent reviews."""
        cutoff_date = datetime.now() - timedelta(days=days)
        return BookReview.objects.filter(
            created_at__gte=cutoff_date,
            is_approved=True
        ).order_by('-created_at')
    
    @staticmethod
    def helpful_reviews(min_helpfulness=70):
        """Get reviews that users found helpful."""
        helpful_reviews = []
        for review in BookReview.objects.filter(is_approved=True):
            if review.total_votes > 5 and review.helpfulness_ratio >= min_helpfulness:
                helpful_reviews.append(review)
        
        return sorted(helpful_reviews, 
                     key=lambda x: x.helpfulness_ratio, reverse=True)
```

### Pagination and Performance

> **Note:** The `django_dynamodb_backend` package includes a built-in `DynamoDBPaginator` (see [API Reference](../docs/API_REFERENCE.md#dynamodbpaginator)) that handles token-based pagination for you. The example below shows the underlying concepts for learning purposes.

```python
# myapp/pagination.py

from django.core.paginator import Paginator, Page
from django.utils.functional import cached_property

class DynamoDBPaginator(Paginator):
    """
    Custom paginator optimized for DynamoDB operations.
    Handles cursor-based pagination for better performance.
    """
    
    def __init__(self, object_list, per_page, orphans=0, allow_empty_first_page=True):
        super().__init__(object_list, per_page, orphans, allow_empty_first_page)
        self._last_evaluated_key = None
    
    def get_page(self, number, last_key=None):
        """Get a page with optional cursor."""
        try:
            number = self.validate_number(number)
        except PageNotAnInteger:
            number = 1
        except EmptyPage:
            number = self.num_pages
        
        # For DynamoDB, we use cursor-based pagination
        if last_key:
            # This would integrate with your QuerySet's pagination
            # For now, we'll use the standard approach
            pass
        
        return self._get_page(self._get_page_items(number), number, self)
    
    def _get_page_items(self, page_number):
        """Get items for a specific page."""
        start = (page_number - 1) * self.per_page
        end = start + self.per_page
        return list(self.object_list[start:end])

# Usage example
def paginated_books(request, page=1):
    """View function demonstrating pagination."""
    books = Book.objects.filter(is_available=True).order_by('-created_at')
    
    paginator = DynamoDBPaginator(books, 25)  # 25 books per page
    page_obj = paginator.get_page(page)
    
    return {
        'books': page_obj,
        'paginator': paginator,
        'page_number': page,
    }
```

## Performance Optimization Strategies

### 1. Denormalization

```python
# Example of maintaining denormalized data
def update_author_book_count(author_id):
    """Update the book count for an author."""
    try:
        author = Author.objects.get(id=author_id)
        book_count = Book.objects.filter(author_id=author_id).count()
        total_pages = Book.objects.filter(author_id=author_id).aggregate(
            sum=models.Sum('pages')
        )['sum'] or 0
        
        author.book_count = book_count
        author.total_pages_written = total_pages
        author.save()
        
        return True
    except Author.DoesNotExist:
        return False

def update_book_rating_stats(book_isbn):
    """Update rating statistics for a book."""
    try:
        book = Book.objects.get(isbn=book_isbn)
        reviews = BookReview.objects.filter(book_isbn=book_isbn, is_approved=True)
        
        if reviews.exists():
            ratings = [review.rating for review in reviews]
            avg_rating = sum(ratings) / len(ratings)
            
            book.rating_average = round(avg_rating, 2)
            book.rating_count = len(ratings)
            book.save()
        
        return True
    except Book.DoesNotExist:
        return False
```

### 2. Batch Operations

```python
# myapp/batch_operations.py

def batch_update_book_availability(isbn_list, is_available=True):
    """Batch update availability for multiple books."""
    updated_count = 0
    
    # DynamoDB supports batch operations, but we'll simulate here
    for isbn in isbn_list:
        try:
            book = Book.objects.get(isbn=isbn)
            book.is_available = is_available
            book.save()
            updated_count += 1
        except Book.DoesNotExist:
            continue
    
    return updated_count

def batch_create_reviews(reviews_data):
    """Batch create multiple reviews."""
    created_reviews = []
    
    for review_data in reviews_data:
        try:
            review = BookReview(**review_data)
            review.save()
            created_reviews.append(review)
        except Exception as e:
            # Log the error but continue with other reviews
            print(f"Failed to create review: {e}")
            continue
    
    return created_reviews
```

### 3. Caching Strategies

```python
# myapp/cache_utils.py

from django.core.cache import cache
from django.utils.encoding import force_str
import hashlib

def get_cache_key(prefix, *args, **kwargs):
    """Generate a cache key from arguments."""
    key_parts = [prefix]
    key_parts.extend(force_str(arg) for arg in args)
    key_parts.extend(f"{k}:{force_str(v)}" for k, v in sorted(kwargs.items()))
    
    key = ":".join(key_parts)
    
    # Hash if too long
    if len(key) > 200:
        key = hashlib.md5(key.encode()).hexdigest()
    
    return key

def cached_book_stats(book_isbn, timeout=3600):
    """Get cached book statistics."""
    cache_key = get_cache_key('book_stats', book_isbn)
    stats = cache.get(cache_key)
    
    if stats is None:
        try:
            book = Book.objects.get(isbn=book_isbn)
            reviews = BookReview.objects.filter(book_isbn=book_isbn, is_approved=True)
            
            stats = {
                'review_count': reviews.count(),
                'avg_rating': sum(r.rating for r in reviews) / len(reviews) if reviews else 0,
                'recent_reviews_count': reviews.filter(
                    created_at__gte=datetime.now() - timedelta(days=30)
                ).count(),
            }
            
            cache.set(cache_key, stats, timeout)
        except Book.DoesNotExist:
            stats = None
    
    return stats

def invalidate_book_cache(book_isbn):
    """Invalidate cache for a book when data changes."""
    cache_keys = [
        get_cache_key('book_stats', book_isbn),
        get_cache_key('book_reviews', book_isbn),
        # Add other related cache keys
    ]
    
    cache.delete_many(cache_keys)
```

## Testing Advanced Queries

### myapp/test_queries.py

```python
from django.test import TestCase
from datetime import date, datetime, timedelta
from decimal import Decimal
from .models import Author, Publisher, Book, BookReview
from .queries import BookQueryService, AuthorQueryService

class QueryServiceTest(TestCase):
    def setUp(self):
        # Create test data
        self.author = Author.objects.create(
            first_name='Test',
            last_name='Author',
            birth_date=date(1980, 1, 1),
            nationality='US'
        )
        
        self.publisher = Publisher.objects.create(
            name='Test Publisher',
            founded_year=2000,
            company_type='indie'
        )
        
        self.book = Book.objects.create(
            isbn='9781234567890',
            title='Test Book',
            author_id=self.author.id,
            author_name=self.author.full_name,
            publisher_name=self.publisher.name,
            publication_date=date.today() - timedelta(days=10),
            pages=300,
            price=Decimal('29.99'),
            genre='fiction',
            is_bestseller=True,
            is_available=True,
            rating_average=Decimal('4.5'),
            rating_count=100
        )
    
    def test_recent_bestsellers(self):
        """Test recent bestsellers query."""
        results = BookQueryService.recent_bestsellers(days=30)
        self.assertIn(self.book, results)
        
        # Test with shorter time frame
        results = BookQueryService.recent_bestsellers(days=5)
        self.assertNotIn(self.book, results)
    
    def test_price_range_query(self):
        """Test price range filtering."""
        results = BookQueryService.books_by_price_range(20, 40)
        self.assertIn(self.book, results)
        
        results = BookQueryService.books_by_price_range(50, 100)
        self.assertNotIn(self.book, results)
    
    def test_highly_rated_books(self):
        """Test highly rated books query."""
        results = BookQueryService.highly_rated_books(min_rating=4.0, min_review_count=50)
        self.assertIn(self.book, results)
        
        results = BookQueryService.highly_rated_books(min_rating=5.0)
        self.assertNotIn(self.book, results)
    
    def test_search_functionality(self):
        """Test book search."""
        results = BookQueryService.search_books('Test')
        self.assertIn(self.book, results)
        
        results = BookQueryService.search_books('Nonexistent')
        self.assertNotIn(self.book, results)
        
        # Test genre filtering
        results = BookQueryService.search_books('', genres=['fiction'])
        self.assertIn(self.book, results)
        
        results = BookQueryService.search_books('', genres=['non-fiction'])
        self.assertNotIn(self.book, results)
```

## Summary

In this tutorial, we've covered:

1. **Advanced Model Design** - Complex relationships using denormalization
2. **Query Services** - Organized, reusable query patterns
3. **Performance Optimization** - Caching, batch operations, denormalization
4. **Pagination Strategies** - Cursor-based pagination for DynamoDB
5. **Testing** - Comprehensive testing of query functionality

## Next Steps

- **[Feature Walkthrough](../docs/FEATURE_WALKTHROUGH.md)**: Custom admin actions, bulk operations, GSI optimization
- **[Deployment Guide](../docs/DEPLOYMENT_GUIDE.md)**: Production deployment and monitoring
- **[Django Compatibility Guide](../docs/DJANGO_COMPATIBILITY.md)**: Full feature support matrix

The key to success with DynamoDB is understanding its strengths (scale, performance) and designing your data model and queries accordingly. Unlike traditional relational databases, DynamoDB requires more upfront design thinking but provides excellent performance at scale.