"""
Advanced Django Admin Actions optimized for DynamoDB.

This module provides enhanced admin actions with confirmation pages, progress tracking,
and DynamoDB-specific batch optimizations.
"""

import csv
import json
import logging
from datetime import datetime
from decimal import Decimal

from django.contrib import messages
from django.contrib.admin import helpers
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext

logger = logging.getLogger(__name__)


class DynamoDBActionMixin:
    """Mixin providing DynamoDB-optimized admin actions."""

    def get_actions(self, request):
        """Get available actions with DynamoDB optimizations."""
        actions = super().get_actions(request)

        # Add DynamoDB-specific actions
        actions.update(
            {
                "bulk_update_with_confirmation": (
                    self.bulk_update_with_confirmation,
                    "bulk_update_with_confirmation",
                    _("Bulk update selected items (with confirmation)"),
                ),
                "export_to_json": (
                    self.export_to_json,
                    "export_to_json",
                    _("Export selected items to JSON"),
                ),
                "clone_selected": (
                    self.clone_selected,
                    "clone_selected",
                    _("Clone selected items"),
                ),
                "bulk_delete_optimized": (
                    self.bulk_delete_optimized,
                    "bulk_delete_optimized",
                    _("Delete selected items (DynamoDB optimized)"),
                ),
                "check_item_sizes": (
                    self.check_item_sizes,
                    "check_item_sizes",
                    _("Check item sizes for DynamoDB limits"),
                ),
                "backup_to_s3": (
                    self.backup_to_s3,
                    "backup_to_s3",
                    _("Backup selected items to S3"),
                ),
            }
        )

        return actions

    def bulk_update_with_confirmation(self, request, queryset):
        """Bulk update with confirmation page and progress tracking."""
        opts = self.model._meta
        app_label = opts.app_label

        # Check permissions
        if not self.has_change_permission(request):
            raise PermissionDenied("You don't have permission to change these items")

        # Handle POST request (actual update)
        if request.POST.get("post") == "yes":
            return self._execute_bulk_update(request, queryset)

        # Show confirmation page
        context = {
            "title": _("Bulk Update Confirmation"),
            "queryset": queryset,
            "opts": opts,
            "app_label": app_label,
            "action_checkbox_name": helpers.ACTION_CHECKBOX_NAME,
            "selected_items": request.POST.getlist(helpers.ACTION_CHECKBOX_NAME),
            "update_fields": self._get_bulk_update_fields(),
            "estimated_capacity_units": self._estimate_capacity_consumption(
                queryset, "update"
            ),
            "estimated_cost": self._estimate_operation_cost(queryset, "update"),
        }

        return TemplateResponse(
            request, "admin/dynamodb_bulk_update_confirmation.html", context
        )

    def _execute_bulk_update(self, request, queryset):
        """Execute the bulk update operation."""
        update_fields = {}

        # Extract update fields from POST data
        for field_name in self._get_bulk_update_fields():
            value = request.POST.get(f"update_{field_name}")
            if value:
                update_fields[field_name] = self._convert_field_value(field_name, value)

        if not update_fields:
            messages.warning(request, "No fields specified for update")
            return HttpResponseRedirect(request.get_full_path())

        # Perform bulk update with DynamoDB optimization
        updated_count = 0
        errors = []

        # Process in batches for better performance
        batch_size = 25  # DynamoDB batch limit
        items = list(queryset)

        for i in range(0, len(items), batch_size):
            batch = items[i : i + batch_size]
            batch_updated, batch_errors = self._update_batch(batch, update_fields)
            updated_count += batch_updated
            errors.extend(batch_errors)

        # Report results
        if updated_count:
            message = ngettext(
                "Successfully updated %(count)d item.",
                "Successfully updated %(count)d items.",
                updated_count,
            ) % {"count": updated_count}
            messages.success(request, message)

        if errors:
            error_message = f"Encountered {len(errors)} errors during update"
            messages.error(request, error_message)
            logger.error(f"Bulk update errors: {errors}")

        return HttpResponseRedirect(request.get_full_path())

    def _update_batch(self, batch, update_fields):
        """Update a batch of items."""
        updated_count = 0
        errors = []

        for item in batch:
            try:
                for field_name, value in update_fields.items():
                    setattr(item, field_name, value)
                item.save()
                updated_count += 1
            except Exception as e:
                errors.append(f"Failed to update {item}: {e}")
                logger.error(f"Error updating item {item}: {e}")

        return updated_count, errors

    def export_to_json(self, request, queryset):
        """Export selected items to JSON format."""
        if not self.has_view_permission(request):
            raise PermissionDenied("You don't have permission to view these items")

        response = HttpResponse(content_type="application/json")
        response["Content-Disposition"] = (
            f'attachment; filename="{self.model.__name__}_export.json"'
        )

        # Convert queryset to JSON-serializable data
        data = []
        for obj in queryset:
            item_data = {}
            for field in obj._meta.fields:
                value = getattr(obj, field.name)
                if isinstance(value, (datetime, Decimal)):
                    value = str(value)
                elif hasattr(value, "isoformat"):
                    value = value.isoformat()
                item_data[field.name] = value
            data.append(item_data)

        json.dump(data, response, indent=2, default=str)

        messages.success(request, f"Exported {len(data)} items to JSON")
        return response

    def clone_selected(self, request, queryset):
        """Clone selected items with confirmation."""
        opts = self.model._meta

        if not self.has_add_permission(request):
            raise PermissionDenied("You don't have permission to add items")

        # Handle POST request (actual cloning)
        if request.POST.get("post") == "yes":
            return self._execute_clone(request, queryset)

        # Show confirmation page
        context = {
            "title": _("Clone Confirmation"),
            "queryset": queryset,
            "opts": opts,
            "app_label": opts.app_label,
            "action_checkbox_name": helpers.ACTION_CHECKBOX_NAME,
            "selected_items": request.POST.getlist(helpers.ACTION_CHECKBOX_NAME),
            "estimated_capacity_units": self._estimate_capacity_consumption(
                queryset, "create"
            ),
            "estimated_cost": self._estimate_operation_cost(queryset, "create"),
        }

        return TemplateResponse(
            request, "admin/dynamodb_clone_confirmation.html", context
        )

    def _execute_clone(self, request, queryset):
        """Execute the clone operation."""
        cloned_count = 0
        errors = []

        for obj in queryset:
            try:
                # Create a copy of the object
                new_obj = obj.__class__()

                # Copy all field values except primary key
                for field in obj._meta.fields:
                    if not field.primary_key:
                        value = getattr(obj, field.name)
                        setattr(new_obj, field.name, value)

                # Generate new primary key if needed
                if hasattr(new_obj, "generate_new_id"):
                    new_obj.generate_new_id()

                new_obj.save()
                cloned_count += 1

            except Exception as e:
                errors.append(f"Failed to clone {obj}: {e}")
                logger.error(f"Error cloning item {obj}: {e}")

        # Report results
        if cloned_count:
            message = ngettext(
                "Successfully cloned %(count)d item.",
                "Successfully cloned %(count)d items.",
                cloned_count,
            ) % {"count": cloned_count}
            messages.success(request, message)

        if errors:
            error_message = f"Encountered {len(errors)} errors during cloning"
            messages.error(request, error_message)

        return HttpResponseRedirect(request.get_full_path())

    def bulk_delete_optimized(self, request, queryset):
        """Optimized bulk delete for DynamoDB."""
        if not self.has_delete_permission(request):
            raise PermissionDenied("You don't have permission to delete these items")

        # Handle POST request (actual deletion)
        if request.POST.get("post") == "yes":
            return self._execute_bulk_delete(request, queryset)

        # Show confirmation page
        context = {
            "title": _("Delete Confirmation"),
            "queryset": queryset,
            "opts": self.model._meta,
            "app_label": self.model._meta.app_label,
            "action_checkbox_name": helpers.ACTION_CHECKBOX_NAME,
            "selected_items": request.POST.getlist(helpers.ACTION_CHECKBOX_NAME),
            "estimated_capacity_units": self._estimate_capacity_consumption(
                queryset, "delete"
            ),
            "estimated_cost": self._estimate_operation_cost(queryset, "delete"),
        }

        return TemplateResponse(
            request, "admin/dynamodb_delete_confirmation.html", context
        )

    def _execute_bulk_delete(self, request, queryset):
        """Execute optimized bulk delete."""
        deleted_count = 0
        errors = []

        # Use batch delete for efficiency
        batch_size = 25  # DynamoDB batch limit
        items = list(queryset)

        for i in range(0, len(items), batch_size):
            batch = items[i : i + batch_size]
            batch_deleted, batch_errors = self._delete_batch(batch)
            deleted_count += batch_deleted
            errors.extend(batch_errors)

        # Report results
        if deleted_count:
            message = ngettext(
                "Successfully deleted %(count)d item.",
                "Successfully deleted %(count)d items.",
                deleted_count,
            ) % {"count": deleted_count}
            messages.success(request, message)

        if errors:
            error_message = f"Encountered {len(errors)} errors during deletion"
            messages.error(request, error_message)

        return HttpResponseRedirect(request.get_full_path())

    def _delete_batch(self, batch):
        """Delete a batch of items."""
        deleted_count = 0
        errors = []

        for item in batch:
            try:
                item.delete()
                deleted_count += 1
            except Exception as e:
                errors.append(f"Failed to delete {item}: {e}")
                logger.error(f"Error deleting item {item}: {e}")

        return deleted_count, errors

    def check_item_sizes(self, request, queryset):
        """Check item sizes against DynamoDB limits."""
        results = []
        total_size = 0
        large_items = []

        for obj in queryset:
            item_size = self._calculate_item_size(obj)
            total_size += item_size

            status = "OK"
            if item_size > 400 * 1024:  # 400KB DynamoDB limit
                status = "ERROR"
                large_items.append((obj, item_size))
            elif item_size > 350 * 1024:  # 350KB warning threshold
                status = "WARNING"
                large_items.append((obj, item_size))

            results.append(
                {
                    "object": obj,
                    "size_bytes": item_size,
                    "size_kb": round(item_size / 1024, 2),
                    "status": status,
                }
            )

        # Create response
        context = {
            "title": _("Item Size Check Results"),
            "results": results,
            "total_size_kb": round(total_size / 1024, 2),
            "large_items_count": len(large_items),
            "opts": self.model._meta,
        }

        return TemplateResponse(request, "admin/dynamodb_size_check.html", context)

    def backup_to_s3(self, request, queryset):
        """Backup selected items to S3 (requires AWS configuration)."""
        if not self.has_view_permission(request):
            raise PermissionDenied("You don't have permission to backup these items")

        try:
            import boto3
            from django.conf import settings

            # Create S3 client
            s3_client = boto3.client("s3")
            bucket_name = getattr(settings, "DYNAMODB_BACKUP_BUCKET", None)

            if not bucket_name:
                messages.error(request, "S3 backup bucket not configured")
                return HttpResponseRedirect(request.get_full_path())

            # Generate backup filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.model.__name__}_backup_{timestamp}.json"

            # Prepare data
            backup_data = {
                "model": self.model.__name__,
                "timestamp": timestamp,
                "items": [],
            }

            for obj in queryset:
                item_data = {}
                for field in obj._meta.fields:
                    value = getattr(obj, field.name)
                    if isinstance(value, (datetime, Decimal)):
                        value = str(value)
                    item_data[field.name] = value
                backup_data["items"].append(item_data)

            # Upload to S3
            s3_client.put_object(
                Bucket=bucket_name,
                Key=filename,
                Body=json.dumps(backup_data, indent=2, default=str),
                ContentType="application/json",
            )

            messages.success(
                request,
                f"Successfully backed up {len(backup_data['items'])} items "
                f"to s3://{bucket_name}/{filename}",
            )

        except ImportError:
            messages.error(request, "boto3 is required for S3 backup functionality")
        except Exception as e:
            logger.error(f"S3 backup error: {e}")
            messages.error(request, f"Backup failed: {e}")

        return HttpResponseRedirect(request.get_full_path())

    # Helper methods
    def _get_bulk_update_fields(self):
        """Get fields available for bulk update."""
        # Return fields that are safe for bulk update
        safe_fields = []
        for field in self.model._meta.fields:
            if (
                not field.primary_key
                and not field.auto_created
                and field.editable
                and not field.name.endswith("_at")
            ):  # Exclude timestamp fields
                safe_fields.append(field.name)
        return safe_fields

    def _convert_field_value(self, field_name, value):
        """Convert string value to appropriate field type."""
        field = self.model._meta.get_field(field_name)

        if hasattr(field, "to_python"):
            return field.to_python(value)
        return value

    def _estimate_capacity_consumption(self, queryset, operation):
        """Estimate DynamoDB capacity units for operation."""
        # Simplified estimation - in production, this could be more sophisticated
        item_count = len(list(queryset))

        if operation == "read":
            return item_count * 1  # 1 RCU per item
        elif operation in ["create", "update", "delete"]:
            return item_count * 1  # 1 WCU per item

        return item_count

    def _estimate_operation_cost(self, queryset, operation):
        """Estimate operation cost in USD."""
        capacity_units = self._estimate_capacity_consumption(queryset, operation)

        # Rough AWS pricing estimates (as of 2024)
        if operation == "read":
            cost_per_million = 0.25  # $0.25 per million RCU
        else:
            cost_per_million = 1.25  # $1.25 per million WCU

        estimated_cost = (capacity_units / 1_000_000) * cost_per_million
        return max(0.01, estimated_cost)  # Minimum $0.01

    def _calculate_item_size(self, obj):
        """Calculate approximate size of DynamoDB item."""
        size = 0

        for field in obj._meta.fields:
            value = getattr(obj, field.name)
            if value is not None:
                if isinstance(value, str):
                    size += len(value.encode("utf-8"))
                elif isinstance(value, (int, float, Decimal)):
                    size += 8  # Approximate size for numbers
                elif isinstance(value, bool):
                    size += 1
                else:
                    size += len(str(value).encode("utf-8"))

        return size


# Action functions that can be used independently
def export_selected_to_csv(modeladmin, request, queryset):
    """Export selected items to CSV."""
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = (
        f'attachment; filename="{modeladmin.model.__name__}_export.csv"'
    )

    writer = csv.writer(response)

    # Write header
    field_names = [field.name for field in modeladmin.model._meta.fields]
    writer.writerow(field_names)

    # Write data
    for obj in queryset:
        row = []
        for field_name in field_names:
            value = getattr(obj, field_name)
            if isinstance(value, (datetime, Decimal)):
                value = str(value)
            row.append(value)
        writer.writerow(row)

    messages.success(request, f"Exported {len(list(queryset))} items to CSV")
    return response


export_selected_to_csv.short_description = "Export selected items to CSV"
