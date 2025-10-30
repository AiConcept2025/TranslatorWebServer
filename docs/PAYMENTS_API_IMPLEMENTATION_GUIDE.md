# Implementation Guide: GET /api/v1/payments Endpoint

**Developer Guide for Implementing the New Admin Payments Endpoint**

---

## Quick Start

This guide provides step-by-step instructions for implementing the new `GET /api/v1/payments` endpoint for admin dashboard viewing of all subscription payments.

---

## 1. Endpoint Specification

### Route Definition

```python
@router.get(
    "/",  # Maps to /api/v1/payments
    response_model=PaymentListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get all subscription payments (admin)",
    description="Retrieve all payment records with filtering and pagination. Admin access required."
)
```

### Function Signature

```python
async def get_all_payments(
    status_filter: Optional[str] = Query(
        None,
        description="Filter by payment status",
        alias="status",
        example="COMPLETED"
    ),
    company_name_filter: Optional[str] = Query(
        None,
        description="Filter by company name",
        alias="company_name",
        example="Acme Health LLC"
    ),
    limit: int = Query(
        50,
        ge=1,
        le=100,
        description="Maximum results to return"
    ),
    skip: int = Query(
        0,
        ge=0,
        description="Results to skip for pagination"
    ),
    start_date: Optional[datetime] = Query(
        None,
        description="Filter from date (ISO 8601)"
    ),
    end_date: Optional[datetime] = Query(
        None,
        description="Filter to date (ISO 8601)"
    ),
    current_user: dict = Depends(get_current_admin_user)  # Admin auth required
):
    """Implementation here"""
```

---

## 2. Database Query Implementation

### Build Query Filter

```python
# Start with empty filter
query_filter = {}

# Add status filter
if status_filter:
    valid_statuses = ["COMPLETED", "PENDING", "FAILED", "REFUNDED"]
    if status_filter not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid payment status. Must be one of: {', '.join(valid_statuses)}"
        )
    query_filter["payment_status"] = status_filter

# Add company filter
if company_name_filter:
    query_filter["company_name"] = company_name_filter

# Add date range filter
if start_date or end_date:
    date_filter = {}
    if start_date:
        date_filter["$gte"] = start_date
    if end_date:
        date_filter["$lte"] = end_date
    query_filter["payment_date"] = date_filter
```

### Execute Query with Pagination

```python
from app.services.payment_repository import payment_repository

# Get total count (for pagination metadata)
total_count = await payment_repository.count_payments(query_filter)

# Get paginated results
payments = await payment_repository.get_all_payments(
    filter_dict=query_filter,
    limit=limit,
    skip=skip,
    sort_by="payment_date",
    sort_order=-1  # Newest first
)

# Convert ObjectIds and datetimes
for payment in payments:
    payment["_id"] = str(payment["_id"])
    # Handle nested ObjectIds in refunds if needed
```

### Calculate Pagination Metadata

```python
import math

current_page = (skip // limit) + 1
total_pages = math.ceil(total_count / limit) if total_count > 0 else 0
has_next = skip + limit < total_count
has_previous = skip > 0

page_info = {
    "current_page": current_page,
    "total_pages": total_pages,
    "has_next": has_next,
    "has_previous": has_previous
}
```

---

## 3. Repository Method

### Add to payment_repository.py

```python
class PaymentRepository:
    # ... existing methods ...

    async def count_payments(self, filter_dict: dict) -> int:
        """
        Count total payments matching filter.

        Args:
            filter_dict: MongoDB filter dictionary

        Returns:
            Total count of matching payments
        """
        try:
            count = await self.collection.count_documents(filter_dict)
            return count
        except Exception as e:
            logger.error(f"Failed to count payments: {e}")
            raise

    async def get_all_payments(
        self,
        filter_dict: dict,
        limit: int = 50,
        skip: int = 0,
        sort_by: str = "payment_date",
        sort_order: int = -1
    ) -> List[dict]:
        """
        Get all payments with filtering, sorting, and pagination.

        Args:
            filter_dict: MongoDB filter dictionary
            limit: Maximum results to return
            skip: Number of results to skip
            sort_by: Field to sort by
            sort_order: 1 for ascending, -1 for descending

        Returns:
            List of payment documents
        """
        try:
            cursor = self.collection.find(filter_dict)
            cursor = cursor.sort(sort_by, sort_order)
            cursor = cursor.skip(skip).limit(limit)

            payments = await cursor.to_list(length=limit)
            return payments

        except Exception as e:
            logger.error(f"Failed to get all payments: {e}")
            raise
```

---

## 4. Response Construction

