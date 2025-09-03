"""
Payment API endpoints.
"""

from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any
import uuid
import time

router = APIRouter(prefix="/api/payment", tags=["Payments"])

class PaymentIntentRequest(BaseModel):
    amount: int
    currency: str = "usd"
    metadata: Optional[Dict[str, Any]] = None
    description: str = "Translation Service Payment"
    receipt_email: EmailStr

@router.post("/create-intent")
async def create_payment_intent(
    request: PaymentIntentRequest,
    x_csrf_token: Optional[str] = Header(None),
    idempotency_key: Optional[str] = Header(None)
):
    """
    Create payment intent for Stripe integration - STUB IMPLEMENTATION.
    Validates amount, currency and creates payment intent.
    """
    print(f"Hello World - Payment intent endpoint called for ${request.amount/100:.2f}")
    print(f"Hello World - Email: {request.receipt_email}")
    
    # Validate amount (50 cents to $10,000)
    if request.amount < 50:
        raise HTTPException(
            status_code=400,
            detail="Amount must be at least 50 cents ($0.50)"
        )
    
    if request.amount > 1000000:  # $10,000 in cents
        raise HTTPException(
            status_code=400,
            detail="Amount cannot exceed $10,000"
        )
    
    # Validate currency
    valid_currencies = ['usd', 'eur', 'gbp', 'cad', 'aud']
    if request.currency.lower() not in valid_currencies:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid currency: {request.currency}. Supported: {', '.join(valid_currencies)}"
        )
    
    # Generate payment intent ID and client secret
    payment_intent_id = f"pi_{uuid.uuid4().hex[:16]}"
    client_secret = f"{payment_intent_id}_secret_{uuid.uuid4().hex[:16]}"
    
    print(f"Hello World - Created payment intent: {payment_intent_id}")
    
    # Stub: In real implementation, this would call Stripe API
    return JSONResponse(
        content={
            "success": True,
            "data": {
                "clientSecret": client_secret,
                "paymentIntentId": payment_intent_id
            },
            "error": None
        }
    )

@router.get("/{payment_intent_id}/verify")
async def verify_payment(payment_intent_id: str):
    """
    Verify payment completion - STUB IMPLEMENTATION.
    Checks payment status and returns verification result.
    """
    print(f"Hello World - Payment verification endpoint called for: {payment_intent_id}")
    
    # Validate payment intent ID format
    if not payment_intent_id.startswith('pi_'):
        raise HTTPException(
            status_code=400,
            detail="Invalid payment intent ID format"
        )
    
    # Stub: In real implementation, this would check Stripe API
    # For demo purposes, we'll simulate different payment states based on the ID
    if 'fail' in payment_intent_id.lower():
        payment_status = "failed"
        verified = False
    elif 'cancel' in payment_intent_id.lower():
        payment_status = "canceled"
        verified = False
    else:
        payment_status = "succeeded"
        verified = True
    
    # Generate stub amount (in real implementation, this would come from Stripe)
    stub_amount = 1000  # $10.00
    
    print(f"Hello World - Payment status: {payment_status}, Verified: {verified}")
    
    return JSONResponse(
        content={
            "success": True,
            "data": {
                "verified": verified,
                "status": payment_status,
                "amount": stub_amount
            },
            "error": None
        }
    )