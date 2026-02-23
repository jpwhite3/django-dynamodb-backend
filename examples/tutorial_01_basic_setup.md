# Tutorial 1: Basic Setup and First Model

This tutorial will guide you through setting up Django with DynamoDB and creating your first model.

## Prerequisites

- Python 3.11 or higher
- AWS account (for production) or LocalStack / DynamoDB Local (for development)
- Basic Django knowledge

## Step 1: Installation

### Clone and Set Up the Project

```bash
git clone https://github.com/jpwhite3/django-dynamodb-backend.git
cd django-dynamodb-backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install the package with dev dependencies
pip install -e ".[dev]"
```

### Install DynamoDB Local (Development)

```bash
# Download DynamoDB Local
wget https://s3.us-west-2.amazonaws.com/dynamodb-local/dynamodb_local_latest.tar.gz
tar -xzf dynamodb_local_latest.tar.gz

# Start DynamoDB Local
java -Djava.library.path=./DynamoDBLocal_lib -jar DynamoDBLocal.jar -sharedDb
```

Or use Docker:

```bash
docker run -p 8000:8000 amazon/dynamodb-local -jar DynamoDBLocal.jar -sharedDb -dbPath ./data
```

## Step 2: Django Configuration

### Update settings.py

```python
# settings.py

DATABASES = {
    'default': {
        'ENGINE': 'django_dynamodb_backend.db',
        'NAME': 'tutorial_db',
        'OPTIONS': {
            'region_name': 'us-east-1',
            'endpoint_url': 'http://localhost:4566',  # LocalStack for dev
            'aws_access_key_id': 'test',
            'aws_secret_access_key': 'test',
        },
    }
}

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_dynamodb_backend',
    'myapp',  # Your application
]
```

### Create Your Django App

```bash
python manage.py startapp myapp
```

## Step 3: Create Your First Model

### myapp/models.py

```python
from django.db import models
from django_dynamodb_backend.models import DynamoDBModel

class Book(DynamoDBModel):
    """A simple book model to demonstrate DynamoDB integration."""
    
    # Primary key - must be unique
    isbn = models.CharField(primary_key=True, max_length=13, 
                           help_text="13-digit ISBN code")
    
    # Book information
    title = models.CharField(max_length=200)
    author = models.CharField(max_length=100)
    publisher = models.CharField(max_length=100)
    
    # Publication details
    publication_date = models.DateField()
    pages = models.IntegerField()
    price = models.DecimalField(max_digits=6, decimal_places=2)
    
    # Categories
    genre = models.CharField(max_length=50, choices=[
        ('fiction', 'Fiction'),
        ('non-fiction', 'Non-Fiction'),
        ('mystery', 'Mystery'),
        ('romance', 'Romance'),
        ('sci-fi', 'Science Fiction'),
        ('biography', 'Biography'),
    ])
    
    # Status
    is_available = models.BooleanField(default=True)
    is_bestseller = models.BooleanField(default=False)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Optional fields
    description = models.TextField(blank=True)
    cover_image_url = models.URLField(blank=True)
    
    def __str__(self):
        return f"{self.title} by {self.author}"
    
    @property
    def is_recent(self):
        """Check if book was published in the last 2 years."""
        from datetime import date, timedelta
        return self.publication_date >= (date.today() - timedelta(days=730))
```

## Step 4: Create Migration

### Create the migration file

```bash
python manage.py dynamodb_makemigrations myapp --create-table Book
```

This creates a file like `myapp/dynamodb_migrations/0001_create_book_table.py`:

```python
from django_dynamodb_backend.migrations_dynamo import DynamoDBMigration, CreateTable
from myapp.models import Book

class Migration(DynamoDBMigration):
    dependencies = []
    
    operations = [
        CreateTable(
            model_class=Book,
            read_capacity=5,
            write_capacity=5
        ),
    ]
```

### Apply the migration

```bash
# View what will be created
python manage.py dynamodb_migrate --plan

# Apply the migration
python manage.py dynamodb_migrate
```

## Step 5: Configure Admin Interface

### myapp/admin.py

```python
from django.contrib import admin
from django_dynamodb_backend.admin import DynamoDBAdmin
from django_dynamodb_backend.admin_filters import DynamoDBBooleanFilter, DynamoDBDateRangeFilter
from .models import Book

class GenreFilter(admin.SimpleListFilter):
    title = 'genre'
    parameter_name = 'genre'
    
    def lookups(self, request, model_admin):
        return Book.genre.field.choices
    
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(genre=self.value())
        return queryset

class AvailabilityFilter(DynamoDBBooleanFilter):
    title = 'availability'
    parameter_name = 'is_available'

class PublicationDateFilter(DynamoDBDateRangeFilter):
    title = 'publication date'
    parameter_name = 'publication_date'

@admin.register(Book)
class BookAdmin(DynamoDBAdmin):
    # List view configuration
    list_display = [
        'title', 'author', 'genre', 'price', 
        'is_available', 'is_bestseller', 'publication_date'
    ]
    list_display_links = ['title']
    list_editable = ['is_available', 'is_bestseller', 'price']
    
    # Filtering and search
    list_filter = [
        GenreFilter,
        AvailabilityFilter,
        PublicationDateFilter,
        'publisher',
    ]
    search_fields = ['title', 'author', 'publisher', 'isbn']
    
    # Form organization
    fieldsets = [
        (None, {
            'fields': ['isbn', 'title', 'author', 'description']
        }),
        ('Publication Details', {
            'fields': ['publisher', 'publication_date', 'pages', 'genre']
        }),
        ('Pricing & Availability', {
            'fields': ['price', 'is_available', 'is_bestseller']
        }),
        ('Media', {
            'fields': ['cover_image_url'],
            'classes': ['collapse']
        }),
    ]
    
    # Read-only fields
    readonly_fields = ['created_at', 'updated_at']
    
    # Pagination
    list_per_page = 25
    
    # Custom actions
    actions = ['mark_as_bestseller', 'mark_as_available', 'export_to_csv']
    
    def mark_as_bestseller(self, request, queryset):
        count = queryset.update(is_bestseller=True)
        self.message_user(request, f"Marked {count} book(s) as bestsellers.")
    mark_as_bestseller.short_description = "Mark as bestseller"
    
    def mark_as_available(self, request, queryset):
        count = queryset.update(is_available=True)
        self.message_user(request, f"Marked {count} book(s) as available.")
    mark_as_available.short_description = "Mark as available"
```

