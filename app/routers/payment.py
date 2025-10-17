"""
Payment API endpoints.
"""

from fastapi import APIRouter, HTTPException, Header, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any, List
import uuid
import time
import logging
import asyncio

from app.services.google_drive_service import google_drive_service

router = APIRouter(prefix="/api/payment", tags=["Payments"])

# Simplified payment workflow - no sessions needed

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

class SimplePaymentSuccessRequest(BaseModel):
    """Simplified payment success request - accepts camelCase from frontend."""
    customer_email: Optional[EmailStr] = None
    payment_intent_id: Optional[str] = None
    # Accept camelCase fields from frontend
    paymentIntentId: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    paymentMethod: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    timestamp: Optional[str] = None

    class Config:
        # Allow population by field name
        populate_by_name = True

    def get_payment_intent_id(self) -> str:
        """Get payment intent ID from either snake_case or camelCase field."""
        return self.payment_intent_id or self.paymentIntentId or ""

    def get_customer_email(self) -> Optional[str]:
        """Get customer email from field or metadata."""
        if self.customer_email:
            return self.customer_email
        if self.metadata and 'customer_email' in self.metadata:
            return self.metadata['customer_email']
        return None

class SimplifiedPaymentSuccessRequest(BaseModel):
    """Simplified payment success request using customer email lookup."""
    customer_email: EmailStr
    payment_intent_id: str


async def process_payment_success_background(
    customer_email: str,
    payment_intent_id: str,
    amount: Optional[float],
    currency: Optional[str],
    payment_method: Optional[str]
):
    """
    Background task to process file moves after payment confirmation.
    Runs asynchronously without blocking the HTTP response.
    """
    try:
        print("=" * 80)
        print(f"🔄 BACKGROUND TASK STARTED - Processing payment success")
        print(f"   Customer: {customer_email}")
        print(f"   Payment Intent: {payment_intent_id}")
        print("=" * 80)

        # Find files for this customer that are awaiting payment
        print(f"🔍 Finding files for customer: {customer_email}")
        files_to_move = await google_drive_service.find_files_by_customer_email(
            customer_email=customer_email,
            status="awaiting_payment"
        )

        if not files_to_move:
            print(f"⚠️ No files found for customer {customer_email} with status 'awaiting_payment'")
            print("=" * 80)
            return

        file_ids = [file_info['file_id'] for file_info in files_to_move]
        print(f"📁 Found {len(file_ids)} files to move:")
        for i, file_info in enumerate(files_to_move, 1):
            print(f"   File {i}: {file_info['filename']} (ID: {file_info['file_id']}, Pages: {file_info['page_count']})")

        # Move files from Temp to Inbox
        print(f"📦 Moving files from Temp/ to Inbox/...")
        result = await google_drive_service.move_files_to_inbox_on_payment_success(
            customer_email=customer_email,
            file_ids=file_ids
        )

        # Update file status to payment_confirmed
        print(f"🔄 Updating file status to 'payment_confirmed'...")
        for file_id in file_ids:
            try:
                await google_drive_service.update_file_status(
                    file_id=file_id,
                    new_status="payment_confirmed",
                    payment_intent_id=payment_intent_id
                )
                print(f"   ✅ Updated status for file: {file_id}")
            except Exception as e:
                print(f"   ❌ Failed to update status for file {file_id}: {e}")

        print("=" * 80)
        print(f"✅ BACKGROUND TASK COMPLETE")
        print(f"   Customer: {customer_email}")
        print(f"   Files moved: {result['moved_successfully']}/{result['total_files']}")
        print(f"   Inbox folder: {result['inbox_folder_id']}")
        print("=" * 80)

        logging.info(f"Payment success background task completed for {customer_email}: {result['moved_successfully']}/{result['total_files']} files moved")

    except Exception as e:
        print("=" * 80)
        print(f"❌ BACKGROUND TASK ERROR")
        print(f"   Customer: {customer_email}")
        print(f"   Error: {e}")
        print("=" * 80)
        logging.error(f"Payment success background task error for {customer_email}: {e}", exc_info=True)


