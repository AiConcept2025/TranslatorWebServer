"""
Simplified Payment API endpoints - No sessions, just customer email lookup.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, Dict, Any
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
    square_transaction_id: Optional[str] = None

    model_config = {'populate_by_name': True}

class PaymentSuccessRequest(BaseModel):
    """Payment success webhook - accepts all client fields."""
    # Can be at root or in metadata
    customer_email: Optional[EmailStr] = Field(None, alias='customerEmail')

    # Payment ID (required)
    payment_intent_id: Optional[str] = Field(None, alias='paymentIntentId')

    # Square transaction ID (for user payments)
    square_transaction_id: Optional[str] = None

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

async def process_payment_files_background(
    customer_email: str,
    payment_intent_id: str,
    amount: Optional[float],
    currency: Optional[str],
    payment_metadata: Optional[PaymentMetadata] = None
):
    """
    Background task to move files from Temp to Inbox and persist payment data.
    Runs asynchronously without blocking HTTP response.
    """
    import time
    task_start = time.time()

    try:
        print("\n" + "=" * 80)
        print("🔄 BACKGROUND TASK STARTED")
        print("=" * 80)
        print(f"⏱️  Started at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📋 Task Details:")
        print(f"   Customer: {customer_email}")
        print(f"   Payment ID: {payment_intent_id}")
        print(f"   Amount: ${amount} {currency}")
        print("=" * 80)

        # Step 0: Check for duplicate payment (idempotency)
        print(f"\n🔍 Step 0: Checking for duplicate payment...")
        idempotency_start = time.time()

        from app.services.payment_repository import payment_repository
        from app.models.payment import PaymentCreate

        # Check if payment already processed
        existing_payment = await payment_repository.get_payment_by_square_id(payment_intent_id)
        if existing_payment:
            idempotency_time = (time.time() - idempotency_start) * 1000
            print(f"⏱️  Idempotency check completed in {idempotency_time:.2f}ms")
            print(f"⚠️  Payment {payment_intent_id} already processed (duplicate webhook)")
            print(f"✅ Returning early - payment ID: {existing_payment.get('_id')}")
            logging.info(f"Duplicate payment webhook ignored: {payment_intent_id}")
            return  # Exit early, don't reprocess

        print(f"✅ No duplicate found, proceeding with payment persistence...")

        # Step 1: Persist payment data to payments collection
        print(f"\n💾 Step 1: Persisting payment data to database...")
        persist_start = time.time()

        try:
            # Fix: Only use valid PaymentCreate fields (no company_name for individual users)
            payment_data = PaymentCreate(
                company_name=None,  # Individual users don't have companies
                user_email=customer_email,
                square_payment_id=payment_intent_id,
                amount=int((amount or 0) * 100) if amount else 0,  # Convert to cents
                currency=currency or "USD",
                payment_status="COMPLETED",  # Use schema enum value
                payment_date=None  # Will default to now() in repository
            )
            # Note: card_brand, last4, receipt_url stored in metadata collection separately

            payment_id = await payment_repository.create_payment(payment_data)
            persist_time = (time.time() - persist_start) * 1000
            print(f"⏱️  Payment persistence completed in {persist_time:.2f}ms")
            print(f"✅ Payment record created with ID: {payment_id}")
        except Exception as e:
            persist_time = (time.time() - persist_start) * 1000
            print(f"⏱️  Payment persistence attempted in {persist_time:.2f}ms")
            print(f"⚠️  Failed to persist payment: {str(e)}")
            logging.warning(f"Failed to persist payment {payment_intent_id}: {e}")

        # Find files awaiting payment
        print(f"\n🔍 Step 2: Finding files for customer...")
        find_start = time.time()
        files_to_move = await google_drive_service.find_files_by_customer_email(
            customer_email=customer_email,
            status="awaiting_payment"
        )
        find_time = (time.time() - find_start) * 1000
        print(f"⏱️  File search completed in {find_time:.2f}ms")

        if not files_to_move:
            print(f"⚠️  No pending files found for {customer_email}")
            total_time = (time.time() - task_start) * 1000
            print(f"⏱️  BACKGROUND TASK TOTAL TIME: {total_time:.2f}ms")
            print("=" * 80 + "\n")
            return

        print(f"\n✅ Found {len(files_to_move)} files to move:")
        for i, file_info in enumerate(files_to_move, 1):
            print(f"   {i}. {file_info.get('filename')} (ID: {file_info.get('file_id')[:20]}...)")

        # Move files from Temp to Inbox
        print(f"\n📁 Step 3: Moving files from Temp to Inbox...")
        move_start = time.time()
        file_ids = [f['file_id'] for f in files_to_move]
        result = await google_drive_service.move_files_to_inbox_on_payment_success(
            customer_email=customer_email,
            file_ids=file_ids
        )
        move_time = (time.time() - move_start) * 1000
        print(f"⏱️  File move completed in {move_time:.2f}ms")
        print(f"✅ Moved: {result['moved_successfully']}/{result['total_files']} files")
        print(f"📂 Inbox folder ID: {result.get('inbox_folder_id', 'N/A')}")

        # Update file statuses - ONLY for successfully moved files
        print(f"\n🔄 Step 4: Updating file statuses (only for successfully moved files)...")
        update_start = time.time()
        success_count = 0
        error_count = 0

        # Extract IDs of successfully moved files
        successfully_moved_file_ids = [f['file_id'] for f in result.get('moved_files', [])]

        # Only update status for files that were actually moved
        for i, file_id in enumerate(successfully_moved_file_ids, 1):
            try:
                await google_drive_service.update_file_status(
                    file_id=file_id,
                    new_status="payment_confirmed",
                    payment_intent_id=payment_intent_id
                )
                success_count += 1
                print(f"   {i}/{len(successfully_moved_file_ids)} ✓ Updated: {file_id[:20]}...")
            except Exception as e:
                error_count += 1
                print(f"   {i}/{len(successfully_moved_file_ids)} ⚠️  Failed: {file_id[:20]}... - {str(e)[:50]}")

        # Log files that failed to move (status remains 'awaiting_payment' for retry)
        failed_move_count = result.get('failed_moves', 0)
        if failed_move_count > 0:
            print(f"\n⚠️  {failed_move_count} files failed to move - status NOT updated (will retry on next payment)")
            for failed_file in result.get('failed_files', []):
                print(f"      ❌ {failed_file['file_id'][:20]}...: {failed_file.get('error', 'Unknown error')[:60]}")

        update_time = (time.time() - update_start) * 1000
        print(f"⏱️  Status updates completed in {update_time:.2f}ms")
        print(f"✅ Updated: {success_count}/{len(successfully_moved_file_ids)} successfully moved files")
        if error_count > 0:
            print(f"⚠️  Status update errors: {error_count}/{len(successfully_moved_file_ids)} files")

        total_time = (time.time() - task_start) * 1000
        print(f"\n✅ BACKGROUND TASK COMPLETE")
        print(f"⏱️  TOTAL TASK TIME: {total_time:.2f}ms")
        print(f"   - File search: {find_time:.2f}ms")
        print(f"   - File move: {move_time:.2f}ms")
        print(f"   - Status updates: {update_time:.2f}ms")
        print("=" * 80 + "\n")

        logging.info(f"Background task completed for {customer_email}: {result['moved_successfully']}/{result['total_files']} files moved in {total_time:.2f}ms")

    except Exception as e:
        total_time = (time.time() - task_start) * 1000
        print(f"\n❌ BACKGROUND TASK ERROR")
        print(f"⏱️  Failed after: {total_time:.2f}ms")
        print(f"💥 Error type: {type(e).__name__}")
        print(f"💥 Error message: {str(e)}")
        print("=" * 80 + "\n")
        logging.error(f"Background file processing error for {customer_email}: {e}", exc_info=True)


@router.post("/success")
async def handle_payment_success(
    request: PaymentSuccessRequest,
    background_tasks: BackgroundTasks
):
    """
    INSTANT payment success webhook - returns immediately.
    Files are moved in background (non-blocking).
    """
    import time
    start_time = time.time()

    print("\n" + "=" * 80)
    print("⚡ INSTANT PAYMENT SUCCESS WEBHOOK")
    print("=" * 80)
    print(f"⏱️  Request received at: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        # Log raw request data
        print("\n📥 RAW REQUEST DATA:")
        print(f"   payment_intent_id (snake_case): {request.payment_intent_id}")
        print(f"   customer_email (root): {request.customer_email}")
        print(f"   amount: {request.amount}")
        print(f"   currency: {request.currency}")
        print(f"   payment_method: {request.payment_method}")
        print(f"   timestamp: {request.timestamp}")

        if request.metadata:
            print(f"\n📋 METADATA:")
            print(f"   status: {request.metadata.status}")
            print(f"   cardBrand: {request.metadata.cardBrand}")
            print(f"   last4: {request.metadata.last4}")
            print(f"   receiptNumber: {request.metadata.receiptNumber}")
            print(f"   created: {request.metadata.created}")
            print(f"   simulated: {request.metadata.simulated}")
            print(f"   customer_email (metadata): {request.metadata.customer_email}")

        # Extract required fields (FAST - no I/O)
        parse_start = time.time()
        customer_email = request.get_customer_email()
        payment_intent_id = request.get_payment_intent_id()
        parse_time = (time.time() - parse_start) * 1000

        print(f"\n✅ EXTRACTED FIELDS (took {parse_time:.2f}ms):")
        print(f"   Customer: {customer_email}")
        print(f"   Payment ID: {payment_intent_id}")
        print(f"   Amount: ${request.amount} {request.currency}")
        print(f"   Payment Method: {request.payment_method}")

        # Schedule background file processing
        task_schedule_start = time.time()
        background_tasks.add_task(
            process_payment_files_background,
            customer_email=customer_email,
            payment_intent_id=payment_intent_id,
            amount=request.amount,
            currency=request.currency,
            payment_metadata=request.metadata
        )
        task_schedule_time = (time.time() - task_schedule_start) * 1000

        total_time = (time.time() - start_time) * 1000
        print(f"\n⚡ INSTANT RESPONSE - Background task scheduled (took {task_schedule_time:.2f}ms)")
        print(f"⏱️  TOTAL PROCESSING TIME: {total_time:.2f}ms")
        print("=" * 80 + "\n")

        # Return IMMEDIATELY (< 100ms)
        return JSONResponse(
            content={
                "success": True,
                "message": "Payment confirmed. Files are being processed in the background.",
                "data": {
                    "customer_email": customer_email,
                    "payment_intent_id": payment_intent_id,
                    "status": "processing",
                    "processing_time_ms": round(total_time, 2)
                }
            }
        )

    except ValueError as e:
        print(f"❌ VALIDATION ERROR: {e}")
        print("=" * 80 + "\n")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {e}")
        print("=" * 80 + "\n")
        logging.error(f"Payment success error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


async def process_user_payment_files_background(
    customer_email: str,
    square_transaction_id: str,
    amount: Optional[float] = None,
    currency: Optional[str] = None,
    payment_metadata: Optional[PaymentMetadata] = None
):
    """
    Background task to move user transaction files from Temp to Inbox and persist payment data.
    Updates user_transactions collection status to "completed".
    Runs asynchronously without blocking HTTP response.

    Args:
        customer_email: User email address
        square_transaction_id: Square payment transaction ID
        amount: Payment amount in dollars
        currency: Currency code (default: USD)
        payment_metadata: Additional payment metadata from Square
    """
    import time
    from app.utils.user_transaction_helper import (
        get_user_transaction,
        update_user_transaction_status
    )

    task_start = time.time()

    try:
        print("\n" + "=" * 80)
        print("🔄 USER PAYMENT BACKGROUND TASK STARTED")
        print("=" * 80)
        print(f"⏱️  Started at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📋 Task Details:")
        print(f"   Customer: {customer_email}")
        print(f"   Square Transaction ID: {square_transaction_id}")
        print("=" * 80)

        # Step 0: Persist payment data to payments collection
        print(f"\n💾 Step 0: Persisting payment data to database...")
        persist_start = time.time()

        from app.services.payment_repository import payment_repository
        from app.models.payment import PaymentCreate

        try:
            # Fix: Only use valid PaymentCreate fields (no company_name for individual users)
            payment_data = PaymentCreate(
                company_name=None,  # Individual users don't have companies
                user_email=customer_email,
                square_payment_id=square_transaction_id,
                amount=int((amount or 0) * 100) if amount else 0,  # Convert to cents
                currency=currency or "USD",
                payment_status="COMPLETED",  # Use schema enum value
                payment_date=None  # Will default to now() in repository
            )
            # Note: card_brand, last4, receipt_url stored in metadata collection separately

            payment_id = await payment_repository.create_payment(payment_data)
            persist_time = (time.time() - persist_start) * 1000
            print(f"⏱️  Payment persistence completed in {persist_time:.2f}ms")
            print(f"✅ Payment record created with ID: {payment_id}")
        except Exception as e:
            persist_time = (time.time() - persist_start) * 1000
            print(f"⏱️  Payment persistence attempted in {persist_time:.2f}ms")
            print(f"⚠️  Failed to persist payment: {str(e)}")
            logging.warning(f"Failed to persist user payment {square_transaction_id}: {e}")

        # Step 1: Get transaction from user_transactions collection
        print(f"\n🔍 Step 1: Fetching user transaction...")
        fetch_start = time.time()
        transaction = await get_user_transaction(square_transaction_id)
        fetch_time = (time.time() - fetch_start) * 1000
        print(f"⏱️  Transaction fetch completed in {fetch_time:.2f}ms")

        if not transaction:
            print(f"⚠️  Transaction not found: {square_transaction_id}")
            total_time = (time.time() - task_start) * 1000
            print(f"⏱️  BACKGROUND TASK TOTAL TIME: {total_time:.2f}ms")
            print("=" * 80 + "\n")
            logging.warning(
                f"User payment background task: Transaction not found - {square_transaction_id}"
            )
            return

        print(f"✅ Transaction found:")
        print(f"   User: {transaction.get('user_name')} ({transaction.get('user_email')})")
        print(f"   Document: {transaction.get('document_url')}")
        print(f"   Status: {transaction.get('status')}")
        print(f"   Total Cost: ${transaction.get('total_cost')}")

        # Step 2: Extract file_id from document_url
        print(f"\n📁 Step 2: Extracting file information...")
        document_url = transaction.get('document_url', '')

        # Extract file_id from Google Drive URL
        # Format: https://drive.google.com/file/d/{FILE_ID}/view or similar
        file_id = None
        if '/file/d/' in document_url:
            parts = document_url.split('/file/d/')
            if len(parts) > 1:
                file_id = parts[1].split('/')[0]

        if not file_id:
            error_msg = f"Could not extract file_id from document_url: {document_url}"
            print(f"❌ {error_msg}")
            await update_user_transaction_status(
                square_transaction_id=square_transaction_id,
                new_status="failed",
                error_message=error_msg
            )
            total_time = (time.time() - task_start) * 1000
            print(f"⏱️  BACKGROUND TASK TOTAL TIME: {total_time:.2f}ms")
            print("=" * 80 + "\n")
            logging.error(f"User payment background task: {error_msg}")
            return

        print(f"✅ Extracted file_id: {file_id[:20]}...")

        # Step 3: Move file from Temp to Inbox
        print(f"\n📂 Step 3: Moving file from Temp to Inbox...")
        move_start = time.time()

        try:
            result = await google_drive_service.move_files_to_inbox_on_payment_success(
                customer_email=customer_email,
                file_ids=[file_id]
            )
            move_time = (time.time() - move_start) * 1000
            print(f"⏱️  File move completed in {move_time:.2f}ms")
            print(f"✅ Moved: {result['moved_successfully']}/{result['total_files']} files")
            print(f"📂 Inbox folder ID: {result.get('inbox_folder_id', 'N/A')}")

            if result['moved_successfully'] == 0:
                error_msg = "File move failed - no files moved successfully"
                if result.get('failed_files'):
                    error_details = result['failed_files'][0].get('error', 'Unknown error')
                    error_msg = f"File move failed: {error_details}"

                print(f"❌ {error_msg}")
                await update_user_transaction_status(
                    square_transaction_id=square_transaction_id,
                    new_status="failed",
                    error_message=error_msg
                )
                total_time = (time.time() - task_start) * 1000
                print(f"⏱️  BACKGROUND TASK TOTAL TIME: {total_time:.2f}ms")
                print("=" * 80 + "\n")
                logging.error(f"User payment background task: {error_msg}")
                return

        except Exception as move_error:
            error_msg = f"Google Drive move error: {str(move_error)}"
            print(f"❌ {error_msg}")
            await update_user_transaction_status(
                square_transaction_id=square_transaction_id,
                new_status="failed",
                error_message=error_msg
            )
            total_time = (time.time() - task_start) * 1000
            print(f"⏱️  BACKGROUND TASK TOTAL TIME: {total_time:.2f}ms")
            print("=" * 80 + "\n")
            logging.error(f"User payment background task: {error_msg}", exc_info=True)
            return

        # Step 4: Update transaction status to "completed"
        print(f"\n🔄 Step 4: Updating transaction status to 'completed'...")
        update_start = time.time()

        success = await update_user_transaction_status(
            square_transaction_id=square_transaction_id,
            new_status="completed"
        )

        update_time = (time.time() - update_start) * 1000
        print(f"⏱️  Status update completed in {update_time:.2f}ms")

        if success:
            print(f"✅ Transaction status updated to 'completed'")
        else:
            print(f"⚠️  Failed to update transaction status (transaction may not exist)")

        # Step 5: Update file status in Google Drive metadata
        print(f"\n🔄 Step 5: Updating file status in Google Drive metadata...")
        status_start = time.time()

        try:
            await google_drive_service.update_file_status(
                file_id=file_id,
                new_status="payment_confirmed",
                payment_intent_id=square_transaction_id
            )
            status_time = (time.time() - status_start) * 1000
            print(f"⏱️  File status update completed in {status_time:.2f}ms")
            print(f"✅ File status updated to 'payment_confirmed'")
        except Exception as status_error:
            print(f"⚠️  Failed to update file status: {str(status_error)[:60]}")
            logging.warning(
                f"User payment: Failed to update file status for {file_id}: {status_error}"
            )

        total_time = (time.time() - task_start) * 1000
        print(f"\n✅ USER PAYMENT BACKGROUND TASK COMPLETE")
        print(f"⏱️  TOTAL TASK TIME: {total_time:.2f}ms")
        print(f"   - Transaction fetch: {fetch_time:.2f}ms")
        print(f"   - File move: {move_time:.2f}ms")
        print(f"   - Status update: {update_time:.2f}ms")
        print("=" * 80 + "\n")

        logging.info(
            f"User payment background task completed for {customer_email}: "
            f"transaction {square_transaction_id} processed in {total_time:.2f}ms"
        )

    except Exception as e:
        total_time = (time.time() - task_start) * 1000
        print(f"\n❌ USER PAYMENT BACKGROUND TASK ERROR")
        print(f"⏱️  Failed after: {total_time:.2f}ms")
        print(f"💥 Error type: {type(e).__name__}")
        print(f"💥 Error message: {str(e)}")
        print("=" * 80 + "\n")

        # Attempt to mark transaction as failed
        try:
            from app.utils.user_transaction_helper import update_user_transaction_status
            await update_user_transaction_status(
                square_transaction_id=square_transaction_id,
                new_status="failed",
                error_message=str(e)
            )
        except Exception as update_error:
            logging.error(
                f"Failed to update transaction status after error: {update_error}"
            )

        logging.error(
            f"User payment background task error for {customer_email}: {e}",
            exc_info=True
        )


@router.post("/user-success")
async def handle_user_payment_success(
    request: PaymentSuccessRequest,
    background_tasks: BackgroundTasks
):
    """
    INSTANT user payment success webhook for individual users.
    Returns immediately, processes user transaction files in background.

    Updates user_transactions collection and moves files from Temp to Inbox.

    Expected request format:
    {
        "customerEmail": "user@example.com",
        "square_transaction_id": "txn_abc123",  // Can be in root or metadata
        "amount": 10.00,
        "currency": "USD",
        "paymentMethod": "square",
        "metadata": {
            "square_transaction_id": "txn_abc123"  // Alternative location
        }
    }
    """
    import time
    start_time = time.time()

    print("\n" + "=" * 80)
    print("⚡ INSTANT USER PAYMENT SUCCESS WEBHOOK")
    print("=" * 80)
    print(f"⏱️  Request received at: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        # Log raw request data
        print("\n📥 RAW REQUEST DATA:")
        print(f"   customer_email (root): {request.customer_email}")
        print(f"   payment_intent_id: {request.payment_intent_id}")
        print(f"   amount: {request.amount}")
        print(f"   currency: {request.currency}")
        print(f"   payment_method: {request.payment_method}")
        print(f"   timestamp: {request.timestamp}")

        # Extract square_transaction_id from request or metadata
        square_transaction_id = None

        # Try to get from root level first (check if request has square_transaction_id attribute)
        if hasattr(request, 'square_transaction_id') and getattr(request, 'square_transaction_id'):
            square_transaction_id = getattr(request, 'square_transaction_id')
            print(f"   square_transaction_id (root): {square_transaction_id}")

        # Try metadata next
        if not square_transaction_id and request.metadata:
            print(f"\n📋 METADATA:")
            print(f"   status: {request.metadata.status}")
            print(f"   cardBrand: {request.metadata.cardBrand}")
            print(f"   last4: {request.metadata.last4}")
            print(f"   receiptNumber: {request.metadata.receiptNumber}")
            print(f"   created: {request.metadata.created}")
            print(f"   simulated: {request.metadata.simulated}")
            print(f"   customer_email (metadata): {request.metadata.customer_email}")

            # Check for square_transaction_id in metadata
            if hasattr(request.metadata, 'square_transaction_id'):
                square_transaction_id = getattr(request.metadata, 'square_transaction_id')
                print(f"   square_transaction_id (metadata): {square_transaction_id}")

        # Validate square_transaction_id
        if not square_transaction_id:
            error_msg = "square_transaction_id not found in request or metadata"
            print(f"❌ VALIDATION ERROR: {error_msg}")
            print("=" * 80 + "\n")
            raise HTTPException(status_code=400, detail=error_msg)

        # Extract customer email (FAST - no I/O)
        parse_start = time.time()
        customer_email = request.get_customer_email()
        parse_time = (time.time() - parse_start) * 1000

        print(f"\n✅ EXTRACTED FIELDS (took {parse_time:.2f}ms):")
        print(f"   Customer: {customer_email}")
        print(f"   Square Transaction ID: {square_transaction_id}")
        print(f"   Amount: ${request.amount} {request.currency}")
        print(f"   Payment Method: {request.payment_method}")

        # Schedule background file processing for user transaction
        task_schedule_start = time.time()
        background_tasks.add_task(
            process_user_payment_files_background,
            customer_email=customer_email,
            square_transaction_id=square_transaction_id,
            amount=request.amount,
            currency=request.currency,
            payment_metadata=request.metadata
        )
        task_schedule_time = (time.time() - task_schedule_start) * 1000

        total_time = (time.time() - start_time) * 1000
        print(f"\n⚡ INSTANT RESPONSE - User payment background task scheduled (took {task_schedule_time:.2f}ms)")
        print(f"⏱️  TOTAL PROCESSING TIME: {total_time:.2f}ms")
        print("=" * 80 + "\n")

        # Return IMMEDIATELY (< 100ms)
        return JSONResponse(
            content={
                "success": True,
                "message": "Payment confirmed. Files are being processed in the background.",
                "data": {
                    "customer_email": customer_email,
                    "square_transaction_id": square_transaction_id,
                    "status": "processing",
                    "processing_time_ms": round(total_time, 2)
                }
            }
        )

    except ValueError as e:
        print(f"❌ VALIDATION ERROR: {e}")
        print("=" * 80 + "\n")
        raise HTTPException(status_code=400, detail=str(e))

    except HTTPException:
        # Re-raise HTTP exceptions without wrapping
        raise

    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {e}")
        print("=" * 80 + "\n")
        logging.error(f"User payment success error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


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