## Step 6: Create and Test Data

### Using Django Shell

```bash
python manage.py shell
```

```python
from myapp.models import Book
from datetime import date
from decimal import Decimal

# Create sample books
book1 = Book(
    isbn='9781234567890',
    title='Django for Beginners',
    author='William S. Vincent',
    publisher='WelcomeToCode',
    publication_date=date(2022, 1, 15),
    pages=300,
    price=Decimal('29.99'),
    genre='non-fiction',
    is_available=True,
    description='Learn Django web development from scratch.'
)
book1.save()

book2 = Book(
    isbn='9780987654321',
    title='The Python Way',
    author='Jane Doe',
    publisher='TechBooks',
    publication_date=date(2023, 6, 10),
    pages=450,
    price=Decimal('39.99'),
    genre='non-fiction',
    is_bestseller=True,
    description='Advanced Python programming techniques.'
)
book2.save()

# Query examples
print("All books:", Book.objects.all())
print("Available books:", Book.objects.filter(is_available=True))
print("Recent books:", [book for book in Book.objects.all() if book.is_recent])
print("Fiction books:", Book.objects.filter(genre='fiction'))
```

### Using the Admin Interface

1. Create a superuser:
```bash
python manage.py createsuperuser
```

2. Start the development server:
```bash
python manage.py runserver
```

3. Navigate to `http://localhost:8000/admin/` and log in

## Step 7: Testing Your Setup

### Create a simple test file

Create `myapp/tests.py`:

```python
from django.test import TestCase
from django.core.exceptions import ValidationError
from datetime import date
from decimal import Decimal
from .models import Book

class BookModelTest(TestCase):
    def setUp(self):
        self.book_data = {
            'isbn': '9781234567890',
            'title': 'Test Book',
            'author': 'Test Author',
            'publisher': 'Test Publisher',
            'publication_date': date(2023, 1, 1),
            'pages': 200,
            'price': Decimal('19.99'),
            'genre': 'fiction'
        }
    
    def test_book_creation(self):
        """Test basic book creation and string representation."""
        book = Book(**self.book_data)
        book.save()
        
        self.assertEqual(str(book), 'Test Book by Test Author')
        self.assertTrue(book.is_available)  # Default value
        self.assertFalse(book.is_bestseller)  # Default value
    
    def test_is_recent_property(self):
        """Test the is_recent property."""
        # Recent book
        recent_book = Book(**self.book_data)
        recent_book.save()
        self.assertTrue(recent_book.is_recent)
        
        # Old book
        old_book_data = self.book_data.copy()
        old_book_data['isbn'] = '9780000000000'
        old_book_data['publication_date'] = date(2000, 1, 1)
        old_book = Book(**old_book_data)
        old_book.save()
        self.assertFalse(old_book.is_recent)
    
    def test_book_queries(self):
        """Test various query patterns."""
        # Create test books
        book1 = Book(**self.book_data)
        book1.save()
        
        book2_data = self.book_data.copy()
        book2_data['isbn'] = '9780000000000'
        book2_data['genre'] = 'non-fiction'
        book2_data['is_bestseller'] = True
        book2 = Book(**book2_data)
        book2.save()
        
        # Test queries
        self.assertEqual(Book.objects.count(), 2)
        self.assertEqual(Book.objects.filter(genre='fiction').count(), 1)
        self.assertEqual(Book.objects.filter(is_bestseller=True).count(), 1)
        self.assertEqual(Book.objects.filter(author='Test Author').count(), 2)
```

### Run the tests

```bash
python manage.py test myapp --settings=test_settings
```

## What We've Accomplished

1. ✅ Set up Django with DynamoDB backend
2. ✅ Created a DynamoDB model with various field types
3. ✅ Created and applied migrations
4. ✅ Configured a comprehensive admin interface
5. ✅ Added custom admin actions and filters
6. ✅ Created and tested sample data
7. ✅ Wrote tests for the model

## Next Steps

- **Tutorial 2**: Advanced Relationships and Queries
- **Tutorial 3**: Custom Admin Actions and Bulk Operations
- **Tutorial 4**: Performance Optimization and Caching
- **Tutorial 5**: Production Deployment

## Common Issues and Solutions

### Issue: DynamoDB Local not starting
**Solution**: Check Java installation and port availability:
```bash
java -version  # Should show Java 8 or higher
lsof -i :8000  # Check if port is in use
```

### Issue: Migration fails
**Solution**: Check AWS credentials and table permissions:
```bash
aws dynamodb list-tables --endpoint-url http://localhost:8000
```

### Issue: Admin interface not showing data
**Solution**: Verify data exists and admin configuration:
```python
python manage.py shell
>>> from myapp.models import Book
>>> Book.objects.count()
```

Congratulations! You've successfully set up Django with DynamoDB and created your first model with admin interface.