@router.post("/success")
async def handle_payment_success(
    request: SimplePaymentSuccessRequest,
    background_tasks: BackgroundTasks
):
    """
    INSTANT PAYMENT SUCCESS WEBHOOK (with background processing):
    1. Receive payment confirmation with customer_email → IMMEDIATE 200 OK
    2. Schedule background task to move files from Temp/ to Inbox/
    3. Background task processes files asynchronously

    Response time: < 100ms (validates and returns immediately)
    File processing: Happens in background (3-10 seconds)
    """
    print("=" * 80)
    print("⚡ INSTANT PAYMENT SUCCESS WEBHOOK")
    print("=" * 80)

    try:
        # FastAPI automatically parses and validates the body (non-blocking)
        payment_intent_id = request.get_payment_intent_id()
        customer_email = request.get_customer_email()

        print(f"📄 Payment confirmation received: {customer_email} | {payment_intent_id}")

        if not payment_intent_id:
            raise HTTPException(status_code=400, detail="payment_intent_id or paymentIntentId is required")

        if not customer_email:
            raise HTTPException(
                status_code=400,
                detail="customer_email is required (either as field or in metadata)"
            )

        print(f"✅ PAYMENT CONFIRMED - Scheduling background task")
        print(f"   Customer: {customer_email}")
        print(f"   Payment Intent: {payment_intent_id}")
        print(f"   Amount: ${request.amount} {request.currency}")
        print(f"   Payment Method: {request.paymentMethod}")

        # Schedule background task for file processing
        background_tasks.add_task(
            process_payment_success_background,
            customer_email=customer_email,
            payment_intent_id=payment_intent_id,
            amount=request.amount,
            currency=request.currency,
            payment_method=request.paymentMethod
        )

        print(f"⚡ INSTANT RESPONSE - Background task scheduled")
        print("=" * 80)

        # Return IMMEDIATE response (< 100ms)
        return JSONResponse(
            content={
                "success": True,
                "message": "Payment confirmed. Files are being processed in the background.",
                "data": {
                    "customer_email": customer_email,
                    "payment_intent_id": payment_intent_id,
                    "status": "processing",
                    "workflow": "background_processing"
                },
                "error": None
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Payment success processing error: {e}")
        logging.error(f"Payment success error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process payment success: {str(e)}"
        )

@router.post("/failure")
async def handle_payment_failure(request: PaymentFailureRequest):
    """
    SIMPLIFIED PAYMENT FAILURE HANDLER:
    1. Find all files for customer with status "awaiting_payment"
    2. Delete files from Temp folder
    3. No sessions required - uses file metadata
    """
    logging.warning(f"❌ PAYMENT FAILED for {request.customer_email}")
    
    try:
        # Find files for this customer that are awaiting payment
        print(f"🔍 Finding files for failed payment: {request.customer_email}")
        files_to_delete = await google_drive_service.find_files_by_customer_email(
            customer_email=request.customer_email,
            status="awaiting_payment"
        )
        
        if not files_to_delete:
            print(f"ℹ️ No files found for customer {request.customer_email} to clean up")
            return JSONResponse(
                content={
                    "success": True,
                    "message": "No files found to clean up",
                    "data": {
                        "customer_email": request.customer_email,
                        "payment_intent_id": request.payment_intent_id,
                        "total_files": 0,
                        "deleted_successfully": 0,
                        "failed_deletions": 0,
                        "deleted_files": []
                    }
                }
            )
        
        file_ids = [file_info['file_id'] for file_info in files_to_delete]
        print(f"🗑️ Found {len(file_ids)} files to delete for failed payment")
        for i, file_info in enumerate(files_to_delete, 1):
            print(f"   File {i}: {file_info['filename']} (ID: {file_info['file_id']})")
        
        # Delete files from Temp folder
        result = await google_drive_service.delete_files_on_payment_failure(
            customer_email=request.customer_email,
            file_ids=file_ids
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
                    "deleted_files": result['deleted_files'],
                    "workflow": "simplified_no_sessions"
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