```python
from fastapi.responses import JSONResponse

response_data = {
    "success": True,
    "data": {
        "payments": payments,
        "count": len(payments),
        "total": total_count,
        "limit": limit,
        "skip": skip,
        "filters": {
            "status": status_filter,
            "company_name": company_name_filter,
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None
        },
        "page_info": page_info
    }
}

return JSONResponse(content=response_data)
```

---

## 5. Authentication & Authorization

### Option 1: Create Admin Dependency

```python
# In app/middleware/auth_middleware.py

async def get_current_admin_user(
    current_user: dict = Depends(get_current_user)
) -> dict:
    """
    Verify that the current user has admin privileges.

    Raises:
        HTTPException: If user is not admin
    """
    permission_level = current_user.get("permission_level", "user")

    if permission_level not in ["admin", "superadmin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    return current_user
```

### Option 2: Check Permissions in Endpoint

```python
async def get_all_payments(
    # ... parameters ...
    current_user: dict = Depends(get_current_user)
):
    # Check admin permission
    if current_user.get("permission_level") not in ["admin", "superadmin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    # Rest of implementation
```

---

## 6. Error Handling

```python
try:
    # Database operations
    total_count = await payment_repository.count_payments(query_filter)
    payments = await payment_repository.get_all_payments(...)

    # Response construction
    return JSONResponse(content=response_data)

except HTTPException:
    # Re-raise HTTP exceptions (validation errors, auth errors)
    raise

except Exception as e:
    logger.error(f"Failed to retrieve all payments: {e}", exc_info=True)
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Failed to retrieve payments: {str(e)}"
    )
```

---

## 7. OpenAPI Documentation

### Add Response Examples

```python
@router.get(
    "/",
    response_model=PaymentListResponse,
    responses={
        200: {
            "description": "Successfully retrieved payments",
            "content": {
                "application/json": {
                    "examples": {
                        "all_payments": {
                            "summary": "All payments",
                            "value": {
                                "success": True,
                                "data": {
                                    "payments": [...],
                                    "count": 50,
                                    "total": 125,
                                    "limit": 50,
                                    "skip": 0,
                                    "filters": {
                                        "status": None,
                                        "company_name": None,
                                        "start_date": None,
                                        "end_date": None
                                    },
                                    "page_info": {
                                        "current_page": 1,
                                        "total_pages": 3,
                                        "has_next": True,
                                        "has_previous": False
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        401: {"description": "Authentication required"},
        403: {"description": "Admin access required"},
        500: {"description": "Internal server error"}
    }
)
```

---

## 8. Testing

### Integration Test

```python
# tests/integration/test_payments_admin_integration.py

import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_get_all_payments_admin_success(admin_token):
    """Test successful retrieval of all payments by admin."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/payments",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "payments" in data["data"]
    assert "count" in data["data"]
    assert "total" in data["data"]
    assert "page_info" in data["data"]


@pytest.mark.asyncio
async def test_get_all_payments_filter_by_status(admin_token):
    """Test filtering by payment status."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/payments?status=COMPLETED",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

    assert response.status_code == 200
    data = response.json()

    # Verify all payments have COMPLETED status
    for payment in data["data"]["payments"]:
        assert payment["payment_status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_get_all_payments_pagination(admin_token):
    """Test pagination logic."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # First page
        response1 = await client.get(
            "/api/v1/payments?limit=10&skip=0",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        # Second page
        response2 = await client.get(
            "/api/v1/payments?limit=10&skip=10",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

    assert response1.status_code == 200
    assert response2.status_code == 200

    data1 = response1.json()["data"]
    data2 = response2.json()["data"]

    # Verify pagination metadata
    assert data1["page_info"]["current_page"] == 1
    assert data2["page_info"]["current_page"] == 2


@pytest.mark.asyncio
async def test_get_all_payments_unauthorized(user_token):
    """Test that non-admin users cannot access endpoint."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/payments",
            headers={"Authorization": f"Bearer {user_token}"}
        )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_all_payments_invalid_status(admin_token):
    """Test invalid status filter."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/payments?status=INVALID",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

    assert response.status_code == 400
```

---

## 9. Complete Implementation Example

### File: app/routers/payments.py

