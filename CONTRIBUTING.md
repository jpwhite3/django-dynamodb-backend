# Contributing to Django DynamoDB Admin

We welcome contributions to Django DynamoDB Admin! This document provides guidelines for contributing to the project.

## 🚀 Getting Started

### Prerequisites

- Python 3.8+
- Django 4.2+
- AWS Account (for testing with DynamoDB)
- Git
- Virtual environment tool (venv, conda, etc.)

### Development Setup

1. **Fork and Clone the Repository**

```bash
# Fork the repository on GitHub, then clone your fork
git clone https://github.com/YOUR-USERNAME/django-dynamo-admin.git
cd django-dynamo-admin

# Add upstream remote
git remote add upstream https://github.com/original-org/django-dynamo-admin.git
```

2. **Set Up Development Environment**

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install development dependencies
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install
```

3. **Set Up Local Testing**

```bash
# Set up test environment
export DJANGO_SETTINGS_MODULE=test_settings

# Run quick validation
python tests/test_runner_complete.py --quick

# Run all tests
python tests/test_runner_complete.py
```

## 🛠️ Development Workflow

### Branch Strategy

- `main` - Production-ready code
- `develop` - Integration branch for features
- `feature/*` - New features
- `bugfix/*` - Bug fixes
- `hotfix/*` - Critical production fixes

### Making Changes

1. **Create a Feature Branch**

```bash
git checkout develop
git pull upstream develop
git checkout -b feature/your-feature-name
```

2. **Make Your Changes**

- Follow the [Code Style Guidelines](#code-style)
- Add tests for new functionality
- Update documentation as needed
- Ensure all tests pass

3. **Test Your Changes**

```bash
# Run all tests
python tests/test_runner_complete.py

# Run specific test phase
python tests/test_runner_complete.py --phase 7

# Test enhanced admin features
DJANGO_SETTINGS_MODULE=test_settings python -c "import tests.test_enhanced_admin_features"

# Run performance tests
python manage.py dynamodb_performance --format json
```

4. **Commit Your Changes**

```bash
# Add files
git add .

# Commit with descriptive message
git commit -m "feat: add GSI optimization recommendations

- Implement automatic GSI selection based on query patterns
- Add performance monitoring dashboard
- Include cost estimation for operations
- Add comprehensive test coverage

Closes #123"
```

5. **Push and Create Pull Request**

```bash
git push origin feature/your-feature-name
```

Then create a pull request on GitHub.

## 📝 Code Style Guidelines

### Python Code Style

We follow PEP 8 with some project-specific conventions:

- **Line Length**: 88 characters (Black formatter default)
- **Imports**: Use isort for import sorting
- **Type Hints**: Required for all public functions and methods
- **Docstrings**: Google-style docstrings for all public functions

```python
from typing import Dict, List, Optional, Union
from django.db import models
from dynamodb_adapter.models import DynamoDBModel

class ExampleAdmin(DynamoDBAdmin):
    """Example admin class with proper documentation.
    
    This class demonstrates the proper style for Django Admin classes
    in the DynamoDB Django Admin project.
    
    Attributes:
        list_display: Fields to display in the admin list view.
        search_fields: Fields to include in admin search.
    """
    
    list_display: List[str] = ['name', 'created_at', 'is_active']
    search_fields: List[str] = ['name', 'description']
    
    def get_queryset(self, request: HttpRequest) -> QuerySet:
        """Get optimized queryset for admin interface.
        
        Args:
            request: The HTTP request object.
            
        Returns:
            Optimized queryset with DynamoDB-specific enhancements.
        """
        return super().get_queryset(request)
```

### Code Formatting

We use automated code formatting tools:

```bash
# Format code with black
black .

# Sort imports with isort
isort .

# Check code quality with flake8
flake8 .

# Type checking with mypy
mypy dynamodb_adapter/
```

### Django Conventions

- **Models**: Use DynamoDBModel as base class
- **Admin**: Inherit from DynamoDBAdmin for enhanced features  
- **Forms**: Use DynamoDBModelForm for optimized validation
- **Views**: Follow Django's CBV patterns where possible

## 🧪 Testing Guidelines

### Test Structure

```
tests/
├── __init__.py
├── conftest.py                 # Test configuration
├── test_complete_integration.py # Full system tests
├── test_enhanced_admin_features.py # Enhanced feature tests
├── test_runner_complete.py     # Test runner
├── unit/                       # Unit tests
│   ├── test_database_backend.py
│   ├── test_models.py
│   └── test_migrations.py
├── integration/                # Integration tests
│   ├── test_admin_comprehensive.py
│   └── test_migration_integration.py
└── performance/                # Performance tests
    └── test_performance.py
```

### Writing Tests

1. **Unit Tests**: Test individual components in isolation

```python
class TestGSIOptimizer(TestCase):
    """Test GSI optimization functionality."""
    
    def setUp(self):
        self.optimizer = GSIOptimizer(MyModel)
    
    def test_gsi_selection(self):
        """Test automatic GSI selection for queries."""
        filters = {'category': 'electronics'}
        gsi_name, operation_type = self.optimizer.analyze_query_for_gsi(filters)
        
        self.assertIsNotNone(gsi_name)
        self.assertEqual(operation_type, 'query')
```

2. **Integration Tests**: Test component interactions

```python
class TestAdminIntegration(TestCase):
    """Test Django Admin integration."""
    
    def test_enhanced_admin_features(self):
        """Test that all enhanced features are available."""
        admin = DynamoDBAdmin(MyModel, AdminSite())
        
        # Test action integration
        actions = admin.get_actions(self.request)
        self.assertIn('bulk_update_with_confirmation', actions)
        
        # Test autocomplete integration
        self.assertTrue(hasattr(admin, 'autocomplete_fields'))
```

3. **Mock External Dependencies**: Use mocks for AWS services

```python
@patch('dynamodb_adapter.models.MyModel._get_pynamodb_model')
def test_model_operations(self, mock_get_model):
    """Test model operations with mocked DynamoDB."""
    mock_pynamodb_model = MagicMock()
    mock_get_model.return_value = mock_pynamodb_model
    
    # Test model creation
    obj = MyModel(name='Test')
    obj.save()
    
    mock_pynamodb_model.assert_called_once()
```

### Running Tests

```bash
# Run all tests
python tests/test_runner_complete.py

# Run specific test phase
python tests/test_runner_complete.py --phase 1

# Run with verbose output
python tests/test_runner_complete.py --verbose

# Quick validation test
python tests/test_runner_complete.py --quick
```

## 📚 Documentation Guidelines

### Documentation Structure

- **README.md**: Project overview and quick start
- **docs/API_REFERENCE.md**: Complete API documentation
- **docs/DEPLOYMENT_GUIDE.md**: Production deployment guide
- **examples/**: Working example applications
- **ENHANCED_ADMIN_FEATURES.md**: New admin capabilities

### Writing Documentation

1. **Use Clear Examples**: Always include working code examples

```python
# Good: Complete, runnable example
class BlogPostAdmin(DynamoDBAdmin):
    list_display = ['title', 'author', 'published_date']
    inlines = [CommentInline]
    actions = ['bulk_update_with_confirmation']
```

2. **Explain DynamoDB Concepts**: Help Django developers understand DynamoDB

```markdown
### GSI (Global Secondary Index) Optimization

DynamoDB Global Secondary Indexes allow querying on non-primary key attributes.
The admin interface automatically selects the optimal GSI based on your filters:

- **Hash Key Match**: When your filter includes a GSI hash key
- **Range Key Usage**: When range key filters can optimize the query
- **Projection Efficiency**: Considers which attributes are projected
```

3. **Include Performance Notes**: Explain performance implications

```markdown
⚠️ **Performance Note**: Scan operations are more expensive than Query operations.
The GSI optimizer automatically detects when filters can use a Query instead of Scan.
```

### API Documentation Format

Use Google-style docstrings:

```python
def analyze_query_for_gsi(
    self, 
    filters: Dict[str, Any], 
    ordering: List[str] = None
) -> Tuple[Optional[str], str]:
    """Analyze a query to determine the best GSI to use.
    
    Args:
        filters: Django ORM filter conditions.
        ordering: List of field names for ordering.
        
    Returns:
        Tuple of (gsi_name, operation_type). gsi_name is None if no 
        suitable GSI found. operation_type is either 'query' or 'scan'.
        
    Example:
        >>> optimizer = GSIOptimizer(MyModel)
        >>> gsi_name, op_type = optimizer.analyze_query_for_gsi(
        ...     {'category': 'electronics'},
        ...     ['created_at']
        ... )
        >>> print(f"Use {gsi_name} for {op_type} operation")
    """
```

## 🐛 Bug Reports

### Before Submitting

1. **Search Existing Issues**: Check if the bug has already been reported
2. **Test Against Latest**: Ensure the bug exists in the latest version
3. **Minimal Reproduction**: Create the smallest possible example

### Bug Report Template

```markdown
## Bug Description
Brief description of the issue.

## Steps to Reproduce
1. Create model with these fields...
2. Configure admin with these settings...
3. Navigate to admin interface...
4. Click on...

## Expected Behavior
What should happen.

## Actual Behavior
What actually happens.

## Environment
- Python version: 3.11.0
- Django version: 4.2.7
- DynamoDB Django Admin version: 1.0.0
- AWS Region: us-east-1
- DynamoDB Local: No

## Additional Context
- Error messages
- Screenshots
- Relevant configuration
```

## 🚀 Feature Requests

### Feature Request Template

```markdown
## Feature Description
Clear description of the requested feature.

## Use Case
Specific scenario where this feature would be helpful.

## Proposed Solution
How you envision this feature working.

## Alternative Solutions
Other approaches you've considered.

## DynamoDB Considerations
How this feature relates to DynamoDB's capabilities and limitations.
```

## 🔄 Pull Request Guidelines

### Pull Request Checklist

- [ ] **Code Quality**:
  - [ ] Code follows project style guidelines
  - [ ] All tests pass
  - [ ] New functionality has tests
  - [ ] Type hints are provided
  - [ ] Docstrings are complete

- [ ] **Documentation**:
  - [ ] README updated if needed
  - [ ] API documentation updated
  - [ ] Examples provided for new features
  - [ ] CHANGELOG.md updated

- [ ] **Testing**:
  - [ ] All existing tests pass
  - [ ] New tests cover new functionality
  - [ ] Integration tests updated if needed
  - [ ] Performance impact considered

- [ ] **Commit Messages**:
  - [ ] Follow conventional commit format
  - [ ] Include issue references
  - [ ] Clear and descriptive

### Pull Request Template

```markdown
## Description
Brief description of changes made.

## Type of Change
- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update

## Related Issues
Closes #123
Related to #456

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests pass
- [ ] Manual testing completed

## Screenshots (if applicable)
Include screenshots of admin interface changes.

## DynamoDB Considerations
How these changes work with DynamoDB's characteristics:
- Query vs Scan implications
- GSI usage
- Performance impact
- Cost considerations
```

## 🏆 Recognition

Contributors will be recognized in:
- **CONTRIBUTORS.md**: List of all contributors
- **Release Notes**: Major contribution acknowledgments
- **Documentation**: Author attribution for significant features

## 📞 Getting Help

- **GitHub Discussions**: For questions and community support
- **GitHub Issues**: For bug reports and feature requests
- **Code Review**: All PRs receive thorough review and feedback

## 🤝 Code of Conduct

We are committed to providing a welcoming and inclusive environment. Please:

- **Be Respectful**: Treat all contributors with respect
- **Be Inclusive**: Welcome developers of all skill levels
- **Be Constructive**: Provide helpful feedback and suggestions
- **Be Patient**: Remember that everyone is learning

Thank you for contributing to Django DynamoDB Admin! 🎉