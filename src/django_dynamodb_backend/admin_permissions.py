"""
DynamoDB-aware admin permissions and security utilities.
"""

import logging

from django.contrib import messages
from django.contrib.admin.utils import quote
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)

User = get_user_model()


class DynamoDBPermissionMixin:
    """Mixin providing DynamoDB-aware permission checking."""

    def _check_dynamodb_permissions(self, request, obj=None, action="view"):
        """Check DynamoDB-specific permissions."""
        # Add custom permission logic here
        # For example, check if user has access to specific DynamoDB tables

        # Basic permission check
        if not request.user.is_authenticated:
            raise PermissionDenied("Authentication required")

        # Check if user is staff
        if not request.user.is_staff:
            raise PermissionDenied("Staff access required")

        # Log permission check
        logger.info(
            f"Permission check: {request.user.username} - {action} on {self.model._meta.label}"
        )

        return True

    def has_add_permission(self, request):
        """Check add permission with DynamoDB considerations."""
        try:
            self._check_dynamodb_permissions(request, action="add")
            return super().has_add_permission(request)
        except PermissionDenied as e:
            logger.warning(f"Add permission denied: {e}")
            return False

    def has_change_permission(self, request, obj=None):
        """Check change permission with DynamoDB considerations."""
        try:
            self._check_dynamodb_permissions(request, obj, action="change")
            return super().has_change_permission(request, obj)
        except PermissionDenied as e:
            logger.warning(f"Change permission denied: {e}")
            return False

    def has_delete_permission(self, request, obj=None):
        """Check delete permission with DynamoDB considerations."""
        try:
            self._check_dynamodb_permissions(request, obj, action="delete")
            return super().has_delete_permission(request, obj)
        except PermissionDenied as e:
            logger.warning(f"Delete permission denied: {e}")
            return False

    def has_view_permission(self, request, obj=None):
        """Check view permission with DynamoDB considerations."""
        try:
            self._check_dynamodb_permissions(request, obj, action="view")
            return super().has_view_permission(request, obj)
        except PermissionDenied as e:
            logger.warning(f"View permission denied: {e}")
            return False


class DynamoDBSecurityMixin:
    """Mixin providing security enhancements for DynamoDB admin."""

    def get_object(self, request, object_id, from_field=None):
        """Securely get object with additional validation."""
        try:
            # Get the object using parent method
            obj = super().get_object(request, object_id, from_field)

            if obj is None:
                raise Http404(_("Object not found"))

            # Add additional security checks
            self._validate_object_access(request, obj)

            return obj

        except Exception as e:
            logger.error(f"Error getting object {object_id}: {e}")
            raise Http404(_("Object not found or access denied"))

    def _validate_object_access(self, request, obj):
        """Validate that user has access to this specific object."""
        # Add custom object-level security checks here
        # For example, check if object belongs to user's organization

        # Basic validation
        if not obj:
            raise PermissionDenied("Object not found")

        # Log access
        logger.info(f"Object access: {request.user.username} accessing {obj}")

        return True

    def get_queryset(self, request):
        """Get queryset with user-specific filtering."""
        queryset = super().get_queryset(request)

        # Add user-specific filtering here
        # For example, filter objects based on user permissions

        # For superusers, return all objects
        if request.user.is_superuser:
            return queryset

        # For regular staff, add filtering logic
        # This is where you'd add your business logic
        # Example: return queryset.filter(created_by=request.user)

        return queryset

    def save_model(self, request, obj, form, change):
        """Save model with security enhancements."""
        try:
            # Add created_by or updated_by if fields exist
            if hasattr(obj, "created_by") and not change:
                obj.created_by = request.user

            if hasattr(obj, "updated_by"):
                obj.updated_by = request.user

            # Log the save operation
            action = "updated" if change else "created"
            logger.info(f"Object {action}: {request.user.username} {action} {obj}")

            super().save_model(request, obj, form, change)

        except Exception as e:
            logger.error(f"Error saving object: {e}")
            raise

    def delete_model(self, request, obj):
        """Delete model with security logging."""
        try:
            logger.info(f"Object deleted: {request.user.username} deleted {obj}")
            super().delete_model(request, obj)
        except Exception as e:
            logger.error(f"Error deleting object: {e}")
            raise


