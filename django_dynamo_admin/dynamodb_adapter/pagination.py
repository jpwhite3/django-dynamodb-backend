"""
Advanced pagination system for DynamoDB Django Admin.

This module provides bidirectional pagination, page jumping, and other advanced
pagination features optimized for DynamoDB's key-based pagination.
"""

import base64
import json
import logging
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlencode

from django.core.cache import cache
from django.core.paginator import EmptyPage, Page, PageNotAnInteger, Paginator
from django.http import QueryDict
from django.utils.functional import cached_property

logger = logging.getLogger(__name__)


@dataclass
class PaginationToken:
    """Represents pagination state for DynamoDB."""

    last_evaluated_key: Optional[Dict[str, Any]] = None
    page_number: int = 1
    direction: str = "forward"  # 'forward' or 'backward'
    per_page: int = 25
    sort_key: Optional[str] = None
    filters_hash: Optional[str] = None

    def to_string(self) -> str:
        """Convert token to base64 string for URL transmission."""
        data = asdict(self)
        json_str = json.dumps(data, default=str)
        return base64.b64encode(json_str.encode()).decode()

    @classmethod
    def from_string(cls, token_str: str) -> "PaginationToken":
        """Create token from base64 string."""
        try:
            json_str = base64.b64decode(token_str.encode()).decode()
            data = json.loads(json_str)
            return cls(**data)
        except Exception as e:
            logger.error(f"Error parsing pagination token: {e}")
            return cls()


@dataclass
class PaginationState:
    """Stores complete pagination state for a session."""

    pages: Dict[int, PaginationToken]  # page_number -> token
    total_pages_estimate: int
    has_previous: bool
    has_next: bool
    current_page: int
    per_page: int

    def get_cache_key(self, table_name: str, user_id: int, filters_hash: str) -> str:
        """Generate cache key for this pagination state."""
        return f"dynamodb_pagination:{table_name}:{user_id}:{filters_hash}"


class DynamoDBPage(Page):
    """Enhanced page class for DynamoDB with bidirectional navigation."""

    def __init__(self, object_list, number, paginator, token: PaginationToken = None):
        super().__init__(object_list, number, paginator)
        self.token = token or PaginationToken(page_number=number)
        self._next_token = None
        self._previous_token = None

    def has_next(self):
        """Check if there's a next page."""
        return self.token.last_evaluated_key is not None

    def has_previous(self):
        """Check if there's a previous page."""
        return self.number > 1

    def next_page_number(self):
        """Get next page number."""
        if self.has_next():
            return self.number + 1
        raise EmptyPage("No next page")

    def previous_page_number(self):
        """Get previous page number."""
        if self.has_previous():
            return self.number - 1
        raise EmptyPage("No previous page")

    def get_next_token(self) -> Optional[str]:
        """Get token for next page."""
        if self.has_next():
            next_token = PaginationToken(
                last_evaluated_key=self.token.last_evaluated_key,
                page_number=self.next_page_number(),
                direction="forward",
                per_page=self.token.per_page,
                sort_key=self.token.sort_key,
                filters_hash=self.token.filters_hash,
            )
            return next_token.to_string()
        return None

    def get_previous_token(self) -> Optional[str]:
        """Get token for previous page."""
        if self.has_previous():
            # For previous page, we need to use the cached token from pagination state
            return self.paginator.get_previous_page_token(self.number)
        return None

    def get_elided_page_range(self, on_each_side=2, on_ends=1):
        """Get elided page range optimized for DynamoDB pagination."""
        # Since DynamoDB doesn't have total count, we estimate based on current position
        estimated_total = min(
            self.paginator.get_estimated_total_pages(), self.number + 10
        )

        if estimated_total <= 10:
            # Show all pages if we have few pages
            return range(1, estimated_total + 1)

        # Create elided range
        page_range = []

        # Add first pages
        for i in range(1, min(on_ends + 1, estimated_total + 1)):
            page_range.append(i)

        # Add ellipsis if needed
        if self.number > on_ends + on_each_side + 1:
            page_range.append("…")

        # Add pages around current page
        start = max(self.number - on_each_side, on_ends + 1)
        end = min(self.number + on_each_side + 1, estimated_total - on_ends + 1)

        for i in range(start, end):
            if i not in page_range:
                page_range.append(i)

        # Add ellipsis if needed
        if self.number < estimated_total - on_ends - on_each_side:
            if estimated_total - on_ends not in page_range:
                page_range.append("…")

        # Add last pages
        for i in range(max(estimated_total - on_ends + 1, 1), estimated_total + 1):
            if i not in page_range:
                page_range.append(i)

        return sorted(
            [x for x in page_range if isinstance(x, int)]
            + [x for x in page_range if not isinstance(x, int)]
        )


