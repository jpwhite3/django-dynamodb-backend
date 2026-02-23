# DynamoDB Django Admin - API Reference

This document provides detailed API reference for all components of the DynamoDB Django Admin system.

## Table of Contents

- [Models](#models)
- [QuerySet and Manager](#queryset-and-manager)
- [Admin Classes](#admin-classes)
- [Sessions](#sessions)
- [Authentication (auth_dynamo)](#authentication-auth_dynamo)
- [Migration System](#migration-system)
- [Filters](#filters)
- [Forms](#forms)
- [Database Backend](#database-backend)
- [Management Commands](#management-commands)

## Models

### DynamoDBModel

Base model class that provides DynamoDB integration for Django models.

```python
class DynamoDBModel(models.Model, metaclass=DynamoDBModelMeta)
```

#### Methods

##### `save(force_insert=False, force_update=False, using=None, update_fields=None)`

Saves the model instance to DynamoDB.

**Parameters:**
- `force_insert` (bool): Force INSERT operation
- `force_update` (bool): Force UPDATE operation  
- `using` (str): Database alias to use
- `update_fields` (list): List of field names to update

**Returns:** None

**Raises:**
- `ImproperlyConfigured`: If PynamoDB model is not properly configured
- `ValidationError`: If model validation fails

**Example:**
```python
book = Book(isbn='123', title='Test Book')
book.save()
```

##### `delete(using=None, keep_parents=False)`

Deletes the model instance from DynamoDB.

**Parameters:**
- `using` (str): Database alias to use
- `keep_parents` (bool): Keep parent records (not applicable for DynamoDB)

**Returns:** None

**Raises:**
- `DoesNotExist`: If object doesn't exist in DynamoDB

##### `refresh_from_db(using=None, fields=None)`

Refreshes the model instance from DynamoDB.

**Parameters:**
- `using` (str): Database alias to use
- `fields` (list): List of field names to refresh

**Returns:** None

##### `_get_pynamodb_model()`

Class method that returns the associated PynamoDB model class.

**Returns:** PynamoDB Model class

**Raises:**
- `ImproperlyConfigured`: If PynamoDB model is not created

#### Properties

##### `_field_values`

Dictionary containing the current field values for the instance.

**Type:** `dict`

#### Example Usage

```python
from django_dynamodb_backend.models import DynamoDBModel
from django.db import models

class MyModel(DynamoDBModel):
    id = models.CharField(primary_key=True, max_length=50)
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name

# Usage
instance = MyModel(id='test-id', name='Test Name')
instance.save()

# Refresh from database
instance.refresh_from_db()

# Delete
instance.delete()
```

---

## QuerySet and Manager

### DynamoDBManager

Custom manager for DynamoDB models that provides Django ORM-like interface.

```python
class DynamoDBManager(models.Manager)
```

#### Methods

##### `get_queryset()`

Returns a DynamoDBQuerySet instance.

**Returns:** `DynamoDBQuerySet`

##### `create(**kwargs)`

Creates and saves a new model instance.

**Parameters:**
- `**kwargs`: Field values for the new instance

**Returns:** Model instance

**Example:**
```python
book = Book.objects.create(
    isbn='123456789',
    title='New Book',
    author='Author Name'
)
```

### DynamoDBQuerySet

Custom QuerySet implementation optimized for DynamoDB operations.

```python
class DynamoDBQuerySet(models.QuerySet)
```

#### Query Methods

##### `filter(**kwargs)`

Filters the queryset based on given parameters.

**Parameters:**
- `**kwargs`: Field lookups

**Returns:** `DynamoDBQuerySet`

**Supported Lookups:**
- `exact`: Exact match (default)
- `iexact`: Case-insensitive exact match
- `contains`: Contains substring
- `icontains`: Case-insensitive contains
- `startswith`: Starts with string
- `endswith`: Ends with string
- `gt`: Greater than
- `gte`: Greater than or equal
- `lt`: Less than
- `lte`: Less than or equal
- `in`: In list of values
- `range`: Between two values

**Example:**
```python
# Basic filtering
books = Book.objects.filter(genre='fiction')
recent_books = Book.objects.filter(pub_date__gte=datetime.now() - timedelta(days=30))

# Multiple conditions
popular_books = Book.objects.filter(
    is_bestseller=True,
    price__lte=50,
    genre__in=['fiction', 'mystery']
)
```

##### `exclude(**kwargs)`

Excludes records matching the given parameters.

**Parameters:**
- `**kwargs`: Field lookups

**Returns:** `DynamoDBQuerySet`

##### `order_by(*fields)`

Orders the queryset by given fields. Note: DynamoDB has limited ordering support.

**Parameters:**
- `*fields`: Field names to order by

**Returns:** `DynamoDBQuerySet`

**Note:** DynamoDB ordering is limited to sort keys and may require Global Secondary Indexes.

##### `distinct(field=None)`

Returns distinct values. Limited support in DynamoDB.

**Parameters:**
- `field` (str): Field name for distinct values

**Returns:** `DynamoDBQuerySet`

##### `count()`

Returns the count of objects in the queryset.

**Returns:** `int`

**Note:** Uses DynamoDB's Count operation when possible, otherwise performs a scan.

##### `exists()`

Returns True if the queryset contains any results.

**Returns:** `bool`

##### `first()`

Returns the first object in the queryset, or None if empty.

**Returns:** Model instance or None

##### `last()`

Returns the last object in the queryset, or None if empty.

**Returns:** Model instance or None

##### `get(**kwargs)`

Returns a single object matching the given parameters.

**Parameters:**
- `**kwargs`: Field lookups

**Returns:** Model instance

**Raises:**
- `DoesNotExist`: If no object is found
- `MultipleObjectsReturned`: If multiple objects are found

#### Bulk Operations

##### `update(**kwargs)`

Updates all objects in the queryset with the given values.

**Parameters:**
- `**kwargs`: Field values to update

**Returns:** `int` - Number of updated objects

**Example:**
```python
# Update all fiction books to be featured
updated_count = Book.objects.filter(genre='fiction').update(is_featured=True)
```

##### `delete()`

Deletes all objects in the queryset.

**Returns:** `tuple` - (number_deleted, {model_label: count})

**Example:**
```python
# Delete all draft posts
deleted_count, details = Book.objects.filter(status='draft').delete()
```

#### Aggregation Methods

##### `aggregate(**kwargs)`

Performs aggregation operations. Limited support in DynamoDB.

**Parameters:**
- `**kwargs`: Aggregation functions

**Returns:** `dict`

**Supported Aggregations:**
- `Count`: Count of objects
- `Sum`: Sum of numeric fields (limited)
- `Avg`: Average of numeric fields (limited)
- `Max`: Maximum value (limited)
- `Min`: Minimum value (limited)

**Example:**
```python
from django.db.models import Count, Avg

# Basic aggregations
stats = Book.objects.aggregate(
    total_books=Count('id'),
    avg_price=Avg('price')
)
```

#### DynamoDB-Specific Methods

##### `scan_filter(**kwargs)`

Applies DynamoDB scan filters directly.

**Parameters:**
- `**kwargs`: DynamoDB filter expressions

**Returns:** `DynamoDBQuerySet`

##### `set_last_evaluated_key(key)`

Sets the LastEvaluatedKey for pagination.

**Parameters:**
- `key` (dict): DynamoDB LastEvaluatedKey

**Returns:** `DynamoDBQuerySet`

---

## Sessions

### SessionStore

DynamoDB-backed session store implementing Django's session backend API.

```python
from django_dynamodb_backend.sessions import SessionStore
```

#### Configuration

```python
# settings.py
SESSION_ENGINE = 'django_dynamodb_backend.sessions'
DYNAMODB_SESSION_TABLE_NAME = 'django_sessions'  # Default
```

#### Methods

##### `load()`
Load session data from DynamoDB.

**Returns:** `dict` - Session data

##### `save(must_create=False)`
Save session data to DynamoDB.

**Parameters:**
- `must_create` (bool): If True, raise CreateError if session already exists

##### `delete(session_key=None)`
Delete a session from DynamoDB.

##### `exists(session_key)`
Check if a session key exists.

**Returns:** `bool`

##### `create()`
Create a new session with a unique key.

##### `clear_expired()`
No-op since DynamoDB TTL handles expiration automatically.

### create_session_table()

Create the DynamoDB sessions table with TTL enabled.

```python
from django_dynamodb_backend.sessions import create_session_table

create_session_table()
```

**Table Schema:**
- Partition Key: `session_key` (String)
- TTL Attribute: `expire_date` (Number, Unix timestamp)
- Billing Mode: PAY_PER_REQUEST

---

## Authentication (auth_dynamo)

### DynamoUser

DynamoDB-backed User model compatible with Django's auth system.

```python
from django_dynamodb_backend.contrib.auth_dynamo.models import DynamoUser
```

#### Configuration

```python
# settings.py
INSTALLED_APPS = [
    ...
    'django_dynamodb_backend.contrib.auth_dynamo',
]

AUTH_USER_MODEL = 'auth_dynamo.DynamoUser'
DYNAMODB_USER_TABLE_NAME = 'django_users'  # Default

AUTHENTICATION_BACKENDS = [
    'django_dynamodb_backend.contrib.auth_dynamo.backends.DynamoAuthBackend',
]
```

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | CharField (PK) | UUID primary key |
| `username` | CharField | Unique username (GSI) |
| `email` | EmailField | Email address (GSI) |
| `password` | CharField | Hashed password |
| `first_name` | CharField | First name |
| `last_name` | CharField | Last name |
| `is_active` | BooleanField | Active status |
| `is_staff` | BooleanField | Staff status |
| `is_superuser` | BooleanField | Superuser status |
| `date_joined` | DateTimeField | Registration date |
| `last_login` | DateTimeField | Last login time |
| `user_permissions` | TextField | Comma-separated permissions |
| `groups` | TextField | Comma-separated group names |

#### Methods

##### `set_password(raw_password)`
Hash and set the password.

##### `check_password(raw_password)`
Check if the provided password matches.

**Returns:** `bool`

##### `has_perm(perm, obj=None)`
Check if user has a specific permission.

**Returns:** `bool`

##### `has_module_perms(app_label)`
Check if user has any permission in the app.

**Returns:** `bool`

##### `get_all_permissions(obj=None)`
Return all permissions the user has.

**Returns:** `set`

##### `add_permission(perm)`
Add a permission to the user.

##### `remove_permission(perm)`
Remove a permission from the user.

#### Example

```python
from django_dynamodb_backend.contrib.auth_dynamo.models import DynamoUser

# Create user
user = DynamoUser.objects.create_user(
    username='john',
    email='john@example.com',
    password='secret123'
)

# Create superuser
admin = DynamoUser.objects.create_superuser(
    username='admin',
    email='admin@example.com',
    password='admin123'
)

# Check permissions
if user.has_perm('myapp:model:add'):
    ...
```

### DynamoUserManager

Manager for DynamoUser with authentication-specific methods.

```python
from django_dynamodb_backend.contrib.auth_dynamo.managers import DynamoUserManager
```

#### Methods

##### `create_user(username, email=None, password=None, **extra_fields)`
Create a regular user.

**Parameters:**
- `username` (str): Required username
- `email` (str): Optional email
- `password` (str): Password (will be hashed)
- `**extra_fields`: Additional fields

**Returns:** `DynamoUser`

##### `create_superuser(username, email=None, password=None, **extra_fields)`
Create a superuser with staff and superuser flags.

**Returns:** `DynamoUser`

##### `get(pk=None, username=None, email=None)`
Get user by primary key, username (GSI), or email (GSI).

**Returns:** `DynamoUser`

**Raises:** `DynamoUser.DoesNotExist`

### DynamoAuthBackend

Authentication backend for DynamoDB users.

```python
from django_dynamodb_backend.contrib.auth_dynamo.backends import DynamoAuthBackend
```

#### Methods

##### `authenticate(request, username=None, password=None, **kwargs)`
Authenticate a user by username and password.

**Returns:** `DynamoUser` or `None`

##### `get_user(user_id)`
Get a user by their primary key.

**Returns:** `DynamoUser` or `None`

### create_user_table()

Create the DynamoDB users table with GSIs.

```python
from django_dynamodb_backend.contrib.auth_dynamo.models import create_user_table

create_user_table()
```

**Table Schema:**
- Partition Key: `id` (String)
- GSI `username-index`: Partition Key = `username`
- GSI `email-index`: Partition Key = `email`
- Billing Mode: PAY_PER_REQUEST

---

## Admin Classes

### DynamoDBAdmin

Enhanced admin class for DynamoDB models with full Django Admin compatibility.

```python
class DynamoDBAdmin(DynamoDBCoreMixin, DynamoDBActionsMixin, DynamoDBSecurityMixin, ModelAdmin)
```

#### Attributes

##### `list_display`
Fields to display in the change list.
**Type:** `list` or `tuple`
**Default:** Auto-generated from model fields

##### `list_filter`
Filters to show in the admin sidebar.
**Type:** `list` or `tuple`
**Default:** Auto-generated for common fields

##### `search_fields`
Fields to include in search functionality.
**Type:** `list` or `tuple`
**Default:** Auto-generated for text fields

##### `actions`
Admin actions available for bulk operations.
**Type:** `list`
**Default:** `['delete_selected_optimized', 'export_to_csv']`

##### `list_per_page`
Number of items to show per page.
**Type:** `int`
**Default:** `25`

#### Methods

##### `get_queryset(request)`

Returns the queryset for the admin changelist.

**Parameters:**
- `request`: HTTP request object

**Returns:** `DynamoDBQuerySet`

##### `get_paginator(request, queryset, per_page, orphans=0, allow_empty_first_page=True)`

Returns a paginator instance optimized for DynamoDB.

**Returns:** `DynamoDBPaginator`

##### `get_search_results(request, queryset, search_term)`

Performs search on the queryset.

**Parameters:**
- `request`: HTTP request object
- `queryset`: Base queryset
- `search_term` (str): Search term

**Returns:** `tuple` - (filtered_queryset, use_distinct)

#### Custom Actions

##### `delete_selected_optimized(request, queryset)`

Optimized bulk delete action for DynamoDB.

**Parameters:**
- `request`: HTTP request object
- `queryset`: Objects to delete

##### `export_to_csv(request, queryset)`

Exports selected objects to CSV format.

**Parameters:**
- `request`: HTTP request object
- `queryset`: Objects to export

**Returns:** HTTP response with CSV file

#### Example Usage

```python
from django.contrib import admin
from django_dynamodb_backend.admin import DynamoDBAdmin
from .models import Book

@admin.register(Book)
class BookAdmin(DynamoDBAdmin):
    list_display = ['title', 'author', 'genre', 'price', 'is_available']
    list_filter = ['genre', 'is_available', 'publication_date']
    search_fields = ['title', 'author', 'isbn']
    list_editable = ['price', 'is_available']
    
    fieldsets = [
        (None, {'fields': ['isbn', 'title', 'author']}),
        ('Details', {'fields': ['genre', 'price', 'publication_date']}),
        ('Status', {'fields': ['is_available', 'is_bestseller']}),
    ]
    
    actions = ['mark_as_bestseller', 'export_to_csv']
    
    def mark_as_bestseller(self, request, queryset):
        count = queryset.update(is_bestseller=True)
        self.message_user(request, f"Marked {count} books as bestsellers.")
    mark_as_bestseller.short_description = "Mark as bestseller"
```

### DynamoDBChangeList

Custom ChangeList implementation for DynamoDB admin views.

```python
class DynamoDBChangeList(ChangeList)
```

#### Methods

##### `get_queryset(request)`

Returns the filtered and sorted queryset for the changelist.

**Returns:** `DynamoDBQuerySet`

##### `get_results(request)`

Executes the queryset and retrieves results.

### DynamoDBPaginator

Custom paginator optimized for DynamoDB operations.

```python
class DynamoDBPaginator(Paginator)
```

#### Properties

##### `count`
Total number of objects (may be estimated for performance).
**Type:** `int`

#### Methods

##### `get_page(number)`

Returns a page object for the given page number.

**Parameters:**
- `number` (int): Page number

**Returns:** `Page` object

---

## Migration System

### DynamoDBMigration

Base class for DynamoDB migrations.

```python
class DynamoDBMigration
```

#### Attributes

##### `dependencies`
List of migration dependencies.
**Type:** `list` of `tuple`
**Format:** `[('app_label', 'migration_name'), ...]`

##### `operations`
List of migration operations to perform.
**Type:** `list` of `DynamoDBOperation`

#### Methods

##### `apply(**kwargs)`

Applies the migration by executing all operations.

**Parameters:**
- `**kwargs`: Additional parameters

##### `unapply(**kwargs)`

Reverses the migration by reversing all operations.

**Parameters:**
- `**kwargs`: Additional parameters

#### Example

```python
from django_dynamodb_backend.migrations_dynamo import DynamoDBMigration, CreateTable
from myapp.models import Book

class Migration(DynamoDBMigration):
    dependencies = []
    
    operations = [
        CreateTable(
            model_class=Book,
            read_capacity=10,
            write_capacity=5
        ),
    ]
```

### Migration Operations

#### CreateTable

Creates a DynamoDB table for a model.

```python
CreateTable(model_class, read_capacity=5, write_capacity=5)
```

**Parameters:**
- `model_class`: Django model class
- `read_capacity` (int): Read capacity units
- `write_capacity` (int): Write capacity units

#### UpdateTableCapacity

Updates read/write capacity for a table.

```python
UpdateTableCapacity(model_class, read_capacity=None, write_capacity=None)
```

**Parameters:**
- `model_class`: Django model class
- `read_capacity` (int): New read capacity units
- `write_capacity` (int): New write capacity units

#### DataMigration

Performs data migration operations.

```python
DataMigration(model_class, migration_func, reverse_func=None)
```

**Parameters:**
- `model_class`: Django model class
- `migration_func`: Function to apply to each item
- `reverse_func`: Function to reverse the migration

#### RunPython

Executes custom Python code.

```python
RunPython(code_func, reverse_code_func=None)
```

**Parameters:**
- `code_func`: Function or code string to execute
- `reverse_code_func`: Reverse function or code string

### Management Commands

#### `dynamodb_migrate`

Applies DynamoDB migrations.

```bash
python manage.py dynamodb_migrate [app_label] [migration_name]
```

**Options:**
- `--fake`: Mark migrations as applied without executing
- `--list`: Show migration status
- `--plan`: Show migration plan without executing

#### `dynamodb_makemigrations`

Creates new migration files.

```bash
python manage.py dynamodb_makemigrations app_label
```

**Options:**
- `--name NAME`: Custom migration name
- `--empty`: Create empty migration
- `--create-table MODEL`: Create table operation for model
- `--data-migration`: Create data migration template

#### `dynamodb_rollback`

Rollback to a specific migration.

```bash
python manage.py dynamodb_rollback app_label migration_name
```

#### `dynamodb_showmigrations`

Show migration status.

```bash
python manage.py dynamodb_showmigrations [app_label]
```

**Options:**
- `--verbose`: Show detailed information
- `--format {table,json}`: Output format

---

## Filters

### DynamoDBListFilter

Base filter class optimized for DynamoDB operations.

```python
class DynamoDBListFilter(SimpleListFilter)
```

#### Methods

##### `queryset(request, queryset)`

Applies the filter to the queryset.

**Parameters:**
- `request`: HTTP request object
- `queryset`: Base queryset

**Returns:** Filtered queryset

### Specific Filter Classes

#### DynamoDBBooleanFilter

Filter for boolean fields.

```python
class DynamoDBBooleanFilter(DynamoDBListFilter)
```

**Usage:**
```python
class IsActiveFilter(DynamoDBBooleanFilter):
    title = 'active status'
    parameter_name = 'is_active'
```

#### DynamoDBDateRangeFilter

Filter for date range selections.

```python
class DynamoDBDateRangeFilter(DynamoDBListFilter)
```

**Options:**
- Today
- Yesterday  
- This week
- This month
- Last 30 days
- This year

#### DynamoDBNumericRangeFilter

Filter for numeric ranges.

```python
class DynamoDBNumericRangeFilter(DynamoDBListFilter)
```

#### DynamoDBTextSearchFilter

Filter for text search with contains operations.

```python
class DynamoDBTextSearchFilter(DynamoDBListFilter)
```

---

## Forms

### DynamoDBModelForm

Enhanced ModelForm for DynamoDB models.

```python
class DynamoDBModelForm(DynamoDBFormMixin, forms.ModelForm)
```

#### Methods

##### `clean()`

Enhanced validation for DynamoDB constraints.

**Returns:** Cleaned data dictionary

**Validates:**
- Primary key constraints
- DynamoDB data type limits
- Item size limits (400KB)

##### `save(commit=True)`

Saves the form data to a model instance.

**Parameters:**
- `commit` (bool): Whether to save to database

**Returns:** Model instance

#### Example

```python
from django_dynamodb_backend.admin_forms import DynamoDBModelForm
from .models import Book

class BookForm(DynamoDBModelForm):
    class Meta:
        model = Book
        fields = ['isbn', 'title', 'author', 'price']
    
    def clean_price(self):
        price = self.cleaned_data.get('price')
        if price and price < 0:
            raise ValidationError("Price cannot be negative.")
        return price
```

### Form Widgets

#### DynamoDBTextInput

Enhanced text input widget.

#### DynamoDBTextarea

Enhanced textarea widget with auto-sizing.

#### DynamoDBNumberInput

Number input with validation.

#### JSONEditorWidget

JSON editor with syntax highlighting and validation.

#### UUIDWidget

UUID input with generation button.

---

## Database Backend

### DynamoDBWrapper

Database wrapper that provides Django ORM interface to DynamoDB.

```python
class DynamoDBWrapper
```

#### Methods

##### `connect()`

Establishes connection to DynamoDB.

##### `close()`

Closes the DynamoDB connection.

##### `execute_query(operation)`

Executes a DynamoDB operation.

**Parameters:**
- `operation` (dict): DynamoDB operation specification

**Returns:** Operation results

### Compiler Classes

#### DynamoDBCompiler

Base compiler for translating Django queries to DynamoDB operations.

#### DynamoDBInsertCompiler

Compiler for INSERT operations.

#### DynamoDBUpdateCompiler

Compiler for UPDATE operations.

#### DynamoDBDeleteCompiler

Compiler for DELETE operations.

---

## Error Handling

### Custom Exceptions

#### `DynamoDBError`

Base exception for DynamoDB-related errors.

#### `ValidationError`

Raised when data validation fails.

#### `ImproperlyConfigured`

Raised when configuration is invalid.

#### `DoesNotExist`

Raised when a requested object doesn't exist.

#### `MultipleObjectsReturned`

Raised when a get() query returns multiple objects.

---

## Configuration Reference

### Database Settings

```python
DATABASES = {
    'default': {
        'ENGINE': 'django_dynamodb_backend.db',
        'NAME': 'my_app',
        'OPTIONS': {
            'region_name': 'us-east-1',
            'endpoint_url': 'http://localhost:4566',  # Optional, for LocalStack
            'aws_access_key_id': 'test',  # Optional, uses IAM role if omitted
            'aws_secret_access_key': 'test',  # Optional
        }
    }
}
```

### Admin Settings

```python
# Custom admin site
DYNAMODB_ADMIN_SITE_HEADER = "Custom DynamoDB Admin"
DYNAMODB_ADMIN_SITE_TITLE = "DynamoDB Admin"
DYNAMODB_ADMIN_INDEX_TITLE = "DynamoDB Administration"

# Pagination
DYNAMODB_ADMIN_LIST_PER_PAGE = 25
DYNAMODB_ADMIN_LIST_MAX_SHOW_ALL = 200

# Performance
DYNAMODB_ADMIN_ENABLE_CACHING = True
DYNAMODB_ADMIN_CACHE_TIMEOUT = 300
```

### Migration Settings

```python
# Migration table name
DYNAMODB_MIGRATION_TABLE = 'django_dynamodb_migrations'

# Migration batch size
DYNAMODB_MIGRATION_BATCH_SIZE = 25
```

---

## Management Commands

### dynamodb_create_session_table

Create the DynamoDB sessions table with TTL enabled.

```bash
python manage.py dynamodb_create_session_table
```

### dynamodb_create_user_table

Create the DynamoDB users table with GSIs.

```bash
# Create table only
python manage.py dynamodb_create_user_table

# Create table and admin user
python manage.py dynamodb_create_user_table --create-admin

# Custom admin credentials
python manage.py dynamodb_create_user_table --create-admin \
    --admin-username=myadmin \
    --admin-password=mypassword \
    --admin-email=admin@example.com
```

**Options:**
- `--create-admin`: Also create an admin superuser
- `--admin-username`: Username for admin (default: `admin`)
- `--admin-password`: Password for admin (default: `admin123`)
- `--admin-email`: Email for admin (default: `admin@example.com`)

### dynamodb_migrate

Apply DynamoDB migrations.

```bash
python manage.py dynamodb_migrate [app_label] [migration_name]
```

**Options:**
- `--fake`: Mark migrations as applied without executing
- `--list`: Show migration status
- `--plan`: Show migration plan without executing

### dynamodb_makemigrations

Create new DynamoDB migration files.

```bash
python manage.py dynamodb_makemigrations app_label
```

**Options:**
- `--name NAME`: Custom migration name
- `--empty`: Create empty migration
- `--create-table MODEL`: Create table operation for model

### dynamodb_showmigrations

Show DynamoDB migration status.

```bash
python manage.py dynamodb_showmigrations [app_label]
```

### dynamodb_rollback

Rollback to a specific DynamoDB migration.

```bash
python manage.py dynamodb_rollback app_label migration_name
```

---

## Related Documentation

| Document | When to read |
|----------|-------------|
| [Documentation Index](INDEX.md) | Find the right doc for any task |
| [Migration Tutorial](MIGRATION_TUTORIAL.md) | Step-by-step setup guide |
| [Django Compatibility Guide](DJANGO_COMPATIBILITY.md) | Check feature support and limitations |
| [Deployment Guide](DEPLOYMENT_GUIDE.md) | Production deployment instructions |
| [Feature Walkthrough](FEATURE_WALKTHROUGH.md) | Deep-dive with code examples |