class DynamoDBAdminAuditMixin:
    """Mixin providing audit trail functionality."""

    def _log_admin_action(self, request, obj, action, extra_data=None):
        """Log admin actions for audit purposes."""
        try:
            audit_data = {
                "user": request.user.username,
                "user_id": request.user.id,
                "action": action,
                "model": f"{obj._meta.app_label}.{obj._meta.model_name}",
                "object_id": str(obj.pk) if obj.pk else None,
                "object_repr": str(obj),
                "timestamp": timezone.now().isoformat(),
                "ip_address": self._get_client_ip(request),
                "user_agent": request.META.get("HTTP_USER_AGENT", ""),
            }

            if extra_data:
                audit_data.update(extra_data)

            # Log to standard logger
            logger.info(f"Admin audit: {audit_data}")

            # You could also save to a database table here
            # self._save_audit_record(audit_data)

        except Exception as e:
            logger.error(f"Error logging admin action: {e}")

    def _get_client_ip(self, request):
        """Get client IP address from request."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0]
        else:
            ip = request.META.get("REMOTE_ADDR")
        return ip

    def save_model(self, request, obj, form, change):
        """Save model with audit logging."""
        action = "change" if change else "add"

        # Get changed fields for audit
        changed_fields = []
        if change and hasattr(form, "changed_data"):
            changed_fields = form.changed_data

        super().save_model(request, obj, form, change)

        # Log the action
        extra_data = {
            "changed_fields": changed_fields,
            "form_data": (
                {k: str(v) for k, v in form.cleaned_data.items()}
                if hasattr(form, "cleaned_data")
                else {}
            ),
        }

        self._log_admin_action(request, obj, action, extra_data)

    def delete_model(self, request, obj):
        """Delete model with audit logging."""
        # Log before deletion (while we still have the object)
        self._log_admin_action(request, obj, "delete")

        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        """Delete queryset with audit logging."""
        # Log each object being deleted
        for obj in queryset:
            self._log_admin_action(request, obj, "delete", {"bulk_delete": True})

        super().delete_queryset(request, queryset)


class DynamoDBRateLimitMixin:
    """Mixin providing rate limiting for DynamoDB operations."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._request_counts = {}

    def _check_rate_limit(self, request, action="view"):
        """Check if user is within rate limits."""
        from datetime import timedelta

        from django.utils import timezone

        user_key = f"{request.user.id}_{action}"
        now = timezone.now()

        # Clean old entries
        cutoff_time = now - timedelta(minutes=1)
        self._request_counts = {
            k: v
            for k, v in self._request_counts.items()
            if v["timestamp"] > cutoff_time
        }

        # Check current count
        if user_key in self._request_counts:
            count = self._request_counts[user_key]["count"]
            # Allow 60 requests per minute for regular operations
            limit = 60 if action in ["view", "list"] else 10

            if count >= limit:
                logger.warning(
                    f"Rate limit exceeded: {request.user.username} - {action}"
                )
                messages.warning(request, _("Rate limit exceeded. Please slow down."))
                return False

            self._request_counts[user_key]["count"] += 1
        else:
            self._request_counts[user_key] = {"count": 1, "timestamp": now}

        return True

    def changelist_view(self, request, extra_context=None):
        """Rate-limited changelist view."""
        if not self._check_rate_limit(request, "list"):
            return HttpResponseRedirect(request.path)

        return super().changelist_view(request, extra_context)

    def add_view(self, request, form_url="", extra_context=None):
        """Rate-limited add view."""
        if not self._check_rate_limit(request, "add"):
            return HttpResponseRedirect(request.path)

        return super().add_view(request, form_url, extra_context)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        """Rate-limited change view."""
        if not self._check_rate_limit(request, "change"):
            return HttpResponseRedirect(request.path)

        return super().change_view(request, object_id, form_url, extra_context)


# Combined security admin class
class SecureDynamoDBAdmin:
    """Admin class combining all security mixins."""

    pass


# Apply mixins in the correct order
SecureDynamoDBAdmin = type(
    "SecureDynamoDBAdmin",
    (
        DynamoDBPermissionMixin,
        DynamoDBSecurityMixin,
        DynamoDBAdminAuditMixin,
        DynamoDBRateLimitMixin,
    ),
    {},
)
