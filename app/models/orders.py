"""
Orders models for corporate order management and history.

These models support the corporate orders dashboard with filtering,
search, and period-based organization.
"""

from datetime import datetime
from typing import List, Optional, Literal
from pydantic import BaseModel, Field


# ============================================================================
# Query Parameters Models
# ============================================================================

class OrdersQueryParams(BaseModel):
    """Query parameters for filtering orders."""
    date_period: Literal["current", "previous", "last-3-months", "last-6-months", "all"] = Field(
        default="current",
        description="Time period filter for orders"
    )
    language: str = Field(
        default="any",
        description="Language pair filter (e.g., 'en-zh') or 'any' for all languages"
    )
    status: Literal["delivered", "processing", "pending", "failed", "cancelled", "any"] = Field(
        default="any",
        description="Order status filter"
    )
    search: str = Field(
        default="",
        description="Search term for order number, user name, or filenames"
    )

    model_config = {
        'json_schema_extra': {
            'example': {
                'date_period': 'current',
                'language': 'en-zh',
                'status': 'delivered',
                'search': 'contract'
            }
        }
    }


# ============================================================================
# Order Item Model
# ============================================================================

class OrderItem(BaseModel):
    """Individual order item in the orders list."""
    id: str = Field(..., description="MongoDB ObjectId of the transaction")
    order_number: str = Field(..., description="Order number with # prefix (e.g., #A10293)")
    user: str = Field(..., description="User email address")
    date: str = Field(..., description="Order date in YYYY-MM-DD format")
    language_pair: str = Field(..., description="Language pair in format 'EN → ZH'")
    original_file: str = Field(..., description="Original filename")
    translated_file: str = Field(..., description="Translated filename")
    translated_file_name: str = Field(default="", description="Alternative translated filename field")
    pages: int = Field(..., ge=0, description="Number of pages/units")
    status: str = Field(..., description="Order status: delivered | processing | pending | failed | cancelled")

    model_config = {
        'json_schema_extra': {
            'example': {
                'id': '68fe1edeac2359ccbc6b05b2',
                'order_number': '#A10293',
                'user': 'user@company.com',
                'date': '2025-10-28',
                'language_pair': 'EN → ZH',
                'original_file': 'contract_v3.pdf',
                'translated_file': 'contract_v3_zh.pdf',
                'translated_file_name': '',
                'pages': 12,
                'status': 'delivered'
            }
        }
    }


# ============================================================================
# Period Model
# ============================================================================

class OrderPeriod(BaseModel):
    """Period grouping for orders (monthly grouping)."""
    id: str = Field(..., description="Period identifier (e.g., 'period-1')")
    date_range: str = Field(..., description="Human-readable date range (e.g., 'Oct 1-31, 2025')")
    period_label: str = Field(..., description="Period label (e.g., 'Current Period', 'Previous Period')")
    is_current: bool = Field(..., description="Whether this is the current period")
    orders_count: int = Field(..., ge=0, description="Number of orders in this period")
    pages_count: int = Field(..., ge=0, description="Total pages/units in this period")
    orders: List[OrderItem] = Field(..., description="List of orders in this period")

    model_config = {
        'json_schema_extra': {
            'example': {
                'id': 'period-1',
                'date_range': 'Oct 1-31, 2025',
                'period_label': 'Current Period',
                'is_current': True,
                'orders_count': 128,
                'pages_count': 1947,
                'orders': [
                    {
                        'id': '68fe1edeac2359ccbc6b05b2',
                        'order_number': '#A10293',
                        'user': 'user@company.com',
                        'date': '2025-10-28',
                        'language_pair': 'EN → ZH',
                        'original_file': 'contract_v3.pdf',
                        'translated_file': 'contract_v3_zh.pdf',
                        'translated_file_name': '',
                        'pages': 12,
                        'status': 'delivered'
                    }
                ]
            }
        }
    }


# ============================================================================
# Response Models
# ============================================================================

class OrdersData(BaseModel):
    """Orders data payload."""
    periods: List[OrderPeriod] = Field(..., description="List of order periods")
    totalOrders: int = Field(..., ge=0, description="Total number of orders across all periods")
    totalPages: int = Field(..., ge=0, description="Total number of pages/units across all periods")

    model_config = {
        'json_schema_extra': {
            'example': {
                'periods': [
                    {
                        'id': 'period-1',
                        'date_range': 'Oct 1-31, 2025',
                        'period_label': 'Current Period',
                        'is_current': True,
                        'orders_count': 128,
                        'pages_count': 1947,
                        'orders': []
                    }
                ],
                'totalOrders': 128,
                'totalPages': 1947
            }
        }
    }


class OrdersResponse(BaseModel):
    """Standardized response for orders endpoint."""
    success: bool = Field(True, description="Indicates if the request was successful")
    data: OrdersData = Field(..., description="Orders data with periods and statistics")

    model_config = {
        'json_schema_extra': {
            'example': {
                'success': True,
                'data': {
                    'periods': [
                        {
                            'id': 'period-1',
                            'date_range': 'Oct 1-31, 2025',
                            'period_label': 'Current Period',
                            'is_current': True,
                            'orders_count': 128,
                            'pages_count': 1947,
                            'orders': [
                                {
                                    'id': '68fe1edeac2359ccbc6b05b2',
                                    'order_number': '#A10293',
                                    'user': 'user@company.com',
                                    'date': '2025-10-28',
                                    'language_pair': 'EN → ZH',
                                    'original_file': 'contract_v3.pdf',
                                    'translated_file': 'contract_v3_zh.pdf',
                                    'translated_file_name': '',
                                    'pages': 12,
                                    'status': 'delivered'
                                }
                            ]
                        }
                    ],
                    'totalOrders': 128,
                    'totalPages': 1947
                }
            }
        }
    }
