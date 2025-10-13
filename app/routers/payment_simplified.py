"""
Simplified Payment API endpoints - No sessions, just customer email lookup.
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, Dict, Any
import json
import logging

from app.services.google_drive_service import google_drive_service

router = APIRouter(prefix="/api/payment", tags=["Payments"])

class PaymentMetadata(BaseModel):
    """Payment metadata from Square/Stripe."""
    status: Optional[str] = None
    cardBrand: Optional[str] = Field(None, alias='card_brand')
    last4: Optional[str] = None
    receiptNumber: Optional[str] = Field(None, alias='receipt_number')
    created: Optional[str] = None
    simulated: Optional[bool] = None
    customer_email: Optional[EmailStr] = None

    model_config = {'populate_by_name': True}

class PaymentSuccessRequest(BaseModel):
    """Payment success webhook - accepts all client fields."""
    # Can be at root or in metadata
    customer_email: Optional[EmailStr] = Field(None, alias='customerEmail')

    # Payment ID (required)
    payment_intent_id: Optional[str] = Field(None, alias='paymentIntentId')

    # Payment details
    amount: Optional[float] = None
    currency: Optional[str] = "USD"
    payment_method: Optional[str] = Field(None, alias='paymentMethod')

    # Additional fields
    metadata: Optional[PaymentMetadata] = None
    timestamp: Optional[str] = None

    model_config = {'populate_by_name': True}

    def get_customer_email(self) -> str:
        """Extract customer email from root or metadata."""
        if self.customer_email:
            return self.customer_email
        if self.metadata and self.metadata.customer_email:
            return self.metadata.customer_email
        raise ValueError("customer_email not found in request or metadata")

    def get_payment_intent_id(self) -> str:
        """Get payment intent ID."""
        if not self.payment_intent_id:
            raise ValueError("payment_intent_id is required")
        return self.payment_intent_id

@router.post("/success")
async def handle_payment_success(raw_request: Request):
    """
    Payment success webhook - moves files from Temp to Inbox.
    Accepts customer_email in root or metadata.
    """
    print("\n" + "=" * 80)
    print("💳 PAYMENT SUCCESS WEBHOOK - INCOMING REQUEST")
    print("=" * 80)

    # Log raw incoming request
    try:
        raw_body = await raw_request.body()
        raw_json = raw_body.decode('utf-8')
        print("📥 INCOMING PAYLOAD:")
        print(raw_json)

        # Parse JSON
        json_data = json.loads(raw_json)
        print("\n📋 PARSED JSON:")
        print(json.dumps(json_data, indent=2))

    except Exception as e:
        print(f"❌ ERROR reading request: {e}")
        raise HTTPException(status_code=400, detail="Invalid request format")

    # Validate with Pydantic model
    try:
        request = PaymentSuccessRequest(**json_data)
    except Exception as e:
        print(f"❌ VALIDATION ERROR: {e}")
        raise HTTPException(status_code=422, detail=str(e))

    print("\n" + "-" * 80)
    print("✅ PARSED FIELDS:")
    print("-" * 80)

    try:
        # Extract required fields
        customer_email = request.get_customer_email()
        payment_intent_id = request.get_payment_intent_id()

        # Log all parsed fields
        print(f"Customer Email:    {customer_email}")
        print(f"Payment Intent ID: {payment_intent_id}")
        print(f"Amount:            ${request.amount} {request.currency}")
        print(f"Payment Method:    {request.payment_method}")
        print(f"Timestamp:         {request.timestamp}")

        if request.metadata:
            print(f"\nMetadata:")
            print(f"  Status:         {request.metadata.status}")
            print(f"  Card Brand:     {request.metadata.cardBrand}")
            print(f"  Last 4 Digits:  {request.metadata.last4}")
            print(f"  Receipt Number: {request.metadata.receiptNumber}")
            print(f"  Created:        {request.metadata.created}")
            print(f"  Simulated:      {request.metadata.simulated}")

        print("-" * 80)

    except ValueError as e:
        print(f"❌ VALIDATION ERROR: {e}")
        print("=" * 80)
        raise HTTPException(status_code=400, detail=str(e))

    try:
        # Find files awaiting payment
        files_to_move = await google_drive_service.find_files_by_customer_email(
            customer_email=customer_email,
            status="awaiting_payment"
        )

        if not files_to_move:
            print(f"\n⚠️  No pending files found for customer")

            response_content = {
                "success": True,
                "message": f"Payment confirmed but no pending files found",
                "data": {
                    "customer_email": customer_email,
                    "payment_intent_id": payment_intent_id,
                    "files_moved": 0
                }
            }

            print("\n" + "=" * 80)
            print("📤 OUTGOING RESPONSE:")
            print("=" * 80)
            print(json.dumps(response_content, indent=2))
            print("=" * 80 + "\n")

            return JSONResponse(content=response_content)

        print(f"\n✅ Found {len(files_to_move)} files to move")
        for i, file_info in enumerate(files_to_move, 1):
            print(f"   {i}. {file_info.get('filename')} (ID: {file_info.get('file_id')})")

        # Move files from Temp to Inbox
        print(f"\n📁 Moving files from Temp to Inbox...")
        file_ids = [f['file_id'] for f in files_to_move]
        result = await google_drive_service.move_files_to_inbox_on_payment_success(
            customer_email=customer_email,
            file_ids=file_ids
        )

        # Update file status
        print(f"🔄 Updating file statuses...")
        for file_id in file_ids:
            try:
                await google_drive_service.update_file_status(
                    file_id=file_id,
                    new_status="payment_confirmed",
                    payment_intent_id=payment_intent_id
                )
                print(f"   ✓ Updated: {file_id}")
            except Exception as e:
                print(f"   ⚠️  Warning: Failed to update {file_id}: {e}")

        print(f"\n✅ SUCCESS: {result['moved_successfully']}/{result['total_files']} files moved to Inbox")

        response_content = {
            "success": True,
            "message": f"Payment confirmed. {result['moved_successfully']} files moved to Inbox.",
            "data": {
                "customer_email": customer_email,
                "payment_intent_id": payment_intent_id,
                "total_files": result['total_files'],
                "moved_successfully": result['moved_successfully'],
                "inbox_folder_id": result['inbox_folder_id']
            }
        }

        print("\n" + "=" * 80)
        print("📤 OUTGOING RESPONSE:")
        print("=" * 80)
        print(json.dumps(response_content, indent=2))
        print("=" * 80 + "\n")

        return JSONResponse(content=response_content)

    except HTTPException as he:
        # Log HTTP exceptions before re-raising
        print(f"\n❌ HTTP EXCEPTION: {he.status_code} - {he.detail}")
        print("=" * 80 + "\n")
        raise

    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        logging.error(f"Payment success error: {e}", exc_info=True)

        error_response = {
            "success": False,
            "error": {
                "code": 500,
                "message": f"Failed to process payment: {str(e)}",
                "type": "internal_error"
            }
        }

        print("\n" + "=" * 80)
        print("📤 OUTGOING ERROR RESPONSE:")
        print("=" * 80)
        print(json.dumps(error_response, indent=2))
        print("=" * 80 + "\n")

        raise HTTPException(
            status_code=500,
            detail=f"Failed to process payment: {str(e)}"
        )

@router.post("/failure")
async def handle_payment_failure(customer_email: EmailStr, payment_intent_id: str):
    """
    SIMPLIFIED PAYMENT FAILURE HANDLER:
    1. Find all files for customer with status "awaiting_payment"
    2. Delete files from Temp folder
    """
    print(f"❌ PAYMENT FAILED for {customer_email}: {payment_intent_id}")
    
    try:
        # Find files for customer
        files_to_delete = await google_drive_service.find_files_by_customer_email(
            customer_email=customer_email,
            status="awaiting_payment"
        )
        
        if not files_to_delete:
            return JSONResponse(
                content={
                    "success": True,
                    "message": f"Payment failed but no pending files found for {customer_email}",
                    "data": {
                        "customer_email": customer_email,
                        "payment_intent_id": payment_intent_id,
                        "files_deleted": 0
                    }
                }
            )
        
        # Delete files
        file_ids = [file_info.get('file_id') for file_info in files_to_delete]
        result = await google_drive_service.delete_files_on_payment_failure(
            customer_email=customer_email,
            file_ids=file_ids
        )
        
        print(f"Payment failure cleanup: {result['deleted_successfully']}/{result['total_files']} files deleted")
        
        return JSONResponse(
            content={
                "success": True,
                "message": f"Payment failed. {result['deleted_successfully']} files deleted from Temp folder.",
                "data": {
                    "customer_email": customer_email,
                    "payment_intent_id": payment_intent_id,
                    "total_files": result['total_files'],
                    "deleted_successfully": result['deleted_successfully'],
                    "workflow": "simplified_no_sessions"
                }
            }
        )
        
    except Exception as e:
        logging.error(f"Payment failure cleanup error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to clean up files: {str(e)}"
        )