class DynamoDBAdvancedPaginator(Paginator):
    """
    Advanced paginator for DynamoDB with bidirectional navigation,
    token-based pagination, and smart page estimation.
    """

    def __init__(
        self,
        object_list,
        per_page,
        orphans=0,
        allow_empty_first_page=True,
        user_id=None,
    ):
        super().__init__(object_list, per_page, orphans, allow_empty_first_page)
        self.user_id = user_id
        self._pagination_state = None
        self._estimated_total_pages = None

        # Generate filters hash for caching
        self.filters_hash = self._generate_filters_hash()

        # Cache key for pagination state
        if hasattr(object_list, "model"):
            table_name = object_list.model._meta.db_table
            self.cache_key = (
                f"dynamodb_pagination:{table_name}:{user_id}:{self.filters_hash}"
            )
        else:
            self.cache_key = (
                f"dynamodb_pagination:unknown:{user_id}:{self.filters_hash}"
            )

    def _generate_filters_hash(self) -> str:
        """Generate hash of current filters for pagination caching."""
        import hashlib

        filter_data = ""
        if hasattr(self.object_list, "_dynamodb_scan_filters"):
            filter_data = str(self.object_list._dynamodb_scan_filters)
        if hasattr(self.object_list, "_order_by_fields"):
            filter_data += str(self.object_list._order_by_fields)

        return hashlib.md5(filter_data.encode()).hexdigest()

    def get_pagination_state(self) -> PaginationState:
        """Get or create pagination state."""
        if self._pagination_state is None:
            cached_state = cache.get(self.cache_key)
            if cached_state:
                self._pagination_state = cached_state
            else:
                self._pagination_state = PaginationState(
                    pages={},
                    total_pages_estimate=1,
                    has_previous=False,
                    has_next=True,
                    current_page=1,
                    per_page=self.per_page,
                )
        return self._pagination_state

    def save_pagination_state(self):
        """Save pagination state to cache."""
        if self._pagination_state:
            cache.set(self.cache_key, self._pagination_state, 3600)  # Cache for 1 hour

    def get_page(self, number, token_str: str = None):
        """Get a page with enhanced token-based navigation."""
        try:
            number = int(number)
        except (ValueError, TypeError):
            raise PageNotAnInteger("Page number must be an integer")

        if number < 1:
            raise EmptyPage("Page number must be 1 or greater")

        # Parse token if provided
        token = None
        if token_str:
            token = PaginationToken.from_string(token_str)

        # Get pagination state
        pagination_state = self.get_pagination_state()

        # Check if we have this page cached
        if number in pagination_state.pages and not token:
            token = pagination_state.pages[number]

        if not token:
            token = PaginationToken(
                page_number=number,
                per_page=self.per_page,
                filters_hash=self.filters_hash,
            )

        # Execute query with pagination
        try:
            page_data = self._get_page_data(token)

            # Create page object
            page = DynamoDBPage(page_data["items"], number, self, token)

            # Update token with last evaluated key
            if page_data.get("last_evaluated_key"):
                token.last_evaluated_key = page_data["last_evaluated_key"]
            else:
                token.last_evaluated_key = None

            # Update pagination state
            pagination_state.pages[number] = token
            pagination_state.current_page = number
            pagination_state.has_next = page.has_next()
            pagination_state.has_previous = page.has_previous()

            # Update estimated total pages
            if page.has_next():
                pagination_state.total_pages_estimate = max(
                    pagination_state.total_pages_estimate, number + 1
                )

            # Save state
            self.save_pagination_state()

            return page

        except Exception as e:
            logger.error(f"Error getting page {number}: {e}")
            raise EmptyPage(f"Error retrieving page {number}")

    def _get_page_data(self, token: PaginationToken) -> Dict[str, Any]:
        """Get page data from DynamoDB using the token."""
        # Clone the queryset
        queryset = self.object_list._clone()

        # Apply pagination parameters
        if token.last_evaluated_key and token.direction == "forward":
            # Set the exclusive start key for forward pagination
            if hasattr(queryset, "set_exclusive_start_key"):
                queryset = queryset.set_exclusive_start_key(token.last_evaluated_key)

        # Apply limit
        queryset = queryset[: token.per_page]

        # Execute query and get items
        items = list(queryset)

        # Get last evaluated key if available
        last_evaluated_key = None
        if hasattr(queryset, "get_last_evaluated_key"):
            last_evaluated_key = queryset.get_last_evaluated_key()
        elif len(items) == token.per_page:
            # If we got a full page, assume there are more items
            # Generate a simple continuation key from the last item
            if items:
                last_item = items[-1]
                last_evaluated_key = self._generate_continuation_key(last_item)

        return {
            "items": items,
            "last_evaluated_key": last_evaluated_key,
            "count": len(items),
        }

    def _generate_continuation_key(self, last_item) -> Dict[str, Any]:
        """Generate a continuation key from the last item."""
        # This is a simplified implementation
        # In production, you'd use the actual DynamoDB key structure
        key = {}

        # Get primary key field
        pk_field = last_item._meta.pk
        if pk_field:
            key[pk_field.name] = getattr(last_item, pk_field.name)

        return key

    def get_estimated_total_pages(self) -> int:
        """Get estimated total number of pages."""
        pagination_state = self.get_pagination_state()
        return pagination_state.total_pages_estimate

    def get_previous_page_token(self, current_page: int) -> Optional[str]:
        """Get token for the previous page."""
        if current_page <= 1:
            return None

        pagination_state = self.get_pagination_state()

        # Get token for previous page
        previous_page = current_page - 1
        if previous_page in pagination_state.pages:
            token = pagination_state.pages[previous_page]
            return token.to_string()

        # Generate token for previous page (simplified)
        token = PaginationToken(
            page_number=previous_page,
            direction="backward",
            per_page=self.per_page,
            filters_hash=self.filters_hash,
        )
        return token.to_string()

    def get_page_range_with_tokens(
        self, current_page: int, on_each_side: int = 2
    ) -> List[Dict[str, Any]]:
        """Get page range with navigation tokens."""
        pagination_state = self.get_pagination_state()
        estimated_total = self.get_estimated_total_pages()

        page_range = []

        # Calculate visible range
        start_page = max(1, current_page - on_each_side)
        end_page = min(estimated_total, current_page + on_each_side)

        # Add ellipsis and adjust range if needed
        if start_page > 1:
            page_range.append(
                {"number": 1, "token": self._get_page_token(1), "is_current": False}
            )
            if start_page > 2:
                page_range.append({"number": "...", "token": None, "is_current": False})

        # Add visible pages
        for page_num in range(start_page, end_page + 1):
            page_range.append(
                {
                    "number": page_num,
                    "token": self._get_page_token(page_num),
                    "is_current": page_num == current_page,
                }
            )

        # Add ending ellipsis and last page if needed
        if end_page < estimated_total:
            if end_page < estimated_total - 1:
                page_range.append({"number": "...", "token": None, "is_current": False})
            page_range.append(
                {
                    "number": estimated_total,
                    "token": self._get_page_token(estimated_total),
                    "is_current": False,
                }
            )

        return page_range

    def _get_page_token(self, page_number: int) -> Optional[str]:
        """Get token for a specific page number."""
        pagination_state = self.get_pagination_state()

        if page_number in pagination_state.pages:
            return pagination_state.pages[page_number].to_string()

        # Generate basic token
        token = PaginationToken(
            page_number=page_number,
            per_page=self.per_page,
            filters_hash=self.filters_hash,
        )
        return token.to_string()

    @property
    def count(self):
        """Return the total number of objects, or an estimated count for DynamoDB QuerySets."""
        if isinstance(self.object_list, (list, tuple)):
            return len(self.object_list)
        
        # For DynamoDB QuerySets, return an estimate
        pagination_state = self.get_pagination_state()
        return pagination_state.total_pages_estimate * self.per_page

    @property
    def num_pages(self):
        """Return estimated number of pages."""
        return self.get_estimated_total_pages()


