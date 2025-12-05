"""
Pydantic models for subscription management.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Literal
from datetime import datetime
from decimal import Decimal
from bson import ObjectId


class UsagePeriod(BaseModel):
    """Usage period tracking within a subscription."""
    period_start: datetime
    period_end: datetime
    units_allocated: int = Field(ge=0)
    units_used: int = Field(default=0, ge=0)
    units_remaining: int = Field(ge=0)
    promotional_units: int = Field(default=0, ge=0)
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    period_number: Optional[int] = Field(None, ge=1, le=12, description="Period number within the year (1-12)")

    # New fields requested by user
    start_period: Optional[datetime] = None  # Alternative naming for period_start
    end_period: Optional[datetime] = None    # Alternative naming for period_end
    units_per_subscription: Optional[int] = Field(None, ge=0)  # Alternative naming for units_allocated
    used_units: Optional[int] = Field(None, ge=0)  # Alternative naming for units_used

    @field_validator('units_remaining')
    @classmethod
    def validate_units_remaining(cls, v, info):
        """Ensure units_remaining = units_allocated - units_used"""
        if info.data.get('units_allocated') is not None and info.data.get('units_used') is not None:
            expected = info.data['units_allocated'] - info.data['units_used']
            if v != expected:
                return expected
        return v

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class SubscriptionCreate(BaseModel):
    """Model for creating a new subscription."""
    company_name: str  # Company name (String, not ObjectId)
    subscription_unit: Literal["page", "word", "character"]
    units_per_subscription: int = Field(gt=0)
    price_per_unit: Decimal = Field(gt=0)
    promotional_units: int = Field(default=0, ge=0)
    discount: Decimal = Field(default=Decimal("1.0"), ge=0, le=1)
    subscription_price: Decimal = Field(gt=0)
    start_date: datetime
    end_date: Optional[datetime] = None
    status: Literal["active", "inactive", "expired"] = "active"
    billing_frequency: Literal["monthly", "quarterly", "yearly"] = Field(default="monthly", description="Billing frequency")
    payment_terms_days: int = Field(default=30, ge=1, le=90, description="Payment terms in days (Net 30, Net 60, etc.)")

    @field_validator('end_date')
    @classmethod
    def validate_end_date(cls, v, info):
        """Ensure end_date is after start_date"""
        if v and info.data.get('start_date'):
            if v <= info.data['start_date']:
                raise ValueError('end_date must be after start_date')
        return v


class SubscriptionUpdate(BaseModel):
    """Model for updating an existing subscription."""
    subscription_unit: Optional[Literal["page", "word", "character"]] = None
    units_per_subscription: Optional[int] = Field(None, gt=0)
    price_per_unit: Optional[Decimal] = Field(None, gt=0)
    promotional_units: Optional[int] = Field(None, ge=0)
    discount: Optional[Decimal] = Field(None, ge=0, le=1)
    subscription_price: Optional[Decimal] = Field(None, gt=0)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    status: Optional[Literal["active", "inactive", "expired"]] = None
    billing_frequency: Optional[Literal["monthly", "quarterly", "yearly"]] = None
    payment_terms_days: Optional[int] = Field(None, ge=1, le=90)


class UsagePeriodCreate(BaseModel):
    """Model for creating a new usage period."""
    period_start: datetime
    period_end: datetime
    units_allocated: int = Field(gt=0)

    @field_validator('period_end')
    @classmethod
    def validate_period_end(cls, v, info):
        """Ensure period_end is after period_start"""
        if v and info.data.get('period_start'):
            if v <= info.data['period_start']:
                raise ValueError('period_end must be after period_start')
        return v


class UsageUpdate(BaseModel):
    """Model for updating usage in a period."""
    units_to_add: int = Field(gt=0)
    use_promotional_units: bool = False
    translation_mode: str = Field(default="default", description="Translation mode: default, formats, human, handwriting, or mixed")


class SubscriptionResponse(BaseModel):
    """Response model for subscription data."""
    id: str
    company_name: str
    subscription_unit: str
    units_per_subscription: int
    price_per_unit: float
    promotional_units: int
    discount: float
    subscription_price: float
    start_date: datetime
    end_date: Optional[datetime]
    status: str
    usage_periods: List[UsagePeriod]
    created_at: datetime
    updated_at: datetime

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            ObjectId: lambda v: str(v)
        }


class SubscriptionSummary(BaseModel):
    """Summary of subscription usage."""
    subscription_id: str
    company_name: str
    subscription_unit: str
    total_units_allocated: int
    total_units_used: int
    total_units_remaining: int
    promotional_units_available: int
    promotional_units_used: int
    current_period: Optional[UsagePeriod]
    status: str
    expires_at: Optional[datetime]

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
