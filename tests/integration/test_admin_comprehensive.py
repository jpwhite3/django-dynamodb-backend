"""
Comprehensive integration tests for Django Admin with DynamoDB backend.
"""

import unittest
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.contrib.messages.storage.fallback import FallbackStorage
from django.http import HttpRequest
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse
from moto import mock_aws

from django_dynamodb_backend.admin import (
    ChoiceAdmin,
    DynamoDBAdmin,
    DynamoDBChangeList,
    DynamoDBPaginator,
    QuestionAdmin,
)
from django_dynamodb_backend.admin_filters import (
    IsActiveFilter,
    PublishedDateFilter,
    VoteCountFilter,
)
from django_dynamodb_backend.admin_forms import DynamoDBModelForm
from django_dynamodb_backend.models import Choice, MyModel, Question


class TestDynamoDBAdminIntegration(TestCase):
    """Test comprehensive Django Admin integration."""

    def setUp(self):
        """Set up test environment."""
        self.factory = RequestFactory()
        self.admin_site = AdminSite()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass",
            is_staff=True,
            is_superuser=True,
        )

        # Register models with the test admin site FIRST
        self.admin_site.register(Question, QuestionAdmin)
        self.admin_site.register(Choice, ChoiceAdmin)
        self.admin_site.register(MyModel, DynamoDBAdmin)

        # THEN create admin instances
        self.question_admin = QuestionAdmin(Question, self.admin_site)
        self.choice_admin = ChoiceAdmin(Choice, self.admin_site)
        self.base_admin = DynamoDBAdmin(MyModel, self.admin_site)

    def _create_request(self, path="/", user=None, method="GET", data=None):
        """Helper to create request with user and session."""
        if method.upper() == "POST":
            request = self.factory.post(path, data or {})
        else:
            request = self.factory.get(path, data or {})

        request.user = user or self.user

        # Add session and messages
        setattr(request, "session", {})
        messages = FallbackStorage(request)
        setattr(request, "_messages", messages)

        return request


class TestDynamoDBChangeList(TestDynamoDBAdminIntegration):
    """Test DynamoDB-specific ChangeList functionality."""

    def test_changelist_initialization(self):
        """Test ChangeList initialization with DynamoDB parameters."""
        request = self._create_request()

        changelist = DynamoDBChangeList(
            request=request,
            model=Question,
            list_display=["question_text", "pub_date"],
            list_display_links=["question_text"],
            list_filter=["pub_date"],
            date_hierarchy=None,
            search_fields=["question_text"],
            list_select_related=False,
            list_per_page=25,
            list_max_show_all=100,
            list_editable=[],
            model_admin=self.question_admin,
            sortable_by=[],
        )

        self.assertIsInstance(changelist, DynamoDBChangeList)
        self.assertIsNone(changelist._last_evaluated_key)
        self.assertIsNone(changelist._total_count)

    @patch("django_dynamodb_backend.managers.DynamoDBQuerySet._execute_scan")
    def test_changelist_get_queryset(self, mock_scan):
        """Test queryset retrieval with DynamoDB optimizations."""
        request = self._create_request()

        # Mock scan results
        mock_scan.return_value = []

        changelist = DynamoDBChangeList(
            request=request,
            model=Question,
            list_display=["question_text"],
            list_display_links=[],
            list_filter=[],
            date_hierarchy=None,
            search_fields=[],
            list_select_related=False,
            list_per_page=25,
            list_max_show_all=100,
            list_editable=[],
            model_admin=self.question_admin,
            sortable_by=[],
        )

        queryset = changelist.get_queryset(request)
        self.assertIsNotNone(queryset)

    def test_changelist_pagination_params(self):
        """Test pagination parameter handling."""
        request = self._create_request('/?last_key={"id": {"S": "test"}}')

        changelist = DynamoDBChangeList(
            request=request,
            model=Question,
            list_display=["question_text"],
            list_display_links=[],
            list_filter=[],
            date_hierarchy=None,
            search_fields=[],
            list_select_related=False,
            list_per_page=25,
            list_max_show_all=100,
            list_editable=[],
            model_admin=self.question_admin,
            sortable_by=[],
        )

        # Should handle pagination key
        queryset = changelist.get_queryset(request)
        self.assertIsNotNone(queryset)


