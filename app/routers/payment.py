"""
Payment API endpoints.
"""

from fastapi import APIRouter, HTTPException, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, ValidationError
from typing import Optional, Dict, Any, List
import uuid
import time
import logging
import json

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

@router.post("/success")
async def handle_payment_success(raw_request: Request):
    """
    SIMPLIFIED PAYMENT SUCCESS WEBHOOK:
    1. Receive payment confirmation with customer_email
    2. Find all files for customer with status "awaiting_payment"
    3. Move files from Temp/ to Inbox/ folder
    4. Update file status to "payment_confirmed"
    
    NO SESSIONS REQUIRED - uses file metadata for linking.
    """
    print("=" * 80)
    print("💳 SIMPLIFIED PAYMENT SUCCESS WEBHOOK")
    print("=" * 80)
    
    try:
        # Parse request body
        raw_body = await raw_request.body()
        print(f"📄 Request body: {raw_body.decode('utf-8') if raw_body else 'EMPTY'}")
        
        if not raw_body:
            raise HTTPException(status_code=400, detail="Empty request body")
        
        json_data = json.loads(raw_body)
        print(f"📋 Parsed data: {json_data}")
        
        # Validate request
        request = SimplePaymentSuccessRequest(**json_data)
        payment_intent_id = request.get_payment_intent_id()
        customer_email = request.get_customer_email()

        if not payment_intent_id:
            raise HTTPException(status_code=400, detail="payment_intent_id or paymentIntentId is required")

        if not customer_email:
            raise HTTPException(
                status_code=400,
                detail="customer_email is required (either as field or in metadata)"
            )

        print(f"✅ PAYMENT CONFIRMED")
        print(f"   Customer: {customer_email}")
        print(f"   Payment Intent: {payment_intent_id}")
        print(f"   Amount: ${request.amount} {request.currency}")
        print(f"   Payment Method: {request.paymentMethod}")
        if request.metadata:
            print(f"   Metadata: {request.metadata}")
        
        # Find files for this customer that are awaiting payment
        print(f"🔍 Finding files for customer: {customer_email}")
        files_to_move = await google_drive_service.find_files_by_customer_email(
            customer_email=customer_email,
            status="awaiting_payment"
        )
        
        if not files_to_move:
            print(f"❌ No files found for customer {customer_email} with status 'awaiting_payment'")
            raise HTTPException(
                status_code=404,
                detail=f"No pending files found for customer {customer_email}"
            )
        
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
                print(f"   Updated status for file: {file_id}")
            except Exception as e:
                print(f"   Failed to update status for file {file_id}: {e}")
        
        print(f"✅ PAYMENT SUCCESS COMPLETE")
        print(f"   Customer: {customer_email}")
        print(f"   Files moved: {result['moved_successfully']}/{result['total_files']}")
        print(f"   Inbox folder: {result['inbox_folder_id']}")
        
        return JSONResponse(
            content={
                "success": True,
                "message": f"Payment confirmed. {result['moved_successfully']} files moved to Inbox.",
                "data": {
                    "customer_email": customer_email,
                    "payment_intent_id": payment_intent_id,
                    "total_files": result['total_files'],
                    "moved_successfully": result['moved_successfully'],
                    "failed_moves": result['failed_moves'],
                    "inbox_folder_id": result['inbox_folder_id'],
                    "moved_files": result['moved_files'],
                    "workflow": "simplified_no_sessions"
                },
                "error": None
            }
        )
        
    except HTTPException:
        raise
    except json.JSONDecodeError as e:
        print(f"❌ JSON parsing error: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON format")
    except ValidationError as e:
        print(f"❌ Validation error: {e.errors()}")
        raise HTTPException(status_code=422, detail=f"Validation error: {e.errors()}")
    except Exception as e:
        print(f"❌ Payment success processing error: {e}")
        logging.error(f"Payment success error for {customer_email if 'customer_email' in locals() else 'unknown'}: {e}")
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