"""
Payment API endpoints.
"""

from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any, List
import uuid
import time
import logging

from app.services.google_drive_service import google_drive_service

router = APIRouter(prefix="/api/payment", tags=["Payments"])

class PaymentIntentRequest(BaseModel):
    amount: int
    currency: str = "usd"
    metadata: Optional[Dict[str, Any]] = None
    description: str = "Translation Service Payment"
    receipt_email: EmailStr

class PaymentSuccessRequest(BaseModel):
    customer_email: EmailStr
    file_ids: List[str]
    payment_intent_id: str

class PaymentFailureRequest(BaseModel):
    customer_email: EmailStr
    file_ids: List[str]
    payment_intent_id: str

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
    logging.info(f"Payment intent requested: ${request.amount/100:.2f} for {request.receipt_email}")
    
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
    
    logging.info(f"Payment intent created: {payment_intent_id}")
    
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
    logging.info(f"Payment verification requested for: {payment_intent_id}")
    
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
    
    logging.info(f"Payment verification result - Status: {payment_status}, Verified: {verified}")
    
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

@router.post("/success")
async def handle_payment_success(request: PaymentSuccessRequest):
    """
    Handle successful payment - move files from Temp to Inbox folder.
    
    This endpoint is called when payment is confirmed to move files
    from the temporary storage to the customer's inbox.
    """
    logging.info(f"PAYMENT CONFIRMED - Processing success for {request.customer_email}: {len(request.file_ids)} files")
    logging.info(f"Moving files from TEMP to INBOX folder for customer: {request.customer_email}")
    
    try:
        # Move files from Temp to Inbox
        result = await google_drive_service.move_files_to_inbox_on_payment_success(
            customer_email=request.customer_email,
            file_ids=request.file_ids
        )
        
        logging.info(f"✅ PAYMENT SUCCESS: Files moved to Inbox: {result['moved_successfully']}/{result['total_files']}")
        logging.info(f"Customer {request.customer_email} can now access files in Inbox folder")
        
        return JSONResponse(
            content={
                "success": True,
                "message": f"Payment confirmed. {result['moved_successfully']} files moved to Inbox.",
                "data": {
                    "customer_email": request.customer_email,
                    "payment_intent_id": request.payment_intent_id,
                    "total_files": result['total_files'],
                    "moved_successfully": result['moved_successfully'],
                    "failed_moves": result['failed_moves'],
                    "inbox_folder_id": result['inbox_folder_id'],
                    "moved_files": result['moved_files']
                },
                "error": None
            }
        )
        
    except Exception as e:
        logging.error(f"❌ PAYMENT SUCCESS FAILED: Error moving files to Inbox: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to move files to Inbox: {str(e)}"
        )

@router.post("/failure")
async def handle_payment_failure(request: PaymentFailureRequest):
    """
    Handle failed payment - delete files from Temp folder.
    
    This endpoint is called when payment fails to clean up
    temporary files that were uploaded.
    """
    logging.warning(f"❌ PAYMENT FAILED - Processing failure for {request.customer_email}: {len(request.file_ids)} files to delete")
    
    try:
        # Delete files from Temp folder
        result = await google_drive_service.delete_files_on_payment_failure(
            customer_email=request.customer_email,
            file_ids=request.file_ids
        )
        
        logging.info(f"Payment failure cleanup: {result['deleted_successfully']}/{result['total_files']} files deleted from Temp")
        
        return JSONResponse(
            content={
                "success": True,
                "message": f"Payment failed. {result['deleted_successfully']} files deleted from Temp folder.",
                "data": {
                    "customer_email": request.customer_email,
                    "payment_intent_id": request.payment_intent_id,
                    "total_files": result['total_files'],
                    "deleted_successfully": result['deleted_successfully'],
                    "failed_deletions": result['failed_deletions'],
                    "deleted_files": result['deleted_files']
                },
                "error": None
            }
        )
        
    except Exception as e:
        logging.error(f"Payment failure cleanup error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete files: {str(e)}"
        )