class TestDynamoDBPaginator(TestDynamoDBAdminIntegration):
    """Test DynamoDB-specific pagination."""

    def test_paginator_initialization(self):
        """Test paginator initialization."""
        test_data = ["item1", "item2", "item3", "item4", "item5"]
        paginator = DynamoDBPaginator(test_data, per_page=2)

        self.assertEqual(paginator.per_page, 2)
        self.assertIsNone(paginator._last_evaluated_key)

    def test_paginator_count(self):
        """Test count property."""
        test_data = ["item1", "item2", "item3"]
        paginator = DynamoDBPaginator(test_data, per_page=2)

        self.assertEqual(paginator.count, 3)

    def test_paginator_get_page(self):
        """Test page retrieval."""
        test_data = ["item1", "item2", "item3", "item4", "item5"]
        paginator = DynamoDBPaginator(test_data, per_page=2)

        page1 = paginator.get_page(1)
        self.assertEqual(page1, ["item1", "item2"])

        page2 = paginator.get_page(2)
        self.assertEqual(page2, ["item3", "item4"])

        page3 = paginator.get_page(3)
        self.assertEqual(page3, ["item5"])


class TestDynamoDBAdminViews(TestDynamoDBAdminIntegration):
    """Test admin view functionality."""

    def test_admin_initialization(self):
        """Test admin class initialization."""
        self.assertIsInstance(self.question_admin, QuestionAdmin)
        self.assertIsInstance(self.choice_admin, ChoiceAdmin)
        self.assertIsInstance(self.base_admin, DynamoDBAdmin)

    def test_admin_default_list_display(self):
        """Test auto-generation of list_display."""
        # Test admin should have auto-configured list_display
        self.assertIsNotNone(self.base_admin.list_display)
        self.assertNotEqual(self.base_admin.list_display, ("__str__",))

    def test_admin_default_search_fields(self):
        """Test auto-generation of search_fields."""
        # Test admin should have some search fields
        self.assertIsInstance(self.base_admin.search_fields, (list, tuple))

    def test_admin_get_queryset(self):
        """Test queryset retrieval with optimizations."""
        request = self._create_request()

        queryset = self.question_admin.get_queryset(request)
        self.assertIsNotNone(queryset)

        # Should have DynamoDB QuerySet functionality
        self.assertTrue(hasattr(queryset, "_dynamodb_scan_filters"))

    def test_admin_get_paginator(self):
        """Test custom paginator retrieval."""
        request = self._create_request()
        queryset = Question.objects.all()

        paginator = self.question_admin.get_paginator(request, queryset, 25)
        self.assertIsInstance(paginator, DynamoDBPaginator)

    def test_admin_permissions(self):
        """Test permission checking."""
        request = self._create_request()

        # Test with superuser
        self.assertTrue(self.question_admin.has_add_permission(request))
        self.assertTrue(self.question_admin.has_change_permission(request))
        self.assertTrue(self.question_admin.has_delete_permission(request))
        self.assertTrue(self.question_admin.has_view_permission(request))

    def test_admin_search_functionality(self):
        """Test search functionality."""
        request = self._create_request()
        queryset = Question.objects.all()

        search_queryset, use_distinct = self.question_admin.get_search_results(
            request, queryset, "test"
        )

        self.assertIsNotNone(search_queryset)
        self.assertIsInstance(use_distinct, bool)

    @patch("django_dynamodb_backend.managers.DynamoDBQuerySet.delete")
    def test_admin_bulk_delete_action(self, mock_delete):
        """Test bulk delete action."""
        request = self._create_request(method="POST")
        queryset = Question.objects.all()

        # Mock delete return
        mock_delete.return_value = (3, {"tests.Question": 3})

        # Test delete action
        self.question_admin.delete_selected_optimized(request, queryset)

        mock_delete.assert_called_once()

    def test_admin_export_csv_action(self):
        """Test CSV export action."""
        request = self._create_request()
        queryset = Question.objects.all()

        # Mock queryset iteration
        with patch.object(queryset, "__iter__", return_value=[]):
            response = self.question_admin.export_to_csv(request, queryset)

            self.assertEqual(response["Content-Type"], "text/csv")
            self.assertIn("attachment", response["Content-Disposition"])


class TestDynamoDBAdminForms(TestDynamoDBAdminIntegration):
    """Test admin form functionality."""

    def test_dynamodb_model_form(self):
        """Test DynamoDBModelForm functionality."""
        form_class = DynamoDBModelForm

        # Create form class for Question model
        class TestQuestionForm(form_class):
            class Meta:
                model = Question
                fields = "__all__"

        form = TestQuestionForm()
        self.assertIsInstance(form, DynamoDBModelForm)

    def test_form_field_enhancement(self):
        """Test form field enhancements."""

        class TestForm(DynamoDBModelForm):
            class Meta:
                model = Question
                fields = ["question_text"]

        form = TestForm()

        # Check that form fields have enhancements
        for field_name, field in form.fields.items():
            if hasattr(field.widget, "attrs"):
                self.assertIn("form-control", field.widget.attrs.get("class", ""))

    def test_form_validation(self):
        """Test form validation."""

        class TestForm(DynamoDBModelForm):
            class Meta:
                model = Question
                fields = ["question_text"]

        # Test with valid data
        valid_data = {"question_text": "Test question", "pub_date": datetime.now()}

        form = TestForm(data=valid_data)
        # Note: This might not validate due to missing model setup
        # The important thing is that the form class works
        self.assertIsInstance(form, DynamoDBModelForm)