```python
@router.get(
    "/",
    response_model=PaymentListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get all subscription payments (admin)",
    description="Retrieve all payment records with filtering and pagination. Admin access required."
)
async def get_all_payments(
    status_filter: Optional[str] = Query(None, alias="status"),
    company_name_filter: Optional[str] = Query(None, alias="company_name"),
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """
    Get all payments with filtering and pagination (admin only).

    This endpoint provides comprehensive payment viewing for administrative dashboards.
    """
    try:
        # Check admin permission
        if current_user.get("permission_level") not in ["admin", "superadmin"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required"
            )

        logger.info(f"Admin {current_user.get('email')} fetching all payments")

        # Build query filter
        query_filter = {}

        if status_filter:
            valid_statuses = ["COMPLETED", "PENDING", "FAILED", "REFUNDED"]
            if status_filter not in valid_statuses:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid payment status. Must be one of: {', '.join(valid_statuses)}"
                )
            query_filter["payment_status"] = status_filter

        if company_name_filter:
            query_filter["company_name"] = company_name_filter

        if start_date or end_date:
            date_filter = {}
            if start_date:
                date_filter["$gte"] = start_date
            if end_date:
                date_filter["$lte"] = end_date
            query_filter["payment_date"] = date_filter

        # Get total count
        total_count = await payment_repository.count_payments(query_filter)

        # Get paginated results
        payments = await payment_repository.get_all_payments(
            filter_dict=query_filter,
            limit=limit,
            skip=skip,
            sort_by="payment_date",
            sort_order=-1
        )

        # Convert ObjectIds to strings
        def convert_doc(obj):
            if isinstance(obj, ObjectId):
                return str(obj)
            elif isinstance(obj, datetime):
                return obj.isoformat()
            elif isinstance(obj, dict):
                return {key: convert_doc(value) for key, value in obj.items()}
            elif isinstance(obj, list):
                return [convert_doc(item) for item in obj]
            return obj

        payments = [convert_doc(payment) for payment in payments]

        # Calculate pagination metadata
        import math
        current_page = (skip // limit) + 1
        total_pages = math.ceil(total_count / limit) if total_count > 0 else 0
        has_next = skip + limit < total_count
        has_previous = skip > 0

        response_data = {
            "success": True,
            "data": {
                "payments": payments,
                "count": len(payments),
                "total": total_count,
                "limit": limit,
                "skip": skip,
                "filters": {
                    "status": status_filter,
                    "company_name": company_name_filter,
                    "start_date": start_date.isoformat() if start_date else None,
                    "end_date": end_date.isoformat() if end_date else None
                },
                "page_info": {
                    "current_page": current_page,
                    "total_pages": total_pages,
                    "has_next": has_next,
                    "has_previous": has_previous
                }
            }
        }

        logger.info(f"Retrieved {len(payments)} payments (total: {total_count})")
        return JSONResponse(content=response_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve all payments: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve payments: {str(e)}"
        )
```

---

## 10. Checklist

### Implementation Steps

- [ ] Add repository methods (`count_payments`, `get_all_payments`)
- [ ] Create admin authentication dependency
- [ ] Implement endpoint function with all query parameters
- [ ] Add filter validation
- [ ] Implement pagination logic
- [ ] Add error handling
- [ ] Convert ObjectIds and datetimes
- [ ] Add OpenAPI documentation decorators
- [ ] Write integration tests
- [ ] Test with Swagger UI
- [ ] Test authentication/authorization
- [ ] Test all filter combinations
- [ ] Test pagination edge cases
- [ ] Add logging
- [ ] Update API documentation

### Testing Checklist

- [ ] Test successful retrieval (200)
- [ ] Test status filter
- [ ] Test company_name filter
- [ ] Test date range filter
- [ ] Test pagination (skip/limit)
- [ ] Test empty results
- [ ] Test unauthorized access (401)
- [ ] Test non-admin access (403)
- [ ] Test invalid status (400)
- [ ] Test invalid date format (400)
- [ ] Test edge cases (large skip, negative values)

---

## 11. Performance Considerations

### Database Indexes

Ensure indexes exist for:
```python
# In migration or startup
await db.payments.create_index([("payment_status", 1)])
await db.payments.create_index([("company_name", 1)])
await db.payments.create_index([("payment_date", -1)])
await db.payments.create_index([("user_email", 1)])
```

### Query Optimization

- Use projection to exclude unnecessary fields
- Consider using aggregation pipeline for complex filters
- Cache total count for frequent queries
- Use cursor pagination for very large datasets

---

## 12. Frontend Integration

### Example API Call (JavaScript)

```javascript
// Fetch all completed payments
const response = await fetch(
  'http://localhost:8000/api/v1/payments?status=COMPLETED&limit=50&skip=0',
  {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${adminToken}`,
      'Content-Type': 'application/json'
    }
  }
);

const data = await response.json();

if (data.success) {
  console.log('Payments:', data.data.payments);
  console.log('Total:', data.data.total);
  console.log('Page Info:', data.data.page_info);
}
```

---

**Ready to Implement!** Follow this guide step-by-step to create the new admin payments endpoint.
