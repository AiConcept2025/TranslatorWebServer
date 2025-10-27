"""
Pydantic models for user transaction API responses.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class UserTransactionListItem(BaseModel):
    """Individual user transaction record in the response."""

    id: str = Field(
        alias="_id",
        description="MongoDB ObjectId (24-character hex string)",
        examples=["68fac0c78d81a68274ac140b"]
    )
    user_name: str = Field(
        ...,
        description="Full name of the user",
        examples=["John Doe"]
    )
    user_email: str = Field(
        ...,
        description="User's email address",
        examples=["john.doe@example.com"]
    )
    document_url: str = Field(
        ...,
        description="URL to the translated document",
        examples=["https://drive.google.com/file/d/1ABC_sample_document/view"]
    )
    number_of_units: int = Field(
        ...,
        description="Number of units translated",
        examples=[10]
    )
    unit_type: str = Field(
        ...,
        description="Type of unit (e.g., page, word, character)",
        examples=["page", "word", "character"]
    )
    cost_per_unit: float = Field(
        ...,
        description="Cost per unit in dollars",
        examples=[0.15]
    )
    source_language: str = Field(
        ...,
        description="Source language code (ISO 639-1)",
        examples=["en", "es", "fr"]
    )
    target_language: str = Field(
        ...,
        description="Target language code (ISO 639-1)",
        examples=["es", "en", "de"]
    )
    square_transaction_id: str = Field(
        ...,
        description="Square payment transaction identifier",
        examples=["SQR-1EC28E70F10B4D9E"]
    )
    date: str = Field(
        ...,
        description="Transaction date (ISO 8601 format)",
        examples=["2025-10-23T23:56:55.438Z"]
    )
    status: str = Field(
        ...,
        description="Transaction status (completed, pending, failed)",
        examples=["completed", "pending", "failed"]
    )
    total_cost: float = Field(
        ...,
        description="Total transaction cost in dollars",
        examples=[1.5]
    )
    created_at: str = Field(
        ...,
        description="Record creation timestamp (ISO 8601 format)",
        examples=["2025-10-23T23:56:55.438Z"]
    )
    updated_at: str = Field(
        ...,
        description="Last update timestamp (ISO 8601 format)",
        examples=["2025-10-23T23:56:55.438Z"]
    )

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "_id": "68fac0c78d81a68274ac140b",
                "user_name": "John Doe",
                "user_email": "john.doe@example.com",
                "document_url": "https://drive.google.com/file/d/1ABC_sample_document/view",
                "number_of_units": 10,
                "unit_type": "page",
                "cost_per_unit": 0.15,
                "source_language": "en",
                "target_language": "es",
                "square_transaction_id": "SQR-1EC28E70F10B4D9E",
                "date": "2025-10-23T23:56:55.438Z",
                "status": "completed",
                "total_cost": 1.5,
                "created_at": "2025-10-23T23:56:55.438Z",
                "updated_at": "2025-10-23T23:56:55.438Z"
            }
        }


class UserTransactionListFilters(BaseModel):
    """Applied filter values."""

    user_email: str = Field(
        ...,
        description="User email used for filtering",
        examples=["john.doe@example.com"]
    )
    status: Optional[str] = Field(
        None,
        description="Status filter applied (if any)",
        examples=["completed", "pending", "failed", None]
    )


class UserTransactionListData(BaseModel):
    """Data payload containing user transactions list and metadata."""

    transactions: List[UserTransactionListItem] = Field(
        ...,
        description="Array of user transaction records"
    )
    count: int = Field(
        ...,
        description="Number of transactions in this response",
        examples=[3]
    )
    limit: int = Field(
        ...,
        description="Maximum number of results per page",
        examples=[50]
    )
    skip: int = Field(
        ...,
        description="Number of results skipped (pagination offset)",
        examples=[0]
    )
    filters: UserTransactionListFilters = Field(
        ...,
        description="Applied filter parameters"
    )


class UserTransactionListResponse(BaseModel):
    """Root response wrapper for user transactions list endpoint."""

    success: bool = Field(
        True,
        description="Indicates whether the request was successful"
    )
    data: UserTransactionListData = Field(
        ...,
        description="Response data payload"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "data": {
                    "transactions": [
                        {
                            "_id": "68fac0c78d81a68274ac140b",
                            "user_name": "John Doe",
                            "user_email": "john.doe@example.com",
                            "document_url": "https://drive.google.com/file/d/1ABC_sample_document/view",
                            "number_of_units": 10,
                            "unit_type": "page",
                            "cost_per_unit": 0.15,
                            "source_language": "en",
                            "target_language": "es",
                            "square_transaction_id": "SQR-1EC28E70F10B4D9E",
                            "date": "2025-10-23T23:56:55.438Z",
                            "status": "completed",
                            "total_cost": 1.5,
                            "created_at": "2025-10-23T23:56:55.438Z",
                            "updated_at": "2025-10-23T23:56:55.438Z"
                        }
                    ],
                    "count": 1,
                    "limit": 50,
                    "skip": 0,
                    "filters": {
                        "user_email": "john.doe@example.com",
                        "status": None
                    }
                }
            }
        }
