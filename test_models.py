#!/usr/bin/env python3
"""
Simple test script to verify our DynamoDB model integration works.
"""

import os
import sys

import django

# Set up Django environment
sys.path.insert(0, "django_dynamo_admin")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_dynamo_admin.settings")
django.setup()

from dynamodb_adapter.models import Choice, MyModel, Question


def test_model_creation():
    """Test creating PynamoDB models from Django models."""
    print("Testing model creation...")

    try:
        # Test MyModel
        print("\n1. Testing MyModel PynamoDB model creation...")
        pynamodb_model = MyModel._get_pynamodb_model()
        print(f"   ✓ MyModel PynamoDB model created: {pynamodb_model.__name__}")
        print(f"   ✓ Table name: {pynamodb_model.Meta.table_name}")
        print(f"   ✓ Region: {pynamodb_model.Meta.region}")

        # Test Question
        print("\n2. Testing Question PynamoDB model creation...")
        question_pynamodb_model = Question._get_pynamodb_model()
        print(
            f"   ✓ Question PynamoDB model created: {question_pynamodb_model.__name__}"
        )
        print(f"   ✓ Table name: {question_pynamodb_model.Meta.table_name}")

        # Test Choice
        print("\n3. Testing Choice PynamoDB model creation...")
        choice_pynamodb_model = Choice._get_pynamodb_model()
        print(f"   ✓ Choice PynamoDB model created: {choice_pynamodb_model.__name__}")
        print(f"   ✓ Table name: {choice_pynamodb_model.Meta.table_name}")

        return True

    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False


def test_model_instances():
    """Test creating model instances."""
    print("\n\nTesting model instances...")

    try:
        # Test creating a MyModel instance
        print("\n1. Testing MyModel instance creation...")
        my_model = MyModel(name="test_model", question_text="Test question")
        print(f"   ✓ MyModel instance created: {my_model}")

        # Test creating a Question instance
        print("\n2. Testing Question instance creation...")
        question = Question(question_text="What is your favorite color?")
        print(f"   ✓ Question instance created: {question}")

        # Test creating a Choice instance
        print("\n3. Testing Choice instance creation...")
        choice = Choice(question_id="1", choice_text="Blue", votes=0)
        print(f"   ✓ Choice instance created: {choice}")

        return True

    except Exception as e:
        print(f"   ✗ Error: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_field_mapping():
    """Test field mapping between Django and DynamoDB."""
    print("\n\nTesting field mapping...")

    try:
        from django.db import models
        from dynamodb_adapter.fields import FieldMapper
        from pynamodb.attributes import (BooleanAttribute, NumberAttribute,
                                         UnicodeAttribute)

        print("\n1. Testing CharField mapping...")
        char_field = models.CharField(max_length=100)
        mapped_attr = FieldMapper.get_dynamodb_attribute(char_field)
        assert mapped_attr == UnicodeAttribute
        print("   ✓ CharField -> UnicodeAttribute")

        print("\n2. Testing IntegerField mapping...")
        int_field = models.IntegerField()
        mapped_attr = FieldMapper.get_dynamodb_attribute(int_field)
        assert mapped_attr == NumberAttribute
        print("   ✓ IntegerField -> NumberAttribute")

        print("\n3. Testing BooleanField mapping...")
        bool_field = models.BooleanField()
        mapped_attr = FieldMapper.get_dynamodb_attribute(bool_field)
        assert mapped_attr == BooleanAttribute
        print("   ✓ BooleanField -> BooleanAttribute")

        return True

    except Exception as e:
        print(f"   ✗ Error: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("Django DynamoDB Model Integration Test")
    print("=" * 60)

    success = True

    # Test model creation
    if not test_model_creation():
        success = False

    # Test model instances
    if not test_model_instances():
        success = False

    # Test field mapping
    if not test_field_mapping():
        success = False

    print("\n" + "=" * 60)
    if success:
        print("🎉 All tests passed! Phase 2 model integration is working!")
    else:
        print("❌ Some tests failed. Check the output above for details.")
    print("=" * 60)