class DynamoDBPaginationMixin:
    """Mixin to add advanced DynamoDB pagination to Django Admin."""

    def get_paginator(
        self, request, queryset, per_page, orphans=0, allow_empty_first_page=True
    ):
        """Get advanced DynamoDB paginator."""
        user_id = request.user.id if request.user.is_authenticated else 0
        return DynamoDBAdvancedPaginator(
            queryset,
            per_page,
            orphans=orphans,
            allow_empty_first_page=allow_empty_first_page,
            user_id=user_id,
        )

    def changelist_view(self, request, extra_context=None):
        """Enhanced changelist view with advanced pagination."""
        extra_context = extra_context or {}

        # Get pagination token from request
        token_str = request.GET.get("pt")  # pt = pagination token

        # Add pagination enhancements to context
        extra_context.update(
            {
                "pagination_token": token_str,
                "advanced_pagination": True,
                "show_jump_to_page": True,
            }
        )

        return super().changelist_view(request, extra_context)


# Utility functions for template usage
def build_pagination_url(
    base_url: str, page_number: int, token: str = None, **params
) -> str:
    """Build pagination URL with token support."""
    query_params = dict(params)
    query_params["p"] = page_number

    if token:
        query_params["pt"] = token

    query_string = urlencode(query_params)
    return f"{base_url}?{query_string}"


def get_pagination_context(page: DynamoDBPage, request) -> Dict[str, Any]:
    """Get pagination context for templates."""
    base_url = request.path
    query_params = request.GET.copy()

    # Remove pagination parameters
    for key in ["p", "pt"]:
        query_params.pop(key, None)

    context = {
        "page_obj": page,
        "is_paginated": page.paginator.num_pages > 1,
        "page_range": page.get_elided_page_range(),
        "base_url": base_url,
        "query_params": query_params,
    }

    # Add navigation URLs
    if page.has_previous():
        context["previous_url"] = build_pagination_url(
            base_url,
            page.previous_page_number(),
            page.get_previous_token(),
            **query_params,
        )

    if page.has_next():
        context["next_url"] = build_pagination_url(
            base_url, page.next_page_number(), page.get_next_token(), **query_params
        )

    return context