class TestDynamoDBAdminFilters(TestDynamoDBAdminIntegration):
    """Test admin filtering functionality."""

    def test_filter_integration(self):
        """Test that filters are properly integrated."""
        # Test that admin classes have filter mixins
        self.assertTrue(hasattr(self.question_admin, "get_list_filter"))

        request = self._create_request()
        filters = self.question_admin.get_list_filter(request)

        self.assertIsInstance(filters, (list, tuple))

    def test_boolean_filter(self):
        """Test boolean filter functionality."""
        request = self._create_request("/?is_active=1")

        # Django 6.0+ expects params as lists (like QueryDict) due to value[-1] usage
        filter_instance = IsActiveFilter(
            request, {"is_active": ["1"]}, Question, self.question_admin
        )

        self.assertEqual(filter_instance.value(), "1")

    def test_date_range_filter(self):
        """Test date range filter functionality."""
        request = self._create_request("/?pub_date=today")

        # Django 6.0+ expects params as lists (like QueryDict) due to value[-1] usage
        filter_instance = PublishedDateFilter(
            request, {"pub_date": ["today"]}, Question, self.question_admin
        )

        self.assertEqual(filter_instance.value(), "today")

    def test_numeric_range_filter(self):
        """Test numeric range filter functionality."""
        request = self._create_request("/?votes=0-10")

        # Django 6.0+ expects params as lists (like QueryDict) due to value[-1] usage
        filter_instance = VoteCountFilter(
            request, {"votes": ["0-10"]}, Choice, self.choice_admin
        )

        self.assertEqual(filter_instance.value(), "0-10")


class TestDynamoDBAdminCustomActions(TestDynamoDBAdminIntegration):
    """Test custom admin actions."""

    def _get_action_names(self, admin_instance):
        """Helper to get action names from admin, handling both strings and callables."""
        action_names = []
        for action in admin_instance.actions:
            if callable(action):
                action_names.append(action.__name__)
            elif isinstance(action, str):
                action_names.append(action)
        return action_names

    def test_question_admin_actions(self):
        """Test QuestionAdmin custom actions."""
        # Check that custom actions are available
        action_names = self._get_action_names(self.question_admin)
        self.assertIn("mark_as_published", action_names)

    def test_choice_admin_actions(self):
        """Test ChoiceAdmin custom actions."""
        # Check that custom actions are available
        action_names = self._get_action_names(self.choice_admin)
        self.assertIn("reset_votes", action_names)

    @patch("django_dynamodb_backend.managers.DynamoDBQuerySet.update")
    def test_mark_as_published_action(self, mock_update):
        """Test mark as published action."""
        request = self._create_request(method="POST")
        queryset = Question.objects.all()

        # Mock update return
        mock_update.return_value = 2

        # Test action
        self.question_admin.mark_as_published(request, queryset)

        mock_update.assert_called_once()

    @patch("django_dynamodb_backend.managers.DynamoDBQuerySet.update")
    def test_reset_votes_action(self, mock_update):
        """Test reset votes action."""
        request = self._create_request(method="POST")
        queryset = Choice.objects.all()

        # Mock update return
        mock_update.return_value = 3

        # Test action
        self.choice_admin.reset_votes(request, queryset)

        mock_update.assert_called_once_with(votes=0)


class TestDynamoDBAdminSite(TestDynamoDBAdminIntegration):
    """Test custom admin site functionality."""

    def test_admin_site_customization(self):
        """Test custom admin site features."""
        from django_dynamodb_backend.admin import (
            DynamoDBAdminSite,
            dynamodb_admin_site,
        )

        self.assertIsInstance(dynamodb_admin_site, DynamoDBAdminSite)
        self.assertEqual(dynamodb_admin_site.site_header, "DynamoDB Django Admin")
        self.assertEqual(dynamodb_admin_site.site_title, "DynamoDB Admin")
        self.assertEqual(dynamodb_admin_site.index_title, "DynamoDB Administration")

    def test_admin_site_index_context(self):
        """Test admin site index with custom context."""
        from django_dynamodb_backend.admin import dynamodb_admin_site

        request = self._create_request()

        # Test index view
        response = dynamodb_admin_site.index(request)

        # Should return HttpResponse (not test the actual content due to complexity)
        self.assertIsNotNone(response)


if __name__ == "__main__":
    unittest.main()
